"""SQLAlchemy async engine and session factory for Supabase PostgreSQL."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .base import Base  # noqa: F401 — re-exported for convenience

# Use pooler URL (port 6543) at runtime for multi-worker compatibility.
# Alembic migrations use DATABASE_URL_DIRECT (port 5432, sync driver).
DATABASE_URL = os.getenv("DATABASE_URL", "")

_DB_CONFIGURED = bool(DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL or "postgresql+asyncpg://placeholder/placeholder",
    pool_size=5,
    max_overflow=10,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
