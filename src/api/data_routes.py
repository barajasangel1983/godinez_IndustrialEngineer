"""
Godínez IndustrialEngineer — Data Upload API Routes

Endpoints:
    POST   /api/data              — Upload a production CSV
    GET    /api/data/list         — List available datasets
    DELETE /api/data/{filename}   — Remove a dataset
"""

import csv as csv_module
import io
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.config import DATA_DIR
from src.tools.csv_reader import read_production_csv, get_machine_ids, get_date_range

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

router = APIRouter(prefix="/api/data", tags=["Data"])


# ── Response models ───────────────────────────────────────────────

class DatasetInfo(BaseModel):
    filename: str
    size_bytes: int
    row_count: Optional[int] = None
    columns: Optional[list[str]] = None
    date_range: Optional[tuple[str, str]] = None
    machine_ids: Optional[list[str]] = None


class DataUploadResponse(DatasetInfo):
    saved_path: str


class DataListResponse(BaseModel):
    datasets: list[DatasetInfo]
    total: int


class DeleteResponse(BaseModel):
    success: bool
    filename: str


# ── Helpers ───────────────────────────────────────────────────────

def _timestamped_name(original_filename: str) -> str:
    stem = Path(original_filename).stem
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{ts}.csv"


def _safe_data_path(filename: str) -> Path:
    """Resolve filename to an absolute path inside DATA_DIR; reject traversal attempts."""
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Filename must not contain path separators")
    target = (DATA_DIR / safe_name).resolve()
    # Confirm the resolved path is still inside DATA_DIR
    if not str(target).startswith(str(DATA_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return target


def _dataset_info(path: Path) -> DatasetInfo:
    """Build a DatasetInfo for a file; metadata is best-effort."""
    info = DatasetInfo(
        filename=path.name,
        size_bytes=path.stat().st_size,
    )
    try:
        rows = read_production_csv(path)
        # Read raw headers separately (read_production_csv only returns mapped keys)
        with open(path, newline="") as f:
            columns = list(csv_module.DictReader(f).fieldnames or [])
        info.row_count = len(rows)
        info.columns = columns
        info.date_range = get_date_range(rows)
        info.machine_ids = get_machine_ids(rows)
    except Exception:
        pass  # Return partial info if file can't be parsed
    return info


# ── Routes ───────────────────────────────────────────────────────

@router.post(
    "",
    response_model=DataUploadResponse,
    responses={
        400: {"description": "Not a CSV or missing required columns"},
        413: {"description": "File exceeds 50 MB size limit"},
    },
    summary="Upload a production CSV dataset",
)
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a CSV file to the data directory.

    - Must have a `.csv` extension.
    - Must contain all required production columns.
    - Size limit: 50 MB.
    - Saved with a timestamped filename to avoid collisions.

    Returns the saved filename, row count, column list, date range,
    and machine IDs extracted from the file.
    """
    # ── Extension check ───────────────────────────────────────
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must have a .csv extension")

    # ── Size check ────────────────────────────────────────────
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content):,} bytes). Maximum is 50 MB.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── Parse columns from header ─────────────────────────────
    text = content.decode("utf-8", errors="replace")
    raw_reader = csv_module.DictReader(io.StringIO(text))
    columns = list(raw_reader.fieldnames or [])
    if not columns:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    # ── Validate required columns via csv_reader ──────────────
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        rows = read_production_csv(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {exc}")
    finally:
        os.unlink(tmp_path)

    # ── Save with timestamped name ────────────────────────────
    dest_name = _timestamped_name(file.filename)
    dest_path = DATA_DIR / dest_name
    dest_path.write_bytes(content)

    return DataUploadResponse(
        filename=dest_name,
        saved_path=str(dest_path),
        size_bytes=len(content),
        row_count=len(rows),
        columns=columns,
        date_range=get_date_range(rows),
        machine_ids=get_machine_ids(rows),
    )


@router.get(
    "/list",
    response_model=DataListResponse,
    summary="List available datasets",
)
def list_datasets():
    """
    List all CSV datasets in the data directory.

    Returns filename, size, and best-effort metadata (row count,
    columns, date range, machine IDs) for each file.
    """
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    datasets = [_dataset_info(p) for p in csv_files]
    return DataListResponse(datasets=datasets, total=len(datasets))


@router.delete(
    "/{filename}",
    response_model=DeleteResponse,
    responses={
        400: {"description": "Invalid filename"},
        404: {"description": "Dataset not found"},
    },
    summary="Delete a dataset",
)
def delete_dataset(filename: str):
    """
    Delete a dataset from the data directory.

    Only filenames (no path components) are accepted.
    """
    target = _safe_data_path(filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found: {filename}")
    target.unlink()
    return DeleteResponse(success=True, filename=filename)
