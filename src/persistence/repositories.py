"""
Godínez IndustrialEngineer — Repository Pattern

Clean interface for all database operations.
Each method is self-contained and can be unit-tested independently.
Designed for swap-ability — the API doesn't care what backend stores data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session as SASession

from .models import Session, Query, AnalysisResult
from .config import get_db_session


def _session_or_default(fn):
    """Decorator: provide a session if none given, auto-cleanup on exit."""

    def wrapper(*args, **kwargs):
        provided_session = kwargs.pop("session", None)
        need_cleanup = provided_session is None
        session = provided_session or get_db_session()
        try:
            result = fn(*args, session=session, **kwargs)
            if need_cleanup and session is not None:
                session.commit()
            return result
        except Exception:
            if need_cleanup and session is not None:
                session.rollback()
            raise
        finally:
            if need_cleanup and session is not None:
                session.close()

    return wrapper


# ── Session Repository ────────────────────────────────────────────


@_session_or_default
def create_session(
    session_id: str,
    user_id: Optional[str] = None,
    *,
    session: SASession = None,
) -> Session:
    """
    Create a new session record. Returns existing if session_id already exists.

    Idempotent — safe to call multiple times with the same session_id.
    """
    # Check if session already exists
    existing = session.query(Session).filter_by(session_id=session_id).first()
    if existing:
        return existing

    record = Session(session_id=session_id, user_id=user_id)
    session.add(record)
    session.flush()
    return record


@_session_or_default
def get_all_sessions(
    *,
    session: SASession = None,
) -> list[Session]:
    """
    Get all sessions sorted by most recent activity.

    Returns a list of Session objects with their queries eagerly loaded.
    """
    from sqlalchemy import desc

    sessions = (
        session.query(Session)
        .order_by(desc(Session.updated_at))
        .limit(100)
        .all()
    )
    return sessions


# ── Query Repository ──────────────────────────────────────────────


def save_query(
    session_id: str,
    query_text: str,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    *,
    session: SASession = None,
) -> Query:
    """
    Save a query record within a session.

    Args:
        session_id: The session this query belongs to
        query_text: The original query text
        intent: The classified intent (oee, bottleneck, cost, etc.)
        confidence: Classification confidence (0.0–1.0, stored as 0–100 integer)

    Returns:
        The created Query record
    """
    confidence_int = int(confidence * 100) if confidence is not None else None

    record = Query(
        session_id=session_id,
        query_text=query_text,
        intent=intent,
        confidence=confidence_int,
        timestamp=datetime.now(timezone.utc),
    )
    session.add(record)
    session.flush()
    return record


def get_results_by_session(
    session_id: str,
    *,
    session: SASession = None,
) -> list[Query]:
    """
    Get all queries for a session, ordered by timestamp.

    Each query has its result eagerly loaded (if any).

    Returns:
        List of Query objects with result relationships loaded
    """
    from sqlalchemy import desc

    queries = (
        session.query(Query)
        .filter_by(session_id=session_id)
        .order_by(desc(Query.timestamp))
        .all()
    )
    return queries


def get_query_by_id(
    query_id: int,
    *,
    session: SASession = None,
) -> Optional[Query]:
    """Get a single query by ID (with result eagerly loaded)."""
    return (
        session.query(Query)
        .options(
            # Eagerly load the single result relationship
        )
        .filter(Query.id == query_id)
        .first()
    )


# ── AnalysisResult Repository ─────────────────────────────────────


@_session_or_default
def save_result(
    query_id: int,
    intent: Optional[str] = None,
    response: Optional[str] = None,
    metadata: Optional[dict] = None,
    charts: Optional[list] = None,
    errors: Optional[list] = None,
    *,
    session: SASession = None,
) -> AnalysisResult:
    """
    Save an analysis result for a query.

    This is the main persistence point — called after workflow completion.

    Args:
        query_id: The query this result belongs to
        intent: The intent that was analyzed
        response: The generated response text
        metadata: Full metadata dict (execution metrics, OEE scores, etc.)
        charts: Base64-encoded chart data (if any)
        errors: Any errors that occurred during analysis

    Returns:
        The created AnalysisResult record
    """
    record = AnalysisResult(
        query_id=query_id,
        intent=intent,
        response=response,
        analysis_metadata=metadata,
        charts=charts,
        errors=errors,
    )
    session.add(record)
    session.flush()
    return record


@_session_or_default
def get_result_by_id(
    result_id: int,
    *,
    session: SASession = None,
) -> Optional[AnalysisResult]:
    """Get a single result by ID."""
    return session.query(AnalysisResult).filter_by(id=result_id).first()


# ── Bulk Operations ───────────────────────────────────────────────


@_session_or_default
def get_session_summary(
    session_id: str,
    *,
    session: SASession = None,
) -> dict:
    """
    Get a summary of a session — query count, intents, date range.

    Returns:
        Dict with query_count, intents (list), first_query, last_query
    """
    from sqlalchemy import func, desc, extract

    # Count queries
    count = session.query(func.count(Query.id)).filter_by(session_id=session_id).scalar()

    # Get distinct intents
    intents = (
        session.query(Query.intent)
        .filter_by(session_id=session_id)
        .filter(Query.intent.isnot(None))
        .distinct()
        .all()
    )
    intents = [i[0] for i in intents if i[0]]

    # Date range
    first_query = (
        session.query(Query.timestamp)
        .filter_by(session_id=session_id)
        .order_by(Query.timestamp)
        .first()
    )
    last_query = (
        session.query(Query.timestamp)
        .filter_by(session_id=session_id)
        .order_by(desc(Query.timestamp))
        .first()
    )

    return {
        "session_id": session_id,
        "query_count": count,
        "intents": intents,
        "first_query": first_query[0].isoformat() if first_query else None,
        "last_query": last_query[0].isoformat() if last_query else None,
    }


# ── Convenience: Full Persistence Pipeline ────────────────────────


def persist_query_result(
    session_id: str,
    query_text: str,
    user_id: Optional[str] = None,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    response: Optional[str] = None,
    metadata: Optional[dict] = None,
    charts: Optional[list] = None,
    errors: Optional[list] = None,
    *,
    session: SASession = None,
) -> dict:
    """
    Full persistence pipeline in one call:
    1. Create/ensure session exists
    2. Save the query record
    3. Save the analysis result

    This is the main function called from the API after query processing.

    Returns:
        Dict with query_id, result_id, and session_id
    """
    # Ensure session exists
    sess = create_session(session_id, user_id, session=session)

    # Save query
    query = save_query(
        session_id=session_id,
        query_text=query_text,
        intent=intent,
        confidence=confidence,
        session=session,
    )

    # Save result
    result = save_result(
        query_id=query.id,
        intent=intent,
        response=response,
        metadata=metadata,
        charts=charts,
        errors=errors,
        session=session,
    )

    return {
        "session_id": session_id,
        "query_id": query.id,
        "result_id": result.id,
    }


# ── Error Handling ────────────────────────────────────────────────


def is_persistence_available() -> bool:
    """Check if persistence is enabled and the database is accessible."""
    from .config import get_cached_engine
    from .models import Base

    engine = get_cached_engine()
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            return True
    except Exception:
        return False


__all__ = [
    "create_session",
    "save_query",
    "save_result",
    "get_results_by_session",
    "get_query_by_id",
    "get_result_by_id",
    "get_session_summary",
    "persist_query_result",
    "get_all_sessions",
    "is_persistence_available",
]
