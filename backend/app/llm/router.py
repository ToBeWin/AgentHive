from decimal import Decimal

from fastapi import HTTPException, status

from app.llm.circuit_breaker import CircuitBreaker, circuit_breaker as default_circuit_breaker
from app.llm.pricing import ModelPricingCatalog
from app.llm.schemas import (
    DeploymentConfig,
    LLMAdapterType,
    LLMChatRequest,
    LLMDeploymentStatus,
    PolicyDecision,
    ProviderConfig,
    RouteSelection,
)


class ModelRouter:
    """Selects the concrete deployment after policy and budget checks."""

    def __init__(
        self,
        providers: list[ProviderConfig],
        deployments: list[DeploymentConfig],
        *,
        circuit_breaker: CircuitBreaker | None = None,
        pricing: ModelPricingCatalog | None = None,
        cost_aware_routing_enabled: bool = False,
    ):
        self.providers = {provider.provider_key: provider for provider in providers}
        self.deployments = deployments
        self.circuit_breaker = circuit_breaker or default_circuit_breaker
        self.pricing = pricing
        self.cost_aware_routing_enabled = cost_aware_routing_enabled

    async def select(
        self,
        request: LLMChatRequest,
        decision: PolicyDecision,
    ) -> RouteSelection:
        routes = await self.plan(request, decision)
        return routes[0]

    async def plan(
        self,
        request: LLMChatRequest,
        decision: PolicyDecision,
    ) -> list[RouteSelection]:
        candidates = [
            deployment
            for deployment in self.deployments
            if deployment.status == LLMDeploymentStatus.ACTIVE
        ]
        model_key = decision.model_key or request.model_key
        if model_key:
            candidates = [
                deployment for deployment in candidates if deployment.model_key == model_key
            ]
        if decision.routing_key:
            policy_candidates = [
                deployment
                for deployment in candidates
                if deployment.routing_key == decision.routing_key
            ]
            if not policy_candidates:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_route_error_detail(
                        code="policy_routing_key_not_found",
                        message="No active LLM deployment matched the policy routing key.",
                        request=request,
                        decision=decision,
                        candidate_count=len(candidates),
                    ),
                )
            candidates = policy_candidates
        if request.routing_key:
            candidates = [
                deployment
                for deployment in candidates
                if deployment.routing_key == request.routing_key
            ]

        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_route_error_detail(
                    code="deployment_not_found",
                    message="No active LLM deployment matched the request.",
                    request=request,
                    decision=decision,
                    candidate_count=0,
                ),
            )

        # Filter out deployments whose circuit breaker is OPEN. If every
        # candidate is open we keep them all so the caller can still attempt a
        # last-resort call rather than failing hard — the breaker's cooldown
        # will eventually allow probes through.
        open_skipped: list[str] = []
        healthy_candidates = []
        for deployment in candidates:
            if self.circuit_breaker.is_open(str(deployment.id)):
                open_skipped.append(str(deployment.id))
            else:
                healthy_candidates.append(deployment)
        if healthy_candidates:
            candidates = healthy_candidates

        routes: list[RouteSelection] = []
        missing_provider_keys: list[str] = []
        cost_aware = (
            self.cost_aware_routing_enabled
            and self.pricing is not None
            and decision.metadata.get("routing_strategy") == "cost_priority"
        )
        for deployment in self._sort_candidates(candidates, request, cost_aware):
            provider = self.providers.get(deployment.provider_key)
            if provider is None:
                missing_provider_keys.append(deployment.provider_key)
                continue
            routes.append(
                RouteSelection(
                    deployment=deployment,
                    provider=provider,
                    reason="cost_priority_route" if cost_aware else "priority_route",
                )
            )

        if routes:
            return routes

        if missing_provider_keys:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=_route_error_detail(
                    code="deployment_provider_not_registered",
                    message="LLM deployment provider is not registered.",
                    request=request,
                    decision=decision,
                    candidate_count=len(candidates),
                    missing_provider_keys=missing_provider_keys,
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_route_error_detail(
                code="usable_deployment_not_found",
                message="No usable LLM deployment matched the request.",
                request=request,
                decision=decision,
                candidate_count=len(candidates),
            ),
        )

    def adapter_type_for(self, provider_key: str) -> LLMAdapterType:
        return self.providers[provider_key].adapter_type

    def _sort_candidates(
        self,
        candidates: list[DeploymentConfig],
        request: LLMChatRequest,
        cost_aware: bool,
    ) -> list[DeploymentConfig]:
        """Order candidates for route selection.

        Default order is ascending ``priority``. When cost-aware routing is
        enabled, equal-priority candidates are tie-broken by ascending
        estimated cost (input + output per 1k tokens) so the cheapest
        eligible deployment is preferred. Deployments without a pricing rule
        are pushed to the back of their priority bucket.
        """
        if not cost_aware or self.pricing is None:
            return sorted(candidates, key=lambda item: item.priority)
        pricing = self.pricing

        def cost_key(deployment: DeploymentConfig) -> tuple[int, Decimal]:
            rule = pricing.price_rule_for(deployment.model_key)
            # Combined per-1k-token cost — actual request volume cancels out
            # when comparing deployments that share the same request.
            return (deployment.priority, rule.input_per_1k + rule.output_per_1k)

        return sorted(candidates, key=cost_key)


def _route_error_detail(
    *,
    code: str,
    message: str,
    request: LLMChatRequest,
    decision: PolicyDecision,
    candidate_count: int,
    missing_provider_keys: list[str] | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "request_model_key": request.model_key,
        "request_routing_key": request.routing_key,
        "policy_model_key": decision.model_key,
        "policy_routing_key": decision.routing_key,
        "candidate_count": candidate_count,
        "missing_provider_keys": sorted(set(missing_provider_keys or [])),
    }
