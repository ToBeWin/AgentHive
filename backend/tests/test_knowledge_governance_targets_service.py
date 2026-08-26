import unittest
from uuid import uuid4

from app.api.deps import Principal
from app.models.org import Department
from app.services.knowledge_service import list_knowledge_governance_targets


class KnowledgeGovernanceTargetsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_knowledge_governance_targets_returns_minimal_department_targets(
        self,
    ) -> None:
        tenant_id = uuid4()
        parent_id = uuid4()
        child_id = uuid4()
        session = FakeKnowledgeGovernanceTargetsSession(
            [
                Department(
                    id=parent_id,
                    tenant_id=tenant_id,
                    name="Customer Success",
                    description="Customer-facing AI workflows.",
                    sort_order=10,
                ),
                Department(
                    id=child_id,
                    tenant_id=tenant_id,
                    parent_id=parent_id,
                    name="VIP Support",
                    description=None,
                    sort_order=20,
                ),
            ]
        )

        response = await list_knowledge_governance_targets(
            session,
            Principal(
                tenant_id=tenant_id,
                user_id=uuid4(),
                permissions={"knowledge:read"},
            ),
        )

        self.assertEqual(
            ["Customer Success", "VIP Support"], [target.label for target in response.departments]
        )
        self.assertEqual("Customer-facing AI workflows.", response.departments[0].description)
        self.assertIsNone(response.departments[0].metadata["parent_id"])
        self.assertEqual(str(parent_id), response.departments[1].metadata["parent_id"])
        self.assertEqual(20, response.departments[1].metadata["sort_order"])
        self.assertEqual(1, session.execute_count)


class FakeKnowledgeGovernanceTargetsSession:
    def __init__(self, departments: list[Department]) -> None:
        self.departments = departments
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        return FakeScalarListResult(self.departments)


class FakeScalarListResult:
    def __init__(self, rows: list[Department]) -> None:
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
