"""
Observability module — Structured logging, LangSmith tracing, and metrics.

Phase 2: Provides observability for the Godinez workflow.

Modules:
    - logger: Structured JSON logging with correlation IDs
    - tracing: LangSmith integration for workflow tracing
    - metrics: Execution metrics tracking (latency, tokens, order)

Usage:
    from src.observability import ObservationLogger, ExecutionMetrics

    logger = ObservationLogger("godinez")
    metrics = ExecutionMetrics()

    # In workflow nodes:
    metrics.start_node("oee_analysis")
    # ... node logic ...
    metrics.end_node("oee_analysis", latency_ms=250)
"""

from .logger import ObservationLogger
from .metrics import ExecutionMetrics, NodeExecution
from .tracing import (
    get_tracer,
    trace_node,
    trace_workflow,
    log_to_langsmith,
)

__all__ = [
    "ObservationLogger",
    "ExecutionMetrics",
    "NodeExecution",
    "get_tracer",
    "trace_node",
    "trace_workflow",
    "log_to_langsmith",
]
