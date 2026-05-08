"""Alembic migration environment.

Reads DATABASE_URL_DIRECT from the environment for migrations.
Uses a synchronous psycopg2 driver (port 5432, not the pooler).
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Make backend-py/src importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.database.base import Base  # noqa: E402
import src.database.models  # noqa: F401, E402 — registers all models on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Read directly from env — do NOT use config.set_main_option() because
# configparser treats % as an interpolation character, which breaks passwords
# that contain %, |, ^ or other special characters.
DATABASE_URL_DIRECT = os.environ.get("DATABASE_URL_DIRECT", "")


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to the database."""
    context.configure(
        url=DATABASE_URL_DIRECT,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and run migrations."""
    if not DATABASE_URL_DIRECT:
        raise RuntimeError(
            "DATABASE_URL_DIRECT is not set. "
            "Add it to backend-py/.env (port 5432, psycopg2 driver)."
        )

    connectable = create_engine(DATABASE_URL_DIRECT, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
