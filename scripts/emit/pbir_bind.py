"""pbir_bind.py — IR-aware field binding resolution for the PBIR emitter.

Given the IR (analysis.json) and the LLM decisions.json, resolve which entity +
property each dashboard zone should bind to. Keeps emit_pbir.py thin: charts use
the worksheet's resolved category/value fields, slicers map to real columns or
disconnected parameter tables, and measures bind as measures (not columns).
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import date_levels as D  # noqa: E402
import field_param as FP  # noqa: E402

_TWB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "twb")
sys.path.insert(0, os.path.normpath(_TWB_DIR))
import csv_probe as CP  # noqa: E402


def _norm(s: Optional[str]) -> str:
    """Normalize a column name (underscores/slashes/hyphens/spaces -> space)."""
    return re.sub(r"[_/\-\s]+", " ", s or "").strip().lower()


_COL_ENTITY_CACHE: Dict[int, Dict[str, str]] = {}


def column_entity_map(decisions: Dict) -> Dict[str, str]:
    """Map each normalized column name to its owning table (entity).

    Probes every fact/dim/date table's CSV headers (mirrors emit_tmdl's column
    assignment) so a chart category like 'Sub-Category' resolves to DimProduct,
    'Region' -> DimLocation, etc. Dim/date tables override the fact on shared
    names (keys) so dimension attributes bind to their dimension. Calculated
    columns map to their declared table.
    """
    key = id(decisions)
    cached = _COL_ENTITY_CACHE.get(key)
    if cached is not None:
        return cached
    tables = decisions.get("tables", [])
    ordered = ([t for t in tables if t.get("role") == "fact"]
               + [t for t in tables if t.get("role") in ("dim", "date")])
    mapping: Dict[str, str] = {}
    for t in ordered:
        src = t.get("sourceFile")
        if not src:
            continue
        probe = CP.probe(src)
        if not probe:
            continue
        for h in probe.get("headers", []):
            mapping[_norm(h)] = t["name"]
    for cc in decisions.get("calculatedColumns", []):
        if cc.get("table") and cc.get("name"):
            mapping[_norm(cc["name"])] = cc["table"]
    _COL_ENTITY_CACHE[key] = mapping
    return mapping


def column_entity(prop: Optional[str], decisions: Dict, default_entity: str) -> str:
    """Resolve the owning table for a non-measure category/column field."""
    if not prop:
        return default_entity
    return column_entity_map(decisions).get(_norm(prop), default_entity)


def fact_entity(decisions: Dict) -> str:
    for t in decisions.get("tables", []):
        if t.get("role") == "fact":
            return t["name"]
    tables = decisions.get("tables", [])
    return tables[0]["name"] if tables else "Table"


def measure_list(decisions: Dict) -> List[str]:
    return [m["name"] for m in decisions.get("measures", [])]


def column_names(ir: Dict) -> Set[str]:
    return {c["name"] for c in ir.get("columns", [])}


def param_tables(decisions: Dict) -> Set[str]:
    return {t["name"] for t in decisions.get("tables", []) if t.get("role") == "param"}


def first_date_col(ir: Dict) -> Optional[str]:
    for c in ir.get("columns", []):
        if c.get("dataType") in ("date", "datetime"):
            return c["name"]
    return None


def date_cols(ir: Dict) -> Set[str]:
    return {c["name"] for c in ir.get("columns", [])
            if c.get("dataType") in ("date", "datetime")}


def part_prop(field: Optional[str], level: Optional[str], dcols: Set[str]) -> Optional[str]:
    """Map a date field + Tableau level to its derived part column (or itself)."""
    if field and field in dcols and D.needs_part(level):
        return D.part_column_name(field, level)
    return field


def first_dim_col(ir: Dict) -> Optional[str]:
    for c in ir.get("columns", []):
        if c.get("dataType") in ("string", "date", "datetime"):
            return c["name"]
    return None


def ws_by_name(ir: Dict, name: str) -> Optional[Dict]:
    for ws in ir.get("worksheets", []):
        if ws["name"] == name:
            return ws
    return None


def decode_field(enc: Optional[str]) -> Optional[str]:
    """Extract the column name from a Tableau encoding ref.

    Examples: 'federated...].[none:rating:nk' -> 'rating',
    '...].[ctd:show_id:qk' -> 'show_id', '...].[yr:Calc_123:ok' -> 'Calc_123'.
    """
    if not enc:
        return None
    m = re.search(r"\]\.\[(.+)$", enc)
    body = m.group(1) if m else enc
    parts = body.split(":")
    if len(parts) >= 3:
        return parts[1]
    if len(parts) == 2:
        return parts[0]
    return parts[0] if parts and parts[0] else None


def card_column(ws: Optional[Dict], ir: Dict, cols: Set[str]) -> Optional[str]:
    """Resolve the text/dimension column a single-value card displays."""
    if not ws:
        return None
    enc = ws.get("encodings") or {}
    for key in ("text", "color"):
        c = decode_field(enc.get(key))
        if c and c in cols:
            return c
    for d in ws.get("dimensions") or []:
        if d in cols:
            return d
    return None


def geo_column(ir: Dict) -> Optional[str]:
    """First column whose name reads as a geographic location."""
    for c in ir.get("columns", []):
        if re.search(r"\b(country|state|province|city|region)\b", c["name"], re.I):
            return c["name"]
    return None


def color_field(ws: Optional[Dict], ir: Dict, cols: Set[str]) -> Optional[str]:
    """The category a pie/series split should use (Tableau color/text encoding)."""
    enc = (ws.get("encodings") or {}) if ws else {}
    c = decode_field(enc.get("color")) or decode_field(enc.get("text"))
    if c and c in cols:
        return c
    return first_dim_col(ir)


def slug(text: str) -> str:
    return (re.sub(r"[^\w]+", "", (text or "").replace(" ", "")) or "f").lower()


def field_param_for_ws(ws_name: str, decisions: Dict) -> Optional[Dict]:
    """Field parameter whose PRIMARY (live) worksheet is ws_name, if any."""
    for fp in decisions.get("fieldParameters", []):
        if FP.primary_worksheet(fp) == ws_name:
            return fp
    return None


def field_param_by_field(field: Optional[str], decisions: Dict) -> Optional[Dict]:
    """Field parameter matching a paramctrl zone field (by name slug)."""
    if not field:
        return None
    for fp in decisions.get("fieldParameters", []):
        if slug(fp["name"]) == slug(field):
            return fp
    return None


def suppressed_worksheets(decisions: Dict) -> set:
    return FP.suppressed_worksheets(decisions.get("fieldParameters", []))


def _param_value_column(table_name: str, decisions: Dict) -> str:
    """The value column a disconnected parameter slicer binds to (e.g. 'Year').

    Falls back to the table name only if no datatable/key column is declared.
    """
    for t in decisions.get("tables", []):
        if t["name"] != table_name:
            continue
        dt = t.get("datatable") or {}
        cols = dt.get("columns") or []
        if cols:
            return cols[0]["name"]
        keys = t.get("keyColumns") or []
        if keys:
            return keys[0]
    return table_name


def resolve_slicer(zone: Dict, ir: Dict, decisions: Dict):
    """Return (entity, prop, title, mode) for a filter / parameter-control zone.

    mode is 'Between' for date-range parameters (Start/End Date) so each acts as
    an independent bound on the date column, else 'Dropdown' for list slicers.
    """
    field = zone.get("field")
    cols = column_names(ir)
    ptables = param_tables(decisions)
    title = field or zone.get("worksheet") or "Filter"
    # Date-range parameter (e.g. 'Start Date' / 'End Date') -> Between slicer on
    # the fact date column, so Start and End are independent bounds.
    if zone.get("type") == "paramctrl" and _is_date_param(field, decisions):
        entity = fact_entity(decisions)
        dcol = first_date_col(ir)
        if dcol:
            return entity, dcol, title, "Between"
    # Parameter list-slicers bind to a disconnected table on its value column
    # (e.g. SelectYear[Year]), NOT the table name.
    pmap = {slug(t): t for t in ptables}
    if field and slug(field) in pmap:
        tbl = pmap[slug(field)]
        return tbl, _param_value_column(tbl, decisions), title, "Dropdown"
    # Resolve the correct entity (dim table or fact) for this field via the
    # CSV-header owner map so Category/Sub-Category -> DimProduct,
    # Region/State/City -> DimLocation, etc. (single denormalized IR datasource
    # means the field cannot be attributed by datasource alone).
    entity = column_entity(field, decisions, fact_entity(decisions))
    if field and field in cols:
        return entity, field, title, "Dropdown"
    if zone.get("type") == "paramctrl":
        dcol = first_date_col(ir)
        if dcol:
            return entity, dcol, title, "Dropdown"
    fallback = field if field in cols else (next(iter(cols)) if cols else "Column")
    return entity, fallback, title, "Dropdown"


def _is_date_param(field: Optional[str], decisions: Dict) -> bool:
    """A range/date parameter that is NOT backed by a disconnected list table."""
    if not field:
        return False
    names = {t["name"] for t in decisions.get("tables", []) if t.get("role") == "param"}
    if field in names or slug(field) in {slug(n) for n in names}:
        return False  # it's a list parameter -> dropdown
    return bool(re.search(r"\bdate\b", field, re.IGNORECASE))


def category_binding(ws: Optional[Dict], entity: str, cols: Set[str],
                     ir: Dict) -> Dict:
    """Resolve a chart category, aggregating dates to the Tableau date level."""
    catf = ws.get("categoryField") if ws else None
    level = ws.get("categoryDateLevel") if ws else None
    dcols = date_cols(ir)
    prop = part_prop(catf, level, dcols)
    if prop and (prop in cols or (catf in dcols)):
        return {"entity": entity, "prop": prop}
    if catf and catf in cols:
        return {"entity": entity, "prop": catf}
    dim = first_dim_col(ir)
    return {"entity": entity, "prop": dim or (next(iter(cols)) if cols else "Column")}


def value_binding(valf: Optional[str], entity: str, mset: Set[str],
                  mlist: List[str], cols: Set[str], ir: Dict) -> Dict:
    if valf and valf in mset:
        return {"entity": entity, "prop": valf, "isMeasure": True}
    if valf and valf in cols:
        return {"entity": entity, "prop": valf, "isMeasure": False}
    if mlist:
        return {"entity": entity, "prop": mlist[0], "isMeasure": True}
    col = next(iter(cols)) if cols else "Value"
    return {"entity": entity, "prop": col, "isMeasure": False}


def table_columns(ws: Optional[Dict], ir: Dict, entity: str,
                  mset: Set[str], cols: Set[str]) -> List[Dict]:
    out: List[Dict] = []
    dcols = date_cols(ir)
    level = ws.get("categoryDateLevel") if ws else None
    if ws:
        for d in ws.get("dimensions", []) or []:
            if d in dcols and D.needs_part(level):
                out.append({"entity": entity, "prop": D.part_column_name(d, level),
                            "isMeasure": False})
            elif d in cols:
                out.append({"entity": entity, "prop": d, "isMeasure": False})
        for v in ws.get("values", []) or []:
            if v in mset:
                out.append({"entity": entity, "prop": v, "isMeasure": True})
            elif v in cols:
                out.append({"entity": entity, "prop": v, "isMeasure": False})
    if not out:
        out = [{"entity": entity, "prop": c["name"], "isMeasure": False}
               for c in ir.get("columns", [])[:6]]
    return out or [{"entity": entity, "prop": "Column", "isMeasure": False}]
