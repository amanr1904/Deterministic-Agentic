"""pbir_blocks.py — PBIR JSON visual builders (enhanced folder format).

Builds visual.json / page.json dictionaries that conform to the PBIR
visualContainer schema. Per the format rules, a visual.json root may ONLY carry
$schema / name / position / visual — no filters or extra properties. Color and
boolean values use the Literal expression wrapper Power BI Desktop requires.
"""
from __future__ import annotations

from typing import Dict, List, Optional

VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"


def literal(value) -> Dict:
    """Wrap a scalar in the PBIR Literal expression form."""
    if isinstance(value, bool):
        return {"expr": {"Literal": {"Value": "true" if value else "false"}}}
    if isinstance(value, str):
        return {"expr": {"Literal": {"Value": f"'{value}'"}}}
    return {"expr": {"Literal": {"Value": str(value)}}}


def color(hex_value: str) -> Dict:
    """Build a solid-color property value."""
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_value}'"}}}}}


def position(x: int, y: int, w: int, h: int, z: int) -> Dict:
    """Standard visual position block."""
    return {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}


def projection(entity: str, prop: str, active: bool = True) -> Dict:
    """A single column projection for a visual query."""
    return {
        "field": {"Column": {
            "Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": active,
    }


def measure_projection(entity: str, prop: str, active: bool = True) -> Dict:
    """A single measure projection for a visual query."""
    return {
        "field": {"Measure": {
            "Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": active,
    }


def binding_projection(b: Dict) -> Dict:
    """Build a projection from a {entity, prop, isMeasure} binding dict."""
    if b.get("isMeasure"):
        return measure_projection(b["entity"], b["prop"])
    return projection(b["entity"], b["prop"])


def slicer_visual(name: str, pos: Dict, entity: str, prop: str,
                  title: str, header_color: str = "#004263",
                  mode: str = "Dropdown", single: bool = True,
                  default_value: Optional[str] = None) -> Dict:
    """Build a slicer visual.json dict (Dropdown list or Between range).

    mode='Between' produces a numeric/date range slicer so two such slicers on
    the same column act as independent lower/upper bounds (Start / End dates).
    default_value pre-selects one item (used for field-parameter toggles so the
    bound visual opens on one field instead of showing every field at once).
    """
    data_props = {"mode": literal(mode)}
    objects = {
        "data": [{"properties": data_props}],
        "header": [{"properties": {
            "show": literal(True), "text": literal(title),
            "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{header_color}'"}}}}},
        }}],
    }
    if mode != "Between":
        objects["selection"] = [{"properties": {"singleSelect": literal(single)}}]
    if default_value is not None and mode != "Between":
        objects["general"] = [{"properties": {
            "filter": _slicer_default_filter(entity, prop, default_value)}}]
    return {
        "$schema": VC_SCHEMA, "name": name, "position": pos,
        "visual": {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [projection(entity, prop)]}}},
            "objects": objects,
            "visualContainerObjects": {
                "title": [{"properties": {"show": literal(False)}}],
            },
        },
    }


def _slicer_default_filter(entity: str, prop: str, value: str) -> Dict:
    """A single-value In condition used as a slicer's pre-selected default."""
    return {"filter": {
        "Version": 2,
        "From": [{"Name": "s", "Entity": entity, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {
                "Expression": {"SourceRef": {"Source": "s"}}, "Property": prop}}],
            "Values": [[{"Literal": {"Value": f"'{value}'"}}]],
        }}}],
    }}


def chart_visual(name: str, pos: Dict, visual_type: str, category: Dict,
                 value: Dict, title: Optional[str] = None) -> Dict:
    """Build a cartesian chart (bar/column/line) visual.json dict."""
    query = {"queryState": {
        "Category": {"projections": [binding_projection(category)]},
        "Y": {"projections": [binding_projection(value)]},
    }}
    visual = {"visualType": visual_type, "query": query,
              "objects": {"labels": [{"properties": {"show": literal(True)}}]}}
    if title:
        visual["visualContainerObjects"] = {
            "title": [{"properties": {"show": literal(True), "text": literal(title)}}]}
    return {"$schema": VC_SCHEMA, "name": name, "position": pos, "visual": visual}


def table_visual(name: str, pos: Dict, columns: List[Dict],
                 title: Optional[str] = None) -> Dict:
    """Build a tableEx visual.json dict from a list of {entity, prop} columns."""
    projections = [binding_projection(c) for c in columns]
    visual = {"visualType": "tableEx",
              "query": {"queryState": {"Values": {"projections": projections}}}}
    if title:
        visual["visualContainerObjects"] = {
            "title": [{"properties": {"show": literal(True), "text": literal(title)}}]}
    return {"$schema": VC_SCHEMA, "name": name, "position": pos, "visual": visual}


def textbox_visual(name: str, pos: Dict, text: str, size: int = 18,
                   bold: bool = True, hex_color: str = "#004263") -> Dict:
    """Build a textbox visual with a single styled paragraph run."""
    run = {"value": text, "textStyle": {
        "fontSize": f"{size}pt", "fontWeight": "bold" if bold else "normal",
        "color": hex_color}}
    paragraphs = [{"textRuns": [run]}]
    return {
        "$schema": VC_SCHEMA, "name": name, "position": pos,
        "visual": {"visualType": "textbox",
                   "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]}},
    }


def card_visual(name: str, pos: Dict, entity: str, measure: str) -> Dict:
    """Build a single-value card bound to a measure."""
    proj = {"field": {"Measure": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": measure}},
        "queryRef": f"{entity}.{measure}", "nativeQueryRef": measure}
    return {"$schema": VC_SCHEMA, "name": name, "position": pos,
            "visual": {"visualType": "card",
                       "query": {"queryState": {"Values": {"projections": [proj]}}}}}


def page_json(name: str, display: str, width: int, height: int) -> Dict:
    """Build a page.json dict."""
    return {"$schema": PAGE_SCHEMA, "name": name, "displayName": display,
            "displayOption": "FitToPage", "height": height, "width": width}


def pages_json(order: List[str], active: str) -> Dict:
    """Build the pages.json metadata dict."""
    return {"$schema": PAGES_SCHEMA, "pageOrder": order, "activePageName": active}
