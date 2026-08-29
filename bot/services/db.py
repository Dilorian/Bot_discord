from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger("bot.db")


def get_database_url() -> str:
    """Return an async SQLAlchemy URL from Railway/Postgres environment variables."""
    url = os.getenv("DATABASE_URL", "").strip()

    # Railway normally provides DATABASE_URL. If it is not linked to the service,
    # fall back to the standard PostgreSQL PG* variables.
    if not url:
        host = os.getenv("PGHOST", "").strip()
        port = os.getenv("PGPORT", "5432").strip()
        user = os.getenv("PGUSER", "").strip()
        password = os.getenv("PGPASSWORD", "")
        database = os.getenv("PGDATABASE", "").strip()

        if host and user and database:
            url = (
                f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(password)}"
                f"@{host}:{port}/{quote_plus(database)}"
            )

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Connect a PostgreSQL service to Railway "
            "or add DATABASE_URL to the bot service Variables."
        )

    return url


DATABASE_URL = get_database_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def check_db_connection() -> bool:
    """Health check подключения к БД."""
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Не удалось подключиться к базе данных")
        return False
