"""
Load Dataset Node — Handles the "load dataset <file>" system command.

Sets the requested CSV as the active dataset for the current session (see
src/graph/session_datasets.py). Every subsequent query in that session
picks it up via csv_path resolution in the other analysis nodes.
"""

from ..state import GodinezState
from ..session_datasets import set_active_dataset
from ...tools.csv_reader import read_production_csv, get_machine_ids, get_date_range
from ...tools.data_paths import safe_data_path
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
