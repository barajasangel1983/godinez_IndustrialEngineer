"""
CLI subcommand tests — exercises all five commands via their handler functions
without invoking the full workflow (LLM is mocked by conftest.py).
"""

import json
import os
import sys
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────

def _make_args(**kwargs):
    """Build a SimpleNamespace args object for CLI handler testing."""
    from types import SimpleNamespace
    return SimpleNamespace(**kwargs)


# ── analyze command ───────────────────────────────────────────────

class TestAnalyzeCommand:
    def test_analyze_returns_dict_with_required_keys(self):
        from src.cli.commands.analyze import analyze
        args = _make_args(query="What is our OEE?", session="test-cli-01", trace=False)
        result = analyze(args)
        assert "session_id" in result
        assert "query" in result
        assert "intent" in result
        assert "response" in result

    def test_analyze_uses_provided_session_id(self):
        from src.cli.commands.analyze import analyze
        args = _make_args(query="OEE report", session="my-session-123", trace=False)
        result = analyze(args)
        assert result["session_id"] == "my-session-123"

    def test_analyze_generates_session_id_when_empty(self):
        from src.cli.commands.analyze import analyze
        args = _make_args(query="Show bottleneck", session="", trace=False)
        result = analyze(args)
        assert result["session_id"]  # auto-generated UUID

    def test_analyze_response_is_string(self):
        from src.cli.commands.analyze import analyze
        args = _make_args(query="What are our costs?", session="", trace=False)
        result = analyze(args)
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    def test_analyze_execution_summary_present(self):
        from src.cli.commands.analyze import analyze
        args = _make_args(query="trend analysis", session="", trace=False)
        result = analyze(args)
        assert "execution_summary" in result
        assert isinstance(result["execution_summary"], dict)


# ── config command ────────────────────────────────────────────────

class TestConfigCommand:
    @pytest.fixture(autouse=True)
    def _restore_database_url_env(self):
        # config_set("database.url", ...) sets os.environ["DATABASE_URL"] as a
        # real side effect (src/cli/commands/config.py:132) so persistence
        # picks up the change immediately — restore it after each test so a
        # leaked postgresql:// URL doesn't break later tests hitting /api/query.
        original = os.environ.get("DATABASE_URL")
        yield
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original

    def test_config_show_runs_without_error(self, capsys):
        from src.cli.commands.config import config_show
        config_show()
        out = capsys.readouterr().out
        assert "OEE" in out
        assert "LLM" in out

    def test_config_show_displays_thresholds(self, capsys):
        from src.cli.commands.config import config_show
        config_show()
        out = capsys.readouterr().out
        assert "Critical" in out
        assert "World Class" in out

    def test_config_set_writes_json_file(self, tmp_path):
        from src.cli.commands import config as config_module
        config_file = tmp_path / ".godinez_config.json"
        with patch.object(config_module, "_config_file_path", return_value=str(config_file)):
            config_module.config_set("oee_thresholds.critical", "55")
        data = json.loads(config_file.read_text())
        assert data["oee_thresholds"]["critical"] == 55

    def test_config_set_database_url(self, tmp_path):
        from src.cli.commands import config as config_module
        config_file = tmp_path / ".godinez_config.json"
        with patch.object(config_module, "_config_file_path", return_value=str(config_file)):
            config_module.config_set("database.url", "sqlite:///test.db")
        data = json.loads(config_file.read_text())
        assert data["database"]["url"] == "sqlite:///test.db"

    def test_config_set_database_url_accepts_off(self, tmp_path):
        from src.cli.commands import config as config_module
        config_file = tmp_path / ".godinez_config.json"
        with patch.object(config_module, "_config_file_path", return_value=str(config_file)):
            config_module.config_set("database.url", "off")
        data = json.loads(config_file.read_text())
        assert data["database"]["url"] == "off"

    def test_config_set_database_url_accepts_postgresql(self, tmp_path):
        from src.cli.commands import config as config_module
        config_file = tmp_path / ".godinez_config.json"
        with patch.object(config_module, "_config_file_path", return_value=str(config_file)):
            config_module.config_set("database.url", "postgresql://user:pass@localhost/godinez")
        data = json.loads(config_file.read_text())
        assert data["database"]["url"].startswith("postgresql://")

    def test_config_dispatcher_show(self, capsys):
        from src.cli.commands.config import config
        args = _make_args(show=True, config_args=[])
        config(args)
        out = capsys.readouterr().out
        assert "OEE" in out

    def test_config_dispatcher_set(self, tmp_path):
        from src.cli.commands import config as config_module
        config_file = tmp_path / ".godinez_config.json"
        args = _make_args(show=False, config_args=["set", "oee_thresholds.good", "88"])
        with patch.object(config_module, "_config_file_path", return_value=str(config_file)):
            config_module.config(args)
        data = json.loads(config_file.read_text())
        assert data["oee_thresholds"]["good"] == 88

    def test_config_dispatcher_default_shows(self, capsys):
        from src.cli.commands.config import config
        args = _make_args(show=False, config_args=[])
        config(args)
        out = capsys.readouterr().out
        assert "LLM" in out


# ── data command ──────────────────────────────────────────────────

