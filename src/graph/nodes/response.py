"""
Response node — Format and return the final response.

Phase 0: Simple string response with metadata.
Future phases: Markdown formatting, chart embedding, file attachment generation.
"""

from ..state import GodinezState


def response_node(state: GodinezState) -> GodinezState:
    """Format and return the final response."""

    response = state.get("response", "")
    intent = state.get("intent")
    errors = state.get("errors", [])

    # Build a formatted response
    formatted = f"**Godínez IndustrialEngineer**\n"
    formatted += f"{'=' * 40}\n"
    formatted += f"Intent: {intent or 'unknown'}\n"
    formatted += f"\n{response}\n"

    if errors:
        formatted += f"\n⚠️ Errors encountered:\n"
        for err in errors:
            formatted += f"  - {err}\n"

    return {
        "response": formatted,
        "metadata": {**state.get("metadata", {}), "phase": "0"},
    }
