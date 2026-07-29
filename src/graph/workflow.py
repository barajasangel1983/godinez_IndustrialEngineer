"""
Godínez IndustrialEngineer — Workflow definition with observability

Minimal LangGraph StateGraph for Phase 0+.
Nodes: intake → classify → router → analyze → response → END

Phase 2+: Integrated observability (metrics, logging, tracing).
"""

import time
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from .state import GodinezState
from .nodes.intake import intake_node
from .nodes.classify import classify_node
from .nodes.router import router_node
from .nodes.analyze import analyze_node
from .nodes.response import response_node
from ..observability import (
    ExecutionMetrics,
    ObservationLogger,
    get_tracer,
    trace_node,
)

# ── Node wrapper registry ──────────────────────────────────
# Wraps each node with metrics tracking, logging, and tracing


def _wrap_node(fn, node_name, logger, metrics, tracer=None):
    """
    Wrap a node function with observability.

    Adds:
    - Execution order tracking
    - Latency measurement
    - Structured logging (start/end)
    - LangSmith tracing (if tracer provided)
    - Metadata propagation to state
    """
    def wrapped(state: GodinezState) -> dict:
        # Start tracking
        execution_order = metrics.start_node(node_name, intent=state.get("intent"))
        start_time = time.perf_counter()

        # Log start
        logger.info(
            f"Executing node '{node_name}'",
            node=node_name,
            intent=state.get("intent"),
        )

        # Open LangSmith trace span
        trace_ctx = trace_node(tracer, node_name, {"intent": state.get("intent")}) if tracer else None
        if trace_ctx:
            trace_ctx.__enter__()

        try:
            # Execute node
            result = fn(state)

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract metadata from result (if any)
            node_metadata = result.get("metadata", {})
            tokens_used = node_metadata.get("tokens_used")

            # End tracking
            metrics.end_node(
                node_name,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                status="success",
                metadata=node_metadata,
            )

            # Log completion
            logger.info(
                f"Node '{node_name}' completed in {latency_ms:.1f}ms",
                node=node_name,
                intent=state.get("intent"),
                latency_ms=round(latency_ms, 2),
                tokens_used=tokens_used,
            )

            # Ensure metadata includes execution order
            if "metadata" in result:
                result["metadata"]["execution_order"] = execution_order
            else:
                result["metadata"] = {"execution_order": execution_order}

            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Close LangSmith trace with error
            if trace_ctx:
                trace_ctx.__exit__(type(e), e, e.__traceback__)

            metrics.end_node(
                node_name,
                latency_ms=latency_ms,
                status="error",
            )
            logger.error(
                f"Node '{node_name}' failed: {e}",
                node=node_name,
                intent=state.get("intent"),
                latency_ms=round(latency_ms, 2),
                exc=True,
            )
            raise
        else:
            # Close LangSmith trace on success
            if trace_ctx:
                trace_ctx.__exit__(None, None, None)

    return wrapped


def build_workflow(
    session_id: str = "",
    enable_tracing: bool = False,
) -> tuple[StateGraph, dict]:
    """
    Build and return the compiled Godínez IndustrialEngineer workflow with observability.

    Args:
        session_id: Optional session identifier for tracking
        enable_tracing: Whether to enable LangSmith tracing

    Returns:
        Tuple of (StateGraph, observability_context)
        observability_context contains logger, metrics, tracer for inspection
    """
    # Initialize observability
    logger = ObservationLogger("godinez", session_id=session_id)
    metrics = ExecutionMetrics(session_id=session_id or f"session-{int(time.time())}")

    # Get LangSmith tracer if enabled
    tracer = get_tracer("godinez-workflow", session_name=session_id or "session") if enable_tracing else None
    if tracer:
        metrics.record_metadata("tracing_enabled", True)
        metrics.record_metadata("langsmith_project", "godinez-industrial-engineer")

    # Build graph
    workflow = StateGraph(GodinezState)

    # ── Add nodes with observability wrappers ────────────
    node_config = {
        "intake": intake_node,
        "classify": classify_node,
        "router": router_node,
        "analyze": analyze_node,
        "response": response_node,
    }

    for node_name, node_fn in node_config.items():
        wrapped = _wrap_node(node_fn, node_name, logger, metrics, tracer)
        workflow.add_node(node_name, wrapped)

    # ── Edges ───────────────────────────────────────────
    workflow.add_edge("intake", "classify")
    workflow.add_edge("classify", "router")
    workflow.add_edge("router", "analyze")
    workflow.add_edge("analyze", "response")
    workflow.add_edge("response", END)

    # ── Entry point ─────────────────────────────────────
    workflow.set_entry_point("intake")

    # ── Build observability context ─────────────────────
    observability_context = {
        "logger": logger,
        "metrics": metrics,
        "enable_tracing": enable_tracing,
        "tracer": tracer,
    }

    return workflow, observability_context
