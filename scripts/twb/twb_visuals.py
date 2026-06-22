"""twb_visuals.py — extract worksheet marks and dashboard zone layouts.

Deterministic extraction of visual metadata. Where the Tableau mark class is
unambiguous we set inferredVisualType; when it is "Automatic" (or otherwise
ambiguous) we leave it null so the LLM resolves it via decisions.json.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twb_xml as X  # noqa: E402
import twb_fields as F  # noqa: E402

# Unambiguous Tableau mark class -> Power BI visualType
MARK_MAP = {
    "Bar": "barChart", "Line": "lineChart", "Area": "areaChart", "Pie": "pieChart",
    "Square": "treemap", "Circle": "scatterChart", "Text": "tableEx",
    "Gantt": "ganttChart", "Map": "map",
}


def worksheet_datasources(root: ET.Element) -> set:
    """Names of datasources referenced by any worksheet (for active flagging)."""
    used = set()
    for ws in root.iter("worksheet"):
        for ds in ws.iter("datasource"):
            cap = X.attr(ds, "caption") or X.attr(ds, "name")
            if cap and cap not in ("Parameters",):
                used.add(cap)
    return used


def extract_worksheets(root: ET.Element, calc_map: Optional[Dict] = None,
                       measures: Optional[set] = None,
                       param_map: Optional[Dict] = None,
                       passthrough: Optional[Dict] = None) -> List[Dict]:
    """Return IR worksheets with mark type, shelves, encodings and resolved fields."""
    calc_map = calc_map or {}
    measures = measures or set()
    param_map = param_map or {}
    passthrough = passthrough or {}
    sheets: List[Dict] = []
    for ws in root.iter("worksheet"):
        name = X.attr(ws, "name", "")
        pane = ws.find(".//panes/pane")
        mark = pane.find("mark") if pane is not None else None
        mark_class = X.attr(mark, "class", "Automatic")
        rows = _shelf_fields(ws, "rows")
        cols = _shelf_fields(ws, "cols")
        encodings = _encodings(pane)
        fields = F.summarize(rows, cols, encodings, calc_map, measures, passthrough)
        sheets.append({
            "name": name, "datasource": _primary_ds(ws), "markClass": mark_class,
            "rows": rows, "cols": cols, "encodings": encodings,
            "categoryField": fields["category"], "valueField": fields["value"],
            "categoryDateLevel": fields["categoryDateLevel"],
            "dimensions": fields["dimensions"], "values": fields["values"],
            "caption": _worksheet_caption(ws, calc_map, param_map),
            "topN": _extract_topn(ws, calc_map, passthrough),
            "inferredVisualType": _infer_type(mark_class, rows, cols, encodings),
        })
    return sheets


def _extract_topn(ws: ET.Element, calc_map: Dict,
                  passthrough: Dict) -> Optional[Dict]:
    """Extract a Tableau Top-N groupfilter (count=N end=top/bottom) for a worksheet.

    Tableau nests: <filter><groupfilter count='10' end='top' function='end'>
    <groupfilter direction='DESC' expression='COUNTD([show_id])' function='order'>
    <groupfilter level='[none:listed_in:nk]'/></groupfilter></groupfilter></filter>.
    Returns {field, count, end, direction, byExpr} or None.
    """
    for filt in ws.iter("filter"):
        top = next((g for g in filt.iter("groupfilter") if g.get("count")), None)
        if top is None:
            continue
        try:
            count = int(top.get("count"))
        except (TypeError, ValueError):
            continue
        end = (top.get("end") or "top").lower()
        order = next((g for g in top.iter("groupfilter")
                      if g.get("expression")), None)
        by_expr = (X.decode_entities(order.get("expression"))
                   if order is not None else None)
        direction = (order.get("direction") if order is not None else "DESC") or "DESC"
        field = F.resolve_ref(filt.get("column"), calc_map, passthrough)
        if not field:
            lvl = next((g for g in top.iter("groupfilter") if g.get("level")), None)
            if lvl is not None:
                field = F.resolve_ref(lvl.get("level"), calc_map, passthrough)
        if not field:
            continue
        return {"field": field, "count": count, "end": end,
                "direction": direction.upper(), "byExpr": by_expr}
    return None


def _worksheet_caption(ws: ET.Element, calc_map: Dict, param_map: Dict) -> Optional[str]:
    """Resolve a worksheet's dynamic <caption> to a static label skeleton.

    Tableau captions embed live field/parameter tokens (<[Parameters].[..]>,
    <[ds].[none:Field:nk]>). PBIR textboxes cannot bind data, so we substitute
    each token with '{Resolved Field}' to preserve the label structure.
    """
    cap = ws.find(".//layout-options/caption/formatted-text")
    if cap is None:
        return None
    parts: List[str] = []
    for run in cap.findall("run"):
        text = run.text or ""
        for tok in re.findall(r"<([^>]+)>", text):
            resolved = (F.resolve_param(tok, param_map)
                        if "Parameters" in tok else F.resolve_ref(tok, calc_map))
            text = text.replace(f"<{tok}>", f"{{{resolved or 'value'}}}")
        parts.append(text)
    return X.clean_text("".join(parts)) or None


def _primary_ds(ws: ET.Element) -> Optional[str]:
    ds = ws.find(".//datasources/datasource")
    return X.attr(ds, "caption") or X.attr(ds, "name") if ds is not None else None


def _shelf_fields(ws: ET.Element, shelf: str) -> List[str]:
    node = ws.find(f".//{shelf}")
    if node is None or not node.text:
        return []
    parts = [p.strip() for p in node.text.split("/")]
    return [X.strip_brackets(p) for p in parts if p.strip()]


def _encodings(pane: Optional[ET.Element]) -> Dict[str, Optional[str]]:
    enc = {"color": None, "size": None, "text": None}
    node = pane.find("encodings") if pane is not None else None
    if node is None:
        return enc
    for key in ("color", "size", "text"):
        child = node.find(key)
        if child is not None:
            enc[key] = X.strip_brackets(X.attr(child, "column"))
    return enc


def _infer_type(mark_class: str, rows: List[str], cols: List[str],
                enc: Dict[str, Optional[str]]) -> Optional[str]:
    """Return a Power BI visualType, or None when ambiguous (LLM resolves)."""
    if mark_class == "Text":
        return "tableEx"
    if mark_class in MARK_MAP:
        return MARK_MAP[mark_class]
    if mark_class == "Automatic":
        if not rows and not cols:
            return "card"
        if enc.get("color") and enc.get("size") and enc.get("text"):
            return "treemap"
    return None  # could be bar or table -> defer to LLM


def extract_dashboards(root: ET.Element, calc_map: Optional[Dict] = None,
                       param_map: Optional[Dict] = None) -> List[Dict]:
    """Return IR dashboards with size, classified zones and navigation buttons."""
    calc_map = calc_map or {}
    param_map = param_map or {}
    ws_names = {X.attr(w, "name", "") for w in root.iter("worksheet")}
    dashboards: List[Dict] = []
    for db in root.iter("dashboard"):
        size = db.find("size")
        zones, buttons = _zones_and_buttons(db, ws_names, calc_map, param_map)
        dashboards.append({
            "name": X.attr(db, "name", ""),
            "size": {"w": X.int_attr(size, "maxwidth", 1366),
                     "h": X.int_attr(size, "maxheight", 768)},
            "zones": zones, "buttons": buttons,
        })
    return dashboards


def _zones_and_buttons(db: ET.Element, ws_names: set, calc_map: Dict, param_map: Dict):
    """Classify only the main layout's leaf zones (skip the Phone devicelayout)."""
    zones: List[Dict] = []
    buttons: List[Dict] = []
    seen = set()
    layout = db.find("zones")  # direct child -> excludes <devicelayouts>
    if layout is None:
        return zones, buttons
    for zone in layout.iter("zone"):
        zid = X.attr(zone, "id")
        if zid in seen:
            continue
        rect = {
            "x": X.int_attr(zone, "x"), "y": X.int_attr(zone, "y"),
            "w": X.int_attr(zone, "w"), "h": X.int_attr(zone, "h"),
        }
        button = zone.find("button")
        if button is not None:
            seen.add(zid)
            buttons.append(_button_record(button, rect))
            continue
        rec = _classify_zone(zone, ws_names, calc_map, param_map, rect)
        if rec is not None:
            seen.add(zid)
            zones.append(rec)
    return zones, buttons


