import asyncio
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects.postgresql import insert

from app import models  # noqa: F401
from app.core.database import engine
from app.models.agent_module import AgentModule
from app.services.agent_module_service import list_module_definitions
from app.services.migration_service import get_migration_status


def main() -> None:
    _run_migrations()
    asyncio.run(_seed_and_verify())


async def _seed_and_verify() -> None:
    async with engine.begin() as connection:
        await _seed_agent_modules(connection)
    status = await get_migration_status(engine)

    await engine.dispose()
    if not status.is_current:
        raise RuntimeError(
            f"AgentHive database migrations are not current: "
            f"{status.current_revision} != {status.head_revision}"
        )
    print("AgentHive database migrated and official Agent modules seeded.")


def _run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(config, "head")


async def _seed_agent_modules(connection) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        {
            "module_key": definition.id,
            "name": definition.name,
            "category": definition.category,
            "priority": definition.priority,
            "description": definition.description,
            "version": definition.version,
            "manifest": {
                "scenario": definition.scenario,
                "capabilities": definition.capabilities,
                "default_agent_slug": definition.default_agent_slug,
                "required_features": definition.required_features,
                "dependencies": definition.dependencies,
                "recommended_model_capabilities": definition.recommended_model_capabilities or [],
                "recommended_orchestration_runtimes": definition.recommended_orchestration_runtimes
                or [],
                "default_config": definition.default_config or {},
            },
            "is_official": True,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        for definition in list_module_definitions()
    ]
    if not rows:
        return

    statement = insert(AgentModule).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[AgentModule.module_key],
        set_={
            "name": statement.excluded.name,
            "category": statement.excluded.category,
            "priority": statement.excluded.priority,
            "description": statement.excluded.description,
            "version": statement.excluded.version,
            "manifest": statement.excluded.manifest,
            "is_active": statement.excluded.is_active,
            "updated_at": now,
        },
    )
    await connection.execute(statement)


if __name__ == "__main__":
    main()
