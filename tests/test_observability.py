"""
Tests for Godínez IndustrialEngineer observability module.

Phase 2: Structured logging, LangSmith tracing, metrics tracking.
"""

import pytest
import sys
import os
import time
import json

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Test ObservationLogger ─────────────────────────────────

class TestObservationLogger:
    """Tests for structured JSON logging with correlation IDs."""

    def test_logger_creation(self):
        """Logger should be created with default values."""
        from src.observability import ObservationLogger
        logger = ObservationLogger("test")
        assert logger.session_id is not None
        assert logger.execution_order == 0

    def test_logger_with_session_id(self):
        """Logger should use provided session ID."""
        from src.observability import ObservationLogger
        logger = ObservationLogger("test", session_id="abc123")
        assert logger.session_id == "abc123"

    def test_logger_info_with_context(self):
        """Logger should include node, intent, and latency in info logs."""
        from src.observability import ObservationLogger
        import io
        import logging

        logger = ObservationLogger("test")
        logger.logger.setLevel(logging.DEBUG)

        # Capture log output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logger.logger.handlers[0].formatter)
        logger.logger.addHandler(handler)

        logger.info("Test message", node="analyze", intent="oee")
        output = stream.getvalue()

        assert "Test message" in output
        assert "abc123" in output or "session" in output.lower()

    def test_logger_node_start_end(self):
        """Logger should track node start/end with latency."""
        from src.observability import ObservationLogger
        logger = ObservationLogger("test", session_id="test-session")

        start_time = logger.node_start("test_node", intent="oee")
        time.sleep(0.01)
        # node_end calculates latency from start_time internally
        logger.node_end("test_node", start_time, intent="oee")

        assert logger.execution_order >= 2

    def test_logger_error_with_exc(self):
        """Logger should capture exception info on error."""
        from src.observability import ObservationLogger
        import io
        import logging

        logger = ObservationLogger("test")
        logger.logger.setLevel(logging.DEBUG)

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logger.logger.handlers[0].formatter)
        logger.logger.addHandler(handler)

        try:
            raise ValueError("test error")
        except:
            logger.error("Failed operation", exc=True)

        output = stream.getvalue()
        assert "Failed operation" in output


# ── Test ExecutionMetrics ──────────────────────────────────

