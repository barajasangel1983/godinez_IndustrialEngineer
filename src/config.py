"""
Godínez IndustrialEngineer configuration

Defaults are defined here. Values in .godinez_config.json override them
(written by `python main.py config set KEY VALUE`).
"""

import json
from pathlib import Path

# LLM Configuration
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.0

# OEE Benchmarks
OEE_THRESHOLDS = {
    "critical": 60.0,
    "needs_improvement": 75.0,
    "good": 85.0,
    "world_class": 90.0,
}

# Graph Configuration
MAX_ITERATIONS = 10
GRAPH_TIMEOUT = 120  # seconds

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "src" / "knowledge"
TEST_DATA_DIR = DATA_DIR / "test"

# Ensure dirs exist
for d in [DATA_DIR, KNOWLEDGE_DIR, TEST_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Load .godinez_config.json overrides ──────────────────────────
_CONFIG_FILE = BASE_DIR / ".godinez_config.json"


def _load_json_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


_json_config = _load_json_config()

# Apply OEE threshold overrides
if "oee_thresholds" in _json_config:
    for _k, _v in _json_config["oee_thresholds"].items():
        if _k in OEE_THRESHOLDS:
            try:
                OEE_THRESHOLDS[_k] = float(_v)
            except (TypeError, ValueError):
                pass

# Apply LLM overrides
if "llm" in _json_config:
    _llm = _json_config["llm"]
    if "model" in _llm:
        LLM_MODEL = str(_llm["model"])
    if "temperature" in _llm:
        try:
            LLM_TEMPERATURE = float(_llm["temperature"])
        except (TypeError, ValueError):
            pass
