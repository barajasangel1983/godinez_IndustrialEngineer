"""
Tests for Godínez IndustrialEngineer workflow.

Phase 0: Basic smoke test to verify the workflow runs end-to-end.
Future phases: Unit tests for each capability (OEE, bottleneck, etc.).
"""

import pytest
import sys
import os

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph import build_workflow


def test_workflow_runs():
    """Test that the workflow executes end-to-end."""

    # Build and compile the workflow
    workflow = build_workflow()
    app = workflow.compile()

    # Run with a simple query
    result = app.invoke({
        "query": "What's our OEE today?",
        "messages": [{"role": "user", "content": "What's our OEE today?"}],
    })

    # Verify response is generated
    assert "response" in result
    assert result["response"] is not None
    assert len(result["response"]) > 0


def test_empty_query_handling():
    """Test that empty queries are handled gracefully."""

    workflow = build_workflow()
    app = workflow.compile()

    result = app.invoke({
        "query": "",
        "messages": [{"role": "user", "content": ""}],
    })

    # Should return an error message, not crash
    assert "response" in result
    assert "error" in result["response"].lower() or "need" in result["response"].lower()


def test_intent_detection():
    """Test that intent is classified correctly."""

    workflow = build_workflow()
    app = workflow.compile()

    result = app.invoke({
        "query": "What's our OEE today?",
        "messages": [{"role": "user", "content": "What's our OEE today?"}],
    })

    # Intent should be detected
    assert result.get("intent") is not None
    assert result["intent"] in ["oee", "general"]  # OEE keyword should match


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
