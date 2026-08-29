import asyncio
import os
import sys
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, os.getcwd())

from bot.models import Base  # noqa: E402

config = context.config


def get_database_url() -> str:
    """Get DATABASE_URL, with a fallback to Railway/Postgres PG* variables."""
    db_url = os.getenv("DATABASE_URL", "").strip()

    if not db_url:
        host = os.getenv("PGHOST", "").strip()
        port = os.getenv("PGPORT", "5432").strip()
        user = os.getenv("PGUSER", "").strip()
        password = os.getenv("PGPASSWORD", "")
        database = os.getenv("PGDATABASE", "").strip()

        if host and user and database:
            db_url = (
                f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(password)}"
                f"@{host}:{port}/{quote_plus(database)}"
            )

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is empty. In Railway, connect PostgreSQL to this service "
            "or add DATABASE_URL in Variables."
        )

    return db_url


db_url = get_database_url()
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
