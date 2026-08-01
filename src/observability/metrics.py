"""
Execution metrics tracker for workflow observability.

Phase 2: Tracks node execution order, timing, and metadata.
- Records each node execution with timing
- Accumulates metadata across workflow
- Provides execution summary

Usage:
    from src.observability.metrics import ExecutionMetrics
    metrics = ExecutionMetrics(session_id="abc123")

    # In each node:
    metrics.start_node("oee_analysis")
    # ... run node ...
    metrics.end_node("oee_analysis", latency_ms=250, tokens_used=1024)

    # After workflow:
    summary = metrics.get_summary()
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NodeExecution:
    """Record of a single node execution."""
    node_name: str
    execution_order: int
    start_time: float  # perf_counter
    latency_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    intent: Optional[str] = None
    status: str = "running"  # "running", "success", "error"
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """
    Tracks execution metrics across a workflow run.

    Attributes:
        session_id: Unique session identifier
        start_time: Workflow start time
        nodes: List of node executions
        execution_order: Current node execution counter
        workflow_metadata: Accumulated workflow-level metadata
    """

    session_id: str = ""
    start_time: float = field(default_factory=time.perf_counter)
    nodes: list[NodeExecution] = field(default_factory=list)
    execution_order: int = 0
    workflow_metadata: dict = field(default_factory=dict)

    def start_node(
        self,
        node_name: str,
        intent: Optional[str] = None,
    ) -> int:
        """
        Record node start.

        Args:
            node_name: Name of the node being executed
            intent: Optional intent being processed

        Returns:
            Execution order number
        """
        self.execution_order += 1
        self.nodes.append(NodeExecution(
            node_name=node_name,
            execution_order=self.execution_order,
            start_time=time.perf_counter(),
            intent=intent,
        ))
        return self.execution_order

    def end_node(
        self,
        node_name: str,
        latency_ms: float,
        tokens_used: Optional[int] = None,
        status: str = "success",
        metadata: Optional[dict] = None,
    ):
        """
        Record node completion.

        Args:
            node_name: Name of the completed node
            latency_ms: Execution time in milliseconds
            tokens_used: Optional token count from LLM call
            status: "success" or "error"
            metadata: Optional node-specific metadata
        """
        if self.nodes:
            node = self.nodes[-1]
            node.latency_ms = round(latency_ms, 2)
            node.tokens_used = tokens_used
            node.status = status
            if metadata:
                node.metadata.update(metadata)

    def record_metadata(self, key: str, value: Any):
        """Record workflow-level metadata."""
        self.workflow_metadata[key] = value

    def get_execution_order(self) -> list[str]:
        """Get list of node names in execution order."""
        return [node.node_name for node in self.nodes]

    def get_total_latency_ms(self) -> float:
        """Get total workflow latency in milliseconds."""
        return (time.perf_counter() - self.start_time) * 1000

    def get_summary(self) -> dict:
        """
        Get execution summary.

        Returns:
            Dict with total nodes, total latency, execution order, etc.
        """
        return {
            "session_id": self.session_id,
            "total_nodes": len(self.nodes),
            "total_latency_ms": round(self.get_total_latency_ms(), 2),
            "tokens_used": sum(n.tokens_used for n in self.nodes if n.tokens_used) or None,
            "execution_order": self.get_execution_order(),
            "nodes": [
                {
                    "node_name": node.node_name,
                    "execution_order": node.execution_order,
                    "latency_ms": node.latency_ms,
                    "tokens_used": node.tokens_used,
                    "intent": node.intent,
                    "status": node.status,
                }
                for node in self.nodes
            ],
            "metadata": self.workflow_metadata,
        }

    def get_state_metadata(self) -> dict:
        """
        Get metadata dict suitable for storing in GodinezState.

        Returns:
            Dict with node_execution_order, total_latency_ms, and node metadata
        """
        return {
            "node_execution_order": self.get_execution_order(),
            "total_latency_ms": round(self.get_total_latency_ms(), 2),
            "total_nodes": len(self.nodes),
            "metadata": self.workflow_metadata,
        }
