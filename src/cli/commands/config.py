"""
Godínez IndustrialEngineer — CLI config command

Usage:
    python main.py config --show                              # Show current config
    python main.py config set oee_thresholds.critical 60      # Set a threshold
    python main.py config set database.url postgresql://...   # Set database URL
    python main.py config set database.url off                # Disable persistence
"""

import sys
import os
import json


def _get_nested(d, key_path):
    keys = key_path.split(".")
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None, False
    return cur, True


def _set_nested(d, key_path, value):
    keys = key_path.split(".")
    cur = d
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value
    return d


def _parse_value(value_str: str):
    """Parse a string value to int, float, or str."""
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str


def _config_file_path() -> str:
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return os.path.join(repo_root, ".godinez_config.json")


def _load_config() -> dict:
    path = _config_file_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_config(config: dict) -> str:
    path = _config_file_path()
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path


def config_show():
    """Show current configuration."""
    from src.config import (
        LLM_MODEL,
        LLM_TEMPERATURE,
        OEE_THRESHOLDS,
        MAX_ITERATIONS,
        GRAPH_TIMEOUT,
        BASE_DIR,
        DATA_DIR,
    )

    db_url = os.environ.get("DATABASE_URL", "sqlite:///data/godinez.db")
    tracing_enabled = os.environ.get("LANGSMITH_API_KEY") is not None

    # Check .godinez_config.json
    json_config = _load_config()
    has_overrides = bool(json_config)

    print()
    print("=" * 70)
    print("  Godínez IndustrialEngineer — Configuration")
    print("=" * 70)
    print()
    print("  LLM")
    print(f"    Model:            {LLM_MODEL}")
    print(f"    Temperature:      {LLM_TEMPERATURE}")
    print(f"    LangSmith:        {'enabled' if tracing_enabled else 'disabled (no LANGSMITH_API_KEY)'}")
    print()
    print("  OEE Benchmarks")
    print(f"    Critical:         {OEE_THRESHOLDS['critical']}%")
    print(f"    Needs Improvement:{OEE_THRESHOLDS['needs_improvement']}%")
    print(f"    Good:             {OEE_THRESHOLDS['good']}%")
    print(f"    World Class:      {OEE_THRESHOLDS['world_class']}%")
    print()
    print("  Graph")
    print(f"    Max Iterations:   {MAX_ITERATIONS}")
    print(f"    Timeout:          {GRAPH_TIMEOUT}s")
    print()
    print("  Storage")
    print(f"    Base Directory:   {BASE_DIR}")
    print(f"    Data Directory:   {DATA_DIR}")
    print(f"    Database:         {db_url}")
    if has_overrides:
        print(f"    Config overrides: {_config_file_path()}")
    print()
    print("=" * 70)


def config_set(key_path: str, value_str: str):
    """Write a config value to .godinez_config.json."""
    value = _parse_value(value_str)

    config = _load_config()

    # Special handling: database.url sets DATABASE_URL env var
    if key_path == "database.url":
        _set_nested(config, "database.url", value_str)
        path = _save_config(config)
        os.environ["DATABASE_URL"] = value_str
        print(f"  database.url = {value_str}")
        print(f"  Saved to: {path}")
        print("  Restart the API server / CLI for the new URL to take effect.")
        return

    _set_nested(config, key_path, value)
    path = _save_config(config)
    print(f"  {key_path} = {value}")
    print(f"  Saved to: {path}")
    print("  Restart the application for changes to take effect.")


def config(args):
    """Handle config subcommand — show or set values."""
    positional = getattr(args, "config_args", [])

    if positional and positional[0] == "set":
        # config set KEY VALUE
        if len(positional) != 3:
            print("Usage: python main.py config set <key> <value>")
            print("Example: python main.py config set oee_thresholds.critical 60")
            sys.exit(1)
        config_set(positional[1], positional[2])
    else:
        # config --show (or no args → default show)
        config_show()
