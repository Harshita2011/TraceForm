"""
# §5 Database Session — async SQLAlchemy session factory.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from db.connection import connection_settings

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./traceform.db")

connection_url, connect_args = connection_settings(DATABASE_URL)

engine = create_async_engine(
    connection_url,
    echo=os.getenv("TRACEFORM_SQL_ECHO", "false").lower() == "true",
    pool_pre_ping=True if "sqlite" not in DATABASE_URL else False,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
