"""
Godínez IndustrialEngineer — FastAPI REST API

Phase 2: Provides HTTP endpoints for the same workflow logic
as the CLI entry point.
Phase 6.0: PostgreSQL persistence layer with results history.

Usage:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /api/query           — Run analysis on a natural language query
    GET  /api/results/{sid}   — Retrieve all queries for a session
    GET  /health              — Health check
"""

import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load .env before importing workflow (needs LANGSMITH_API_KEY, etc.)
from dotenv import load_dotenv
load_dotenv()

from src.graph import build_workflow

# ── Persistence (optional, enabled via DATABASE_URL env var) ────
from src.persistence import init_db, is_persistence_available
from src.persistence.repositories import persist_query_result, get_session_summary
from src.persistence.config import get_db_session, get_url
from src.persistence.models import Session, Query, AnalysisResult

# ── Lifespan: Initialize Database ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        print(f"⚠️ Persistence init failed (database may not be configured): {e}")
    yield


# ── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="Godínez IndustrialEngineer",
    description="AI-powered manufacturing analysis agent — REST API",
    version="0.6.0",
    lifespan=lifespan,
)

# CORS (allow browser/frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ──────────────────────────────────
class QueryRequest(BaseModel):
    """Request body for /api/query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query (e.g., \"What's our OEE today?\")",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user identifier for tracking/analytics",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for observability tracing",
    )
    enable_tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing (requires LANGSMITH_API_KEY)",
    )


class QueryResponse(BaseModel):
    """Response body for /api/query."""

    query: str
    response: str
    intent: str
    session_id: str
    user_id: Optional[str] = None
    metadata: dict = {}
    execution_summary: dict = {}
    charts: Optional[list[dict]] = None  # Base64-encoded chart data for trend analysis
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    tracing_enabled: bool


class ResultItem(BaseModel):
    """A single query result within a session."""

    query_id: int
    query_text: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: Optional[str] = None
    response: Optional[str] = None
    metadata: Optional[dict] = None
    charts: Optional[list] = None
    errors: Optional[list] = None
    session_id: str


class SessionSummary(BaseModel):
    """Summary of a session's queries."""

    session_id: str
    query_count: int
    intents: list[str]
    first_query: Optional[str] = None
    last_query: Optional[str] = None
    queries: list[ResultItem]


class PersistenceStatus(BaseModel):
    """Status of the persistence layer."""

    enabled: bool
    database_type: Optional[str] = None


# ── Core Logic ───────────────────────────────────────────────
def _run_query(
    query: str,
    session_id: str,
    user_id: Optional[str] = None,
    enable_tracing: bool = False,
) -> QueryResponse:
    """
    Run a single query through the workflow and return a structured response.

    This reuses the same graph pipeline as the CLI — just wrapped in
    FastAPI I/O.
    """
    try:
        # Build and compile the workflow with observability
        workflow, obs_context = build_workflow(
            session_id=session_id,
            enable_tracing=enable_tracing,
        )
        compiled = workflow.compile()

        # Initial state
        initial_state = {
            "query": query,
            "messages": [{"role": "user", "content": query}],
        }

        # Run the workflow
        result = compiled.invoke(initial_state)

        # Extract metrics and metadata
        summary = obs_context["metrics"].get_summary()
        metadata = result.get("metadata", {})
        intent = result.get("intent") or metadata.get("intent", "unknown")

        return QueryResponse(
            query=query,
            response=result.get("response", "No response generated."),
            intent=intent,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata,
            execution_summary=summary,
            charts=result.get("charts"),  # Include base64 chart data for trend analysis
            success=True,
        )

    except Exception as e:
        # Return structured error instead of 500
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "detail": "An error occurred while processing your query.",
            },
        )


# ── Routes ───────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Health check — returns service status and configuration."""
    from src.observability.tracing import _is_tracing_enabled

    return HealthResponse(
        status="healthy",
        version="0.6.0",
        tracing_enabled=_is_tracing_enabled(),
    )


