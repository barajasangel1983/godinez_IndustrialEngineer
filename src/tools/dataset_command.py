"""
Dataset Command — Detect "load dataset <file>" / "list datasets" style
commands in a raw query.

Deterministic regex matching, not LLM-based: these are system commands, and
we want them recognized reliably and instantly regardless of which LLM (or
no LLM) is reachable.
"""

import re
from typing import Optional

# Deterministic system-command intents — classify_node/router_node must
# pass these through unchanged rather than reclassifying them.
DATASET_SYSTEM_INTENTS = frozenset({"load_dataset", "list_datasets"})

_LOAD_DATASET_RE = re.compile(
    r"""^\s*
    (?:load|use|switch(?:\s+to)?)
    \s+dataset\s+
    (?:to\s+)?
    ["']?(?P<filename>[\w\-. ]+\.csv)["']?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_LIST_DATASETS_RE = re.compile(
    r"""^\s*
    (?:
        list\s+(?:the\s+)?datasets
        | show\s+(?:me\s+)?(?:the\s+)?(?:available\s+)?datasets
        | what\s+datasets\s+(?:are\s+)?available
        | available\s+datasets
    )
    \s*\??\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_dataset_filename(query: str) -> Optional[str]:
    """Return the requested CSV filename if query is a load-dataset command, else None."""
    match = _LOAD_DATASET_RE.match(query.strip())
    if not match:
        return None
    return match.group("filename").strip()


def is_list_datasets_command(query: str) -> bool:
    """True if query is a "list datasets" style command."""
    return _LIST_DATASETS_RE.match(query.strip()) is not None
