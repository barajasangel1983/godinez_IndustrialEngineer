"""
Session Datasets — Tracks which dataset filename is "active" for a session.

Backed by the Session.active_dataset DB column (src/persistence) whenever
persistence is available. This matters because scripts/start.sh runs
uvicorn with 2+ workers by default the moment DATABASE_URL points at a
real database (SQLite/off stays single-worker) — with multiple worker
*processes*, a plain in-memory dict would not be shared between them, so
"Load dataset" in one request could silently be invisible to the next
request depending on which worker handled it.

Falls back to an in-memory dict when persistence is off. That mode is
always single-worker (see scripts/start.sh), so the in-memory store is
still correct there — and it's what backs local dev (`python main.py
server`), which never goes through start.sh at all.
"""

from typing import Optional

_active: dict[str, str] = {}


def set_active_dataset(session_id: str, filename: str) -> None:
    from ..persistence.repositories import is_persistence_available, set_session_active_dataset

    if is_persistence_available():
        try:
            set_session_active_dataset(session_id, filename)
            return
        except Exception as e:
            print(f"⚠️ Failed to persist active dataset (using in-memory fallback): {e}")

    _active[session_id] = filename


def get_active_dataset(session_id: str) -> Optional[str]:
    from ..persistence.repositories import is_persistence_available, get_session_active_dataset

    if is_persistence_available():
        try:
            return get_session_active_dataset(session_id)
        except Exception as e:
            print(f"⚠️ Failed to read active dataset from persistence (using in-memory fallback): {e}")

    return _active.get(session_id)
