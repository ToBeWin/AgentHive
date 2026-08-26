import unittest

from app.services.knowledge_service import _pgvector_chunk_schema_ready


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeSchemaSession:
    def __init__(self, value=True, *, fail=False):
        self.value = value
        self.fail = fail

    async def execute(self, _statement):
        if self.fail:
            raise OSError("database unavailable")
        return FakeScalarResult(self.value)


class PGVectorSchemaReadinessTest(unittest.IsolatedAsyncioTestCase):
    async def test_schema_readiness_returns_database_value(self) -> None:
        self.assertTrue(await _pgvector_chunk_schema_ready(FakeSchemaSession(True)))
        self.assertFalse(await _pgvector_chunk_schema_ready(FakeSchemaSession(False)))

    async def test_schema_readiness_fails_closed(self) -> None:
        self.assertFalse(await _pgvector_chunk_schema_ready(FakeSchemaSession(fail=True)))


if __name__ == "__main__":
    unittest.main()
