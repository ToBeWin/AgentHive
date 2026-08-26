from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database import engine


@dataclass(frozen=True)
class MigrationStatus:
    current_revision: str | None
    head_revision: str | None
    is_current: bool
    version_table_present: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_revision": self.current_revision,
            "head_revision": self.head_revision,
            "is_current": self.is_current,
            "version_table_present": self.version_table_present,
        }


async def get_migration_status(db_engine: AsyncEngine = engine) -> MigrationStatus:
    head_revision = get_migration_head()
    current_revision = await get_current_revision(db_engine)
    return MigrationStatus(
        current_revision=current_revision,
        head_revision=head_revision,
        is_current=bool(current_revision and head_revision and current_revision == head_revision),
        version_table_present=current_revision is not None,
    )


def get_migration_head() -> str | None:
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    if not heads:
        return None
    if len(heads) > 1:
        return ",".join(sorted(heads))
    return heads[0]


async def get_current_revision(db_engine: AsyncEngine = engine) -> str | None:
    try:
        async with db_engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT to_regclass('public.alembic_version') IS NOT NULL
                    """
                )
            )
            if not bool(result.scalar()):
                return None
            version_result = await connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            value = version_result.scalar_one_or_none()
            return str(value) if value else None
    except Exception:
        return None


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    return config
