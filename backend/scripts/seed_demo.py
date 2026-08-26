import asyncio

from app import models  # noqa: F401
from app.core.database import AsyncSessionLocal, engine
from scripts.demo_seed.constants import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, DEMO_EMPLOYEE_EMAIL, DEMO_TENANT_SLUG
from scripts.demo_seed.core import seed_demo_data
from scripts.demo_seed.summary import DemoSeedSummary
from scripts.init_db import _run_migrations, _seed_agent_modules

__all__ = [
    "DEMO_ADMIN_EMAIL",
    "DEMO_ADMIN_PASSWORD",
    "DEMO_EMPLOYEE_EMAIL",
    "DEMO_TENANT_SLUG",
    "DemoSeedSummary",
    "seed_demo_data",
]


def main() -> None:
    _run_migrations()
    asyncio.run(_seed_demo())


async def _seed_demo() -> None:
    async with engine.begin() as connection:
        await _seed_agent_modules(connection)

    async with AsyncSessionLocal() as session:
        summary = await seed_demo_data(session)

    await engine.dispose()
    print(summary.to_message())


if __name__ == "__main__":
    main()
