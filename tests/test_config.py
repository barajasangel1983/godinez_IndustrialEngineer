"""
Configuration loader tests — src/config/loader.py and src/config/__init__.py

Tests use Config.load(_config_path=...) to isolate the JSON file path,
and monkeypatch.setenv / monkeypatch.delenv for env var isolation.
"""

import json
import pytest
from pathlib import Path
from dataclasses import FrozenInstanceError

from src.config.loader import (
    Config,
    DatabaseConfig,
    LLMConfig,
    OEEConfig,
    BottleneckConfig,
    CostConfig,
    GraphConfig,
)


# ── Helpers ───────────────────────────────────────────────────────

def _write_json(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / ".godinez_config.json"
    p.write_text(json.dumps(data))
    return p


def _load_clean(tmp_path: Path, monkeypatch, data: dict | None = None) -> Config:
    """Load config using a temp json path, no real .godinez_config.json interference."""
    if data is not None:
        cfg_path = _write_json(tmp_path, data)
    else:
        cfg_path = tmp_path / "missing.json"  # does not exist → no overrides
    # Clear any relevant env vars that might bleed from the test environment
    for key in (
        "CONFIG_FILE", "DATABASE_URL", "LLM_MODEL", "LLM_TEMPERATURE",
        "OEE_CRITICAL", "OEE_NEEDS_IMPROVEMENT", "OEE_GOOD", "OEE_WORLD_CLASS",
        "BOTTLENECK_CRITICAL", "BOTTLENECK_HIGH", "BOTTLENECK_MEDIUM",
        "COST_SCRAP_PER_UNIT", "COST_REWORK_PER_HOUR", "COST_DOWNTIME_PER_HOUR", "COST_DEFECT_PER_UNIT",
        "MAX_ITERATIONS", "GRAPH_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)
    return Config.load(_config_path=cfg_path)


# ── Default values ────────────────────────────────────────────────

class TestDefaults:
    def test_llm_defaults(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.llm.model == "gpt-4o-mini"
        assert cfg.llm.temperature == 0.0

    def test_oee_defaults(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.oee.critical == 60.0
        assert cfg.oee.needs_improvement == 75.0
        assert cfg.oee.good == 85.0
        assert cfg.oee.world_class == 90.0

    def test_bottleneck_defaults(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.bottleneck.severity_critical == 30
        assert cfg.bottleneck.severity_high == 20
        assert cfg.bottleneck.severity_medium == 10

    def test_cost_defaults(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.cost.scrap_per_unit == 25.00
        assert cfg.cost.rework_per_hour == 45.00
        assert cfg.cost.downtime_per_hour == 150.00
        assert cfg.cost.defect_per_unit == 5.00

    def test_graph_defaults(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.graph.max_iterations == 10
        assert cfg.graph.timeout == 120

    def test_database_default(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.database.url == "off"


# ── JSON config file overrides ────────────────────────────────────

class TestJsonConfigOverrides:
    def test_llm_model_override(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch, {"llm": {"model": "gpt-4o"}})
        assert cfg.llm.model == "gpt-4o"

    def test_llm_temperature_override(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch, {"llm": {"temperature": 0.7}})
        assert cfg.llm.temperature == 0.7

    def test_oee_partial_override(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch, {"oee_thresholds": {"critical": 55.0}})
        assert cfg.oee.critical == 55.0
        assert cfg.oee.needs_improvement == 75.0  # unchanged

    def test_oee_full_override(self, tmp_path, monkeypatch):
        data = {"oee_thresholds": {"critical": 50.0, "needs_improvement": 70.0, "good": 82.0, "world_class": 95.0}}
        cfg = _load_clean(tmp_path, monkeypatch, data)
        assert cfg.oee.critical == 50.0
        assert cfg.oee.world_class == 95.0

    def test_bottleneck_override(self, tmp_path, monkeypatch):
        data = {"bottleneck": {"severity_critical": 40, "severity_high": 25, "severity_medium": 15}}
        cfg = _load_clean(tmp_path, monkeypatch, data)
        assert cfg.bottleneck.severity_critical == 40

    def test_cost_override(self, tmp_path, monkeypatch):
        data = {"cost": {"scrap_per_unit": 30.0, "downtime_per_hour": 200.0}}
        cfg = _load_clean(tmp_path, monkeypatch, data)
        assert cfg.cost.scrap_per_unit == 30.0
        assert cfg.cost.downtime_per_hour == 200.0
        assert cfg.cost.rework_per_hour == 45.0  # unchanged

    def test_database_url_override(self, tmp_path, monkeypatch):
        data = {"database": {"url": "sqlite:///data/test.db"}}
        cfg = _load_clean(tmp_path, monkeypatch, data)
        assert cfg.database.url == "sqlite:///data/test.db"

    def test_corrupt_json_falls_back_to_defaults(self, tmp_path, monkeypatch):
        (tmp_path / ".godinez_config.json").write_text("{invalid json")
        for key in ("LLM_MODEL", "LLM_TEMPERATURE"):
            monkeypatch.delenv(key, raising=False)
        cfg = Config.load(_config_path=tmp_path / ".godinez_config.json")
        assert cfg.llm.model == "gpt-4o-mini"

    def test_missing_json_falls_back_to_defaults(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.llm.model == "gpt-4o-mini"


# ── CONFIG_FILE env var ───────────────────────────────────────────

class TestConfigFileEnvVar:
    def test_config_file_env_overrides_json(self, tmp_path, monkeypatch):
        primary = _write_json(tmp_path, {"llm": {"model": "gpt-4o-mini"}})
        secondary = tmp_path / "override.json"
        secondary.write_text(json.dumps({"llm": {"model": "gpt-4-turbo"}}))
        monkeypatch.setenv("CONFIG_FILE", str(secondary))
        for key in ("LLM_MODEL", "LLM_TEMPERATURE"):
            monkeypatch.delenv(key, raising=False)
        cfg = Config.load(_config_path=primary)
        assert cfg.llm.model == "gpt-4-turbo"

    def test_missing_config_file_env_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nonexistent.json"))
        cfg = _load_clean(tmp_path, monkeypatch)
        assert cfg.llm.model == "gpt-4o-mini"


# ── Individual env var overrides ──────────────────────────────────

class TestEnvVarOverrides:
    def test_llm_model_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.llm.model == "gpt-4o"

    def test_llm_temperature_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "1.2")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.llm.temperature == pytest.approx(1.2)

    def test_database_url_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.database.url == "postgresql://localhost/test"

    def test_oee_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OEE_CRITICAL", "55.0")
        monkeypatch.setenv("OEE_GOOD", "88.0")
        for k in ("OEE_NEEDS_IMPROVEMENT", "OEE_WORLD_CLASS", "CONFIG_FILE"):
            monkeypatch.delenv(k, raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.oee.critical == 55.0
        assert cfg.oee.good == 88.0
        assert cfg.oee.needs_improvement == 75.0  # unchanged

    def test_bottleneck_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BOTTLENECK_CRITICAL", "35")
        monkeypatch.setenv("BOTTLENECK_HIGH", "22")
        monkeypatch.setenv("BOTTLENECK_MEDIUM", "12")
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.bottleneck.severity_critical == 35
        assert cfg.bottleneck.severity_high == 22
        assert cfg.bottleneck.severity_medium == 12

    def test_cost_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COST_SCRAP_PER_UNIT", "30.0")
        monkeypatch.setenv("COST_DOWNTIME_PER_HOUR", "200.0")
        for k in ("COST_REWORK_PER_HOUR", "COST_DEFECT_PER_UNIT", "CONFIG_FILE"):
            monkeypatch.delenv(k, raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.cost.scrap_per_unit == 30.0
        assert cfg.cost.downtime_per_hour == 200.0

    def test_graph_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MAX_ITERATIONS", "5")
        monkeypatch.setenv("GRAPH_TIMEOUT", "60")
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.graph.max_iterations == 5
        assert cfg.graph.timeout == 60

    def test_env_vars_override_json_config(self, tmp_path, monkeypatch):
        cfg_path = _write_json(tmp_path, {"llm": {"model": "gpt-4o-mini"}})
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=cfg_path)
        assert cfg.llm.model == "gpt-4o"


# ── Validation ────────────────────────────────────────────────────

class TestValidation:
    def test_temperature_too_low_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "-0.1")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        with pytest.raises(ValueError, match="temperature"):
            Config.load(_config_path=tmp_path / "missing.json")

    def test_temperature_too_high_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "2.1")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        with pytest.raises(ValueError, match="temperature"):
            Config.load(_config_path=tmp_path / "missing.json")

    def test_temperature_boundary_zero_ok(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "0.0")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.llm.temperature == 0.0

    def test_temperature_boundary_two_ok(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LLM_TEMPERATURE", "2.0")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        cfg = Config.load(_config_path=tmp_path / "missing.json")
        assert cfg.llm.temperature == 2.0

    def test_oee_not_ascending_raises(self, tmp_path, monkeypatch):
        data = {"oee_thresholds": {"critical": 80.0, "needs_improvement": 70.0, "good": 85.0, "world_class": 90.0}}
        with pytest.raises(ValueError, match="ascending"):
            _load_clean(tmp_path, monkeypatch, data)

    def test_oee_equal_values_raises(self, tmp_path, monkeypatch):
        data = {"oee_thresholds": {"critical": 75.0, "needs_improvement": 75.0, "good": 85.0, "world_class": 90.0}}
        with pytest.raises(ValueError, match="ascending"):
            _load_clean(tmp_path, monkeypatch, data)

    def test_graph_max_iterations_zero_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MAX_ITERATIONS", "0")
        monkeypatch.delenv("GRAPH_TIMEOUT", raising=False)
        monkeypatch.delenv("CONFIG_FILE", raising=False)
        with pytest.raises(ValueError, match="max_iterations"):
            Config.load(_config_path=tmp_path / "missing.json")


# ── Frozen / immutable ────────────────────────────────────────────

class TestFrozenConfig:
    def test_config_is_frozen(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        with pytest.raises(FrozenInstanceError):
            cfg.llm = LLMConfig(model="changed")  # type: ignore[misc]

    def test_nested_config_is_frozen(self, tmp_path, monkeypatch):
        cfg = _load_clean(tmp_path, monkeypatch)
        with pytest.raises(FrozenInstanceError):
            cfg.llm.model = "changed"  # type: ignore[misc]


# ── Backward-compat imports ───────────────────────────────────────

class TestBackwardCompatImports:
    def test_flat_constants_importable(self):
        import src.config as cfg_mod
        assert hasattr(cfg_mod, "LLM_MODEL")
        assert hasattr(cfg_mod, "LLM_TEMPERATURE")
        assert hasattr(cfg_mod, "OEE_THRESHOLDS")
        assert hasattr(cfg_mod, "MAX_ITERATIONS")
        assert hasattr(cfg_mod, "GRAPH_TIMEOUT")

    def test_path_constants_importable(self):
        from src.config import BASE_DIR, DATA_DIR, KNOWLEDGE_DIR, TEST_DATA_DIR
        assert BASE_DIR.exists()
        assert DATA_DIR.exists()

    def test_oee_thresholds_is_dict(self):
        from src.config import OEE_THRESHOLDS
        assert isinstance(OEE_THRESHOLDS, dict)
        assert "critical" in OEE_THRESHOLDS
        assert "world_class" in OEE_THRESHOLDS

    def test_load_json_config_returns_dict(self):
        import src.config as cfg_mod
        result = cfg_mod._load_json_config()
        assert isinstance(result, dict)

    def test_config_file_patchable(self, tmp_path, monkeypatch):
        """test_cli.py compatibility: patching _CONFIG_FILE changes _load_json_config output."""
        config_data = {"oee_thresholds": {"critical": 55.0}}
        config_file = tmp_path / ".godinez_config.json"
        config_file.write_text(json.dumps(config_data))

        import src.config as cfg_mod
        monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_file)
        overrides = cfg_mod._load_json_config()
        assert overrides["oee_thresholds"]["critical"] == 55.0

    def test_config_instance_exported(self):
        from src.config import config
        assert isinstance(config, Config)
        assert isinstance(config.llm, LLMConfig)
