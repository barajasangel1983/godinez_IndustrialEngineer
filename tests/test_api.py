"""
Tests for FastAPI REST API (`src/api/app.py`).

Tests both request validation and workflow execution via the TestClient.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def _mock_workflow():
    """Create a mock workflow that returns structured OEE results."""
    workflow_mock = MagicMock()
    compiled_mock = MagicMock()
    workflow_mock.compile.return_value = compiled_mock
    compiled_mock.invoke.return_value = {
        "query": "What's our OEE?",
        "messages": [],
        "intent": "oee",
        "confidence": 0.95,
        "entities": {},
        "human_review": False,
        "response": "**OEE Analysis Report**\n\nOverall OEE Score: 86.1%",
        "errors": [],
        "metadata": {
            "oee_score": 86.1,
            "oee_rating": "good",
            "data_points": 84,
            "analyzed_intents": ["oee"],
            "analysis_result_count": 1,
        },
    }
    metrics_mock = MagicMock()
    metrics_mock.get_summary.return_value = {
        "total_latency_ms": 150,
        "execution_order": ["intake", "classify", "router", "analyze", "response"],
    }
    return (workflow_mock, {"metrics": metrics_mock})


def _make_simple_result(intent="general"):
    """Create a simple invoke result for basic tests."""
    compiled_mock = MagicMock()
    compiled_mock.invoke.return_value = {
        "query": "",
        "messages": [],
        "intent": intent,
        "response": f"Response for intent: {intent}",
        "errors": [],
        "metadata": {},
    }
    metrics_mock = MagicMock()
    metrics_mock.get_summary.return_value = {
        "total_latency_ms": 50,
        "execution_order": ["intake", "classify", "router", "response"],
    }
    return MagicMock(compile=MagicMock(return_value=compiled_mock)), {"metrics": metrics_mock}


class TestHealthCheck:
    """Health endpoint tests."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.6.0"
        assert isinstance(data["tracing_enabled"], bool)


class TestQueryRequestValidation:
    """Pydantic request validation tests."""

    def test_missing_query_returns_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_empty_query_returns_422(self, client):
        resp = client.post("/api/query", json={"query": ""})
        assert resp.status_code == 422

    def test_optional_fields_accepted(self, client):
        with patch("src.api.app.build_workflow", return_value=_make_simple_result()):
            resp = client.post("/api/query", json={"query": "What's our OEE?"})
            assert resp.status_code == 200


class TestQueryEndpoint:
    """End-to-end query endpoint tests via TestClient."""

    def test_oee_query_success(self, client):
        """POST /api/query with OEE query returns response."""
        with patch("src.api.app.build_workflow", return_value=_mock_workflow()):
            resp = client.post(
                "/api/query",
                json={"query": "What's our OEE?", "user_id": "test-user-1"},
            )
            assert resp.status_code == 200
            data = resp.json()

            assert data["success"] is True
            assert data["query"] == "What's our OEE?"
            assert data["user_id"] == "test-user-1"
            assert data["intent"] == "oee"
            assert data["response"]
            assert "session_id" in data
            assert isinstance(data["metadata"], dict)
            assert isinstance(data["execution_summary"], dict)

    def test_general_query(self, client):
        """General query works without user_id."""
        with patch("src.api.app.build_workflow", return_value=_make_simple_result("general")):
            resp = client.post(
                "/api/query",
                json={"query": "Tell me about production."},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert len(data["response"]) > 0

    def test_session_id_passed_through(self, client):
        """Explicit session_id is preserved in response."""
        sid = "my-custom-session-123"
        with patch("src.api.app.build_workflow", return_value=_mock_workflow()):
            resp = client.post(
                "/api/query",
                json={"query": "What's our OEE?", "session_id": sid},
            )
            assert resp.status_code == 200
            assert resp.json()["session_id"] == sid

    def test_execution_summary_has_metrics(self, client):
        """Execution summary contains expected metrics keys."""
        with patch("src.api.app.build_workflow", return_value=_mock_workflow()):
            resp = client.post(
                "/api/query",
                json={"query": "What's our OEE?"},
            )
            data = resp.json()
            summary = data["execution_summary"]
            assert "total_latency_ms" in summary
            assert "execution_order" in summary
            assert isinstance(summary["execution_order"], list)
            assert len(summary["execution_order"]) > 0

    def test_tracing_flag_passed_to_workflow(self, client):
        """enable_tracing flag is passed to build_workflow."""
        with patch("src.api.app.build_workflow", return_value=_mock_workflow()) as mock_bw:
            resp = client.post(
                "/api/query",
                json={"query": "What's our OEE?", "enable_tracing": True},
            )
            assert resp.status_code == 200
            # Verify tracing was enabled
            call_kwargs = mock_bw.call_args[1]
            assert call_kwargs["enable_tracing"] is True