# ── POST /api/query with Persistence ─────────────────────────────


@app.post(
    "/api/query",
    response_model=QueryResponse,
    responses={500: {"model": ErrorResponse}},
    tags=["Analysis"],
)
def query_api(request: QueryRequest):
    """
    Run analysis on a natural language query.

    Same logic as `python main.py "query"` — the workflow runs
    intake → classify → router → analyze → response.

    After completion, the result is persisted to the database
    if persistence is configured (DATABASE_URL env var).

    Returns JSON with the response text, detected intent, metadata,
    and execution summary.
    """
    # Generate or accept session ID
    session_id = request.session_id or str(uuid.uuid4())

    # Run the workflow
    response = _run_query(
        query=request.query,
        session_id=session_id,
        user_id=request.user_id,
        enable_tracing=request.enable_tracing,
    )

    # Persist the result if persistence is available
    if is_persistence_available():
        try:
            persist_query_result(
                session_id=session_id,
                query_text=request.query,
                user_id=request.user_id,
                intent=response.intent,
                confidence=response.metadata.get("classification_confidence"),
                response=response.response,
                metadata={
                    k: v for k, v in response.metadata.items()
                    if k != "classification_confidence"
                },
                charts=response.charts,
                errors=[],
            )
        except Exception as e:
            # Non-fatal — don't break the API if persistence fails
            print(f"⚠️ Persistence save failed (result still served): {e}")

    return response


# ── GET /api/results/{session_id} ──────────────────────────────


@app.get(
    "/api/results/{session_id}",
    response_model=SessionSummary,
    responses={404: {"model": ErrorResponse}},
    tags=["Results"],
)
def get_results(session_id: str):
    """
    Retrieve all queries and results for a session.

    Returns queries sorted by timestamp (most recent first),
    each with its intent, response, and metadata.
    """
    if not is_persistence_available():
        return {
            "session_id": session_id,
            "query_count": 0,
            "intents": [],
            "first_query": None,
            "last_query": None,
            "queries": [],
        }

    try:
        from sqlalchemy import desc

        db_session = get_db_session()
        if db_session is None:
            raise HTTPException(status_code=503, detail="Database unavailable")

        # Get all queries for this session
        queries = (
            db_session.query(Query)
            .filter_by(session_id=session_id)
            .order_by(desc(Query.timestamp))
            .all()
        )

        # Get summary (decorator handles session injection)
        summary = get_session_summary(session_id)
        summary_data = summary

        db_session.close()

        # Map queries to ResultItem format
        result_items = [
            ResultItem(
                query_id=q.id,
                query_text=q.query_text,
                intent=q.intent,
                confidence=q.confidence / 100 if q.confidence else None,
                timestamp=q.timestamp.isoformat() if q.timestamp else None,
                session_id=q.session_id,
                response=q.result.response if q.result else None,
                metadata=q.result.analysis_metadata if q.result else None,
                charts=q.result.charts if q.result else None,
                errors=q.result.errors if q.result else None,
            )
            for q in queries
        ]

        return SessionSummary(
            session_id=session_id,
            query_count=summary_data["query_count"],
            intents=summary_data["intents"],
            first_query=summary_data["first_query"],
            last_query=summary_data["last_query"],
            queries=result_items,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e), "detail": "Failed to fetch results"},
        )


# ── GET /api/persistence/status ────────────────────────────────


@app.get(
    "/api/persistence/status",
    response_model=PersistenceStatus,
    tags=["System"],
)
def persistence_status():
    """Check if the persistence layer is configured and available."""
    url = _get_db_url()
    enabled = url != "off"
    db_type = "sqlite" if url.startswith("sqlite") else url.split(":")[0] if ":" in url else "unknown"

    return PersistenceStatus(
        enabled=enabled,
        database_type=db_type,
    )


# ── Helper functions ───────────────────────────────────────────


def _get_db_url():
    """Get the current database URL."""
    return get_url()


# ── Standalone Run ───────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
