"""
Structured JSON logger with correlation IDs.

Phase 2: Provides structured logging for observability.
- JSON output for machine parsing
- Correlation IDs for request tracing
- Log levels (DEBUG, INFO, WARNING, ERROR)
- Context tracking (session_id, node, intent)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

# ── Log levels ─────────────────────────────────────────────
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "session_id": getattr(record, "session_id", None),
            "node": getattr(record, "node", None),
            "intent": getattr(record, "intent", None),
            "latency_ms": getattr(record, "latency_ms", None),
            "tokens_used": getattr(record, "tokens_used", None),
            "execution_order": getattr(record, "execution_order", None),
        }

        # Add any extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry)


class ObservationLogger:
    """
    Structured JSON logger with correlation IDs and context tracking.

    Usage:
        logger = ObservationLogger("godinez")
        logger.info("Starting analysis", node="analyze", intent="oee")
        logger.error("Failed", exc=True, latency_ms=1500)
    """

    def __init__(
        self,
        name: str = "godinez",
        level: str = "INFO",
        session_id: Optional[str] = None,
    ):
        """
        Initialize logger.

        Args:
            name: Logger name (usually module name)
            level: Log level string (DEBUG, INFO, WARNING, ERROR)
            session_id: Optional session/correlation ID
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))

        # Only add handler once
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(handler)

        self.session_id = session_id or str(uuid4())[:8]
        self.execution_order = 0

    def _make_record(
        self,
        level: int,
        message: str,
        node: Optional[str] = None,
        intent: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        extra_fields: Optional[dict] = None,
        exc: bool = False,
    ) -> logging.LogRecord:
        """Create a log record with extra context fields."""
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown)",
            0,
            message,
            (),
            None,
        )

        record.correlation_id = self.session_id
        record.session_id = self.session_id
        record.node = node
        record.intent = intent
        record.latency_ms = latency_ms
        record.tokens_used = tokens_used
        record.execution_order = self.execution_order

        if extra_fields:
            record.extra_fields = extra_fields
        else:
            record.extra_fields = {}

        return record

    def debug(
        self,
        message: str,
        node: Optional[str] = None,
        intent: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        **kwargs,
    ):
        """Log debug message."""
        self.execution_order += 1
        record = self._make_record(
            logging.DEBUG, message, node, intent, latency_ms, tokens_used, kwargs
        )
        self.logger.handle(record)

    def info(
        self,
        message: str,
        node: Optional[str] = None,
        intent: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        **kwargs,
    ):
        """Log info message."""
        self.execution_order += 1
        record = self._make_record(
            logging.INFO, message, node, intent, latency_ms, tokens_used, kwargs
        )
        self.logger.handle(record)

    def warning(
        self,
        message: str,
        node: Optional[str] = None,
        intent: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        **kwargs,
    ):
        """Log warning message."""
        self.execution_order += 1
        record = self._make_record(
            logging.WARNING, message, node, intent, latency_ms, tokens_used, kwargs
        )
        self.logger.handle(record)

    def error(
        self,
        message: str,
        node: Optional[str] = None,
        intent: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_used: Optional[int] = None,
        exc: bool = False,
        **kwargs,
    ):
        """Log error message with optional exception."""
        self.execution_order += 1
        record = self._make_record(
            logging.ERROR, message, node, intent, latency_ms, tokens_used, kwargs
        )
        if exc:
            record.exc_info = sys.exc_info()
        self.logger.handle(record)

    def node_start(self, node_name: str, intent: Optional[str] = None) -> float:
        """
        Log node start and return start time for latency tracking.

        Args:
            node_name: Name of the node being executed
            intent: Optional intent being processed

        Returns:
            Start time (time.perf_counter) for latency calculation
        """
        self.info(
            f"Node '{node_name}' started",
            node=node_name,
            intent=intent,
        )
        return time.perf_counter()

    def node_end(
        self,
        node_name: str,
        start_time: float,
        intent: Optional[str] = None,
        tokens_used: Optional[int] = None,
        extra: Optional[dict] = None,
    ):
        """
        Log node completion with latency.

        Args:
            node_name: Name of the node that completed
            start_time: Time.perf_counter value from node_start
            intent: Intent being processed
            tokens_used: Token count from LLM call
            extra: Additional metadata to include
        """
        latency_ms = (time.perf_counter() - start_time) * 1000
        self.info(
            f"Node '{node_name}' completed in {latency_ms:.1f}ms",
            node=node_name,
            intent=intent,
            latency_ms=round(latency_ms, 2),
            tokens_used=tokens_used,
            extra_fields={"latency_ms": round(latency_ms, 2)} if extra else None,
        )

    def workflow_complete(self, total_latency_ms: float, node_count: int):
        """Log workflow completion summary."""
        self.info(
            f"Workflow complete: {node_count} nodes in {total_latency_ms:.1f}ms",
            extra_fields={
                "total_latency_ms": round(total_latency_ms, 2),
                "nodes_executed": node_count,
            },
        )
