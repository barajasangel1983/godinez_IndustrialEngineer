"""
Conftest for Godínez tests — mocks LLM calls for workflow tests.

The classify_node tries DGX vLLM first (30s timeout). We patch it
to use keyword fallback only so workflow/e2e tests don't hang.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch
from src.graph.nodes.classify import _keyword_fallback


def _mock_classify_node(state):
    """Replace classify_node with keyword-only fallback."""
    from src.graph.nodes.classify import _keyword_fallback

    # Mirror the real classify_node's short-circuit for deterministic
    # system commands (e.g. "load dataset") — these bypass classification
    # entirely and must not be reclassified by keyword matching.
    if state.get("intent") == "load_dataset":
        return {
            **state,
            "confidence": 1.0,
            "human_review": False,
            "metadata": {
                **state.get("metadata", {}),
                "classify_method": "skipped_system_command",
            },
        }

    result = _keyword_fallback(state.get("query", ""))
    return {
        **state,
        "intent": result.intent,
        "confidence": result.confidence,
        "entities": result.entities,
        "human_review": result.confidence < 0.5,
        "metadata": {
            **state.get("metadata", {}),
            "classify_method": "keyword_fallback",
        },
    }


# Patch the module-level classify_node for all tests
import src.graph.nodes.classify as classify_module
classify_module.classify_node = _mock_classify_node

# Also patch in the workflow module's import
import src.graph.workflow as workflow_module
workflow_module.classify_node = _mock_classify_node
