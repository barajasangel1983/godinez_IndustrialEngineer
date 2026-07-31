"""
Godínez IndustrialEngineer — Database configuration loader

Reads DATABASE_URL from environment:
  - If set → uses that URL (any SQLAlchemy-compatible DB)
  - If not set → defaults to SQLite in the project's data/ directory

Returns:
  - get_engine():       Creates and returns a SQLAlchemy engine
  - get_session_factory(): Returns a sessionmaker bound to the engine
  - init_db():          Creates all tables (idempotent, safe to call at startup)
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SASession

# Default SQLite path in the project's data/ directory
_DB_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "godinez.db"
_DEFAULT_URL = f"sqlite:///{_DB_FILE}"

# Environment variable override
_ENV_VAR = "DATABASE_URL"


def _get_url() -> str:
    """Return the database URL from env or default to SQLite."""
    url = os.environ.get(_ENV_VAR, _DEFAULT_URL)
    # Ensure SQLite URLs use the correct prefix
    if url.startswith("sqlite:///") and not Path(url.replace("sqlite:///", "", 1)).exists():
        # Auto-create parent directory for SQLite
        db_path = url.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return url


def get_url() -> str:
    """Public getter for the database URL."""
    return _get_url()


def get_engine():
    """
    Create and return a SQLAlchemy engine.

    Returns None if persistence is disabled (DATABASE_URL=off).
    """
    url = _get_url()
    if url == "off":
        return None

    kwargs: dict = {"echo": os.environ.get("DATABASE_DEBUG", "").lower() == "true"}

    # SQLite-specific settings
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # Use WAL mode for better concurrent read performance
        kwargs["pool_pre_ping"] = True
    else:
        # PostgreSQL/MySQL — connection pooling
        kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "5"))
        kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
        kwargs["pool_timeout"] = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
        kwargs["pool_recycle"] = int(os.environ.get("DB_POOL_RECYCLE", "3600"))

    return create_engine(url, **kwargs)


# Cached engine singleton — created once, reused
_engine = None


def get_cached_engine():
    """Return a cached engine instance (creates on first call)."""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def get_session_factory():
    """Return a sessionmaker bound to the cached engine."""
    engine = get_cached_engine()
    if engine is None:
        return None
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """
    Create all tables defined in models.py.

    Idempotent — safe to call at startup multiple times.
    No-op if DATABASE_URL=off.

    Returns True if tables were created, False if persistence is disabled.
    """
    from .models import Base

    engine = get_cached_engine()
    if engine is None:
        return False

    # Create all tables (no-op if they already exist)
    Base.metadata.create_all(engine)
    return True


def get_db_session() -> SASession | None:
    """Create a new database session. Returns None if persistence is disabled."""
    engine = get_cached_engine()
    if engine is None:
        return None
    return SASession(engine, expire_on_commit=False)


# Expose for imports
__all__ = [
    "get_engine",
    "get_cached_engine",
    "get_session_factory",
    "init_db",
    "get_db_session",
    "get_url",
]
