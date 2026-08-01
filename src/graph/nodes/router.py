"""
Router node — Classify intent and route to appropriate analysis.

Phase 0: Simple keyword-based routing.
Future phases: LLM-based intent classification, confidence scoring.
"""

from ..state import GodinezState
from ...tools.dataset_command import DATASET_SYSTEM_INTENTS

# Phase 0: Simple keyword matching
INTENT_KEYWORDS = {
    "oee": ["oee", "overall equipment effectiveness", "equipment availability"],
    "bottleneck": ["bottleneck", "constraint", "bottleneck", "bottleneck", "bottleneck"],
    "trend": ["trend", "forecast", "projection", "time series", "prediction"],
    "cost": ["cost", "scrap", "rework", "waste", "financial", "roi"],
    "safety": ["safety", "incident", "osha", "compliance", "hazard"],
    "time_study": ["time study", "standard time", "cycle time", "motion study"],
}


def router_node(state: GodinezState) -> GodinezState:
    """Classify intent based on query keywords (Phase 0: simple matching)."""

    # Deterministic system commands (e.g. "load dataset", "list datasets")
    # are already classified by intake_node — don't let keyword matching
    # overwrite them.
    intent = state.get("intent")
    if intent in DATASET_SYSTEM_INTENTS:
        return {
            "intent": intent,
            "confidence": 1.0,
            "metadata": {**state.get("metadata", {}), "router_intent": intent},
        }

    query = state.get("query", "").lower()
    detected_intent = "general"
    confidence = 0.5  # Low confidence for keyword matching

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in query:
                detected_intent = intent
                confidence = 0.8  # Higher confidence if keyword matched
                break
        if detected_intent != "general":
            break

    return {
        "intent": detected_intent,
        "confidence": confidence,
        "metadata": {**state.get("metadata", {}), "router_intent": detected_intent},
    }
