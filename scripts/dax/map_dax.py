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

# Tokens that make a formula genuinely complex (route to LLM). CASE is handled
# deterministically below, so it is intentionally NOT in this list; ELSEIF (IF
# chains), table calcs, LODs and date-string building stay with the LLM.
COMPLEX_TOKENS = re.compile(
    r"\{|\bFIXED\b|\bINCLUDE\b|\bEXCLUDE\b|WINDOW_|RUNNING_|\bINDEX\b|\bRANK\b|"
    r"\bLOOKUP\b|\bPREVIOUS_VALUE\b|\bELSEIF\b|DATEPARSE|DATEADD|DATETRUNC",
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

# Literal value patterns (constants Tableau stores verbatim).
STRING_LIT_RE = re.compile(r"""^\s*(["'])(.*)\1\s*$""", re.DOTALL)
NUMBER_LIT_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*$")
BOOL_LIT_RE = re.compile(r"^\s*(TRUE|FALSE)\s*$", re.IGNORECASE)
DATE_LIT_RE = re.compile(r"^\s*#(\d{4})-(\d{1,2})-(\d{1,2})#\s*$")
# TODAY()/NOW() optionally with +/- N day offset.
TODAY_RE = re.compile(r"^\s*(TODAY|NOW)\s*\(\s*\)\s*(?:([+-])\s*(\d+))?\s*$", re.IGNORECASE)
# Date-part functions wrapping a single column: YEAR([Order Date]) etc.
DATE_PART_RE = re.compile(
    r"^\s*(YEAR|MONTH|DAY|QUARTER|WEEK|WEEKDAY|HOUR|MINUTE|SECOND)\s*\(\s*\[([^\]]+)\]\s*\)\s*$",
    re.IGNORECASE,
)
# Parameter reference with optional +/- N arithmetic: [Parameters].[X] - 1
PARAM_ARITH_RE = re.compile(
    r"^\s*\[Parameters\]\.\[([^\]]+)\]\s*(?:([+-])\s*(\d+(?:\.\d+)?))?\s*$"
)
# Tableau parameter reference: [Parameters].[Internal Name]
PARAM_REF_RE = re.compile(r"^\s*\[Parameters\]\.\[([^\]]+)\]\s*$")
COLUMN_REF_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
# CASE <operand> WHEN .. THEN .. [ELSE ..] END
CASE_RE = re.compile(r"^\s*CASE\s+(.+?)\s+(WHEN\b.+)\bEND\s*$", re.IGNORECASE | re.DOTALL)
WHEN_RE = re.compile(
    r"WHEN\s+(.+?)\s+THEN\s+(.+?)(?=\s+WHEN\s+|\s+ELSE\s+|\s*$)",
    re.IGNORECASE | re.DOTALL,
)
ELSE_RE = re.compile(r"\bELSE\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL)


def _clean_table(name: str) -> str:
    """Normalise a Tableau table name for DAX (drop object-id hash + extension)."""
    name = name.strip().strip("'")
    name = re.sub(r"_[0-9A-Fa-f]{16,}$", "", name)        # object-id suffix
    name = re.sub(r"\.(csv|xlsx?|txt|tsv)$", "", name, flags=re.IGNORECASE)
    return name


def _col_ref(table: str, column: str, colmap: Dict[str, str]) -> str:
    """Qualify a column with its owning table (from columnTableMap, else host)."""
    owner = _clean_table(colmap.get(column, table))
    return f"'{owner}'[{column}]"


def _translate_scalar(expr: str, table: str, ctx: Dict) -> Optional[str]:
    """Translate a single literal / aggregation / column ref to DAX, else None."""
    expr = expr.strip()
    # String literals are checked first: their content may contain words that
    # look like Tableau keywords (e.g. "Include"/"Exclude") but are just text.
    m = STRING_LIT_RE.match(expr)
    if m:
        return '"' + m.group(2).replace('"', '""') + '"'
    if COMPLEX_TOKENS.search(expr):
        return None
    if NUMBER_LIT_RE.match(expr):
        return expr
    if BOOL_LIT_RE.match(expr):
        return f"{expr.strip().upper()}()"
    m = DATE_LIT_RE.match(expr)
    if m:
        return f"DATE ( {int(m.group(1))}, {int(m.group(2))}, {int(m.group(3))} )"
    m = TODAY_RE.match(expr)
    if m:
        base = f"{m.group(1).upper()} ()"
        if m.group(2):
            return f"{base} {m.group(2)} {m.group(3)}"
        return base
    m = DATE_PART_RE.match(expr)
    if m:
        return f"{m.group(1).upper()} ( {_col_ref(table, m.group(2), ctx['colmap'])} )"
    m = PARAM_ARITH_RE.match(expr)
    if m and ctx["params"].get(m.group(1)):
        param = ctx["params"][m.group(1)]
        name = param["name"]
        default = param.get("default") or "BLANK ()"
        ref = f"SELECTEDVALUE ( '{name}'[{name}], {default} )"
        if m.group(2):
            return f"{ref} {m.group(2)} {m.group(3)}"
        return ref
    m = SINGLE_AGG_RE.match(expr)
    if m:
        func = AGG_MAP[m.group(1).upper()]
        return f"{func} ( {_col_ref(table, m.group(2), ctx['colmap'])} )"
    m = COLUMN_REF_RE.match(expr)
    if m and not expr.upper().startswith("[PARAMETERS]"):
        return _col_ref(table, m.group(1), ctx["colmap"])
    return None


def _resolve_operand(operand: str, table: str, ctx: Dict) -> Optional[str]:
    """Resolve a CASE operand (parameter or column) to a DAX scalar expression."""
    m = PARAM_REF_RE.match(operand)
    if m:
        param = ctx["params"].get(m.group(1))
        if not param:
            return None
        name = param["name"]
        default = param.get("default") or "BLANK ()"
        return f"SELECTEDVALUE ( '{name}'[{name}], {default} )"
    m = COLUMN_REF_RE.match(operand)
    if m:
        return _col_ref(table, m.group(1), ctx["colmap"])
    return None


def _translate_case(formula: str, table: str, ctx: Dict) -> Optional[str]:
    """Translate a simple Tableau CASE expression into a DAX SWITCH."""
    cm = CASE_RE.match(formula)
    if not cm:
        return None
    operand = _resolve_operand(cm.group(1).strip(), table, ctx)
    if operand is None:
        return None
    body = cm.group(2)
    else_text = None
    em = ELSE_RE.search(body)
    if em:
        else_text = em.group(1)
        body = body[: em.start()]
    branches = WHEN_RE.findall(body)
    if not branches:
        return None
    parts: List[str] = []
    for when_val, then_val in branches:
        dv = _translate_scalar(when_val, table, ctx)
        rv = _translate_scalar(then_val, table, ctx)
        if dv is None or rv is None:
            return None
        parts.append(f"{dv}, {rv}")
    if else_text is not None:
        ev = _translate_scalar(else_text, table, ctx)
        if ev is None:
            return None
        parts.append(ev)
    inner = ",\n        ".join(parts)
    return f"SWITCH (\n        {operand},\n        {inner}\n    )"


def translate(formula: str, table: str, ctx: Dict) -> Optional[Tuple[str, Optional[str]]]:
    """Return (dax, formatString) if deterministically translatable, else None."""
    formula = formula.strip()

    # CASE is attempted before the complex-token guard so simple CASEs translate;
    # a CASE the parser cannot fully handle falls through to None (-> LLM).
    if re.match(r"^\s*CASE\b", formula, re.IGNORECASE):
        case_dax = _translate_case(formula, table, ctx)
        return (case_dax, None) if case_dax else None

    if COMPLEX_TOKENS.search(formula):
        return None

    m = SINGLE_AGG_RE.match(formula)
    if m:
        func = AGG_MAP[m.group(1).upper()]
        dax = f"{func} ( {_col_ref(table, m.group(2), ctx['colmap'])} )"
        return dax, FORMAT_BY_AGG.get(func)

    m = RATIO_RE.match(formula)
    if m:
        dax = (f"DIVIDE ( SUM ( {_col_ref(table, m.group(1), ctx['colmap'])} ), "
               f"SUM ( {_col_ref(table, m.group(2), ctx['colmap'])} ) )")
        return dax, "#,0.00"

    scalar = _translate_scalar(formula, table, ctx)
    if scalar is not None:
        return scalar, None

    return None


def measure_name(caption: str) -> str:
    """Derive a Title Case measure name from a Tableau caption."""
    return caption.strip()


def _build_context(ir: Dict) -> Dict:
    """Lookup tables used during translation: params (by internal name) + colmap."""
    params: Dict[str, Dict] = {}
    for p in ir.get("parameters", []):
        internal = (p.get("internalName") or "").strip().strip("[]")
        if internal:
            params[internal] = p
    return {"params": params, "colmap": ir.get("columnTableMap", {}) or {}}


def build_measures(ir: Dict, host_table: str) -> Dict[str, List[Dict]]:
    """Split calc fields into deterministically-translated vs LLM-pending.

    Translated measures go to `measures`; translated non-measures (constants,
    column refs, parameter-driven SWITCHes used as columns) go to
    `calculatedColumns`. Only fields the translator cannot handle become
    `pending` for the LLM.
    """
    ctx = _build_context(ir)
    translated: List[Dict] = []
    columns: List[Dict] = []
    pending: List[Dict] = []
    for field in ir.get("calculatedFields", []):
        formula = field["formula"]
        result = translate(formula, host_table, ctx)
        if result is None:
            pending.append({
                "caption": field["caption"],
                "formula": formula,
                "complexity": field["complexity"],
                "suggestedDaxKind": field.get("suggestedDaxKind", "measure"),
                "reason": "complex-token",
            })
            continue
        dax, fmt = result
        if field.get("suggestedDaxKind", "measure") == "measure":
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
            columns.append({
                "table": host_table,
                "name": measure_name(field["caption"]),
                "dax": dax,
                "formatString": fmt,
                "source": "template",
            })
    return {"measures": translated, "calculatedColumns": columns, "pending": pending}


def write_output(payload: Dict, analysis_path: str) -> str:
    """Write dax-partial.json next to analysis.json."""
    out_dir = os.path.dirname(os.path.abspath(analysis_path))
    path = os.path.join(out_dir, "dax-partial.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def _default_table(ir: Dict) -> str:
    """Host table for measures: the real fact/datasource name the model will use.

    Prefers the active (worksheet-referenced) non-Parameters datasource name so
    generated DAX references match the table the emitter creates, then falls back
    to any real datasource, then the workbook PascalName.
    """
    sources = [ds for ds in ir.get("dataSources", [])
               if (ds.get("name") or "").lower() != "parameters"]
    for ds in sources:
        if ds.get("active") and ds.get("name"):
            return _clean_table(ds["name"])
    if sources and sources[0].get("name"):
        return _clean_table(sources[0]["name"])
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
        f"  translated measures (deterministic) : {len(payload['measures'])}\n"
        f"  translated columns  (deterministic) : {len(payload['calculatedColumns'])}\n"
        f"  pending (route to LLM)              : {len(payload['pending'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
