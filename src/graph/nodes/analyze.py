"""
Analysis node — Run the requested analysis on data.

Phase 0: Placeholder that returns a default response.
Phase 1: OEE analysis via oee_analysis_node.
"""

from ..state import GodinezState
from . import oee_analysis

# Phase 1+ analysis capabilities
ANALYSIS_HANDLERS = {
    "oee": oee_analysis.oee_analysis_node,
}


def analyze_node(state: GodinezState) -> GodinezState:
    """Execute analysis based on intent. Phase 1: OEE is implemented."""

    intent = state.get("intent") or "general"
    handler = ANALYSIS_HANDLERS.get(intent)

    if handler:
        return handler(state)
    else:
        query = state.get("query", "")
        response = (
            f"Analysis for intent='{intent}' not yet implemented.\n\n"
            f"Query: {query}\n\n"
            f"Implemented intents: {', '.join(ANALYSIS_HANDLERS.keys())}"
        )
        return {"response": response, "intent": intent}
