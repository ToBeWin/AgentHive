import asyncio

from sqlalchemy import text
from sqlmodel import select

from app.core.database import AsyncSessionLocal, engine
from app.models.agent_module import AgentModule
from app.services.agent_module_service import list_module_definitions
from app.services.migration_service import get_migration_status
from app.services.schema_readiness import expected_media_runtime_indexes, missing_media_runtime_indexes


async def main() -> None:
    migration_status = await get_migration_status(engine)
    try:
        async with AsyncSessionLocal() as session:
            module_keys = set(
                (
                    await session.execute(
                        select(AgentModule.module_key).where(AgentModule.is_official.is_(True))
                    )
                )
                .scalars()
                .all()
            )
            pgvector_installed = bool(
                (
                    await session.execute(
                        text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                    )
                ).scalar_one()
            )
            chunk_embedding_columns = int(
                (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.columns
                            WHERE table_name = 'knowledge_chunks'
                              AND column_name IN ('embedding', 'embedding_dimensions', 'embedding_model_key')
                            """
                        )
                    )
                ).scalar_one()
                or 0
            )
            chunk_embedding_index = bool(
                (
                    await session.execute(
                        text(
                            """
                            SELECT EXISTS (
                                SELECT 1
                                FROM pg_indexes
                                WHERE tablename = 'knowledge_chunks'
                                  AND indexname = 'ix_knowledge_chunks_embedding_cosine'
                            )
                            """
                        )
                    )
                ).scalar_one()
            )
            media_index_rows = (
                (
                    await session.execute(
                        text(
                            """
                            SELECT indexname
                            FROM pg_indexes
                            WHERE tablename = 'media_generation_jobs'
                            """
                        )
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        print("AgentHive database status")
        print(f"  current_revision: {migration_status.current_revision}")
        print(f"  head_revision:    {migration_status.head_revision}")
        print(f"  migrations_head:  {migration_status.is_current}")
        raise SystemExit(f"Database check failed: {exc.__class__.__name__}: {exc}") from exc

    expected_module_keys = expected_official_module_keys()
    missing_module_keys = missing_official_module_keys(module_keys, expected_module_keys)
    extra_module_keys = sorted(module_keys - expected_module_keys)
    missing_media_indexes = missing_media_runtime_indexes(set(media_index_rows))
    print("AgentHive database status")
    print(f"  current_revision: {migration_status.current_revision}")
    print(f"  head_revision:    {migration_status.head_revision}")
    print(f"  migrations_head:  {migration_status.is_current}")
    print(f"  official_modules: {len(module_keys)}/{len(expected_module_keys)}")
    if missing_module_keys:
        print(f"  missing_modules:  {', '.join(missing_module_keys)}")
    if extra_module_keys:
        print(f"  extra_modules:    {', '.join(extra_module_keys)}")
    print(f"  pgvector:         {pgvector_installed}")
    print(f"  chunk_vectors:    {chunk_embedding_columns}/3 columns, index={chunk_embedding_index}")
    print(
        "  media_indexes:    "
        f"{len(expected_media_runtime_indexes()) - len(missing_media_indexes)}/"
        f"{len(expected_media_runtime_indexes())}"
    )
    if missing_media_indexes:
        print(f"  missing_media_indexes: {', '.join(missing_media_indexes)}")

    if not migration_status.is_current:
        raise SystemExit("Database migrations are not at head.")
    if missing_module_keys:
        raise SystemExit("Official Agent modules are not fully seeded.")
    if not pgvector_installed:
        raise SystemExit("PostgreSQL pgvector extension is not installed.")
    if chunk_embedding_columns < 3 or not chunk_embedding_index:
        raise SystemExit("Knowledge chunk embedding schema is not ready.")
    if missing_media_indexes:
        raise SystemExit("Media generation runtime indexes are not ready.")


def expected_official_module_keys() -> set[str]:
    return {definition.id for definition in list_module_definitions()}


def missing_official_module_keys(
    module_keys: set[str],
    expected_module_keys: set[str] | None = None,
) -> list[str]:
    expected = expected_module_keys if expected_module_keys is not None else expected_official_module_keys()
    return sorted(expected - module_keys)


if __name__ == "__main__":
    asyncio.run(main())
