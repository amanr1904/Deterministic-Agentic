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
import emit_tmdl as ET  # noqa: E402  (reuse the same CSV probe the model emitter uses)


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


def _owned_columns(table: Dict, ir: Dict) -> Set[str]:
    """Logical column names a dim/date table actually owns.

    A synthetic table (calendar / datatable, ``sourceDatasource`` is None) owns
    only its declared key/datatable columns — without this guard a calendar
    DimDate would claim every IR column and mis-bind their slicers.

    A real source-backed dim is normally scoped by its datasource, but a
    *federated multi-CSV* datasource exposes every CSV's columns under ONE
    datasource name (e.g. "Sales DataSource" spanning Orders/Customers/Location/
    Products). In that case the dim's ``sourceFile`` is probed so each dim claims
    only its own CSV's columns, matching exactly what emit_tmdl declares.
    """
    src = table.get("sourceDatasource")
    if src is None:
        own = set(table.get("keyColumns", []))
        dt = table.get("datatable") or {}
        own |= {c["name"] for c in dt.get("columns", [])}
        return own
    if table.get("sourceFile"):
        probe = ET._probe_for_table(table, ir)
        if probe and probe.get("columns"):
            return {c["name"] for c in probe["columns"]}
    return {c["name"] for c in ir.get("columns", []) if c.get("datasource") == src}


def entity_for_field(field: Optional[str], default_entity: str,
                     decisions: Dict, ir: Dict) -> str:
    """Resolve a category/table column field to its owning dim/date table.

    Falls back to ``default_entity`` (typically the fact) when the field is not
    owned by any dimension — e.g. fact columns or date-part derived columns.
    """
    if not field:
        return default_entity
    for table in decisions.get("tables", []):
        if table.get("role") in ("dim", "date") and field in _owned_columns(table, ir):
            return table["name"]
    return default_entity


def _field_entity(field: Optional[str], decisions: Dict, ir: Dict) -> str:
    """Return the correct entity (table name) for a slicer field.

    Looks up the field in dim tables first; falls back to the fact entity.
    This ensures Category/Sub-Category → DimProduct, Region/State/City → DimLocation, etc.
    """
    if not field:
        return fact_entity(decisions)
    # Check each dim/date table's columns in the IR
    for table in decisions.get("tables", []):
        if table.get("role") in ("dim", "date"):
            if field in _owned_columns(table, ir):
                return table["name"]
    # Check param tables
    for t in decisions.get("tables", []):
        if t.get("role") == "param" and t["name"] == field:
            return field
    return fact_entity(decisions)


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
    # Parameter list-slicers bind to a disconnected table (column shares name).
    pmap = {slug(t): t for t in ptables}
    if field and slug(field) in pmap:
        tbl = pmap[slug(field)]
        return tbl, tbl, title, "Dropdown"
    # Resolve the correct entity (dim table or fact) for this field
    entity = _field_entity(field, decisions, ir)
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
                     ir: Dict, decisions: Optional[Dict] = None) -> Dict:
    """Resolve a chart category, aggregating dates to the Tableau date level."""
    catf = ws.get("categoryField") if ws else None
    level = ws.get("categoryDateLevel") if ws else None
    dcols = date_cols(ir)
    prop = part_prop(catf, level, dcols)

    def _ent(p: str) -> str:
        return entity_for_field(p, entity, decisions, ir) if decisions else entity

    if prop and (prop in cols or (catf in dcols)):
        # date-part columns live on the fact table that owns the base date column
        return {"entity": entity, "prop": prop}
    if catf and catf in cols:
        return {"entity": _ent(catf), "prop": catf}
    dim = first_dim_col(ir)
    return {"entity": _ent(dim) if dim else entity,
            "prop": dim or (next(iter(cols)) if cols else "Column")}


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
                  mset: Set[str], cols: Set[str],
                  decisions: Optional[Dict] = None) -> List[Dict]:
    out: List[Dict] = []
    dcols = date_cols(ir)
    level = ws.get("categoryDateLevel") if ws else None

    def _ent(prop: str) -> str:
        return entity_for_field(prop, entity, decisions, ir) if decisions else entity

    if ws:
        for d in ws.get("dimensions", []) or []:
            if d in dcols and D.needs_part(level):
                out.append({"entity": entity, "prop": D.part_column_name(d, level),
                            "isMeasure": False})
            elif d in cols:
                out.append({"entity": _ent(d), "prop": d, "isMeasure": False})
        for v in ws.get("values", []) or []:
            if v in mset:
                out.append({"entity": entity, "prop": v, "isMeasure": True})
            elif v in cols:
                out.append({"entity": _ent(v), "prop": v, "isMeasure": False})
    if not out:
        out = [{"entity": _ent(c["name"]), "prop": c["name"], "isMeasure": False}
               for c in ir.get("columns", [])[:6]]
    return out or [{"entity": entity, "prop": "Column", "isMeasure": False}]
