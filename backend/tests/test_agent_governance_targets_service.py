import unittest
from uuid import uuid4

from app.api.deps import Principal
from app.models.knowledge import KnowledgeBase
from app.models.llm import LLMDeployment
from app.models.org import Department
from app.models.user import User
from app.services.agent_runtime_service import list_agent_governance_targets


class AgentGovernanceTargetsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_agent_governance_targets_returns_accessible_configuration_targets(
        self,
    ) -> None:
        tenant_id = uuid4()
        user_id = uuid4()
        member_department_id = uuid4()
        other_department_id = uuid4()
        deployment_id = uuid4()
        session = FakeAgentGovernanceTargetsSession(
            department_ids=[member_department_id],
            departments=[
                Department(
                    id=member_department_id,
                    tenant_id=tenant_id,
                    name="Customer Success",
                    description="Customer-facing workflows.",
                    sort_order=10,
                ),
                Department(
                    id=other_department_id,
                    tenant_id=tenant_id,
                    name="Finance",
                    description="Restricted finance workflows.",
                    sort_order=20,
                ),
            ],
            users=[
                User(
                    id=user_id,
                    tenant_id=tenant_id,
                    email="owner@example.com",
                    hashed_password="hash",
                    full_name="Agent Owner",
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
            ],
            knowledge_bases=[
                KnowledgeBase(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name="Support SOP",
                    description="Support answers.",
                    visibility="department",
                    department_ids=[str(member_department_id)],
                    rag_engine="pgvector",
                    status="active",
                    document_count=3,
                    metadata_json={},
                ),
                KnowledgeBase(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    name="Finance Policy",
                    description="Finance only.",
                    visibility="department",
                    department_ids=[str(other_department_id)],
                    rag_engine="ragflow",
                    status="active",
                    document_count=1,
                    metadata_json={},
                ),
            ],
            deployments=[
                LLMDeployment(
                    id=deployment_id,
                    tenant_id=tenant_id,
                    provider_id=uuid4(),
                    model_id=uuid4(),
                    deployment_name="Default Chat",
                    routing_key="default-chat",
                    is_active=True,
                    priority=10,
                ),
            ],
        )

        response = await list_agent_governance_targets(
            session,
            Principal(
                tenant_id=tenant_id,
                user_id=user_id,
                permissions={"agents:read"},
            ),
        )

        self.assertEqual(["Customer Success"], [target.label for target in response.departments])
        self.assertEqual(
            ["Agent Owner (owner@example.com)"], [target.label for target in response.users]
        )
        self.assertEqual(
            ["Support SOP · pgvector"], [target.label for target in response.knowledge_bases]
        )
        self.assertEqual("pgvector", response.knowledge_bases[0].metadata["rag_engine"])
        self.assertEqual("default-chat · Default Chat", response.model_deployments[0].label)
        self.assertEqual(str(deployment_id), str(response.model_deployments[0].id))
        self.assertEqual(5, session.execute_count)


class FakeAgentGovernanceTargetsSession:
    def __init__(
        self,
        *,
        department_ids: list[object],
        departments: list[Department],
        users: list[User],
        knowledge_bases: list[KnowledgeBase],
        deployments: list[LLMDeployment],
    ) -> None:
        self.execute_count = 0
        self.rows = [department_ids, departments, users, knowledge_bases, deployments]
        self.rollback_called = False

    async def execute(self, _statement):
        rows = self.rows[self.execute_count]
        self.execute_count += 1
        return FakeScalarListResult(rows)

    async def rollback(self):
        self.rollback_called = True


class FakeScalarListResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
