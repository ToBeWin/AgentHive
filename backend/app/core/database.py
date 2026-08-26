from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def check_database_health() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return {"status": "unhealthy"}
    return {"status": "healthy"}
