"""
Godínez IndustrialEngineer — Configuration Loader

Frozen dataclass Config with Config.load() classmethod.
Load order: defaults → .godinez_config.json → CONFIG_FILE env var → individual env vars
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "src" / "knowledge"
TEST_DATA_DIR = DATA_DIR / "test"

_DEFAULT_JSON_CONFIG = BASE_DIR / ".godinez_config.json"


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = "off"


@dataclass(frozen=True)
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.0


@dataclass(frozen=True)
class OEEConfig:
    critical: float = 60.0
    needs_improvement: float = 75.0
    good: float = 85.0
    world_class: float = 90.0


@dataclass(frozen=True)
class BottleneckConfig:
    severity_critical: int = 30
    severity_high: int = 20
    severity_medium: int = 10


@dataclass(frozen=True)
class CostConfig:
    scrap_per_unit: float = 25.00
    rework_per_hour: float = 45.00
    downtime_per_hour: float = 150.00
    defect_per_unit: float = 5.00


@dataclass(frozen=True)
class GraphConfig:
    max_iterations: int = 10
    timeout: int = 120


@dataclass(frozen=True)
class Config:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    oee: OEEConfig = field(default_factory=OEEConfig)
    bottleneck: BottleneckConfig = field(default_factory=BottleneckConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)

    @classmethod
    def load(cls, _config_path: "Path | None" = None) -> "Config":
        """
        Load configuration with precedence (highest wins):
          defaults → .godinez_config.json → CONFIG_FILE env var → individual env vars
        """
        db_kw: dict = {}
        llm_kw: dict = {}
        oee_kw: dict = {}
        bn_kw: dict = {}
        cost_kw: dict = {}
        graph_kw: dict = {}

        json_path = _config_path if _config_path is not None else _DEFAULT_JSON_CONFIG
        _apply_json_file(json_path, db_kw, llm_kw, oee_kw, bn_kw, cost_kw, graph_kw)

        config_file_env = os.environ.get("CONFIG_FILE")
        if config_file_env:
            _apply_json_file(Path(config_file_env), db_kw, llm_kw, oee_kw, bn_kw, cost_kw, graph_kw)

        _apply_env_vars(db_kw, llm_kw, oee_kw, bn_kw, cost_kw, graph_kw)

        llm = LLMConfig(**llm_kw)
        _validate_llm(llm)
        oee = OEEConfig(**oee_kw)
        _validate_oee(oee)
        graph = GraphConfig(**graph_kw)
        _validate_graph(graph)

        return cls(
            database=DatabaseConfig(**db_kw),
            llm=llm,
            oee=oee,
            bottleneck=BottleneckConfig(**bn_kw),
            cost=CostConfig(**cost_kw),
            graph=graph,
        )


def read_json_file(path: Path) -> dict:
    """Read a JSON file, returning {} on any error."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _apply_json_file(path: Path, db_kw, llm_kw, oee_kw, bn_kw, cost_kw, graph_kw):
    data = read_json_file(path)
    if not data:
        return

    if "database" in data:
        d = data["database"]
        if "url" in d:
            db_kw["url"] = str(d["url"])

    if "llm" in data:
        d = data["llm"]
        if "model" in d:
            llm_kw["model"] = str(d["model"])
        if "temperature" in d:
            try:
                llm_kw["temperature"] = float(d["temperature"])
            except (TypeError, ValueError):
                pass

    if "oee_thresholds" in data:
        d = data["oee_thresholds"]
        for key in ("critical", "needs_improvement", "good", "world_class"):
            if key in d:
                try:
                    oee_kw[key] = float(d[key])
                except (TypeError, ValueError):
                    pass

    if "bottleneck" in data:
        d = data["bottleneck"]
        for attr, aliases in (
            ("severity_critical", ("severity_critical", "critical")),
            ("severity_high", ("severity_high", "high")),
            ("severity_medium", ("severity_medium", "medium")),
        ):
            for alias in aliases:
                if alias in d:
                    try:
                        bn_kw[attr] = int(d[alias])
                    except (TypeError, ValueError):
                        pass
                    break

    if "cost" in data:
        d = data["cost"]
        for key in ("scrap_per_unit", "rework_per_hour", "downtime_per_hour", "defect_per_unit"):
            if key in d:
                try:
                    cost_kw[key] = float(d[key])
                except (TypeError, ValueError):
                    pass

    if "graph" in data:
        d = data["graph"]
        if "max_iterations" in d:
            try:
                graph_kw["max_iterations"] = int(d["max_iterations"])
            except (TypeError, ValueError):
                pass
        if "timeout" in d:
            try:
                graph_kw["timeout"] = int(d["timeout"])
            except (TypeError, ValueError):
                pass


