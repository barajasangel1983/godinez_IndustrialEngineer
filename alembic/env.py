"""
Alembic environment configuration for Godínez IndustrialEngineer.

This module is invoked by Alembic to run migrations.
It reads the DATABASE_URL from environment or uses the default SQLite.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ── Import the project's Base and models ──────────────────────

# Add project root to path so we can import models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.persistence.models import Base  # noqa: E402


# ── Alembic Config object ────────────────────────────────────

config = context.config

# Override sqlalchemy.url from environment, with fallback
db_url = os.environ.get("DATABASE_URL", "sqlite:///data/godinez.db")
config.set_main_option("sqlalchemy.url", db_url)

# ── Interpret the config file for Python logging ─────────────

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata for autogenerate ─────────────────────────

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Connects to the actual database and executes migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite compatibility
        )

        with context.begin_transaction():
            context.run_migrations()


# ── Run migrations ───────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
