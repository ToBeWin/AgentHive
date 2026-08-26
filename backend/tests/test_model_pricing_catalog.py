from decimal import Decimal
import unittest

from app.llm.pricing import ModelPricingCatalog, PricingMatchType, PricingRule
from app.llm.schemas import LLMChatRequest, Message
from app.services.llm_service import _DEPLOYMENTS


class ModelPricingCatalogTests(unittest.TestCase):
    def test_default_deployment_models_have_explicit_price_rules(self):
        catalog = ModelPricingCatalog()
        unmatched = []

        for deployment in _DEPLOYMENTS:
            rule = catalog.price_rule_for(deployment.model_key)
            if rule.match_type == PricingMatchType.DEFAULT:
                unmatched.append(deployment.model_key)

        self.assertEqual([], sorted(set(unmatched)))

    def test_openrouter_style_model_alias_uses_underlying_model_rule(self):
        rule = ModelPricingCatalog().price_rule_for("openai/gpt-4o-mini")

        self.assertEqual("gpt-4o-mini", rule.pattern)
        self.assertEqual(Decimal("0.00015"), rule.input_per_1k)

    def test_unknown_model_uses_conservative_default_rule(self):
        rule = ModelPricingCatalog().price_rule_for("vendor/unknown-model")

        self.assertEqual(PricingMatchType.DEFAULT, rule.match_type)
        self.assertEqual(Decimal("0.001"), rule.input_per_1k)

    def test_mimo_external_api_is_not_treated_as_free(self):
        rule = ModelPricingCatalog().price_rule_for("mimo-chat")
        usage = ModelPricingCatalog().calculate(
            input_tokens=1000, output_tokens=1000, model_key="mimo-chat"
        )

        self.assertEqual("mimo-chat", rule.pattern)
        self.assertGreater(rule.input_per_1k, Decimal("0"))
        self.assertGreater(rule.output_per_1k, Decimal("0"))
        self.assertEqual(Decimal("0.003000"), usage.cost_usd)

    def test_estimate_uses_catalog_prices(self):
        usage = ModelPricingCatalog().estimate(
            LLMChatRequest(
                model_key="deepseek-v4-flash",
                messages=[Message(role="user", content="x" * 400)],
                max_tokens=100,
            )
        )

        self.assertEqual(200, usage.total_tokens)
        self.assertEqual(Decimal("0.000042"), usage.cost_usd)

    def test_database_style_override_takes_precedence_over_builtin_rule(self):
        catalog = ModelPricingCatalog(
            overrides=[
                PricingRule(
                    pattern="deepseek-v4-flash",
                    input_per_1k=Decimal("1"),
                    output_per_1k=Decimal("2"),
                    source="database",
                )
            ]
        )

        rule = catalog.price_rule_for("deepseek-v4-flash")
        usage = catalog.calculate(input_tokens=10, output_tokens=10, model_key="deepseek-v4-flash")

        self.assertEqual("database", rule.source)
        self.assertEqual(Decimal("0.030000"), usage.cost_usd)


if __name__ == "__main__":
    unittest.main()
