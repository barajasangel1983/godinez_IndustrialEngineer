"""
Data Paths — Shared filesystem safety helpers for dataset files.
"""

from pathlib import Path
from typing import Optional

from .. import config

DEFAULT_DATASET = "sample_production.csv"


def resolve_csv_path(csv_path: Optional[str]) -> Path:
    """Resolve a state's csv_path to a Path, falling back to the default dataset."""
    return Path(csv_path) if csv_path else config.DATA_DIR / DEFAULT_DATASET


def safe_data_path(filename: str) -> Path:
    """Resolve filename to an absolute path inside DATA_DIR; reject traversal attempts.

    Raises ValueError if filename contains path separators or resolves
    outside DATA_DIR.
    """
    safe_name = Path(filename).name
    if safe_name != filename:
        raise ValueError("Filename must not contain path separators")
    target = (config.DATA_DIR / safe_name).resolve()
    if not str(target).startswith(str(config.DATA_DIR.resolve())):
        raise ValueError("Invalid filename")
    return target
