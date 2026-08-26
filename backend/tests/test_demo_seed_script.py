import unittest
from uuid import uuid4

from app.schemas.knowledge import KnowledgeDocumentSource
from app.services.license_service import DEFAULT_ALLOWED_MODULES
from scripts.demo_seed.agents import _customer_service_agent_config
from scripts.demo_seed.llm import _demo_allowed_models, _demo_allowed_routing_keys
from scripts.demo_seed.knowledge import KnowledgeDocumentSource as DemoKnowledgeDocumentSource
from scripts.demo_seed.license import DEMO_LICENSE_KEY
from scripts.seed_demo import (
    DEMO_ADMIN_EMAIL,
    DEMO_ADMIN_PASSWORD,
    DEMO_EMPLOYEE_EMAIL,
    DEMO_TENANT_SLUG,
    DemoSeedSummary,
)


class DemoSeedScriptTest(unittest.TestCase):
    def test_demo_credentials_match_documented_defaults(self) -> None:
        self.assertEqual("demo", DEMO_TENANT_SLUG)
        self.assertEqual("admin@example.com", DEMO_ADMIN_EMAIL)
        self.assertEqual("employee@example.com", DEMO_EMPLOYEE_EMAIL)
        self.assertEqual("AgentHive123!", DEMO_ADMIN_PASSWORD)

    def test_seed_summary_reports_login_details(self) -> None:
        message = DemoSeedSummary(
            tenant_slug="demo",
            admin_email="admin@example.com",
            admin_password="AgentHive123!",
            employee_email="employee@example.com",
            employee_password="AgentHive123!",
        ).to_message()

        self.assertIn("AgentHive demo data seeded.", message)
        self.assertIn("Tenant slug: demo", message)
        self.assertIn("Admin email: admin@example.com", message)
        self.assertIn("Employee email: employee@example.com", message)

    def test_demo_knowledge_source_uses_public_api_enum(self) -> None:
        self.assertIs(DemoKnowledgeDocumentSource, KnowledgeDocumentSource)
        self.assertIn("internal_import", {item.value for item in KnowledgeDocumentSource})

    def test_demo_agent_config_binds_retrievable_knowledge_base_ids(self) -> None:
        knowledge_base_id = uuid4()
        config = _customer_service_agent_config(knowledge_base_id)

        self.assertEqual([str(knowledge_base_id)], config["knowledge_base_ids"])
        self.assertEqual(["Customer Service SOP"], config["knowledge_base_names"])
        self.assertEqual(3, config["knowledge_top_k"])

    def test_demo_license_unlocks_customer_service_agent(self) -> None:
        self.assertEqual("agenthive-demo-enterprise-active-key", DEMO_LICENSE_KEY)
        self.assertIn("agent.customer_service", DEFAULT_ALLOWED_MODULES)

    def test_demo_model_policy_unlocks_media_generation_routes(self) -> None:
        self.assertIn("google/nano-banana", _demo_allowed_models("qwen-plus"))
        self.assertIn("volcengine/seedance-2.0", _demo_allowed_models("qwen-plus"))
        self.assertIn("image-generation", _demo_allowed_routing_keys("cn-primary-chat"))
        self.assertIn("video-generation", _demo_allowed_routing_keys("cn-primary-chat"))


if __name__ == "__main__":
    unittest.main()
