"""topn.py — shared Top-N (Tableau groupfilter) naming + DAX for both emitters.

Tableau limits a category to the top/bottom N members via a <groupfilter
count='N' end='top'> ordered by an aggregation (e.g. COUNTD([show_id]) DESC).
Power BI cannot express that as a hand-authored VisualTopN filterConfig (the
PBIR schema rejects it and crashes the report), so we reproduce it with a RANKX
rank measure on the model plus a visual-level Advanced "rank <= N" filter.

emit_tmdl (model) and emit_pbir (report) both import this module so the rank
measure name they generate and reference is always identical.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Optional, Tuple

_DAX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dax")
sys.path.insert(0, os.path.normpath(_DAX_DIR))
import map_dax as _M  # noqa: E402


def measure_name(field: str) -> str:
    """Deterministic rank-measure name, e.g. 'listed_in (Rank)'."""
    return f"{field} (Rank)"


def by_dax(by_expr: Optional[str], table: str) -> str:
    """Translate the Tableau order-by aggregation to DAX (fallback COUNTROWS)."""
    if by_expr:
        translated = _M.translate(by_expr, f"'{table}'")
        if translated and translated[0]:
            return translated[0]
    return f"COUNTROWS('{table}')"


def rank_dax(table: str, field: str, by_expr: Optional[str],
             ascending: bool = False) -> str:
    """RANKX DAX ranking a category by an aggregation (DESC for top, ASC bottom)."""
    order = "ASC" if ascending else "DESC"
    expr = by_dax(by_expr, table)
    return f"RANKX(ALLSELECTED('{table}'[{field}]), {expr}, , {order})"


def spec(ws_topn: Dict, table: str) -> Tuple[str, str, int]:
    """Return (measure_name, rank_dax, count) for a worksheet's topN IR block."""
    field = ws_topn["field"]
    count = int(ws_topn.get("count", 10))
    ascending = (ws_topn.get("end", "top").lower() == "bottom")
    return (measure_name(field),
            rank_dax(table, field, ws_topn.get("byExpr"), ascending),
            count)
