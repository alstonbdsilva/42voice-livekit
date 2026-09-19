from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Raw SQL / explicit Alembic migrations are used rather than declarative metadata
target_metadata = None


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            # Ensure voice-agent root is in sys.path for config import
            here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if here not in sys.path:
                sys.path.insert(0, here)
            from config import get_settings
            settings = get_settings()
            if settings.pghost and settings.pgdatabase:
                user = quote_plus(settings.pguser) if settings.pguser else ""
                password = quote_plus(settings.pgpassword) if settings.pgpassword else ""
                auth = f"{user}:{password}@" if (user or password) else ""
                url = f"postgresql+asyncpg://{auth}{settings.pghost}:{settings.pgport}/{settings.pgdatabase}"
        except Exception:
            pass

    if not url:
        pghost = os.getenv("PGHOST")
        pgport = os.getenv("PGPORT", "5432")
        pgdatabase = os.getenv("PGDATABASE")
        pguser = os.getenv("PGUSER")
        pgpassword = os.getenv("PGPASSWORD")
        if pghost and pgdatabase:
            user = quote_plus(pguser) if pguser else ""
            password = quote_plus(pgpassword) if pgpassword else ""
            auth = f"{user}:{password}@" if (user or password) else ""
            url = f"postgresql+asyncpg://{auth}{pghost}:{pgport}/{pgdatabase}"

    if not url:
        raise RuntimeError(
            "DATABASE_URL or PGHOST/PGDATABASE environment settings are required for Alembic migrations"
        )

    # Normalize only when required by the actual application URL
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    return url


def run_migrations_offline() -> None:
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section) or {}
    db_url = get_database_url()
    section["sqlalchemy.url"] = db_url

    connect_args = {}
    if "supabase.co" in db_url:
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
