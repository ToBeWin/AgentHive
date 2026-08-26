import unittest
from uuid import uuid4

from app.api.deps import Principal
from app.models.agent_module import AgentInstance
from app.models.channel import ChannelConfig
from app.models.org import Department
from app.models.tenant import CostCenter
from app.models.user import User
from app.services.budget_admin_service import list_budget_governance_targets


class BudgetGovernanceTargetsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_budget_governance_targets_returns_minimal_scope_targets(self) -> None:
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

        response = await list_budget_governance_targets(
            session,
            Principal(
                tenant_id=tenant_id,
                user_id=uuid4(),
                permissions={"budgets:read"},
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


class FakeGovernanceTargetsSession:
    def __init__(self, rows: list[object]) -> None:
        self.execute_count = 0
        self.rows_by_type = {
            Department: [row for row in rows if isinstance(row, Department)],
            CostCenter: [row for row in rows if isinstance(row, CostCenter)],
            User: [row for row in rows if isinstance(row, User)],
            AgentInstance: [row for row in rows if isinstance(row, AgentInstance)],
            ChannelConfig: [row for row in rows if isinstance(row, ChannelConfig)],
        }

    async def execute(self, _statement):
        ordered_types = [Department, CostCenter, User, AgentInstance, ChannelConfig]
        row_type = ordered_types[self.execute_count]
        self.execute_count += 1
        return FakeScalarListResult(self.rows_by_type[row_type])


class FakeScalarListResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
