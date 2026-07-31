"""
Data upload API tests — POST /api/data, GET /api/data/list, DELETE /api/data/{filename}

All tests patch DATA_DIR so no files are written to the real data/ directory.
"""

import io
import csv as csv_module
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────

REQUIRED_COLUMNS = [
    "date", "shift", "machine_id", "planned_minutes", "actual_run_minutes",
    "downtime_minutes", "ideal_cycle_time_seconds", "total_count", "good_count",
    "downtime_reason",
]


def _make_csv(rows: list[dict] | None = None, columns: list[str] | None = None) -> bytes:
    """Build a minimal valid production CSV as bytes."""
    cols = columns or REQUIRED_COLUMNS
    default_rows = rows or [
        {
            "date": "2024-01-01", "shift": "A", "machine_id": "M1",
            "planned_minutes": "480", "actual_run_minutes": "420",
            "downtime_minutes": "60", "ideal_cycle_time_seconds": "30",
            "total_count": "800", "good_count": "792", "downtime_reason": "breakdown",
        }
    ]
    buf = io.StringIO()
    writer = csv_module.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for row in default_rows:
        writer.writerow({c: row.get(c, "0") for c in cols})
    return buf.getvalue().encode()


@pytest.fixture()
def data_dir(tmp_path):
    """Patch DATA_DIR in both data_routes and csv_reader to a temp directory."""
    import src.api.data_routes as dr
    import src.config as cfg
    original_dr = dr.DATA_DIR
    original_cfg = cfg.DATA_DIR
    dr.DATA_DIR = tmp_path
    cfg.DATA_DIR = tmp_path
    yield tmp_path
    dr.DATA_DIR = original_dr
    cfg.DATA_DIR = original_cfg


# ── POST /api/data ────────────────────────────────────────────────

