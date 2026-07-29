"""
LangSmith tracing integration for workflow observability.

Phase 2: Provides tracing for all workflow steps via LangSmith.
- Automatic tracing of LangGraph workflow execution
- Node-level spans with metadata
- Custom tags and attributes for analysis

Usage:
    # Set in .env or environment:
    # LANGSMITH_TRACING=true
    # LANGSMITH_API_KEY=your-key

    from src.observability.tracing import get_tracer, trace_node
    
    # Use in your code:
    tracer = get_tracer("godinez-workflow")
    if tracer:
        with trace_node(tracer, "analyze"):
            result = analyze_node(state)
"""

import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

# Load .env before reading env vars
from dotenv import load_dotenv
load_dotenv()

from langsmith.run_trees import RunTree

# ── Configuration ──────────────────────────────────────────
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "godinez-industrial-engineer")
LANGSMITH_TRACING = (
    os.getenv("LANGSMITH_TRACING", "false").lower() in ("true", "1", "yes")
)


def _is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    return LANGSMITH_TRACING and bool(LANGSMITH_API_KEY)


def get_tracer(
    workflow_name: str = "godinez-workflow",
    session_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get a LangSmith tracer instance.

    Returns a tracer dict with methods to create spans, or None
    if tracing is not configured.

    Args:
        workflow_name: Name identifier for the workflow
        session_name: Optional session/run name

    Returns:
        Tracer dict with 'workflow_name', 'client', and 'start_time'
        or None if tracing disabled
    """
    if not _is_tracing_enabled():
        return None

    try:
        from langsmith import Client

        client = Client()
        return {
            "client": client,
            "workflow_name": workflow_name,
            "session_name": session_name or f"{workflow_name}-{int(time.time())}",
            "start_time": time.perf_counter(),
        }
    except ImportError:
        return None
    except Exception as e:
        print(f"[WARNING] LangSmith tracer init failed: {e}")
        return None


@contextmanager
def trace_node(
    tracer: Optional[Dict[str, Any]],
    node_name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[None, None, None]:
    """
    Context manager to trace a workflow node.

    Usage:
        tracer = get_tracer("godinez-workflow")
        with trace_node(tracer, "analyze", {"intent": "oee"}):
            result = analyze_node(state)

    Args:
        tracer: LangSmith tracer dict (from get_tracer) or None
        node_name: Name of the node being traced
        metadata: Optional dict of node metadata
    """
    if tracer is None:
        yield
        return

    start_time = time.perf_counter()
    run_id = None
    error = None

    try:
        yield
    except Exception as e:
        error = e
        raise
    finally:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        try:
            # Create a RunTree (span) for this node
            run = RunTree(
                name=node_name,
                run_type="chain",
                project_name=LANGSMITH_PROJECT,
                inputs={"metadata": metadata or {}},
            )
            run_id = run.id

            outputs = {"latency_ms": latency_ms}
            if metadata:
                outputs["metadata"] = metadata

            run.end(
                error=str(error) if error else None,
                outputs=outputs,
            )
            run.post()  # Send to LangSmith
        except Exception as tracing_err:
            # Don't let tracing failures break the workflow
            print(f"[WARNING] Tracing error in {node_name}: {tracing_err}")


@contextmanager
def trace_workflow(
    workflow_name: str = "godinez-workflow",
    session_name: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager to trace an entire workflow execution.

    Usage:
        with trace_workflow("godinez-workflow", session_name="analysis-123") as tracer:
            state = run_workflow("What's our OEE?")
            # tracer dict contains timing and client info

    Args:
        workflow_name: Name of the workflow
        session_name: Optional session name for LangSmith

    Returns:
        Generator yielding tracer dict (or None if tracing disabled)
    """
    tracer = get_tracer(workflow_name, session_name)

    if tracer is not None:
        tracer["start_time"] = time.perf_counter()
        tracer["nodes_executed"] = []

    try:
        yield tracer
    finally:
        if tracer is not None:
            elapsed = round(
                (time.perf_counter() - tracer["start_time"]) * 1000, 2
            )
            tracer["total_latency_ms"] = elapsed

            try:
                # Create a final run for the workflow
                run = RunTree(
                    name=f"workflow-{workflow_name}",
                    run_type="chain",
                    project_name=LANGSMITH_PROJECT,
                )
                run.end(
                    outputs={
                        "total_latency_ms": elapsed,
                        "nodes_executed": tracer.get("nodes_executed", []),
                    }
                )
                run.post()
            except Exception as e:
                print(f"[WARNING] Workflow tracing finalization failed: {e}")


def log_to_langsmith(
    tracer: Optional[Dict[str, Any]],
    message: str,
    level: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a message to LangSmith as a span event.

    Args:
        tracer: LangSmith tracer dict (from get_tracer) or None
        message: Log message
        level: Log level (info, warning, error)
        metadata: Optional metadata dict
    """
    if tracer is None:
        return

    try:
        run = RunTree(
            name=f"log-{level}",
            run_type="chain",
            project_name=LANGSMITH_PROJECT,
        )
        run.end(
            outputs={
                "message": message,
                "level": level,
                "metadata": metadata or {},
            }
        )
        run.post()
    except Exception as e:
        print(f"[WARNING] LangSmith log failed: {e}")
