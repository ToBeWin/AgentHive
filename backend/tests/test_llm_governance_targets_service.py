import unittest
from uuid import uuid4

from app.api.deps import Principal
from app.models.agent_module import AgentInstance
from app.models.channel import ChannelConfig
from app.models.org import Department
from app.models.tenant import CostCenter
from app.models.user import User, UserDepartment
from app.services.llm_service import list_model_governance_targets


class LLMGovernanceTargetsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_model_governance_targets_returns_minimal_policy_targets_for_tenant_admin(
        self,
    ) -> None:
        tenant_id = uuid4()
        department_id = uuid4()
        user_id = uuid4()
        agent_id = uuid4()
        channel_id = uuid4()
        session = FakeGovernanceTargetsSession(
            [
                Department(
                    id=department_id,
                    tenant_id=tenant_id,
                    name="Customer Success",
                    description="Customer-facing AI workflows.",
                    sort_order=10,
                ),
                CostCenter(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    department_id=department_id,
                    code="CS",
                    name="Customer Success",
                    monthly_budget_usd="2500.0000",
                    is_active=True,
                ),
                User(
                    id=user_id,
                    tenant_id=tenant_id,
                    email="leader@example.com",
                    hashed_password="hash",
                    full_name="Support Leader",
                    is_active=True,
                ),
                AgentInstance(
                    id=agent_id,
                    tenant_id=tenant_id,
                    name="Customer Service Assistant",
                    slug="customer-service",
                    agent_key="customer_service",
                    module_key="agent.customer_service",
                    department_id=department_id,
                    status="active",
                ),
                ChannelConfig(
                    id=channel_id,
                    tenant_id=tenant_id,
                    name="Web Widget",
                    channel_type="web_widget",
                    channel_key="default",
                    agent_id=agent_id,
                    status="active",
                ),
            ]
        )

        response = await list_model_governance_targets(
            session,
            Principal(
                tenant_id=tenant_id,
                user_id=uuid4(),
                permissions={"tenant.admin", "models:read"},
            ),
        )

        self.assertEqual(["Customer Success"], [target.label for target in response.departments])
        self.assertEqual("CS - Customer Success", response.cost_centers[0].label)
        self.assertEqual(str(department_id), response.cost_centers[0].metadata["department_id"])
        self.assertEqual("Support Leader (leader@example.com)", response.users[0].label)
        self.assertEqual("leader@example.com", response.users[0].metadata["email"])
        self.assertIn("customer_service:customer-service", response.agents[0].label)
        self.assertEqual(str(department_id), response.agents[0].metadata["department_id"])
        self.assertEqual("Web Widget (web_widget:default)", response.channels[0].label)
        self.assertEqual(str(agent_id), response.channels[0].metadata["agent_id"])
        self.assertEqual(5, session.execute_count)

    async def test_list_model_governance_targets_limits_non_admin_to_direct_scope(self) -> None:
        tenant_id = uuid4()
        principal_id = uuid4()
        own_department_id = uuid4()
        other_department_id = uuid4()
        own_agent_id = uuid4()
        other_agent_id = uuid4()
        session = FakeGovernanceTargetsSession(
            [
                UserDepartment(user_id=principal_id, department_id=own_department_id),
                Department(id=own_department_id, tenant_id=tenant_id, name="Customer Success"),
                Department(id=other_department_id, tenant_id=tenant_id, name="Finance"),
                CostCenter(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    department_id=own_department_id,
                    code="CS",
                    name="Customer Success",
                    is_active=True,
                ),
                CostCenter(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    department_id=other_department_id,
                    code="FIN",
                    name="Finance",
                    is_active=True,
                ),
                User(
                    id=principal_id,
                    tenant_id=tenant_id,
                    email="leader@example.com",
                    hashed_password="hash",
                    full_name="Support Leader",
                    is_active=True,
                ),
                User(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    email="other@example.com",
                    hashed_password="hash",
                    full_name="Other User",
                    is_active=True,
                ),
                AgentInstance(
                    id=own_agent_id,
                    tenant_id=tenant_id,
                    name="Scoped Assistant",
                    slug="scoped",
                    agent_key="customer_service",
                    module_key="agent.customer_service",
                    visibility="department",
                    department_id=own_department_id,
                    status="active",
                ),
                AgentInstance(
                    id=other_agent_id,
                    tenant_id=tenant_id,
                    name="Finance Assistant",
                    slug="finance",
                    agent_key="finance",
                    module_key="agent.finance",
                    visibility="department",
                    department_id=other_department_id,
                    status="active",
                ),
                ChannelConfig(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name="Scoped Widget",
                    channel_type="web_widget",
                    channel_key="scoped",
                    agent_id=own_agent_id,
                    status="active",
                ),
                ChannelConfig(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name="Finance Widget",
                    channel_type="web_widget",
                    channel_key="finance",
                    agent_id=other_agent_id,
                    status="active",
                ),
            ]
        )

        response = await list_model_governance_targets(
            session,
            Principal(
                tenant_id=tenant_id,
                user_id=principal_id,
                permissions={"models:read"},
            ),
        )

        self.assertEqual(["Customer Success"], [target.label for target in response.departments])
        self.assertEqual(
            ["CS - Customer Success"], [target.label for target in response.cost_centers]
        )
        self.assertEqual(
            ["Support Leader (leader@example.com)"], [target.label for target in response.users]
        )
        self.assertEqual(
            ["Scoped Assistant (customer_service:scoped, active)"],
            [target.label for target in response.agents],
        )
        self.assertEqual(
            ["Scoped Widget (web_widget:scoped)"], [target.label for target in response.channels]
        )
        self.assertEqual(6, session.execute_count)


class FakeGovernanceTargetsSession:
    def __init__(self, rows: list[object]) -> None:
        self.execute_count = 0
        self.rows_by_type = {
            UserDepartment: [row for row in rows if isinstance(row, UserDepartment)],
            Department: [row for row in rows if isinstance(row, Department)],
            CostCenter: [row for row in rows if isinstance(row, CostCenter)],
            User: [row for row in rows if isinstance(row, User)],
            AgentInstance: [row for row in rows if isinstance(row, AgentInstance)],
            ChannelConfig: [row for row in rows if isinstance(row, ChannelConfig)],
        }

    async def execute(self, _statement):
        statement_text = str(_statement)
        self.execute_count += 1
        if "user_departments" in statement_text:
            return FakeScalarListResult(
                [row.department_id for row in self.rows_by_type[UserDepartment]]
            )
        if "cost_centers" in statement_text:
            return FakeScalarListResult(self.rows_by_type[CostCenter])
        if "users" in statement_text:
            return FakeScalarListResult(self.rows_by_type[User])
        if "agent_instances" in statement_text:
            return FakeScalarListResult(self.rows_by_type[AgentInstance])
        if "channel_configs" in statement_text:
            return FakeScalarListResult(self.rows_by_type[ChannelConfig])
        return FakeScalarListResult(self.rows_by_type[Department])


class FakeScalarListResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
