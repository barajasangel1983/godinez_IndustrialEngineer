"""
Godínez IndustrialEngineer — State definition

Pydantic state that flows through the LangGraph workflow.
Starts minimal (Phase 0) and grows with each phase.
"""

from typing import TypedDict, Optional, List, Any
from datetime import datetime
from langgraph.graph import MessagesState


class GodinezState(MessagesState):
    """State schema for Godínez IndustrialEngineer."""

    # ── Input ──────────────────────────────────────────────
    query: str                          # Raw natural language input
    user_id: Optional[str] = None       # Optional session/user ID
    timestamp: Optional[str] = None     # When the query was received

    # ── Classification ─────────────────────────────────────
    intent: Optional[str] = None        # Classified intent (e.g. "oee", "bottleneck", "trend")
    confidence: Optional[float] = None  # Classification confidence (0-1)
    entities: dict = {}                 # Detected entities (machines, dates, shifts)
    human_review: bool = False          # Flag for low-confidence classifications

    # ── Analysis Results ───────────────────────────────────
    # Each phase adds its result type here.
    # Phase 0: None (just intake + response)
    # Phase 1: oee_analysis: Optional[dict]
    # Phase 3: trend_analysis: Optional[dict]
    # etc.

    # ── Output ─────────────────────────────────────────────
    response: Optional[str] = None      # Final text response
    report: Optional[str] = None        # Markdown report content
    attachments: Optional[List[str]] = None  # File paths (charts, PDFs, etc.)

    # ── Errors & Metadata ─────────────────────────────────
    errors: List[str] = []              # Accumulated errors during execution
    metadata: dict = {}                 # Arbitrary metadata (latency, token usage, etc.)
