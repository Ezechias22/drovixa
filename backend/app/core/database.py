from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

if settings.APP_ENV == "testing":
    engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, poolclass=StaticPool)
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT_SECONDS,
        connect_args={
            "server_settings": {
                "statement_timeout": str(settings.DATABASE_STATEMENT_TIMEOUT_MS),
                "application_name": "drovixa-api",
            }
        },
    )
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_database() -> None:
    await engine.dispose()
