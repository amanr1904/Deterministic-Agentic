"""map_dax.py — Stage 6 hybrid Tableau-calc -> DAX translator.

Deterministically translates the *trivial* majority of Tableau calculated fields
(simple aggregations and arithmetic) into DAX measures, and reports the remainder
(LOD, table-calcs, multi-branch logic) as "complex" so the agent translates only
those. Output is decisions-ready measure fragments written to dax-partial.json.

Usage:
    python map_dax.py Output/MidnightCensus/analysis.json --table MidnightCensus
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

# Single-aggregation patterns: Tableau func -> DAX func
AGG_MAP = {
    "SUM": "SUM", "AVG": "AVERAGE", "MIN": "MIN", "MAX": "MAX",
    "MEDIAN": "MEDIAN", "COUNT": "COUNT", "COUNTD": "DISTINCTCOUNT",
    "STDEV": "STDEV.S", "VAR": "VAR.S",
}

FORMAT_BY_AGG = {
    "COUNT": "#,0", "DISTINCTCOUNT": "#,0", "SUM": "#,0",
    "AVERAGE": "#,0.00", "MEDIAN": "#,0.00",
}

# Anything containing these tokens is NOT trivially translatable.
COMPLEX_TOKENS = re.compile(
    r"\{|\bFIXED\b|\bINCLUDE\b|\bEXCLUDE\b|WINDOW_|RUNNING_|\bINDEX\b|\bRANK\b|"
    r"\bLOOKUP\b|\bPREVIOUS_VALUE\b|\bCASE\b|\bELSEIF\b|DATEPARSE|DATEADD|DATETRUNC",
    re.IGNORECASE,
)

SINGLE_AGG_RE = re.compile(
    r"^\s*(SUM|AVG|MIN|MAX|MEDIAN|COUNTD|COUNT|STDEV|VAR)\s*\(\s*\[([^\]]+)\]\s*\)\s*$",
    re.IGNORECASE,
)
RATIO_RE = re.compile(
    r"^\s*SUM\s*\(\s*\[([^\]]+)\]\s*\)\s*/\s*SUM\s*\(\s*\[([^\]]+)\]\s*\)\s*$",
    re.IGNORECASE,
)
PASSTHROUGH_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def translate(formula: str, table: str) -> Optional[Tuple[str, Optional[str]]]:
    """Return (dax, formatString) if trivially translatable, else None."""
    if COMPLEX_TOKENS.search(formula):
        return None
    formula = formula.strip()

    m = SINGLE_AGG_RE.match(formula)
    if m:
        func = AGG_MAP[m.group(1).upper()]
        dax = f"{func} ( {table}[{m.group(2)}] )"
        return dax, FORMAT_BY_AGG.get(func)

    m = RATIO_RE.match(formula)
    if m:
        dax = f"DIVIDE ( SUM ( {table}[{m.group(1)}] ), SUM ( {table}[{m.group(2)}] ) )"
        return dax, "#,0.00"

    m = PASSTHROUGH_RE.match(formula)
    if m:
        return f"{table}[{m.group(1)}]", None

    return None


def measure_name(caption: str) -> str:
    """Derive a Title Case measure name from a Tableau caption."""
    return caption.strip()


def build_measures(ir: Dict, host_table: str) -> Dict[str, List[Dict]]:
    """Split calc fields into deterministically-translated vs LLM-pending."""
    translated: List[Dict] = []
    pending: List[Dict] = []
    for field in ir.get("calculatedFields", []):
        formula = field["formula"]
        result = translate(formula, host_table)
        if result and field.get("suggestedDaxKind", "measure") == "measure":
            dax, fmt = result
            translated.append({
                "table": host_table,
                "name": measure_name(field["caption"]),
                "dax": dax,
                "formatString": fmt,
                "displayFolder": "Base Measures",
                "description": None,
                "source": "template",
            })
        else:
            pending.append({
                "caption": field["caption"],
                "formula": formula,
                "complexity": field["complexity"],
                "suggestedDaxKind": field.get("suggestedDaxKind", "measure"),
                "reason": "complex-token" if result is None else "non-measure",
            })
    return {"measures": translated, "pending": pending}


def write_output(payload: Dict, analysis_path: str) -> str:
    """Write dax-partial.json next to analysis.json."""
    out_dir = os.path.dirname(os.path.abspath(analysis_path))
    path = os.path.join(out_dir, "dax-partial.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def _default_table(ir: Dict) -> str:
    for ds in ir.get("dataSources", []):
        if ds.get("active"):
            return ir["workbook"]["pascalName"]
    return ir["workbook"]["pascalName"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Translate trivial Tableau calcs to DAX.")
    parser.add_argument("analysis", help="path to analysis.json (IR)")
    parser.add_argument("--table", help="host table name for measures")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.analysis):
        print(f"ERROR: file not found: {args.analysis}", file=sys.stderr)
        return 2

    with open(args.analysis, encoding="utf-8-sig") as fh:
        ir = json.load(fh)

    host = args.table or _default_table(ir)
    payload = build_measures(ir, host)
    path = write_output(payload, args.analysis)
    print(
        f"Wrote {path}\n"
        f"  translated (deterministic): {len(payload['measures'])}\n"
        f"  pending (route to LLM)    : {len(payload['pending'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
