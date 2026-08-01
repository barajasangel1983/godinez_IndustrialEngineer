"""
Tests for the "load dataset" command feature:
  - src/tools/dataset_command.py — filename extraction regex
  - src/tools/data_paths.py — path resolution/safety helpers
  - src/graph/session_datasets.py — in-memory active-dataset store
  - src/graph/nodes/load_dataset.py — the analysis handler
  - csv_path/session_id wiring in src/api/app.py

These use the repo's real committed datasets (sample_production.csv,
synthetic_production.csv) rather than a patched DATA_DIR, since the
scenarios exercised here (load a real dataset, confirm it's picked up by
a follow-up query) are exactly what those files exist for.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import src.persistence.config as db_config
from src.persistence.models import Base
from src.tools.dataset_command import extract_dataset_filename, is_list_datasets_command
from src.tools.data_paths import resolve_csv_path, safe_data_path, DEFAULT_DATASET
from src.graph import session_datasets
from src.graph.nodes.load_dataset import load_dataset_node, list_datasets_node
from src.api.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_session_datasets():
    session_datasets._active.clear()
    yield
    session_datasets._active.clear()


# ═══════════════════════════════════════════════════════════════════
# Unit — filename extraction
# ═══════════════════════════════════════════════════════════════════

class TestExtractDatasetFilename:

    @pytest.mark.parametrize("query,expected", [
        ('Load dataset "synthetic_production.csv"', "synthetic_production.csv"),
        ("use dataset sample_production.csv", "sample_production.csv"),
        ("switch dataset to synthetic_production.csv", "synthetic_production.csv"),
        ("switch to dataset synthetic_production.csv", "synthetic_production.csv"),
        ("  load dataset   sample_production.csv  ", "sample_production.csv"),
    ])
    def test_recognized_phrasings(self, query, expected):
        assert extract_dataset_filename(query) == expected

    @pytest.mark.parametrize("query", [
        "What is the OEE trend?",
        "Show me bottleneck analysis",
        "load dataset ../../etc/passwd.csv",  # path separators rejected at regex level
        "load dataset notacsvfile",
    ])
    def test_non_matches_return_none(self, query):
        assert extract_dataset_filename(query) is None


class TestIsListDatasetsCommand:

    @pytest.mark.parametrize("query", [
        "list datasets",
        "List Datasets",
        "list the datasets",
        "show datasets",
        "show me the available datasets",
        "what datasets are available",
        "what datasets are available?",
        "available datasets",
    ])
    def test_recognized_phrasings(self, query):
        assert is_list_datasets_command(query) is True

    @pytest.mark.parametrize("query", [
        "What is our OEE?",
        'Load dataset "sample_production.csv"',
        "list the machines",
    ])
    def test_non_matches_return_false(self, query):
        assert is_list_datasets_command(query) is False


# ═══════════════════════════════════════════════════════════════════
# Unit — path resolution / safety
# ═══════════════════════════════════════════════════════════════════

class TestResolveCsvPath:

    def test_none_falls_back_to_default_dataset(self):
        result = resolve_csv_path(None)
        assert result.name == DEFAULT_DATASET

    def test_explicit_path_is_used_as_is(self):
        result = resolve_csv_path("/some/path/other.csv")
        assert str(result) == "/some/path/other.csv"


class TestSafeDataPath:

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            safe_data_path("../../etc/passwd.csv")

    def test_rejects_embedded_separator(self):
        with pytest.raises(ValueError):
            safe_data_path("subdir/file.csv")

    def test_accepts_plain_filename(self):
        result = safe_data_path("sample_production.csv")
        assert result.name == "sample_production.csv"


# ═══════════════════════════════════════════════════════════════════
# Unit — load_dataset_node
# ═══════════════════════════════════════════════════════════════════

class TestLoadDatasetNode:

    def test_missing_filename_returns_error(self):
        result = load_dataset_node({"entities": {}, "session_id": "s1", "errors": []})
        assert result["metadata"]["load_dataset"] == "missing_filename"

    def test_path_traversal_rejected(self):
        result = load_dataset_node({
            "entities": {"dataset_filename": "../../etc/passwd"},
            "session_id": "s1",
            "errors": [],
        })
        assert result["metadata"]["load_dataset"] == "invalid_filename"

    def test_nonexistent_file_lists_available_datasets(self):
        result = load_dataset_node({
            "entities": {"dataset_filename": "does_not_exist.csv"},
            "session_id": "s1",
            "errors": [],
        })
        assert result["metadata"]["load_dataset"] == "not_found"
        assert "sample_production.csv" in result["response"]

    def test_valid_file_activates_dataset_for_session(self):
        result = load_dataset_node({
            "entities": {"dataset_filename": "synthetic_production.csv"},
            "session_id": "session-abc",
            "errors": [],
        })
        assert result["metadata"]["load_dataset"] == "success"
        assert "Loaded dataset" in result["response"]
        assert session_datasets.get_active_dataset("session-abc") == "synthetic_production.csv"

    def test_valid_file_without_session_id_does_not_persist(self):
        result = load_dataset_node({
            "entities": {"dataset_filename": "synthetic_production.csv"},
            "session_id": None,
            "errors": [],
        })
        assert result["metadata"]["load_dataset"] == "success"
        assert session_datasets.get_active_dataset(None) is None


# ═══════════════════════════════════════════════════════════════════
# Unit — list_datasets_node
# ═══════════════════════════════════════════════════════════════════

class TestListDatasetsNode:

    def test_lists_committed_datasets(self):
        result = list_datasets_node({"session_id": "s1"})
        assert result["metadata"]["list_datasets"] == "success"
        assert "sample_production.csv" in result["response"]
        assert "synthetic_production.csv" in result["response"]

    def test_marks_default_as_active_when_nothing_loaded(self):
        result = list_datasets_node({"session_id": "never-loaded-session"})
        assert result["metadata"]["active_dataset"] == DEFAULT_DATASET
        assert f"{DEFAULT_DATASET} (active)" in result["response"]

    def test_marks_loaded_dataset_as_active(self):
        session_datasets.set_active_dataset("s-loaded", "synthetic_production.csv")
        result = list_datasets_node({"session_id": "s-loaded"})
        assert result["metadata"]["active_dataset"] == "synthetic_production.csv"
        assert "synthetic_production.csv (active)" in result["response"]

    def test_no_session_id_still_lists_with_default_active(self):
        result = list_datasets_node({"session_id": None})
        assert result["metadata"]["active_dataset"] == DEFAULT_DATASET


# ═══════════════════════════════════════════════════════════════════
# Integration — real graph, no LLM call needed for load_dataset intent
# ═══════════════════════════════════════════════════════════════════

class TestLoadDatasetEndToEnd:

    def test_load_dataset_command_via_api(self):
        resp = client.post("/api/query", json={
            "query": 'Load dataset "synthetic_production.csv"',
            "session_id": "e2e-session",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "load_dataset"
        assert "Loaded dataset" in body["response"]
        assert session_datasets.get_active_dataset("e2e-session") == "synthetic_production.csv"

    def test_load_dataset_rejects_unknown_file_via_api(self):
        resp = client.post("/api/query", json={
            "query": 'Load dataset "nonexistent_file.csv"',
            "session_id": "e2e-session-2",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "not found" in body["response"].lower()
        assert session_datasets.get_active_dataset("e2e-session-2") is None

    def test_list_datasets_command_via_api(self):
        resp = client.post("/api/query", json={
            "query": "List datasets",
            "session_id": "e2e-list-session",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "list_datasets"
        assert "sample_production.csv" in body["response"]
        assert "synthetic_production.csv" in body["response"]

    def test_list_datasets_reflects_prior_load_in_same_session(self):
        client.post("/api/query", json={
            "query": 'Load dataset "synthetic_production.csv"',
            "session_id": "e2e-list-session-2",
        })
        resp = client.post("/api/query", json={
            "query": "What datasets are available?",
            "session_id": "e2e-list-session-2",
        })
        assert resp.status_code == 200
        assert "synthetic_production.csv (active)" in resp.json()["response"]


# ═══════════════════════════════════════════════════════════════════
# Integration — csv_path/session_id wiring into initial_state
# ═══════════════════════════════════════════════════════════════════

def _mock_workflow_capturing_state(captured: dict):
    """Build a (workflow, obs_context) pair whose invoke() records initial_state."""
    def fake_invoke(initial_state):
        captured.update(initial_state)
        return {"response": "ok", "intent": "oee", "errors": [], "metadata": {}, "charts": None}

    mock_compiled = MagicMock()
    mock_compiled.invoke.side_effect = fake_invoke
    mock_workflow = MagicMock()
    mock_workflow.compile.return_value = mock_compiled
    mock_metrics = MagicMock()
    mock_metrics.get_summary.return_value = {}
    return mock_workflow, {"metrics": mock_metrics}


class TestCsvPathWiring:

    def test_followup_query_receives_loaded_csv_path(self):
        session_datasets.set_active_dataset("wiring-session", "synthetic_production.csv")
        captured = {}

        with patch("src.api.app.build_workflow", return_value=_mock_workflow_capturing_state(captured)):
            resp = client.post("/api/query", json={
                "query": "What is our OEE?",
                "session_id": "wiring-session",
            })

        assert resp.status_code == 200
        assert captured["session_id"] == "wiring-session"
        assert captured["csv_path"].endswith("synthetic_production.csv")

    def test_fresh_session_has_no_csv_path_override(self):
        captured = {}

        with patch("src.api.app.build_workflow", return_value=_mock_workflow_capturing_state(captured)):
            resp = client.post("/api/query", json={
                "query": "What is our OEE?",
                "session_id": "brand-new-session-never-loaded",
            })

        assert resp.status_code == 200
        assert captured["session_id"] == "brand-new-session-never-loaded"
        assert "csv_path" not in captured


# ═══════════════════════════════════════════════════════════════════
# Multi-worker regression — session_datasets must not rely solely on
# in-process memory when persistence is available (scripts/start.sh runs
# 2+ uvicorn workers by default once DATABASE_URL is a real database).
# ═══════════════════════════════════════════════════════════════════

class TestSessionDatasetsPersistenceBacked:

    @pytest.fixture(autouse=True)
    def _sqlite_engine(self, monkeypatch):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        monkeypatch.setattr(db_config, "_engine", engine)
        yield engine

    def test_survives_in_memory_dict_being_cleared(self):
        """Simulates a second worker process (which never saw the in-memory
        write) still resolving the correct active dataset via the DB."""
        session_datasets.set_active_dataset("multiworker-sess", "synthetic_production.csv")

        # A second uvicorn worker process would have its own empty _active
        # dict — simulate that here instead of spawning a real process.
        session_datasets._active.clear()

        assert session_datasets.get_active_dataset("multiworker-sess") == "synthetic_production.csv"

    def test_overwrite_is_visible_across_simulated_workers(self):
        session_datasets.set_active_dataset("multiworker-sess-2", "sample_production.csv")
        session_datasets._active.clear()
        session_datasets.set_active_dataset("multiworker-sess-2", "synthetic_production.csv")
        session_datasets._active.clear()
        assert session_datasets.get_active_dataset("multiworker-sess-2") == "synthetic_production.csv"

    def test_load_dataset_command_persists_across_simulated_worker(self):
        """End-to-end: the real load_dataset_node, then a simulated other
        worker still sees the change."""
        result = load_dataset_node({
            "entities": {"dataset_filename": "synthetic_production.csv"},
            "session_id": "multiworker-sess-3",
            "errors": [],
        })
        assert result["metadata"]["load_dataset"] == "success"

        session_datasets._active.clear()

        assert session_datasets.get_active_dataset("multiworker-sess-3") == "synthetic_production.csv"
