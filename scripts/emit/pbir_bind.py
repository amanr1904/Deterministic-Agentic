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
<<<<<<< HEAD
import tmdl_blocks as TB  # noqa: E402

# Cache of physical CSV headers so we read each file at most once.
_HEADER_CACHE: Dict[str, Set[str]] = {}


def _table_columns(table: Dict, ir: Dict) -> Set[str]:
    """Return the set of column names a table actually owns.

    Prefers the physical CSV header (for csv-backed dims defined with
    sourceFile), then IR columns scoped by sourceDatasource, and only falls
    back to ALL IR columns when neither is available. Without this, a star
    schema dim defined with sourceFile (src=None) would match EVERY IR column
    and wrongly claim fact fields like grade/loan_status -> broken slicers.
    """
    src_file = table.get("sourceFile")
    if src_file and str(src_file).lower().endswith(".csv"):
        key = os.path.abspath(src_file)
        if key not in _HEADER_CACHE:
            _HEADER_CACHE[key] = set(TB.read_csv_header(src_file))
        if _HEADER_CACHE[key]:
            return _HEADER_CACHE[key]
    src = table.get("sourceDatasource")
    if src is not None:
        return {c["name"] for c in ir.get("columns", []) if c.get("datasource") == src}
    return {c["name"] for c in ir.get("columns", [])}
=======
import emit_tmdl as ET  # noqa: E402  (reuse the same CSV probe the model emitter uses)

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
>>>>>>> main


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

    Falls back to the table name only if no datatable/key column is declared.
    """
    if not field:
        return fact_entity(decisions)
    # Check each dim/date table's REAL columns (physical CSV header), so a field
    # only resolves to a dim that actually contains it; otherwise fall through to
    # the fact entity.
    for table in decisions.get("tables", []):
        if table.get("role") in ("dim", "date"):
<<<<<<< HEAD
            if field in _table_columns(table, ir):
=======
            if field in _owned_columns(table, ir):
>>>>>>> main
                return table["name"]
    # Check param tables
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


def _param_candidates(t: Dict) -> Set[str]:
    """All slugs a param table can be matched against (name, value column,
    key columns and any declared sourceFields/aliases). The value column often
    carries the real Tableau parameter caption (e.g. 'Filter Adults/Peds')."""
    cands = {slug(t.get("name", ""))}
    dt = t.get("datatable") or {}
    for c in dt.get("columns") or []:
        cands.add(slug(c.get("name", "")))
    for k in t.get("keyColumns") or []:
        cands.add(slug(k))
    for a in (t.get("sourceFields") or t.get("aliases") or []):
        cands.add(slug(a))
    return {c for c in cands if c}


def param_table_for_field(field: Optional[str], decisions: Dict,
                          zone_type: Optional[str] = None) -> Optional[str]:
    """Resolve the disconnected param table a Tableau zone field maps to.

    The decisions.json param table is frequently RENAMED (e.g. ViewMode,
    AdultsPeds) while the dashboard zone keeps the original Tableau parameter
    caption ('View', 'Filter Adults/Peds'). Match on table name slug, value
    column slug and aliases (any zone); for paramctrl zones also allow a safe
    containment match (>=4 chars) so 'View'->'ViewMode' and
    'Filter Adults/Peds'->'AdultsPeds' resolve instead of falling back to the
    fact date column. Containment is gated to paramctrl so real data filters
    (type='filter') are never redirected to a parameter table."""
    if not field:
        return None
    fs = slug(field)
    params = [t for t in decisions.get("tables", []) if t.get("role") == "param"]
    for t in params:
        if fs in _param_candidates(t):
            return t["name"]
    if zone_type == "paramctrl":
        best: Optional[tuple] = None
        for t in params:
            for cand in _param_candidates(t):
                if len(fs) >= 4 and len(cand) >= 4 and (fs in cand or cand in fs):
                    if best is None or len(cand) > best[1]:
                        best = (t["name"], len(cand))
        if best:
            return best[0]
    return None


def resolve_slicer(zone: Dict, ir: Dict, decisions: Dict):
    """Return (entity, prop, title, mode) for a filter / parameter-control zone.

    mode is 'Between' for date-range parameters (Start/End Date) so each acts as
    an independent bound on the date column, else 'Dropdown' for list slicers.
    """
    field = zone.get("field")
    cols = column_names(ir)
    title = field or zone.get("worksheet") or "Filter"
    # Date-range parameter (e.g. 'Start Date' / 'End Date') -> Between slicer on
    # the fact date column, so Start and End are independent bounds.
    if zone.get("type") == "paramctrl" and _is_date_param(field, decisions):
        entity = fact_entity(decisions)
        dcol = first_date_col(ir)
        if dcol:
            return entity, dcol, title, "Between"
    # Parameter list-slicers bind to a disconnected table on its value column
    # (e.g. SelectYear[Year]), NOT the table name. Match by table name, value
    # column or alias so a RENAMED param table (ViewMode, AdultsPeds) still
    # resolves the original Tableau zone caption ('View', 'Filter Adults/Peds').
    pname = param_table_for_field(field, decisions, zone.get("type"))
    if pname:
        return pname, _param_value_column(pname, decisions), title, "Dropdown"
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
            if _is_pseudo_field(d):
                continue  # Tableau [:Measure Names]/[:Measure Values] have no model column
            if d in dcols and D.needs_part(level):
                out.append({"entity": entity, "prop": D.part_column_name(d, level),
                            "isMeasure": False})
            elif d in cols:
                out.append({"entity": _ent(d), "prop": d, "isMeasure": False})
        for v in ws.get("values", []) or []:
            if _is_pseudo_field(v):
                continue
            if v in mset:
                out.append({"entity": entity, "prop": v, "isMeasure": True})
            elif v in cols:
                out.append({"entity": _ent(v), "prop": v, "isMeasure": False})
    if not out:
        out = [{"entity": _ent(c["name"]), "prop": c["name"], "isMeasure": False}
               for c in ir.get("columns", [])[:6]]
    return out or [{"entity": entity, "prop": "Column", "isMeasure": False}]


def _is_pseudo_field(name: str) -> bool:
    """Tableau synthetic shelf fields ([:Measure Names], [:Measure Values], etc.)
    that have no backing model column/measure — binding them errors the visual."""
    n = (name or "").strip()
    if n.startswith(":"):
        return True
    return n.lower() in {"measure names", "measure values",
                         "number of records", "multiple values"}
