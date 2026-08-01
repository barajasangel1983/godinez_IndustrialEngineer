"""
Intake node — Parse and validate the incoming query.

Phase 0: Simple pass-through with timestamp + basic validation.
Phase 2+: Add NLP parsing, intent classification, data requirement extraction.
"""

from datetime import datetime, timezone

from ..state import GodinezState
from ...tools.dataset_command import extract_dataset_filename, is_list_datasets_command


def intake_node(state: GodinezState) -> GodinezState:
    """Validate the query and attach metadata."""

    query = state.get("query", "").strip()

    if not query:
        return {
            "response": "I need a query to work with. What can I help you analyze?",
            "errors": state.get("errors", []) + ["Empty query received"],
        }

    now = datetime.now(timezone.utc).isoformat()
    result = {
        "query": query,
        "timestamp": state.get("timestamp") or now,
        "metadata": {**state.get("metadata", {}), "phase": "0"},
    }

    # Deterministically detect dataset system commands before classification
    # ever runs — these shouldn't depend on LLM availability or correctness.
    dataset_filename = extract_dataset_filename(query)
    if dataset_filename:
        result["intent"] = "load_dataset"
        result["entities"] = {**state.get("entities", {}), "dataset_filename": dataset_filename}
    elif is_list_datasets_command(query):
        result["intent"] = "list_datasets"

    return result
