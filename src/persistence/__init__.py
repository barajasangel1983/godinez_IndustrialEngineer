"""
Godínez IndustrialEngineer — Persistence Layer (Phase 6.0)

Database models, repository pattern, and session management.
Configurable via DATABASE_URL env var:
  - SQLite (default):     postgresql://localhost/godinez (dev)
  - PostgreSQL (prod):    postgresql://user:pass@host:5432/godinez
"""

from .config import get_engine, get_session_factory, init_db, get_db_session, get_url
from .models import Session, Query, AnalysisResult
from .repositories import (
    create_session,
    save_query,
    save_result,
    get_results_by_session,
    get_result_by_id,
    get_all_sessions,
    is_persistence_available,
    get_session_summary,
    persist_query_result,
)

__all__ = [
    "get_engine",
    "get_session_factory",
    "init_db",
    "get_db_session",
    "get_url",
    "Session",
    "Query",
    "AnalysisResult",
    "create_session",
    "save_query",
    "save_result",
    "get_results_by_session",
    "get_result_by_id",
    "get_all_sessions",
    "is_persistence_available",
    "get_session_summary",
    "persist_query_result",
]
