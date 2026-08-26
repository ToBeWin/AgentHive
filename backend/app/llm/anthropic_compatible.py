from collections.abc import AsyncIterator
from time import perf_counter

import httpx

from app.llm.base import BaseLLMAdapter
from app.llm.mock_policy import llm_mock_allowed, llm_mock_disabled_message
from app.llm.pricing import ModelPricingCatalog
from app.llm.schemas import (
    ConnectionTestRequest,
    ConnectionTestResult,
    LLMChatRequest,
    LLMRequestContext,
    LLMResponse,
)


class AnthropicCompatibleAdapter(BaseLLMAdapter):
    adapter_name = "anthropic_compatible"

    async def chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        if self._should_call_live():
            return await self._live_chat(request, context)
        if not llm_mock_allowed():
            raise RuntimeError(llm_mock_disabled_message("Anthropic-compatible adapter"))
        deployment = self.deployment
        model_key = deployment.model_key if deployment else request.model_key or "claude-compatible"
        usage = ModelPricingCatalog().calculate(
            input_tokens=sum(max(1, len(message.content) // 4) for message in request.messages),
            output_tokens=min(request.max_tokens or 128, 128),
            model_key=model_key,
        )
        return LLMResponse(
            request_id=context.request_id,
            model_key=model_key,
            provider_key=self.provider.provider_key,
            deployment_id=deployment.id if deployment else None,
            content="Anthropic-compatible adapter mock response. Configure endpoint credentials to enable live calls.",
            usage=usage,
            finish_reason="stop",
            metadata={"adapter": self.adapter_name, "mock": True},
        )

    async def stream_chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> AsyncIterator[str]:
        response = await self.chat(request, context)
        for chunk in response.content.split(" "):
            yield f"{chunk} "

    async def test_connection(
        self,
        request: ConnectionTestRequest,
    ) -> ConnectionTestResult:
        started = perf_counter()
        if self._should_call_live(request):
            try:
                await self._post_messages(
                    model=request.model_key
                    or (self.deployment.model_key if self.deployment else "claude-compatible"),
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    timeout_seconds=request.timeout_seconds,
                    api_key=request.api_key or self._api_key(),
                    base_url=request.base_url or self._base_url(),
                )
                latency_ms = int((perf_counter() - started) * 1000)
                return ConnectionTestResult(
                    ok=True,
                    provider_key=request.provider_key or self.provider.provider_key,
                    adapter_type=self.provider.adapter_type,
                    model_key=request.model_key
                    or (self.deployment.model_key if self.deployment else None),
                    latency_ms=latency_ms,
                    message="Anthropic-compatible endpoint responded to a live messages probe.",
                    diagnostics={
                        "base_url": request.base_url or self._base_url(),
                        "live_network_call": True,
                    },
                )
            except httpx.HTTPError as exc:
                latency_ms = int((perf_counter() - started) * 1000)
                return ConnectionTestResult(
                    ok=False,
                    provider_key=request.provider_key or self.provider.provider_key,
                    adapter_type=self.provider.adapter_type,
                    model_key=request.model_key
                    or (self.deployment.model_key if self.deployment else None),
                    latency_ms=latency_ms,
                    message=f"Anthropic-compatible endpoint probe failed: {exc}",
                    diagnostics={
                        "base_url": request.base_url or self._base_url(),
                        "live_network_call": True,
                        "error_type": exc.__class__.__name__,
                    },
                )
        latency_ms = int((perf_counter() - started) * 1000)
        if not llm_mock_allowed():
            return ConnectionTestResult(
                ok=False,
                provider_key=request.provider_key or self.provider.provider_key,
                adapter_type=self.provider.adapter_type,
                model_key=request.model_key
                or (self.deployment.model_key if self.deployment else None),
                latency_ms=latency_ms,
                message=llm_mock_disabled_message("Anthropic-compatible adapter"),
                diagnostics={
                    "base_url": request.base_url or self.provider.base_url,
                    "live_network_call": False,
                    "mock_allowed": False,
                },
            )
        return ConnectionTestResult(
            ok=True,
            provider_key=request.provider_key or self.provider.provider_key,
            adapter_type=self.provider.adapter_type,
            model_key=request.model_key or (self.deployment.model_key if self.deployment else None),
            latency_ms=latency_ms,
            message="Anthropic-compatible endpoint configuration accepted in mock mode.",
            diagnostics={
                "base_url": request.base_url or self.provider.base_url,
                "live_network_call": False,
                "mock_allowed": True,
            },
        )

    async def _live_chat(
        self,
        request: LLMChatRequest,
        context: LLMRequestContext,
    ) -> LLMResponse:
        deployment = self.deployment
        model_key = deployment.model_key if deployment else request.model_key or "claude-compatible"
        payload = await self._post_messages(
            model=model_key,
            messages=[
                message.model_dump(exclude_none=True)
                for message in request.messages
                if message.role != "system"
            ],
            system="\n\n".join(
                message.content for message in request.messages if message.role == "system"
            )
            or None,
            max_tokens=request.max_tokens or 1024,
            timeout_seconds=60,
            api_key=self._api_key(),
            base_url=self._base_url(),
            temperature=request.temperature,
        )
        input_tokens, output_tokens = _extract_usage(payload)
        usage = ModelPricingCatalog().calculate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_key=model_key,
        )
        return LLMResponse(
            request_id=context.request_id,
            model_key=model_key,
            provider_key=self.provider.provider_key,
            deployment_id=deployment.id if deployment else None,
            content=_extract_content(payload),
            usage=usage,
            finish_reason=_extract_finish_reason(payload),
            metadata={
                "adapter": self.adapter_name,
                "mock": False,
                "live_network_call": True,
                "response_id": payload.get("id"),
            },
        )

    async def _post_messages(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        timeout_seconds: float,
        api_key: str,
        base_url: str | None,
        system: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, object]:
        if not base_url:
            raise ValueError("Anthropic-compatible base_url is required for live calls.")
        payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": message["role"], "content": message["content"]}
                for message in messages
                if message.get("role") in {"user", "assistant"} and message.get("content")
            ],
            "max_tokens": max_tokens,
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {
            "x-api-key": api_key,
            "anthropic-version": str(
                self.provider.metadata.get("anthropic_version") or "2023-06-01"
            ),
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/messages",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Anthropic-compatible endpoint returned a non-object response.")
        return data

    def _should_call_live(self, request: ConnectionTestRequest | None = None) -> bool:
        base_url = request.base_url if request else None
        api_key = request.api_key if request else None
        has_target = bool(base_url or self._base_url())
        has_secret = bool(api_key or self._api_key())
        is_mock = self.deployment and self.deployment.config.get("mock") is True
        return has_target and has_secret and not is_mock

    def _base_url(self) -> str | None:
        return self.provider.base_url

    def _api_key(self) -> str:
        secret = self.provider.metadata.get("api_key")
        return str(secret) if secret else ""


def _extract_content(payload: dict[str, object]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return "".join(chunks)
    if isinstance(payload.get("completion"), str):
        return str(payload["completion"])
    return ""


def _extract_finish_reason(payload: dict[str, object]) -> str | None:
    stop_reason = payload.get("stop_reason")
    return stop_reason if isinstance(stop_reason, str) else None


def _extract_usage(payload: dict[str, object]) -> tuple[int, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return 0, 0
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return input_tokens, output_tokens