class TestExecutionMetrics:
    """Tests for execution metrics tracking."""

    def test_metrics_creation(self):
        """Metrics should be created with default values."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")
        assert metrics.session_id == "test-123"
        assert len(metrics.nodes) == 0
        assert metrics.execution_order == 0

    def test_start_end_node(self):
        """Should track node start and end with latency."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("test_node", intent="oee")
        time.sleep(0.01)
        metrics.end_node("test_node", latency_ms=15.5, tokens_used=512)

        assert len(metrics.nodes) == 1
        node = metrics.nodes[0]
        assert node.node_name == "test_node"
        assert node.intent == "oee"
        assert node.latency_ms == 15.5
        assert node.tokens_used == 512
        assert node.status == "success"

    def test_execution_order(self):
        """Should track execution order across multiple nodes."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("node_a")
        metrics.end_node("node_a", latency_ms=10)
        metrics.start_node("node_b")
        metrics.end_node("node_b", latency_ms=20)

        assert metrics.execution_order == 2
        assert metrics.nodes[0].execution_order == 1
        assert metrics.nodes[1].execution_order == 2

    def test_get_execution_order(self):
        """Should return node names in execution order."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("intake")
        metrics.end_node("intake", latency_ms=5)
        metrics.start_node("analyze")
        metrics.end_node("analyze", latency_ms=10)

        order = metrics.get_execution_order()
        assert order == ["intake", "analyze"]

    def test_get_total_latency(self):
        """Should calculate total workflow latency."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("node1")
        metrics.end_node("node1", latency_ms=100)
        metrics.start_node("node2")
        metrics.end_node("node2", latency_ms=50)

        total = metrics.get_total_latency_ms()
        assert total > 0

    def test_get_summary(self):
        """Should return complete execution summary."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("analyze")
        metrics.end_node("analyze", latency_ms=25.0, tokens_used=1024)

        summary = metrics.get_summary()

        assert summary["session_id"] == "test-123"
        assert summary["total_nodes"] == 1
        assert len(summary["execution_order"]) == 1
        assert summary["execution_order"][0] == "analyze"

    def test_get_summary_aggregates_tokens_used_across_nodes(self):
        """Top-level tokens_used should sum every node's token count."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-tokens")

        metrics.start_node("classify")
        metrics.end_node("classify", latency_ms=10.0, tokens_used=150)
        metrics.start_node("response")
        metrics.end_node("response", latency_ms=5.0)  # no tokens_used — shouldn't crash the sum

        summary = metrics.get_summary()
        assert summary["tokens_used"] == 150

    def test_get_summary_tokens_used_none_when_no_node_reports_it(self):
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-no-tokens")

        metrics.start_node("router")
        metrics.end_node("router", latency_ms=1.0)

        summary = metrics.get_summary()
        assert summary["tokens_used"] is None

    def test_record_metadata(self):
        """Should record workflow-level metadata."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.record_metadata("model", "qwen3:8b")
        metrics.record_metadata("provider", "ollama")

        assert metrics.workflow_metadata["model"] == "qwen3:8b"
        assert metrics.workflow_metadata["provider"] == "ollama"

    def test_error_status(self):
        """Should record error status when node fails."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("broken_node")
        metrics.end_node("broken_node", latency_ms=5, status="error")

        assert metrics.nodes[0].status == "error"

    def test_get_state_metadata(self):
        """Should return metadata dict suitable for GodinezState."""
        from src.observability import ExecutionMetrics
        metrics = ExecutionMetrics(session_id="test-123")

        metrics.start_node("intake")
        metrics.end_node("intake", latency_ms=10)

        state_meta = metrics.get_state_metadata()

        assert "node_execution_order" in state_meta
        assert "total_latency_ms" in state_meta
        assert "total_nodes" in state_meta


# ── Test Workflow Integration ───────────────────────────────

class TestWorkflowIntegration:
    """Tests for observability integrated into workflow."""

    def test_build_workflow_with_observability(self):
        """Workflow should build with observability context."""
        from src.graph import build_workflow

        workflow, obs_context = build_workflow(session_id="test-123")
        
        assert workflow is not None
        assert obs_context["logger"] is not None
        assert obs_context["metrics"] is not None
        assert obs_context["logger"].session_id == "test-123"

    def test_workflow_obs_context_has_tracer(self):
        """Workflow should include tracer in context."""
        from src.graph import build_workflow

        workflow, obs_context = build_workflow(session_id="test-123")
        
        assert "tracer" in obs_context
        assert "metrics" in obs_context

    def test_workflow_returns_metrics(self):
        """Build and invoke workflow should capture execution metrics."""
        from src.graph import build_workflow

        workflow, obs_context = build_workflow(session_id="test-123")

        assert "tracer" in obs_context
        assert "metrics" in obs_context

        # Invoke the workflow with a simple query
        compiled = workflow.compile()
        result = compiled.invoke({"query": "What's our OEE?", "messages": []})

        # Metrics should be captured
        summary = obs_context["metrics"].get_summary()
        assert "execution_order" in summary
        assert len(summary["execution_order"]) > 0
        assert "response" in result


# ── Test Tracing Module ────────────────────────────────────

class TestTracing:
    """Tests for LangSmith tracing module."""

    def test_is_tracing_enabled_with_key(self):
        """Tracing should be enabled when API key is present."""
        from src.observability.tracing import _is_tracing_enabled
        assert _is_tracing_enabled() is True

    def test_get_tracer_returns_tracer_when_enabled(self):
        """Should return a tracer dict when tracing is enabled."""
        from src.observability.tracing import get_tracer
        tracer = get_tracer("test-workflow")
        # When enabled, should return a tracer dict with client
        assert tracer is not None
        assert "client" in tracer
        assert "workflow_name" in tracer

    def test_trace_node_context_manager_with_tracer(self):
        """Context manager should work with tracer enabled."""
        from src.observability.tracing import trace_node, get_tracer
        
        # With real tracer (tracing enabled)
        tracer = get_tracer("test-workflow")
        if tracer:
            with trace_node(tracer, "test_node"):
                pass
        # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
