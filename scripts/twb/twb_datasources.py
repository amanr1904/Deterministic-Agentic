"""twb_datasources.py — extract datasources, columns, calculated fields, parameters.

Pure deterministic extraction from the .twb XML into IR fragments. The DAX
complexity classifier lives in scripts/dax/map_dax.py; here we only flag whether
a calc *looks* like a table calc (WINDOW_/RUNNING_/INDEX/LOOKUP) for the IR.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twb_xml as X  # noqa: E402

TABLE_CALC_RE = re.compile(
    r"\b(WINDOW_\w+|RUNNING_\w+|INDEX|RANK|FIRST|LAST|LOOKUP|TOTAL|PREVIOUS_VALUE)\s*\(",
    re.IGNORECASE,
)


def extract_datasources(root: ET.Element, active_names: set) -> List[Dict]:
    """Return IR dataSources list (excluding the inline Parameters store)."""
    result: List[Dict] = []
    for ds in X.iter_datasources(root):
        name = X.attr(ds, "name", "")
        if name == "Parameters":
            continue
        caption = X.datasource_caption(ds)
        conn = _first_connection(ds)
        conn_class = X.attr(conn, "class")
        files = _connection_files(ds)
        result.append({
            "name": caption,
            "internalName": name,
            "connectionClass": conn_class or "",
            "sourceType": X.resolve_source_type(conn_class),
            "files": files,
            "server": X.attr(conn, "server"),
            "database": X.attr(conn, "dbname"),
            "schema": X.attr(conn, "schema"),
            "tables": _relation_tables(ds),
            "active": caption in active_names or name in active_names,
        })
    return result


def _first_connection(ds: ET.Element) -> Optional[ET.Element]:
    conn = X.find(ds, "connection")
    if conn is None:
        return None
    named = conn.find("named-connections/named-connection/connection")
    return named if named is not None else conn


def _connection_files(ds: ET.Element) -> List[str]:
    files: List[str] = []
    for conn in ds.iter("connection"):
        for key in ("filename", "directory"):
            val = conn.get(key)
            if val and val not in files:
                files.append(val)
    return files


def _relation_tables(ds: ET.Element) -> List[str]:
    tables: List[str] = []
    for rel in ds.iter("relation"):
        tbl = rel.get("table") or rel.get("name")
        if tbl:
            clean = X.strip_brackets(tbl)
            if clean and clean not in tables:
                tables.append(clean)
    return tables


def extract_columns(root: ET.Element) -> List[Dict]:
    """Return non-calc <column> IR records, deduped per (datasource, name)."""
    cols: List[Dict] = []
    seen = set()
    for ds in X.iter_datasources(root):
        if X.attr(ds, "name") == "Parameters":
            continue
        ds_caption = X.datasource_caption(ds)
        ordinal = _ordinal_map(ds)
        for col in ds.iter("column"):
            if col.find("calculation") is not None:
                continue
            name = X.attr(col, "name", "")
            if "__tableau_internal" in name or "_object_id__" in name:
                continue
            record = _column_record(col, ds_caption, ordinal)
            key = (record["datasource"], record["name"])
            if key not in seen:
                seen.add(key)
                cols.append(record)
    return cols


def _ordinal_map(ds: ET.Element) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    meta = ds.find("connection/metadata-records")
    if meta is None:
        return mapping
    for rec in meta.findall("metadata-record"):
        local = rec.findtext("local-name")
        ordinal = rec.findtext("ordinal")
        if local and ordinal and ordinal.isdigit():
            mapping[X.strip_brackets(local)] = int(ordinal)
    return mapping


def _column_record(col: ET.Element, ds_caption: str, ordinal: Dict[str, int]) -> Dict:
    name = X.strip_brackets(X.attr(col, "name"))
    return {
        "datasource": ds_caption,
        "name": name,
        "caption": X.attr(col, "caption"),
        "dataType": X.resolve_datatype(X.attr(col, "datatype")),
        "role": "measure" if X.attr(col, "role") == "measure" else "dimension",
        "semanticRole": X.attr(col, "semantic-role"),
        "format": _format_string(col),
        "ordinal": ordinal.get(name),
    }


def _format_string(col: ET.Element) -> Optional[str]:
    fmt = col.find("./format")
    return X.attr(fmt, "format") if fmt is not None else None


def extract_calculated_fields(root: ET.Element) -> List[Dict]:
    """Return IR calculatedFields with verbatim decoded formulas."""
    fields: List[Dict] = []
    seen = set()
    for ds in X.iter_datasources(root):
        for col in ds.iter("column"):
            calc = col.find("calculation")
            if calc is None or calc.get("formula") is None:
                continue
            caption = X.attr(col, "caption") or X.strip_brackets(X.attr(col, "name"))
            if caption in seen:
                continue
            seen.add(caption)
            formula = X.decode_entities(calc.get("formula"))
            is_tc = bool(TABLE_CALC_RE.search(formula))
            fields.append({
                "caption": caption,
                "fieldName": X.attr(col, "name"),
                "dataType": X.resolve_datatype(X.attr(col, "datatype")),
                "role": X.attr(col, "role"),
                "formula": formula,
                "isTableCalc": is_tc,
                "complexity": "complex" if is_tc else "trivial",
                "suggestedDaxKind": "measure" if X.attr(col, "role") == "measure" else "column",
            })
    return fields


def extract_parameters(root: ET.Element) -> List[Dict]:
    """Return IR parameters from the inline Parameters datasource."""
    params: List[Dict] = []
    for ds in X.iter_datasources(root):
        if X.attr(ds, "name") != "Parameters":
            continue
        for col in ds.iter("column"):
            if col.get("param-domain-type") is None:
                continue
            members = [X.attr(m, "value") for m in col.findall("members/member")]
            params.append({
                "name": X.attr(col, "caption") or X.strip_brackets(X.attr(col, "name")),
                "internalName": X.attr(col, "name"),
                "dataType": X.resolve_datatype(X.attr(col, "datatype")),
                "domainType": X.attr(col, "param-domain-type", "any"),
                "default": X.attr(col, "value"),
                "values": [v for v in members if v],
                "range": _param_range(col),
                "format": X.attr(col, "default-format") or _format_string(col),
            })
    return params


def _param_range(col: ET.Element) -> Optional[Dict]:
    """Return {min,max,granularity} for range parameters (What-If in Power BI)."""
    rng = col.find("range")
    if rng is None:
        return None
    return {
        "min": X.attr(rng, "min"),
        "max": X.attr(rng, "max"),
        "granularity": X.attr(rng, "granularity"),
    }
