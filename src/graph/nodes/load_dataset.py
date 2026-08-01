"""
Load Dataset Node — Handles the "load dataset <file>" and "list datasets"
system commands.

"load dataset" sets the requested CSV as the active dataset for the
current session (see src/graph/session_datasets.py). Every subsequent
query in that session picks it up via csv_path resolution in the other
analysis nodes. "list datasets" is read-only — it just reports what's
available in DATA_DIR and which one is currently active.
"""

from ..state import GodinezState
from ..session_datasets import set_active_dataset, get_active_dataset
from ...tools.csv_reader import read_production_csv, get_machine_ids, get_date_range
from ...tools.data_paths import safe_data_path, DEFAULT_DATASET
from ... import config


def load_dataset_node(state: GodinezState) -> dict:
    """Validate and activate the dataset named in the query, scoped to session_id."""

    filename = state.get("entities", {}).get("dataset_filename")
    session_id = state.get("session_id")
    errors = state.get("errors", [])

    if not filename:
        return {
            "response": "⚠️ No dataset filename found in the load command.",
            "errors": errors + ["load_dataset: missing filename"],
            "metadata": {"load_dataset": "missing_filename"},
        }

    try:
        target = safe_data_path(filename)
    except ValueError as exc:
        return {
            "response": f"⚠️ Invalid dataset filename '{filename}': {exc}",
            "errors": errors + [f"load_dataset: {exc}"],
            "metadata": {"load_dataset": "invalid_filename"},
        }

    if not target.exists():
        available = sorted(p.name for p in config.DATA_DIR.glob("*.csv"))
        listing = "\n".join(f"  - {name}" for name in available) or "  (none found)"
        return {
            "response": (
                f"⚠️ Dataset not found: {filename}\n\n"
                f"Available datasets in {config.DATA_DIR}:\n{listing}"
            ),
            "errors": errors + [f"load_dataset: file not found: {filename}"],
            "metadata": {"load_dataset": "not_found"},
        }

    try:
        rows = read_production_csv(target)
        date_range = get_date_range(rows)
        machine_ids = get_machine_ids(rows)
    except Exception as e:
        return {
            "response": f"⚠️ Failed to read dataset '{filename}': {e}",
            "errors": errors + [f"load_dataset: {e}"],
            "metadata": {"load_dataset": "read_error"},
        }

    if session_id:
        set_active_dataset(session_id, target.name)

    response = (
        f"✅ Loaded dataset: {target.name}\n"
        f"  - Rows: {len(rows)}\n"
        f"  - Date range: {date_range[0]} to {date_range[1]}\n"
        f"  - Machines: {', '.join(machine_ids) if machine_ids else 'none'}\n\n"
        f"This dataset will be used for the rest of this session."
    )

    return {
        "response": response,
        "metadata": {
            "load_dataset": "success",
            "active_dataset": target.name,
            "row_count": len(rows),
        },
    }


def list_datasets_node(state: GodinezState) -> dict:
    """List CSV datasets available in DATA_DIR, marking the session's active one."""

    session_id = state.get("session_id")
    active = get_active_dataset(session_id) if session_id else None
    active = active or DEFAULT_DATASET

    csv_files = sorted(config.DATA_DIR.glob("*.csv"))
    if not csv_files:
        return {
            "response": f"No datasets found in {config.DATA_DIR}.",
            "metadata": {"list_datasets": "empty"},
        }

    lines = []
    for path in csv_files:
        marker = " (active)" if path.name == active else ""
        try:
            rows = read_production_csv(path)
            start, end = get_date_range(rows)
            lines.append(f"  - {path.name}{marker} — {len(rows)} rows, {start} to {end}")
        except Exception:
            lines.append(f"  - {path.name}{marker} — (unparseable)")

    response = f"📁 Available datasets ({len(csv_files)}):\n" + "\n".join(lines)

    return {
        "response": response,
        "metadata": {
            "list_datasets": "success",
            "dataset_count": len(csv_files),
            "active_dataset": active,
        },
    }
