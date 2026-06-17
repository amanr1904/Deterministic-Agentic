"""csv_probe.py — Detect CSV delimiter and column headers from the first line.

Used by emit_tmdl.py at generation time so partitions always use the correct
delimiter and actual CSV header names — no hardcoded "," assumptions.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

# Candidates ordered by specificity (semicolon before comma because comma
# appears inside comma-decimal numbers, causing false positive splits).
CANDIDATE_DELIMITERS = [";", "\t", "|", ","]


def detect(path: str) -> Tuple[str, List[str]]:
    """Return (delimiter, [header_names]) for a CSV file.

    Reads only the first line — fast and safe on large files.
    Returns (',', []) if the file cannot be opened.
    """
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            first = fh.readline().rstrip("\r\n")
    except OSError:
        return ",", []

    for delim in CANDIDATE_DELIMITERS:
        parts = first.split(delim)
        if len(parts) >= 2:
            return delim, [h.strip().strip('"') for h in parts]

    # Single-column CSV or unknown format — return as-is with comma
    return ",", [first.strip()]


def probe(path: str) -> Optional[Dict]:
    """Probe a CSV file and return {delimiter, headers, path} or None if not found."""
    if not os.path.isfile(path):
        return None
    delimiter, headers = detect(path)
    return {"delimiter": delimiter, "headers": headers, "path": os.path.abspath(path)}
