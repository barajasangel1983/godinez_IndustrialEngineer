"""
Godínez IndustrialEngineer — Database models (SQLAlchemy 2.0)

Tables:
  - session:    User session groupings (optional user_id)
  - query:      Individual queries within a session
  - result:     Analysis results linked to a query
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── Session ──────────────────────────────────────────────────────


class Session(Base):
    """Tracks a user session group — may contain multiple queries."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(128), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    queries = relationship("Query", back_populates="session", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Session id={self.id} session_id={self.session_id} user_id={self.user_id}>"


# ── Query ────────────────────────────────────────────────────────


class Query(Base):
    """An individual query within a session — stores intent, confidence, etc."""

    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(64),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True, index=True)
    confidence = Column(Integer, nullable=True)  # Stored as 0-100 (int) to avoid FLOAT precision issues
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="queries")
    result = relationship("AnalysisResult", back_populates="query", uselist=False, lazy="joined")

    __table_args__ = (
        Index("ix_queries_session_timestamp", "session_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Query id={self.id} session={self.session_id} intent={self.intent}>"


# ── AnalysisResult ───────────────────────────────────────────────


class AnalysisResult(Base):
    """Stores the full analysis result for a query — response, metadata, charts."""

    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(
        Integer,
        ForeignKey("queries.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    intent = Column(String(64), nullable=True)
    response = Column(Text, nullable=True)
    analysis_metadata = Column("metadata", JSON, nullable=True)  # DB col "metadata"; attr avoids Base.metadata conflict
    charts = Column(JSON, nullable=True)  # Base64-encoded chart data
    errors = Column(JSON, nullable=True)  # Accumulated error messages

    # Relationships
    query = relationship("Query", back_populates="result")

    __table_args__ = (
        Index("ix_results_intent", "intent"),
    )

    def __repr__(self) -> str:
        return f"<Result id={self.id} query_id={self.query_id} intent={self.intent}>"


# ── Convenience: Export Base for Alembic autogeneration ──────────

__all__ = ["Base", "Session", "Query", "AnalysisResult"]