class TestUploadDataset:
    def test_upload_valid_csv_returns_200(self, data_dir):
        content = _make_csv()
        resp = client.post(
            "/api/data",
            files={"file": ("production.csv", content, "text/csv")},
        )
        assert resp.status_code == 200

    def test_upload_returns_metadata(self, data_dir):
        content = _make_csv()
        resp = client.post(
            "/api/data",
            files={"file": ("production.csv", content, "text/csv")},
        )
        body = resp.json()
        assert body["row_count"] == 1
        assert "M1" in body["machine_ids"]
        assert body["date_range"] == ["2024-01-01", "2024-01-01"]
        assert "date" in body["columns"]

    def test_upload_saves_timestamped_file(self, data_dir):
        content = _make_csv()
        resp = client.post(
            "/api/data",
            files={"file": ("mydata.csv", content, "text/csv")},
        )
        saved_name = resp.json()["filename"]
        assert saved_name.startswith("mydata_")
        assert saved_name.endswith(".csv")
        assert (data_dir / saved_name).exists()

    def test_upload_non_csv_extension_rejected(self, data_dir):
        resp = client.post(
            "/api/data",
            files={"file": ("data.txt", b"col1,col2\n1,2\n", "text/plain")},
        )
        assert resp.status_code == 400
        assert "csv" in resp.json()["detail"].lower()

    def test_upload_missing_columns_rejected(self, data_dir):
        bad_content = b"col1,col2\n1,2\n"
        resp = client.post(
            "/api/data",
            files={"file": ("bad.csv", bad_content, "text/csv")},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "missing" in detail or "column" in detail

    def test_upload_empty_file_rejected(self, data_dir):
        resp = client.post(
            "/api/data",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert resp.status_code == 400

    def test_upload_size_limit_enforced(self, data_dir):
        import src.api.data_routes as dr
        oversized = b"x" * (dr.MAX_UPLOAD_BYTES + 1)
        resp = client.post(
            "/api/data",
            files={"file": ("huge.csv", oversized, "text/csv")},
        )
        assert resp.status_code == 413

    def test_upload_multiple_rows(self, data_dir):
        rows = [
            {"date": f"2024-01-0{i}", "shift": "A", "machine_id": f"M{i}",
             "planned_minutes": "480", "actual_run_minutes": "420",
             "downtime_minutes": "60", "ideal_cycle_time_seconds": "30",
             "total_count": "800", "good_count": "792", "downtime_reason": "setup"}
            for i in range(1, 4)
        ]
        content = _make_csv(rows=rows)
        resp = client.post(
            "/api/data",
            files={"file": ("multi.csv", content, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["row_count"] == 3
        assert len(body["machine_ids"]) == 3

    def test_upload_size_bytes_returned(self, data_dir):
        content = _make_csv()
        resp = client.post(
            "/api/data",
            files={"file": ("production.csv", content, "text/csv")},
        )
        assert resp.json()["size_bytes"] == len(content)


# ── GET /api/data/list ────────────────────────────────────────────

class TestListDatasets:
    def test_list_empty_directory(self, data_dir):
        resp = client.get("/api/data/list")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["datasets"] == []

    def test_list_returns_uploaded_file(self, data_dir):
        # Place a valid CSV directly in data_dir
        csv_path = data_dir / "sample.csv"
        csv_path.write_bytes(_make_csv())
        resp = client.get("/api/data/list")
        body = resp.json()
        assert body["total"] == 1
        assert body["datasets"][0]["filename"] == "sample.csv"

    def test_list_returns_metadata_for_valid_csv(self, data_dir):
        (data_dir / "prod.csv").write_bytes(_make_csv())
        resp = client.get("/api/data/list")
        ds = resp.json()["datasets"][0]
        assert ds["row_count"] == 1
        assert ds["machine_ids"] == ["M1"]
        assert ds["date_range"] == ["2024-01-01", "2024-01-01"]

    def test_list_returns_partial_info_for_unparseable_csv(self, data_dir):
        (data_dir / "corrupt.csv").write_bytes(b"garbage,data\n1,2\n")
        resp = client.get("/api/data/list")
        body = resp.json()
        assert body["total"] == 1
        ds = body["datasets"][0]
        assert ds["filename"] == "corrupt.csv"
        assert ds["size_bytes"] > 0
        # row_count absent or None — file couldn't be parsed
        assert ds.get("row_count") is None

    def test_list_multiple_files(self, data_dir):
        for name in ("a.csv", "b.csv", "c.csv"):
            (data_dir / name).write_bytes(_make_csv())
        resp = client.get("/api/data/list")
        assert resp.json()["total"] == 3

    def test_list_ignores_non_csv_files(self, data_dir):
        (data_dir / "notes.txt").write_text("ignore me")
        (data_dir / "real.csv").write_bytes(_make_csv())
        resp = client.get("/api/data/list")
        assert resp.json()["total"] == 1


# ── DELETE /api/data/{filename} ───────────────────────────────────

class TestDeleteDataset:
    def test_delete_existing_file(self, data_dir):
        (data_dir / "todelete.csv").write_bytes(_make_csv())
        resp = client.delete("/api/data/todelete.csv")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert not (data_dir / "todelete.csv").exists()

    def test_delete_returns_filename(self, data_dir):
        (data_dir / "file.csv").write_bytes(_make_csv())
        resp = client.delete("/api/data/file.csv")
        assert resp.json()["filename"] == "file.csv"

    def test_delete_nonexistent_returns_404(self, data_dir):
        resp = client.delete("/api/data/ghost.csv")
        assert resp.status_code == 404

    def test_delete_path_traversal_rejected(self, data_dir):
        resp = client.delete("/api/data/..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404)

    def test_delete_subpath_rejected(self, data_dir):
        import src.api.data_routes as dr
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            dr._safe_data_path("subdir/file.csv")
        assert exc.value.status_code == 400

    def test_delete_after_upload(self, data_dir):
        content = _make_csv()
        upload_resp = client.post(
            "/api/data",
            files={"file": ("upload.csv", content, "text/csv")},
        )
        saved_name = upload_resp.json()["filename"]
        del_resp = client.delete(f"/api/data/{saved_name}")
        assert del_resp.status_code == 200
        assert not (data_dir / saved_name).exists()