class TestDataCommand:
    def test_data_list_runs_without_error(self, capsys):
        from src.cli.commands.data import data_list
        data_list()
        out = capsys.readouterr().out
        # Either shows datasets or "No datasets found"
        assert ("datasets" in out.lower() or "data" in out.lower())

    def test_data_list_shows_sample_file(self, capsys):
        from src.cli.commands.data import data_list
        data_list()
        out = capsys.readouterr().out
        assert "production" in out.lower()

    def test_data_import_validates_missing_columns(self, tmp_path, capsys):
        from src.cli.commands.data import data_import
        # Source CSV has missing required columns; data dir is a separate tmp dir
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        bad_csv = src_dir / "bad.csv"
        bad_csv.write_text("col1,col2\n1,2\n")
        args = _make_args(file=str(bad_csv), type="production", overwrite=False)
        with patch("src.cli.commands.data.DATA_DIR", data_dir):
            data_import(args)
        out = capsys.readouterr().out
        assert "missing" in out.lower() or "failed" in out.lower()

    def test_data_import_valid_production_csv(self, tmp_path, capsys):
        from src.cli.commands.data import data_import
        sample = Path(__file__).resolve().parent.parent / "data" / "sample_production.csv"
        if not sample.exists():
            pytest.skip("sample_production.csv not found")

        dest_data_dir = tmp_path / "data"
        dest_data_dir.mkdir()
        args = _make_args(file=str(sample), type="production", overwrite=True)

        with patch("src.cli.commands.data.DATA_DIR", dest_data_dir):
            data_import(args)

        out = capsys.readouterr().out
        assert "imported" in out.lower() or "records" in out.lower()

    def test_data_command_dispatches_list(self, capsys):
        from src.cli.commands.data import data
        args = _make_args(list=True, file=None, type="production", overwrite=False)
        data(args)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_data_command_dispatches_import_missing_file(self, capsys):
        from src.cli.commands.data import data
        args = _make_args(list=False, file="/nonexistent/file.csv", type="production", overwrite=False)
        data(args)
        out = capsys.readouterr().out
        assert "not found" in out.lower()


# ── server command ────────────────────────────────────────────────

class TestServerCommand:
    def test_server_calls_uvicorn_run(self):
        from src.cli.commands.server import server
        args = _make_args(host="127.0.0.1", port=9999, reload=False)
        with patch("uvicorn.run") as mock_run:
            server(args)
            mock_run.assert_called_once_with(
                "src.api.app:app",
                host="127.0.0.1",
                port=9999,
                reload=False,
            )

    def test_server_uses_default_host_and_port(self):
        from src.cli.commands.server import server
        args = _make_args(host=None, port=None, reload=False)
        with patch("uvicorn.run") as mock_run:
            server(args)
            call_kwargs = mock_run.call_args
            assert call_kwargs[1]["host"] == "0.0.0.0"
            assert call_kwargs[1]["port"] == 8000


# ── CLI parser ────────────────────────────────────────────────────

class TestCliParser:
    def test_analyze_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["analyze", "What is OEE?"])
        assert args.command == "analyze"
        assert args.query == "What is OEE?"
        assert args.trace is False

    def test_analyze_with_flags(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["analyze", "query", "--session", "s1", "--trace"])
        assert args.session == "s1"
        assert args.trace is True

    def test_report_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["report", "--session", "abc-123"])
        assert args.command == "report"
        assert args.session == "abc-123"

    def test_report_format_json(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["report", "--session", "s1", "--format", "json"])
        assert args.format == "json"

    def test_data_list_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["data", "--list"])
        assert args.command == "data"
        assert args.list is True

    def test_data_import_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["data", "--file", "prod.csv", "--type", "production"])
        assert args.file == "prod.csv"
        assert args.type == "production"

    def test_config_show_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["config", "--show"])
        assert args.command == "config"
        assert args.show is True

    def test_config_set_positional_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["config", "set", "oee_thresholds.critical", "55"])
        assert args.config_args == ["set", "oee_thresholds.critical", "55"]

    def test_server_parsed(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["server"])
        assert args.command == "server"

    def test_server_with_flags(self):
        from src.cli.main import create_parser
        parser = create_parser()
        args = parser.parse_args(["server", "--host", "127.0.0.1", "--port", "9000", "--reload"])
        assert args.host == "127.0.0.1"
        assert args.port == 9000
        assert args.reload is True


# ── config.py override loading ────────────────────────────────────

class TestConfigOverrides:
    def test_oee_threshold_override_applied(self, tmp_path, monkeypatch):
        config_data = {"oee_thresholds": {"critical": 55.0, "good": 88.0}}
        config_file = tmp_path / ".godinez_config.json"
        config_file.write_text(json.dumps(config_data))

        import src.config as cfg_module
        monkeypatch.setattr(cfg_module, "_CONFIG_FILE", config_file)

        overrides = cfg_module._load_json_config()
        assert overrides["oee_thresholds"]["critical"] == 55.0

    def test_load_json_config_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        import src.config as cfg_module
        monkeypatch.setattr(cfg_module, "_CONFIG_FILE", tmp_path / "missing.json")
        assert cfg_module._load_json_config() == {}

    def test_load_json_config_handles_corrupt_file(self, tmp_path, monkeypatch):
        bad_file = tmp_path / ".godinez_config.json"
        bad_file.write_text("{invalid json")
        import src.config as cfg_module
        monkeypatch.setattr(cfg_module, "_CONFIG_FILE", bad_file)
        assert cfg_module._load_json_config() == {}
