import asyncio
import time
from collections.abc import AsyncIterator

from fastapi import HTTPException, status

from app.llm.base import BaseLLMAdapter
from app.llm.budget import BudgetGuard
from app.llm.anthropic_compatible import AnthropicCompatibleAdapter
from app.llm.litellm_adapter import LiteLLMAdapter
from app.llm.openai_compatible import OpenAICompatibleAdapter
from app.llm.policy import ModelPolicyEngine
from app.llm.router import ModelRouter
from app.llm.schemas import (
    ConnectionTestRequest,
    ConnectionTestResult,
    DeploymentConfig,
    LLMAdapterType,
    LLMCallStatus,
    LLMChatRequest,
    LLMRequestContext,
    LLMResponse,
    Message,
    PolicyDecision,
    ProviderConfig,
    RouteSelection,
)
from app.llm.circuit_breaker import CircuitBreaker, circuit_breaker as default_circuit_breaker
from app.llm.usage import UsageCollector
from app.observability.metrics import metrics_collector


class LLMGateway:
    """Single model-call entry point: policy -> budget -> router -> adapter -> usage/audit."""

    def __init__(
        self,
        *,
        policy: ModelPolicyEngine,
        budget: BudgetGuard,
        router: ModelRouter,
        usage: UsageCollector,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.policy = policy
        self.budget = budget
        self.router = router
        self.usage = usage
        self.circuit_breaker = circuit_breaker or default_circuit_breaker

    async def chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        route: RouteSelection | None = None
        reservation = None
        budget_reserved = False
        route_error_recorded = False
        chat_started = time.perf_counter()
        try:
            decision = await self.policy.evaluate(request, context)
            if not decision.allowed:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.DENIED,
                    error_code="policy_denied",
                    error_message=decision.reason,
                )
                metrics_collector.observe_llm_call(
                    provider_key=None,
                    model_key=request.model_key,
                    status=LLMCallStatus.DENIED,
                    duration_ms=(time.perf_counter() - chat_started) * 1000,
                    error_code="policy_denied",
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"LLM policy denied request: {decision.reason}",
                )

            effective_request = request.model_copy(
                update={
                    "model_key": request.model_key or decision.model_key,
                    "routing_key": request.routing_key or decision.routing_key,
                    "max_tokens": decision.max_tokens
                    if decision.max_tokens is not None
                    else request.max_tokens,
                }
            )
            reservation = await self.budget.reserve(effective_request, context)
            if not reservation.approved:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.BUDGET_EXCEEDED,
                    error_code="budget_exceeded",
                    error_message=reservation.reason,
                )
                metrics_collector.observe_llm_call(
                    provider_key=None,
                    model_key=effective_request.model_key,
                    status=LLMCallStatus.BUDGET_EXCEEDED,
                    duration_ms=(time.perf_counter() - chat_started) * 1000,
                    error_code="budget_exceeded",
                )
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"LLM budget denied request: {reservation.reason}",
                )
            budget_reserved = True

            routes = await self.router.plan(effective_request, decision)
            route_attempts: list[dict[str, object]] = []
            last_error: Exception | None = None
            for attempt_index, route in enumerate(routes, start=1):
                route_attempt = {
                    "attempt": attempt_index,
                    "provider_key": route.provider.provider_key,
                    "model_key": route.deployment.model_key,
                    "deployment_id": str(route.deployment.id),
                    "routing_key": route.deployment.routing_key,
                }
                try:
                    adapter = self._adapter_for(route)
                    response = await adapter.chat(effective_request, context)
                    self.circuit_breaker.record_success(str(route.deployment.id))
                    successful_attempt = {
                        **route_attempt,
                        "status": LLMCallStatus.SUCCESS.value,
                    }
                    route_attempts.append(successful_attempt)
                    enriched_response = response.model_copy(
                        update={
                            "usage": self.budget.pricing.recalculate_usage(
                                response.usage,
                                model_key=response.model_key,
                            ),
                            "metadata": {
                                **response.metadata,
                                "route_attempts": route_attempts,
                                "fallback_attempt_count": attempt_index - 1,
                                "selected_route_reason": route.reason,
                                "pricing_rule": self.budget.pricing.price_rule_for(
                                    response.model_key
                                ).pattern,
                            },
                        }
                    )
                    await self.budget.settle(reservation, enriched_response.usage, context)
                    await self.usage.record_success(
                        context=context,
                        route=route,
                        response=enriched_response,
                    )
                    metrics_collector.observe_llm_call(
                        provider_key=route.provider.provider_key,
                        model_key=enriched_response.model_key,
                        status=LLMCallStatus.SUCCESS,
                        duration_ms=(time.perf_counter() - chat_started) * 1000,
                    )
                    return enriched_response
                except Exception as exc:
                    last_error = exc
                    self.circuit_breaker.record_failure(
                        str(route.deployment.id),
                        error_code=exc.__class__.__name__,
                    )
                    failed_attempt = {
                        **route_attempt,
                        "status": LLMCallStatus.ERROR.value,
                        "error_code": exc.__class__.__name__,
                        "error_message": str(exc),
                    }
                    route_attempts.append(failed_attempt)
                    is_last_attempt = attempt_index == len(routes)
                    await self.usage.record_failure(
                        context=context,
                        status=LLMCallStatus.ERROR,
                        error_code=exc.__class__.__name__,
                        error_message=str(exc),
                        route=route,
                        metadata={
                            "operation": "chat",
                            "fallback_attempt": not is_last_attempt,
                            "attempt": attempt_index,
                            "total_candidates": len(routes),
                            "route_attempts": route_attempts.copy(),
                        },
                    )
                    if is_last_attempt:
                        route_error_recorded = True
                        if reservation is not None:
                            await self.budget.release(reservation, context, "adapter_exception")
                            reservation = None
                        raise

            if last_error is not None:
                raise last_error
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No usable LLM deployment matched the request.",
            )
        except HTTPException as exc:
            if budget_reserved and not route_error_recorded:
                await self._record_http_failure(
                    context=context,
                    exc=exc,
                    route=route,
                    operation="route_planning",
                )
                route_error_recorded = True
            if reservation is not None:
                await self.budget.release(reservation, context, "http_exception")
            metrics_collector.observe_llm_call(
                provider_key=route.provider.provider_key if route else None,
                model_key=(route.deployment.model_key if route else request.model_key),
                status=LLMCallStatus.ERROR,
                duration_ms=(time.perf_counter() - chat_started) * 1000,
                error_code=exc.__class__.__name__,
            )
            raise
        except Exception as exc:
            if reservation is not None:
                await self.budget.release(reservation, context, "adapter_exception")
            if not route_error_recorded:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.ERROR,
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    route=route,
                )
            metrics_collector.observe_llm_call(
                provider_key=route.provider.provider_key if route else None,
                model_key=(route.deployment.model_key if route else request.model_key),
                status=LLMCallStatus.ERROR,
                duration_ms=(time.perf_counter() - chat_started) * 1000,
                error_code=exc.__class__.__name__,
            )
            raise

    async def stream_chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> AsyncIterator[str]:
        """Stream chat completions through the same governance path as chat().

        Provider streaming protocols do not expose usage consistently, so a
        conservative local token estimate is settled after a successful
        stream. The pre-call reservation still uses ``max_tokens`` and is the
        hard-limit boundary.
        """
        chat_started = time.perf_counter()
        route: RouteSelection | None = None
        reservation = None
        reservation_open = False
        try:
            decision = await self.policy.evaluate(request, context)
            if not decision.allowed:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.DENIED,
                    error_code="policy_denied",
                    error_message=decision.reason,
                )
                metrics_collector.observe_llm_call(
                    provider_key=None,
                    model_key=request.model_key,
                    status=LLMCallStatus.DENIED,
                    duration_ms=(time.perf_counter() - chat_started) * 1000,
                    error_code="policy_denied",
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"LLM policy denied request: {decision.reason}",
                )

            effective_request = request.model_copy(
                update={
                    "model_key": request.model_key or decision.model_key,
                    "routing_key": request.routing_key or decision.routing_key,
                    "max_tokens": decision.max_tokens
                    if decision.max_tokens is not None
                    else request.max_tokens,
                }
            )
            reservation = await self.budget.reserve(effective_request, context)
            if not reservation.approved:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.BUDGET_EXCEEDED,
                    error_code="budget_exceeded",
                    error_message=reservation.reason,
                )
                metrics_collector.observe_llm_call(
                    provider_key=None,
                    model_key=effective_request.model_key,
                    status=LLMCallStatus.BUDGET_EXCEEDED,
                    duration_ms=(time.perf_counter() - chat_started) * 1000,
                    error_code="budget_exceeded",
                )
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"LLM budget denied request: {reservation.reason}",
                )
            reservation_open = True

            routes = await self.router.plan(effective_request, decision)
            last_error: Exception | None = None
            route_attempts: list[dict[str, object]] = []
            for attempt_index, route in enumerate(routes, start=1):
                collected: list[str] = []
                yielded_content = False
                route_attempt = {
                    "attempt": attempt_index,
                    "provider_key": route.provider.provider_key,
                    "model_key": route.deployment.model_key,
                    "deployment_id": str(route.deployment.id),
                    "routing_key": route.deployment.routing_key,
                }
                try:
                    adapter = self._adapter_for(route)
                    async for delta in adapter.stream_chat(effective_request, context):
                        collected.append(delta)
                        yielded_content = yielded_content or bool(delta)
                        yield delta
                    self.circuit_breaker.record_success(str(route.deployment.id))
                    route_attempts.append({**route_attempt, "status": LLMCallStatus.SUCCESS.value})
                    content = "".join(collected)
                    estimated_input = self.budget.pricing.estimate(effective_request).input_tokens
                    estimated_output = max(1, len(content) // 4) if content else 0
                    usage = self.budget.pricing.calculate(
                        input_tokens=estimated_input,
                        output_tokens=estimated_output,
                        model_key=route.deployment.model_key,
                    )
                    streamed_response = LLMResponse(
                        request_id=context.request_id,
                        model_key=route.deployment.model_key,
                        content=content,
                        usage=usage,
                        provider_key=route.provider.provider_key,
                        deployment_id=route.deployment.id,
                        finish_reason="stop",
                        metadata={
                            "adapter": adapter.adapter_name,
                            "streamed": True,
                            "usage_estimated": True,
                            "selected_route_reason": route.reason,
                            "fallback_attempt_count": attempt_index - 1,
                            "route_attempts": route_attempts,
                            "pricing_rule": self.budget.pricing.price_rule_for(
                                route.deployment.model_key
                            ).pattern,
                        },
                    )
                    await self.budget.settle(reservation, usage, context)
                    reservation_open = False
                    await self.usage.record_success(
                        context=context,
                        route=route,
                        response=streamed_response,
                    )
                    metrics_collector.observe_llm_call(
                        provider_key=route.provider.provider_key,
                        model_key=streamed_response.model_key,
                        status=LLMCallStatus.SUCCESS,
                        duration_ms=(time.perf_counter() - chat_started) * 1000,
                    )
                    return
                except HTTPException:
                    raise
                except Exception as exc:
                    last_error = exc
                    self.circuit_breaker.record_failure(
                        str(route.deployment.id),
                        error_code=exc.__class__.__name__,
                    )
                    route_attempts.append(
                        {
                            **route_attempt,
                            "status": LLMCallStatus.ERROR.value,
                            "error_code": exc.__class__.__name__,
                            "error_message": str(exc),
                        }
                    )
                    await self.usage.record_failure(
                        context=context,
                        status=LLMCallStatus.ERROR,
                        error_code=exc.__class__.__name__,
                        error_message=str(exc),
                        route=route,
                        metadata={
                            "operation": "stream_chat",
                            "attempt": attempt_index,
                            "total_candidates": len(routes),
                            "partial_output": yielded_content,
                            "route_attempts": route_attempts.copy(),
                        },
                    )
                    metrics_collector.observe_llm_call(
                        provider_key=route.provider.provider_key,
                        model_key=route.deployment.model_key,
                        status=LLMCallStatus.ERROR,
                        duration_ms=(time.perf_counter() - chat_started) * 1000,
                        error_code=exc.__class__.__name__,
                    )
                    # Once bytes have reached the client, falling back would
                    # concatenate responses from two models into one answer.
                    if yielded_content:
                        raise
                    continue
            if last_error is not None:
                raise last_error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No available LLM route for streaming.",
            )
        except (asyncio.CancelledError, GeneratorExit):
            if reservation_open and reservation is not None:
                await self.budget.release(reservation, context, "stream_cancelled")
                reservation_open = False
            raise
        except Exception:
            if reservation_open and reservation is not None:
                await self.budget.release(reservation, context, "stream_exception")
                reservation_open = False
            raise

    async def test_connection(
        self,
        request: ConnectionTestRequest,
        context: LLMRequestContext,
    ) -> ConnectionTestResult:
        route: RouteSelection | None = None
        reservation = None
        budget_reserved = False
        route_error_recorded = False
        chat_request = LLMChatRequest(
            model_key=request.model_key,
            routing_key=None,
            messages=[Message(role="user", content="ping")],
            max_tokens=1,
        )
        try:
            decision = await self.policy.evaluate(chat_request, context)
            if not decision.allowed:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.DENIED,
                    error_code="policy_denied",
                    error_message=decision.reason,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"LLM policy denied connection test: {decision.reason}",
                )
            reservation = await self.budget.reserve(chat_request, context)
            if not reservation.approved:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.BUDGET_EXCEEDED,
                    error_code="budget_exceeded",
                    error_message=reservation.reason,
                )
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"LLM budget denied connection test: {reservation.reason}",
                )
            budget_reserved = True
            routes = await self._routes_for_connection_test(request, decision, chat_request)
            route_attempts: list[dict[str, object]] = []
            last_result: ConnectionTestResult | None = None
            last_error: Exception | None = None
            for attempt_index, route in enumerate(routes, start=1):
                route_attempt = {
                    "attempt": attempt_index,
                    "provider_key": route.provider.provider_key,
                    "model_key": route.deployment.model_key,
                    "deployment_id": str(route.deployment.id),
                    "routing_key": route.deployment.routing_key,
                }
                try:
                    adapter = self._adapter_for(route)
                    result = await adapter.test_connection(request)
                    last_result = result
                    if result.ok:
                        self.circuit_breaker.record_success(str(route.deployment.id))
                    else:
                        self.circuit_breaker.record_failure(
                            str(route.deployment.id),
                            error_code="connection_test_failed",
                        )
                    route_attempts.append(
                        {
                            **route_attempt,
                            "status": LLMCallStatus.SUCCESS.value
                            if result.ok
                            else LLMCallStatus.ERROR.value,
                            "message": result.message,
                            "latency_ms": result.latency_ms,
                        }
                    )
                    enriched_result = result.model_copy(
                        update={
                            "diagnostics": {
                                **result.diagnostics,
                                "route_attempts": route_attempts,
                                "fallback_attempt_count": attempt_index - 1,
                                "selected_route_reason": route.reason,
                            }
                        }
                    )
                    await self.usage.record_connection_test(
                        context=context,
                        route=route,
                        result=enriched_result,
                    )
                    if result.ok or self._connection_test_is_explicit(request):
                        await self.budget.release(reservation, context, "connection_test")
                        return enriched_result
                except Exception as exc:
                    last_error = exc
                    self.circuit_breaker.record_failure(
                        str(route.deployment.id),
                        error_code=exc.__class__.__name__,
                    )
                    is_last_attempt = attempt_index == len(routes)
                    route_attempts.append(
                        {
                            **route_attempt,
                            "status": LLMCallStatus.ERROR.value,
                            "error_code": exc.__class__.__name__,
                            "error_message": str(exc),
                        }
                    )
                    await self.usage.record_failure(
                        context=context,
                        status=LLMCallStatus.ERROR,
                        error_code=exc.__class__.__name__,
                        error_message=str(exc),
                        route=route,
                        metadata={
                            "operation": "test_connection",
                            "fallback_attempt": not is_last_attempt,
                            "attempt": attempt_index,
                            "total_candidates": len(routes),
                            "route_attempts": route_attempts.copy(),
                        },
                    )
                    if self._connection_test_is_explicit(request) or is_last_attempt:
                        route_error_recorded = True
                        if reservation is not None:
                            await self.budget.release(reservation, context, "adapter_exception")
                            reservation = None
                        raise

            if last_result is not None:
                await self.budget.release(reservation, context, "connection_test")
                return last_result.model_copy(
                    update={
                        "diagnostics": {
                            **last_result.diagnostics,
                            "route_attempts": route_attempts,
                            "fallback_attempt_count": max(0, len(route_attempts) - 1),
                            "all_candidates_failed": True,
                        }
                    }
                )
            if last_error is not None:
                raise last_error
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No usable LLM deployment matched the connection test.",
            )
        except HTTPException as exc:
            if budget_reserved and not route_error_recorded:
                await self._record_http_failure(
                    context=context,
                    exc=exc,
                    route=route,
                    operation="connection_route_planning",
                )
                route_error_recorded = True
            if reservation is not None:
                await self.budget.release(reservation, context, "http_exception")
            raise
        except Exception as exc:
            if reservation is not None:
                await self.budget.release(reservation, context, "adapter_exception")
            if not route_error_recorded:
                await self.usage.record_failure(
                    context=context,
                    status=LLMCallStatus.ERROR,
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    route=route,
                )
            raise

    async def _routes_for_connection_test(
        self,
        request: ConnectionTestRequest,
        decision: PolicyDecision,
        chat_request: LLMChatRequest,
    ) -> list[RouteSelection]:
        if request.deployment_id:
            matches = [
                deployment
                for deployment in self.router.deployments
                if deployment.id == request.deployment_id
            ]
            if not matches:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="LLM deployment not found.",
                )
            deployment = matches[0]
            provider = self.router.providers[deployment.provider_key]
            if self._has_temporary_connection_config(request):
                return [
                    self._temporary_connection_route(
                        request=request,
                        provider=provider,
                        deployment=deployment,
                    )
                ]
            return [
                RouteSelection(deployment=deployment, provider=provider, reason="test_connection")
            ]
        if request.provider_key:
            requested_provider = self.router.providers.get(request.provider_key)
            if requested_provider is not None and self._has_temporary_connection_config(request):
                matches = [
                    deployment
                    for deployment in self.router.deployments
                    if deployment.provider_key == request.provider_key
                ]
                requested_deployment = (
                    sorted(matches, key=lambda item: item.priority)[0] if matches else None
                )
                return [
                    self._temporary_connection_route(
                        request=request,
                        provider=requested_provider,
                        deployment=requested_deployment,
                    )
                ]
            matches = [
                deployment
                for deployment in self.router.deployments
                if deployment.provider_key == request.provider_key
            ]
            if matches:
                routes: list[RouteSelection] = []
                for candidate in sorted(matches, key=lambda item: item.priority):
                    candidate_provider = self.router.providers.get(candidate.provider_key)
                    if candidate_provider is not None:
                        routes.append(
                            RouteSelection(
                                deployment=candidate,
                                provider=candidate_provider,
                                reason="test_connection",
                            )
                        )
                if routes:
                    return routes
        return await self.router.plan(chat_request, decision)

    def _connection_test_is_explicit(self, request: ConnectionTestRequest) -> bool:
        return request.deployment_id is not None or request.provider_key is not None

    def _has_temporary_connection_config(self, request: ConnectionTestRequest) -> bool:
        return bool(
            request.api_key or request.base_url or request.adapter_type or request.model_key
        )

    def _temporary_connection_route(
        self,
        *,
        request: ConnectionTestRequest,
        provider: ProviderConfig,
        deployment: DeploymentConfig | None,
    ) -> RouteSelection:
        model_key = request.model_key or (deployment.model_key if deployment else "chat-model")
        adapter_type = request.adapter_type or provider.adapter_type
        temporary_provider = provider.model_copy(
            update={
                "adapter_type": adapter_type,
                "base_url": request.base_url or provider.base_url,
                "credential_configured": bool(request.api_key or provider.credential_configured),
                "metadata": {
                    **provider.metadata,
                    "api_key": request.api_key or provider.metadata.get("api_key"),
                    "temporary_connection_test": True,
                },
            }
        )
        temporary_deployment = (
            deployment.model_copy(
                update={
                    "adapter_type": adapter_type,
                    "model_key": model_key,
                    "display_name": model_key,
                    "base_url": request.base_url or deployment.base_url,
                    "config": {
                        **deployment.config,
                        "mock": False
                        if request.api_key or request.base_url
                        else deployment.config.get("mock", False),
                        "temporary_connection_test": True,
                    },
                }
            )
            if deployment
            else DeploymentConfig(
                provider_key=provider.provider_key,
                provider_name=provider.name,
                adapter_type=adapter_type,
                model_key=model_key,
                display_name=model_key,
                deployment_name="Temporary Connection Test",
                routing_key=f"{provider.provider_key}-temporary-test",
                base_url=request.base_url or provider.base_url,
                config={"mock": False, "temporary_connection_test": True},
            )
        )
        return RouteSelection(
            deployment=temporary_deployment,
            provider=temporary_provider,
            reason="temporary_connection_test",
        )

    def _adapter_for(self, route: RouteSelection) -> BaseLLMAdapter:
        if route.provider.adapter_type == LLMAdapterType.LITELLM:
            return LiteLLMAdapter(route.provider, route.deployment)
        if route.provider.adapter_type == LLMAdapterType.OPENAI_COMPATIBLE:
            return OpenAICompatibleAdapter(route.provider, route.deployment)
        if route.provider.adapter_type == LLMAdapterType.ANTHROPIC_COMPATIBLE:
            return AnthropicCompatibleAdapter(route.provider, route.deployment)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Unsupported LLM adapter: {route.provider.adapter_type}",
        )

    async def _record_http_failure(
        self,
        *,
        context: LLMRequestContext,
        exc: HTTPException,
        route: RouteSelection | None,
        operation: str,
    ) -> None:
        detail = exc.detail
        await self.usage.record_failure(
            context=context,
            status=LLMCallStatus.ERROR,
            error_code=_http_error_code(detail, exc),
            error_message=_http_error_message(detail),
            route=route,
            metadata={
                "operation": operation,
                "http_status": exc.status_code,
                "detail": _safe_http_detail(detail),
            },
        )


def _http_error_code(detail: object, exc: HTTPException) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("code"), str):
        return str(detail["code"])
    return exc.__class__.__name__


def _http_error_message(detail: object) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return str(detail["message"])
    return str(detail)


def _safe_http_detail(detail: object) -> object:
    if not isinstance(detail, dict):
        return detail
    return {
        key: value
        for key, value in detail.items()
        if "api_key" not in key.lower() and "secret" not in key.lower()
    }
