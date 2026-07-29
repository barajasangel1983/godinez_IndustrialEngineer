"""
Godínez IndustrialEngineer — FastAPI REST API

Phase 2: Provides HTTP endpoints for the same workflow logic
as the CLI entry point.

Usage:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /api/query  — Run analysis on a natural language query
    GET  /health     — Health check
"""

import os
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load .env before importing workflow (needs LANGSMITH_API_KEY, etc.)
from dotenv import load_dotenv
load_dotenv()

from src.graph import build_workflow

# ── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="Godínez IndustrialEngineer",
    description="AI-powered manufacturing analysis agent — REST API",
    version="0.6.0",
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

    Returns JSON with the response text, detected intent, metadata,
    and execution summary.
    """
    # Generate or accept session ID
    session_id = request.session_id or str(uuid.uuid4())

    return _run_query(
        query=request.query,
        session_id=session_id,
        user_id=request.user_id,
        enable_tracing=request.enable_tracing,
    )


# ── Standalone Run ───────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
