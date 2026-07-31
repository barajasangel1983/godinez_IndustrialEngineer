"""
Godínez IndustrialEngineer — Configuration Package

Exports Config (typed dataclass) and backward-compatible flat constants so all
existing `from src.config import DATA_DIR` imports continue to work unchanged.
"""

from src.config.loader import (
    BASE_DIR,
    DATA_DIR,
    KNOWLEDGE_DIR,
    TEST_DATA_DIR,
    Config,
    read_json_file,
)

# Ensure required directories exist
for _d in [DATA_DIR, KNOWLEDGE_DIR, TEST_DATA_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Load config once at import time
config: Config = Config.load()

# ── Backward-compat flat constants ───────────────────────────────────
LLM_MODEL: str = config.llm.model
LLM_TEMPERATURE: float = config.llm.temperature

OEE_THRESHOLDS: dict = {
    "critical": config.oee.critical,
    "needs_improvement": config.oee.needs_improvement,
    "good": config.oee.good,
    "world_class": config.oee.world_class,
}

MAX_ITERATIONS: int = config.graph.max_iterations
GRAPH_TIMEOUT: int = config.graph.timeout

# ── Backward-compat for test_cli.py (patches _CONFIG_FILE and calls _load_json_config) ─
_CONFIG_FILE = BASE_DIR / ".godinez_config.json"


def _load_json_config() -> dict:
    """Load .godinez_config.json — backward-compat helper used by tests and CLI."""
    return read_json_file(_CONFIG_FILE)