def _apply_env_vars(db_kw, llm_kw, oee_kw, bn_kw, cost_kw, graph_kw):
    if v := os.environ.get("DATABASE_URL"):
        db_kw["url"] = v

    if v := os.environ.get("LLM_MODEL"):
        llm_kw["model"] = v
    if v := os.environ.get("LLM_TEMPERATURE"):
        try:
            llm_kw["temperature"] = float(v)
        except (TypeError, ValueError):
            pass

    for env_key, kw_key in (
        ("OEE_CRITICAL", "critical"),
        ("OEE_NEEDS_IMPROVEMENT", "needs_improvement"),
        ("OEE_GOOD", "good"),
        ("OEE_WORLD_CLASS", "world_class"),
    ):
        if v := os.environ.get(env_key):
            try:
                oee_kw[kw_key] = float(v)
            except (TypeError, ValueError):
                pass

    for env_key, kw_key in (
        ("BOTTLENECK_CRITICAL", "severity_critical"),
        ("BOTTLENECK_HIGH", "severity_high"),
        ("BOTTLENECK_MEDIUM", "severity_medium"),
    ):
        if v := os.environ.get(env_key):
            try:
                bn_kw[kw_key] = int(v)
            except (TypeError, ValueError):
                pass

    for env_key, kw_key in (
        ("COST_SCRAP_PER_UNIT", "scrap_per_unit"),
        ("COST_REWORK_PER_HOUR", "rework_per_hour"),
        ("COST_DOWNTIME_PER_HOUR", "downtime_per_hour"),
        ("COST_DEFECT_PER_UNIT", "defect_per_unit"),
    ):
        if v := os.environ.get(env_key):
            try:
                cost_kw[kw_key] = float(v)
            except (TypeError, ValueError):
                pass

    if v := os.environ.get("MAX_ITERATIONS"):
        try:
            graph_kw["max_iterations"] = int(v)
        except (TypeError, ValueError):
            pass
    if v := os.environ.get("GRAPH_TIMEOUT"):
        try:
            graph_kw["timeout"] = int(v)
        except (TypeError, ValueError):
            pass


def _validate_llm(cfg: LLMConfig):
    if not 0.0 <= cfg.temperature <= 2.0:
        raise ValueError(
            f"LLM temperature must be between 0.0 and 2.0, got {cfg.temperature}"
        )


def _validate_oee(cfg: OEEConfig):
    thresholds = [
        ("critical", cfg.critical),
        ("needs_improvement", cfg.needs_improvement),
        ("good", cfg.good),
        ("world_class", cfg.world_class),
    ]
    for i in range(len(thresholds) - 1):
        name_a, val_a = thresholds[i]
        name_b, val_b = thresholds[i + 1]
        if val_a >= val_b:
            raise ValueError(
                f"OEE thresholds must be ascending: {name_a} ({val_a}) must be < {name_b} ({val_b})"
            )


def _validate_graph(cfg: GraphConfig):
    if cfg.max_iterations < 1:
        raise ValueError(f"graph.max_iterations must be >= 1, got {cfg.max_iterations}")
    if cfg.timeout < 1:
        raise ValueError(f"graph.timeout must be >= 1, got {cfg.timeout}")
