"""
Dataset Command — Detect "load dataset <file>" style commands in a raw query.

Deterministic regex matching, not LLM-based: this is a system command, and
we want it recognized reliably and instantly regardless of which LLM (or no
LLM) is reachable.
"""

import re
from typing import Optional

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


def extract_dataset_filename(query: str) -> Optional[str]:
    """Return the requested CSV filename if query is a load-dataset command, else None."""
    match = _LOAD_DATASET_RE.match(query.strip())
    if not match:
        return None
    return match.group("filename").strip()
