from decimal import Decimal
from enum import StrEnum
from dataclasses import dataclass

from app.llm.schemas import LLMChatRequest, LLMUsageMetrics


class PricingMatchType(StrEnum):
    EXACT = "exact"
    PREFIX = "prefix"
    CONTAINS = "contains"
    DEFAULT = "default"


@dataclass(frozen=True)
class PricingRule:
    pattern: str
    input_per_1k: Decimal
    output_per_1k: Decimal
    match_type: PricingMatchType = PricingMatchType.EXACT
    source: str = "agenthive_builtin"


class ModelPricingCatalog:
    """First-pass pricing catalog; later backed by llm_model_prices."""

    _DEFAULT_INPUT_PER_1K = Decimal("0.001")
    _DEFAULT_OUTPUT_PER_1K = Decimal("0.002")
    _RULES: tuple[PricingRule, ...] = (
        PricingRule("gpt-4o", Decimal("0.0025"), Decimal("0.010")),
        PricingRule("gpt-4o-mini", Decimal("0.00015"), Decimal("0.0006")),
        PricingRule(
            "claude-3-5-sonnet", Decimal("0.003"), Decimal("0.015"), PricingMatchType.CONTAINS
        ),
        PricingRule("claude-compatible", Decimal("0"), Decimal("0")),
        PricingRule("gemini-1.5-pro", Decimal("0.00125"), Decimal("0.005")),
        PricingRule("mistral-large", Decimal("0.002"), Decimal("0.006"), PricingMatchType.PREFIX),
        PricingRule("command-r-plus", Decimal("0.003"), Decimal("0.015")),
        PricingRule("grok-2", Decimal("0.002"), Decimal("0.010"), PricingMatchType.PREFIX),
        PricingRule("qwen-plus", Decimal("0.00028"), Decimal("0.00084")),
        PricingRule("deepseek-v4-flash", Decimal("0.00014"), Decimal("0.00028")),
        PricingRule("deepseek-chat", Decimal("0.00014"), Decimal("0.00028")),
        PricingRule("moonshot-v1-128k", Decimal("0.0017"), Decimal("0.0017")),
        PricingRule("mimo-chat", _DEFAULT_INPUT_PER_1K, _DEFAULT_OUTPUT_PER_1K),
        PricingRule("abab6.5s-chat", Decimal("0.0002"), Decimal("0.0006")),
        PricingRule("glm-4-plus", Decimal("0.007"), Decimal("0.007")),
        PricingRule("doubao-pro", Decimal("0.00011"), Decimal("0.00022"), PricingMatchType.PREFIX),
        PricingRule("ernie-4.0", Decimal("0.0017"), Decimal("0.0017"), PricingMatchType.PREFIX),
        PricingRule("hunyuan-pro", Decimal("0.004"), Decimal("0.004")),
        PricingRule("spark-max", Decimal("0.0035"), Decimal("0.0035")),
        PricingRule(
            "llama-3.1-70b", Decimal("0.0009"), Decimal("0.0009"), PricingMatchType.CONTAINS
        ),
        PricingRule(
            "llama-v3p1-70b", Decimal("0.0009"), Decimal("0.0009"), PricingMatchType.CONTAINS
        ),
        PricingRule(
            "DeepSeek-V3", Decimal("0.00014"), Decimal("0.00028"), PricingMatchType.CONTAINS
        ),
        PricingRule("llama3.1", Decimal("0"), Decimal("0")),
        PricingRule("local-chat", Decimal("0"), Decimal("0")),
        PricingRule("local-model", Decimal("0"), Decimal("0")),
        PricingRule("openai/gpt-image-2", Decimal("0"), Decimal("0")),
        PricingRule("google/nano-banana", Decimal("0"), Decimal("0")),
        PricingRule("volcengine/seedance-2.0", Decimal("0"), Decimal("0")),
        PricingRule("openai-compatible-image", Decimal("0"), Decimal("0")),
    )

    def __init__(self, overrides: list[PricingRule] | tuple[PricingRule, ...] | None = None):
        self.overrides = tuple(overrides or ())

    def estimate(self, request: LLMChatRequest) -> LLMUsageMetrics:
        input_tokens = self._estimate_input_tokens(request)
        output_tokens = request.max_tokens or 512
        return self.calculate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_key=request.model_key,
        )

    def calculate(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        model_key: str | None,
    ) -> LLMUsageMetrics:
        input_price, output_price = self._prices_for(model_key)
        cost = (
            Decimal(input_tokens) / Decimal(1000) * input_price
            + Decimal(output_tokens) / Decimal(1000) * output_price
        )
        return LLMUsageMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost.quantize(Decimal("0.000001")),
        )

    def price_rule_for(self, model_key: str | None) -> PricingRule:
        if not model_key:
            return self.default_rule()

        normalized = model_key.lower()
        aliases = {normalized, normalized.rsplit("/", 1)[-1]}
        for rule in (*self.overrides, *self._RULES):
            pattern = rule.pattern.lower()
            if rule.match_type == PricingMatchType.EXACT and pattern in aliases:
                return rule
            if rule.match_type == PricingMatchType.PREFIX and any(
                alias.startswith(pattern) for alias in aliases
            ):
                return rule
            if rule.match_type == PricingMatchType.CONTAINS and any(
                pattern in alias for alias in aliases
            ):
                return rule
        return self.default_rule()

    def default_rule(self) -> PricingRule:
        return PricingRule(
            pattern="*",
            input_per_1k=self._DEFAULT_INPUT_PER_1K,
            output_per_1k=self._DEFAULT_OUTPUT_PER_1K,
            match_type=PricingMatchType.DEFAULT,
            source="agenthive_default",
        )

    def _estimate_input_tokens(self, request: LLMChatRequest) -> int:
        text = "\n".join(message.content for message in request.messages)
        return max(1, len(text) // 4)

    def _prices_for(self, model_key: str | None) -> tuple[Decimal, Decimal]:
        rule = self.price_rule_for(model_key)
        return rule.input_per_1k, rule.output_per_1k

    def recalculate_usage(
        self,
        usage: LLMUsageMetrics,
        *,
        model_key: str | None,
    ) -> LLMUsageMetrics:
        return self.calculate(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            model_key=model_key,
        )
