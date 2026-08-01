"""
Session Datasets — Tracks which dataset filename is "active" for a session.

In-memory only: a module-level dict, reset on process restart. This is
correct for the current single-container / single-worker deployment
(`uvicorn ... --workers 1`) but will NOT be shared across multiple worker
processes or containers. If the API is ever scaled beyond one process,
this needs to move to a shared store (e.g. the existing Session table in
src/persistence/models.py, or Redis).
"""

from typing import Optional

_active: dict[str, str] = {}


def set_active_dataset(session_id: str, filename: str) -> None:
    _active[session_id] = filename


def get_active_dataset(session_id: str) -> Optional[str]:
    return _active.get(session_id)
