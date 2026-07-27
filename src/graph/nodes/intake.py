"""
Intake node — Parse and validate the incoming query.

Phase 0: Simple pass-through with timestamp + basic validation.
Phase 2+: Add NLP parsing, intent classification, data requirement extraction.
"""

from datetime import datetime, timezone

from ..state import GodinezState


def intake_node(state: GodinezState) -> GodinezState:
    """Validate the query and attach metadata."""

    query = state.get("query", "").strip()

    if not query:
        return {
            "response": "I need a query to work with. What can I help you analyze?",
            "errors": state.get("errors", []) + ["Empty query received"],
        }

    now = datetime.now(timezone.utc).isoformat()
    return {
        "query": query,
        "timestamp": state.get("timestamp") or now,
        "metadata": {**state.get("metadata", {}), "phase": "0"},
    }