def _classify_zone(zone: ET.Element, ws_names: set, calc_map: Dict,
                   param_map: Dict, rect: Dict) -> Optional[Dict]:
    """Return an IR zone record, or None for containers/spacers/images."""
    name = X.attr(zone, "name")
    ztype = (X.attr(zone, "type-v2") or X.attr(zone, "type") or "").lower()
    param = X.attr(zone, "param")
    if "filter" in ztype:
        return {"type": "filter", "worksheet": name, "field": F.resolve_ref(param, calc_map), **rect}
    if "paramctrl" in ztype or "parameter" in ztype:
        return {"type": "paramctrl", "worksheet": None, "field": F.resolve_param(param, param_map), **rect}
    if name and name in ws_names:
        return {"type": "viz", "worksheet": name, "field": None, **rect}
    if ztype == "text":
        return {"type": "text", "worksheet": None, "field": None, "text": _zone_text(zone), **rect}
    return None  # layout-basic/flow, empty, bitmap -> not a data visual


def _zone_text(zone: ET.Element) -> str:
    """Concatenate formatted-text runs inside a text zone."""
    runs = [r.text or "" for r in zone.findall(".//formatted-text/run")]
    return X.clean_text(X.decode_entities(" ".join(runs)))


def _button_record(button: ET.Element, rect: Dict) -> Dict:
    action_raw = X.attr(button, "action", "") or ""
    toggle = button.find("toggle-action") is not None
    state = button.find(".//button-visual-state")
    action = "toggle" if toggle else ("goto-sheet" if "goto-sheet" in action_raw else "other")
    return {"action": action, "target": X.attr(button, "window-id"),
            "tooltip": X.attr(state, "tooltip") if state is not None else None, **rect}
