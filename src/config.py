"""
Godínez IndustrialEngineer configuration
"""

from pathlib import Path

# LLM Configuration
LLM_MODEL = "gpt-4o-mini"  # Default; override with env var LLM_MODEL
LLM_TEMPERATURE = 0.0

# OEE Benchmarks
OEE_THRESHOLDS = {
    "critical": 60.0,
    "needs_improvement": 75.0,
    "good": 85.0,
    "world_class": 90.0,
}

# Graph Configuration
MAX_ITERATIONS = 10  # Prevent infinite loops
GRAPH_TIMEOUT = 120  # seconds

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "src" / "knowledge"
TEST_DATA_DIR = DATA_DIR / "test"

# Ensure dirs exist
for d in [DATA_DIR, KNOWLEDGE_DIR, TEST_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)
