"""map_dax.py — Stage 6 hybrid Tableau-calc -> DAX translator.

Deterministically translates the *trivial* majority of Tableau calculated fields
into DAX measures via an ordered handler registry (PATTERN_REGISTRY):

  * single aggregations          SUM([x])                 -> SUM ( T[x] )
  * population stats              STDEVP([x]) / VARP([x])  -> STDEV.P / VAR.P
  * single-value display         ATTR([x])                -> SELECTEDVALUE ( T[x] ) (gated)
  * SUM/SUM ratios               SUM([a]) / SUM([b])      -> DIVIDE(...)
  * any-aggregation ratios       COUNTD([a]) / SUM([b])   -> DIVIDE(...)        (gated)
  * aggregation arithmetic       (SUM([a])-SUM([b]))/SUM([b])                   (gated)
  * column pass-through          [Field]                  -> T[Field]
  * safe expressions             IF/IIF/CASE, AND/OR/NOT, comparisons, and a
                                 whitelist of scalar/date/string/agg functions
                                 over base columns                             (gated)

The remainder (LOD, table-calcs, parameter-driven logic, calc-field/param references)
is reported as "complex" so the agent translates only those. Column-gated handlers
only fire when every referenced field is a real base column, so they never emit DAX
referencing a non-existent column. Output is decisions-ready measure fragments
written to dax-partial.json.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dax_expr as E  # noqa: E402

# Single-aggregation patterns: Tableau func -> DAX func
AGG_MAP = {
    "SUM": "SUM", "AVG": "AVERAGE", "MIN": "MIN", "MAX": "MAX",
    "MEDIAN": "MEDIAN", "COUNT": "COUNT", "COUNTD": "DISTINCTCOUNT",
    "STDEV": "STDEV.S", "STDEVP": "STDEV.P",
    "VAR": "VAR.S", "VARP": "VAR.P",
}

FORMAT_BY_AGG = {
    "COUNT": "#,0", "DISTINCTCOUNT": "#,0", "SUM": "#,0",
    "AVERAGE": "#,0.00", "MEDIAN": "#,0.00",
}

<<<<<<< HEAD
# Tokens that make a formula genuinely complex (route to LLM). CASE is handled
# deterministically below, so it is intentionally NOT in this list; ELSEIF (IF
# chains), table calcs, LODs and date-string building stay with the LLM.
COMPLEX_TOKENS = re.compile(
    r"\{|\bFIXED\b|\bINCLUDE\b|\bEXCLUDE\b|WINDOW_|RUNNING_|\bINDEX\b|\bRANK\b|"
    r"\bLOOKUP\b|\bPREVIOUS_VALUE\b|\bELSEIF\b|DATEPARSE|DATEADD|DATETRUNC",
=======
# Aggregation-keyword alternation, shared by every aggregation regex below.
# Longer keywords come first so e.g. STDEVP wins over STDEV and COUNTD over COUNT.
_AGG_ALT = r"SUM|AVG|MIN|MAX|MEDIAN|COUNTD|COUNT|STDEVP|STDEV|VARP|VAR"

# Anything containing these tokens is NOT trivially translatable; it is routed to
# the agent. CASE / ELSEIF are intentionally NOT here -- the gated expression
# handler (_h_expression) translates them when they reference only base columns,
# and bails (-> agent) otherwise.
COMPLEX_TOKENS = re.compile(
    r"\{|\bFIXED\b|\bINCLUDE\b|\bEXCLUDE\b|WINDOW_|RUNNING_|\bINDEX\b|\bRANK\b|"
    r"\bLOOKUP\b|\bPREVIOUS_VALUE\b|DATEPARSE|DATEADD|DATETRUNC",
>>>>>>> main
    re.IGNORECASE,
)

SINGLE_AGG_RE = re.compile(
    rf"^\s*({_AGG_ALT})\s*\(\s*\[([^\]]+)\]\s*\)\s*$",
    re.IGNORECASE,
)
RATIO_RE = re.compile(
    r"^\s*SUM\s*\(\s*\[([^\]]+)\]\s*\)\s*/\s*SUM\s*\(\s*\[([^\]]+)\]\s*\)\s*$",
    re.IGNORECASE,
)
<<<<<<< HEAD

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


# A datasource-qualified column ref inside a formula: [federated.<hash>].[col]
_DS_QUALIFIED_RE = re.compile(r"\[federated\.[^\]]+\]\.(\[[^\]]+\])")


def _normalize_refs(formula: str) -> str:
    """Strip the datasource prefix from column refs so simple patterns match.

    Tableau stores calc formulas with fully-qualified refs like
    `[federated.18e8..].[int_rate]`. The translator's patterns expect a bare
    `[int_rate]`, so collapse the qualifier here first.
    """
    return _DS_QUALIFIED_RE.sub(r"\1", formula or "")


def _strip_outer_parens(expr: str) -> str:
    """Remove redundant wrapping parentheses: '(SUM([x]))' -> 'SUM([x])'."""
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        wraps = True
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i < len(expr) - 1:
                    wraps = False
                    break
        if wraps:
            expr = expr[1:-1].strip()
        else:
            break
    return expr



def _col_ref(table: str, column: str, colmap: Dict[str, str]) -> str:
    """Qualify a column with its owning table (from columnTableMap, else host)."""
    owner = _clean_table(colmap.get(column, table))
    return f"'{owner}'[{column}]"


def _translate_scalar(expr: str, table: str, ctx: Dict) -> Optional[str]:
    """Translate a single literal / aggregation / column ref to DAX, else None."""
    expr = _strip_outer_parens(_normalize_refs(expr))
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
    formula = _strip_outer_parens(_normalize_refs(formula))

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

=======
PASSTHROUGH_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
# ATTR([Field]) -> SELECTEDVALUE ( T[Field] ): show the single value of a dimension.
ATTR_RE = re.compile(r"^\s*ATTR\s*\(\s*\[([^\]]+)\]\s*\)\s*$", re.IGNORECASE)

# Any single "AGG([Field])" token anywhere in a formula (used by the generalized
# ratio / arithmetic handlers below).
AGG_TOKEN_RE = re.compile(
    rf"\b({_AGG_ALT})\s*\(\s*\[([^\]]+)\]\s*\)",
    re.IGNORECASE,
)
# Exactly "AGG([a]) / AGG([b])" with possibly different aggregations.
ANY_RATIO_RE = re.compile(
    rf"^\s*({_AGG_ALT})\s*\(\s*\[([^\]]+)\]\s*\)"
    r"\s*/\s*"
    rf"({_AGG_ALT})\s*\(\s*\[([^\]]+)\]\s*\)\s*$",
    re.IGNORECASE,
)
# After agg tokens are stripped, a pure arithmetic residual contains only these.
_ARITH_RESIDUAL_RE = re.compile(r"^[\s0-9.+\-*/()]*$")


def _h_single_agg(formula, table, columns, measures):
    """SUM([x]) -> SUM ( T[x] ). Ungated (back-compat)."""
    m = SINGLE_AGG_RE.match(formula)
    if not m:
        return None
    func = AGG_MAP[m.group(1).upper()]
    return f"{func} ( {table}[{m.group(2)}] )", FORMAT_BY_AGG.get(func)


def _h_ratio_sum(formula, table, columns, measures):
    """SUM([a]) / SUM([b]) -> DIVIDE(...). Ungated (back-compat)."""
    m = RATIO_RE.match(formula)
    if not m:
        return None
    dax = f"DIVIDE ( SUM ( {table}[{m.group(1)}] ), SUM ( {table}[{m.group(2)}] ) )"
    return dax, "#,0.00"


def _h_ratio_general(formula, table, columns, measures):
    """AGG([a]) / AGG([b]) (any aggregations) -> DIVIDE(...).

    Column-gated: only fires when both fields are real base columns, so it never
    emits DAX referencing a non-existent column (e.g. a Tableau calc-field token).
    """
    if not columns:
        return None
    m = ANY_RATIO_RE.match(formula)
    if not m:
        return None
    a_field, b_field = m.group(2), m.group(4)
    if a_field not in columns or b_field not in columns:
        return None
    fa = AGG_MAP[m.group(1).upper()]
    fb = AGG_MAP[m.group(3).upper()]
    dax = f"DIVIDE ( {fa} ( {table}[{a_field}] ), {fb} ( {table}[{b_field}] ) )"
    return dax, "#,0.00"


def _h_agg_arithmetic(formula, table, columns, measures):
    """Linear arithmetic over base-column aggregations, e.g.
    (SUM([a]) - SUM([b])) / SUM([b]) -> ( SUM ( T[a] ) - SUM ( T[b] ) ) / SUM ( T[b] ).

    Column-gated and structurally guarded: every aggregated field must be a real
    base column AND the residual (formula minus agg tokens) must be pure arithmetic
    (digits / operators / parens only). Any stray identifier, function call, or
    calc-field reference makes the residual non-arithmetic, so the handler bails to
    the agent rather than emitting broken DAX.
    """
    if not columns:
        return None
    aggs = list(AGG_TOKEN_RE.finditer(formula))
    if not aggs:
        return None
    for m in aggs:
        if m.group(2) not in columns:
            return None
    residual = AGG_TOKEN_RE.sub("", formula)
    if residual.strip() == "" or not _ARITH_RESIDUAL_RE.match(residual):
        # Empty residual is a bare aggregation (handled by _h_single_agg); a
        # non-arithmetic residual means there's logic we can't safely translate.
        return None

    def _repl(m):
        func = AGG_MAP[m.group(1).upper()]
        return f"{func} ( {table}[{m.group(2)}] )"

    dax = re.sub(r"\s+", " ", AGG_TOKEN_RE.sub(_repl, formula)).strip()
    fmt = "#,0.00" if "/" in formula else None
    return dax, fmt


def _h_attr(formula, table, columns, measures):
    """ATTR([Field]) -> SELECTEDVALUE ( T[Field] ).

    Column-gated when a column set is supplied so it never references a Tableau
    calc-field token or parameter.
    """
    m = ATTR_RE.match(formula)
    if not m:
        return None
    field = m.group(1)
    if columns and field not in columns:
        return None
    return f"SELECTEDVALUE ( {table}[{field}] )", None


def _h_passthrough(formula, table, columns, measures):
    """[Field] -> T[Field]. Ungated (back-compat)."""
    m = PASSTHROUGH_RE.match(formula)
    if not m:
        return None
    return f"{table}[{m.group(1)}]", None


def _h_expression(formula, table, columns, measures):
    """Safe IF/IIF/CASE + operators + whitelisted-function expressions -> DAX.

    Delegated to the fail-closed recursive translator in dax_expr. It only fires
    when every ``[field]`` is a real base column or a sibling measure (and at least
    one reference appears), so it never references a parameter, column-kind
    calc-field token, or non-existent column; anything outside the safe subset
    raises Untranslatable and defers to the agent.
    """
    if not columns and not measures:
        return None
    try:
        return E.translate_expression(formula, table, columns, measures), None
    except E.Untranslatable:
        return None


# Ordered registry of deterministic handlers. Each handler returns
# (dax, formatString) on a match or None to defer to the next handler. The
# specialized handlers run first so their tuned format strings win; the general
# expression translator is the last resort. A formula that no handler matches is
# routed to the agent ("pending").
PATTERN_REGISTRY = [
    _h_single_agg,
    _h_ratio_sum,
    _h_ratio_general,
    _h_agg_arithmetic,
    _h_attr,
    _h_passthrough,
    _h_expression,
]


def translate(
    formula: str,
    table: str,
    columns: Optional[set] = None,
    measures: Optional[Dict[str, str]] = None,
) -> Optional[Tuple[str, Optional[str]]]:
    """Return (dax, formatString) if deterministically translatable, else None.

    ``columns`` is the set of real base-column names; column-gated handlers use it
    to avoid emitting DAX that references Tableau calc-field tokens or parameters.
    ``measures`` maps a sibling calc field's internal Tableau name to the DAX
    measure name it becomes, so the expression translator can reference other
    measures (e.g. ``([CY Sales] - [PY Sales]) / [PY Sales]``).
    """
    if COMPLEX_TOKENS.search(formula):
        return None
    formula = formula.strip()
    for handler in PATTERN_REGISTRY:
        result = handler(formula, table, columns, measures)
        if result is not None:
            return result
>>>>>>> main
    return None


def measure_name(caption: str) -> str:
    """Derive a Title Case measure name from a Tableau caption."""
    return caption.strip()


<<<<<<< HEAD
def _build_context(ir: Dict) -> Dict:
    """Lookup tables used during translation: params (by internal name) + colmap."""
    params: Dict[str, Dict] = {}
    for p in ir.get("parameters", []):
        internal = (p.get("internalName") or "").strip().strip("[]")
        if internal:
            params[internal] = p
    return {"params": params, "colmap": ir.get("columnTableMap", {}) or {}}
=======
def _base_columns(ir: Dict) -> set:
    """Set of real base-column names from the IR (top-level ``columns``)."""
    return {c["name"] for c in ir.get("columns", []) if c.get("name")}


def _measure_refs(ir: Dict) -> Dict[str, str]:
    """Map a measure-kind calc field's internal Tableau name -> DAX measure name.

    Keyed by the field's ``fieldName`` with surrounding brackets stripped (the form
    in which sibling formulas reference it), so the expression translator can emit a
    bare ``[Measure Name]`` reference. Only measure-kind calc fields are included so
    we never reference a column-kind calc as if it were already aggregated.
    """
    refs: Dict[str, str] = {}
    for field in ir.get("calculatedFields", []):
        if field.get("suggestedDaxKind") != "measure":
            continue
        internal = field.get("fieldName")
        caption = field.get("caption")
        if not internal or not caption:
            continue
        refs[internal.strip("[]")] = measure_name(caption)
    return refs
>>>>>>> main


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
    columns = _base_columns(ir)
    ref_all = _measure_refs(ir)
    for field in ir.get("calculatedFields", []):
        formula = field["formula"]
<<<<<<< HEAD
        result = translate(formula, host_table, ctx)
        if result is None:
            kind = "measure" if (field.get("role") or "measure") == "measure" else "column"
            pending.append({
                "caption": field["caption"],
                "formula": formula,
                "complexity": "complex",
                "suggestedDaxKind": kind,
                "reason": "complex-token",
            })
            continue
        dax, fmt = result
        if (field.get("role") or "measure") == "measure":
=======
        # exclude the field's own name so a measure can never reference itself.
        self_internal = (field.get("fieldName") or "").strip("[]")
        refs = {k: v for k, v in ref_all.items() if k != self_internal}
        result = translate(formula, host_table, columns, refs)
        if result and field.get("suggestedDaxKind", "measure") == "measure":
            dax, fmt = result
>>>>>>> main
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
