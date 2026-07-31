"""
Persistence layer tests — SQLAlchemy models, config, and repositories.

All tests run against an in-memory SQLite database so no file I/O
or external database is required.
"""
import os
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.pool import StaticPool

import src.persistence.config as db_config
from src.persistence.models import Base, Session, Query, AnalysisResult
from src.persistence.repositories import (
    create_session,
    save_query,
    save_result,
    get_results_by_session,
    get_result_by_id,
    get_session_summary,
    persist_query_result,
    get_all_sessions,
    is_persistence_available,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def engine():
    """In-memory SQLite engine with tables created."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def db(engine, monkeypatch):
    """Database session wired into the persistence module's singleton."""
    monkeypatch.setattr(db_config, "_engine", engine)
    session = SASession(engine, expire_on_commit=False)
    yield session
    session.rollback()
    session.close()


# ── Model tests ───────────────────────────────────────────────────


class TestModels:
    def test_session_repr(self, db):
        record = Session(session_id="abc-123", user_id="user1")
        db.add(record)
        db.flush()
        assert "abc-123" in repr(record)
        assert "user1" in repr(record)

    def test_query_repr(self, db):
        _make_session(db, "s1")
        q = Query(session_id="s1", query_text="test", intent="oee")
        db.add(q)
        db.flush()
        assert "oee" in repr(q)
        assert "s1" in repr(q)

    def test_analysis_result_repr(self, db):
        _make_session(db, "s2")
        q = Query(session_id="s2", query_text="q", intent="cost")
        db.add(q)
        db.flush()
        r = AnalysisResult(query_id=q.id, intent="cost", response="ok")
        db.add(r)
        db.flush()
        assert "cost" in repr(r)
        assert str(q.id) in repr(r)

    def test_session_cascade_deletes_queries(self, db):
        _make_session(db, "s3")
        q = Query(session_id="s3", query_text="q", intent="oee")
        db.add(q)
        db.flush()
        db.delete(db.query(Session).filter_by(session_id="s3").first())
        db.commit()
        assert db.query(Query).filter_by(session_id="s3").count() == 0


# ── Config tests ──────────────────────────────────────────────────


class TestConfig:
    def test_default_url_is_sqlite(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        url = db_config.get_url()
        assert "sqlite" in url

    def test_custom_url_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        assert db_config.get_url() == "sqlite:///test.db"

    def test_init_db_returns_true_with_engine(self, monkeypatch, engine):
        monkeypatch.setattr(db_config, "_engine", engine)
        result = db_config.init_db()
        assert result is True

    def test_init_db_returns_false_when_off(self, monkeypatch):
        monkeypatch.setattr(db_config, "_engine", None)
        monkeypatch.setenv("DATABASE_URL", "off")
        result = db_config.init_db()
        assert result is False


# ── Repository tests ──────────────────────────────────────────────


class TestSessionRepository:
    def test_create_session_new(self, db):
        record = create_session("sess-001", user_id="alice", session=db)
        db.commit()
        assert record.session_id == "sess-001"
        assert record.user_id == "alice"

    def test_create_session_idempotent(self, db):
        s1 = create_session("sess-002", session=db)
        db.commit()
        s2 = create_session("sess-002", session=db)
        db.commit()
        assert s1.id == s2.id

    def test_create_session_no_user_id(self, db):
        record = create_session("sess-003", session=db)
        db.commit()
        assert record.user_id is None

    def test_get_all_sessions_returns_list(self, db, monkeypatch):
        monkeypatch.setattr(db_config, "_engine", db.bind)
        create_session("s-a", session=db)
        create_session("s-b", session=db)
        db.commit()
        sessions = get_all_sessions(session=db)
        ids = [s.session_id for s in sessions]
        assert "s-a" in ids
        assert "s-b" in ids


class TestQueryRepository:
    def test_save_query_creates_record(self, db):
        _make_session(db, "sq-1")
        q = save_query("sq-1", "What is OEE?", intent="oee", confidence=0.9, session=db)
        db.commit()
        assert q.id is not None
        assert q.intent == "oee"
        assert q.query_text == "What is OEE?"

    def test_confidence_stored_as_integer(self, db):
        _make_session(db, "sq-2")
        q = save_query("sq-2", "costs?", intent="cost", confidence=0.75, session=db)
        db.commit()
        assert q.confidence == 75

    def test_save_query_null_confidence(self, db):
        _make_session(db, "sq-3")
        q = save_query("sq-3", "trend?", intent="trend", confidence=None, session=db)
        db.commit()
        assert q.confidence is None

    def test_get_results_by_session_ordered_desc(self, db):
        _make_session(db, "sq-4")
        q1 = save_query("sq-4", "first", intent="oee", session=db)
        q2 = save_query("sq-4", "second", intent="cost", session=db)
        db.commit()
        results = get_results_by_session("sq-4", session=db)
        assert len(results) == 2
        assert results[0].id == q2.id  # most recent first

    def test_get_results_by_session_empty(self, db):
        _make_session(db, "sq-5")
        results = get_results_by_session("sq-5", session=db)
        assert results == []


class TestResultRepository:
    def test_save_result_creates_record(self, db):
        _make_session(db, "sr-1")
        q = save_query("sr-1", "oee?", intent="oee", session=db)
        db.commit()
        r = save_result(q.id, intent="oee", response="OEE is 86%", session=db)
        db.commit()
        assert r.id is not None
        assert r.response == "OEE is 86%"

    def test_save_result_with_metadata(self, db):
        _make_session(db, "sr-2")
        q = save_query("sr-2", "q", intent="oee", session=db)
        db.commit()
        meta = {"oee_score": 86.1, "rating": "good"}
        r = save_result(q.id, metadata=meta, session=db)
        db.commit()
        # Expire the object to force a DB round-trip on next access
        db.expire(r)
        fetched = get_result_by_id(r.id, session=db)
        assert fetched.analysis_metadata["oee_score"] == 86.1
        assert fetched.analysis_metadata["rating"] == "good"

    def test_get_result_by_id_returns_none_for_missing(self, db):
        result = get_result_by_id(99999, session=db)
        assert result is None


class TestSessionSummary:
    def test_summary_empty_session(self, db):
        _make_session(db, "sum-1")
        db.commit()
        summary = get_session_summary("sum-1", session=db)
        assert summary["query_count"] == 0
        assert summary["intents"] == []
        assert summary["first_query"] is None

    def test_summary_with_queries(self, db):
        _make_session(db, "sum-2")
        save_query("sum-2", "oee?", intent="oee", session=db)
        save_query("sum-2", "cost?", intent="cost", session=db)
        db.commit()
        summary = get_session_summary("sum-2", session=db)
        assert summary["query_count"] == 2
        assert set(summary["intents"]) == {"oee", "cost"}
        assert summary["first_query"] is not None
        assert summary["last_query"] is not None


class TestPersistPipeline:
    def test_persist_query_result_full_pipeline(self, db):
        _make_session(db, "pipe-1")
        ids = persist_query_result(
            session_id="pipe-1",
            query_text="full pipeline test",
            intent="oee",
            confidence=0.95,
            response="All good",
            metadata={"score": 90},
            session=db,
        )
        db.commit()
        assert "session_id" in ids
        assert "query_id" in ids
        assert "result_id" in ids

    def test_persist_query_result_creates_session_if_missing(self, db):
        ids = persist_query_result(
            session_id="pipe-auto",
            query_text="auto session",
            intent="trend",
            session=db,
        )
        db.commit()
        sess = db.query(Session).filter_by(session_id="pipe-auto").first()
        assert sess is not None

    def test_is_persistence_available_with_engine(self, monkeypatch, engine):
        monkeypatch.setattr(db_config, "_engine", engine)
        assert is_persistence_available() is True

    def test_is_persistence_available_no_engine(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "off")
        monkeypatch.setattr(db_config, "_engine", None)
        assert is_persistence_available() is False


# ── Helpers ───────────────────────────────────────────────────────


def _make_session(db: SASession, session_id: str) -> Session:
    """Create and flush a session record."""
    existing = db.query(Session).filter_by(session_id=session_id).first()
    if existing:
        return existing
    record = Session(session_id=session_id)
    db.add(record)
    db.flush()
    return record
