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
                       param_map: Optional[Dict] = None) -> List[Dict]:
    """Return IR worksheets with mark type, shelves, encodings and resolved fields."""
    calc_map = calc_map or {}
    measures = measures or set()
    param_map = param_map or {}
    sheets: List[Dict] = []
    for ws in root.iter("worksheet"):
        name = X.attr(ws, "name", "")
        pane = ws.find(".//panes/pane")
        mark = pane.find("mark") if pane is not None else None
        mark_class = X.attr(mark, "class", "Automatic")
        rows = _shelf_fields(ws, "rows")
        cols = _shelf_fields(ws, "cols")
        encodings = _encodings(pane)
        fields = F.summarize(rows, cols, encodings, calc_map, measures)
        sheets.append({
            "name": name, "datasource": _primary_ds(ws), "markClass": mark_class,
            "rows": rows, "cols": cols, "encodings": encodings,
            "categoryField": fields["category"], "valueField": fields["value"],
            "categoryDateLevel": fields["categoryDateLevel"],
            "dimensions": fields["dimensions"], "values": fields["values"],
            "caption": _worksheet_caption(ws, calc_map, param_map),
            "title": _worksheet_title(ws, calc_map, param_map),
            "filters": _worksheet_filters(ws, calc_map),
            "sort": _worksheet_sort(ws, calc_map),
            "formatting": _worksheet_formatting(ws),
            "inferredVisualType": _infer_type(mark_class, rows, cols, encodings),
        })
    return sheets


def _formatted_text_skeleton(node: Optional[ET.Element], calc_map: Dict,
                             param_map: Dict) -> Optional[str]:
    """Resolve a Tableau <formatted-text> block to a static label skeleton.

    Tableau title/caption runs embed live field/parameter tokens
    (<[Parameters].[..]>, <[ds].[none:Field:nk]>). PBIR textboxes cannot bind
    data, so each token becomes '{Resolved Field}' to preserve the label shape.
    'Æ' is Tableau's soft line-break glyph in titles — collapse it to a space.
    """
    if node is None:
        return None
    parts: List[str] = []
    for run in node.findall("run"):
        text = run.text or ""
        for tok in re.findall(r"<([^>]+)>", text):
            resolved = (F.resolve_param(tok, param_map)
                        if "Parameters" in tok else F.resolve_ref(tok, calc_map))
            # Auto-generated calcs with no friendly caption resolve to their
            # internal 'Calculation_<id>' name -> show a neutral '{value}' token.
            if resolved and re.fullmatch(r"Calculation_\d+", resolved):
                resolved = None
            text = text.replace(f"<{tok}>", f"{{{resolved or 'value'}}}")
        parts.append(text)
    return X.clean_text("".join(parts).replace("\u00c6", " ")) or None


def _worksheet_caption(ws: ET.Element, calc_map: Dict, param_map: Dict) -> Optional[str]:
    """Resolve a worksheet's dynamic <caption> to a static label skeleton."""
    return _formatted_text_skeleton(
        ws.find(".//layout-options/caption/formatted-text"), calc_map, param_map)


def _worksheet_title(ws: ET.Element, calc_map: Dict, param_map: Dict) -> Optional[str]:
    """Resolve a worksheet's <title> (shown above the viz) to a label skeleton."""
    return _formatted_text_skeleton(
        ws.find(".//layout-options/title/formatted-text"), calc_map, param_map)


def _worksheet_filters(ws: ET.Element, calc_map: Dict) -> List[str]:
    """Return the fields that filter this worksheet (from <slices>).

    Tableau lists every column applied as a filter to a sheet under <slices>.
    Action-generated filters (cross-viz interactions) are captured separately in
    actions[] and skipped here so this list reflects real user/data filters.
    """
    out: List[str] = []
    seen = set()
    for col in ws.findall(".//slices/column"):
        ref = (col.text or "").strip()
        if not ref or "Action (" in ref:
            continue
        field = F.resolve_ref(ref, calc_map)
        # Skip Tableau internal pseudo-fields (':Measure Names', ':Measure
        # Values') -- they are not real data filters in Power BI.
        if field and not field.startswith(":") and field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _worksheet_sort(ws: ET.Element, calc_map: Dict) -> Optional[Dict]:
    """Return {field, direction} for an explicit field sort, else None."""
    s = ws.find(".//sort")
    if s is None:
        return None
    field = F.resolve_ref(X.attr(s, "column"), calc_map)
    direction = (X.attr(s, "direction") or "").upper() or None
    if not field:
        return None
    return {"field": field, "direction": direction}


def _worksheet_formatting(ws: ET.Element) -> Optional[Dict]:
    """Extract a compact formatting summary for the worksheet's visual.

    Pulls the colour palette, gridline visibility, field-label visibility, and
    mark stroke/label flags from Tableau <style-rule>/<format> blocks. Returns
    None when the sheet carries no explicit formatting (honest empty, no guess).
    """
    fmt: Dict[str, object] = {
        "colorPalette": None, "gridlines": None, "showFieldLabels": None,
        "markStroke": None, "showMarkLabels": None,
    }
    palette = [c.text for c in ws.findall(".//table/style//color-palette/color") if c.text]
    if palette:
        fmt["colorPalette"] = palette
    style = ws.find(".//table/style")
    if style is not None:
        for rule in style.findall("style-rule"):
            elem = X.attr(rule, "element")
            for f in rule.findall("format"):
                attr, val = X.attr(f, "attr"), X.attr(f, "value")
                if elem == "gridline" and attr == "line-visibility":
                    fmt["gridlines"] = (val == "on")
                elif elem == "worksheet" and attr == "display-field-labels":
                    fmt["showFieldLabels"] = (val == "true")
    for f in ws.findall(".//panes/pane/style//format"):
        attr, val = X.attr(f, "attr"), X.attr(f, "value")
        if attr == "stroke-color":
            fmt["markStroke"] = val
        elif attr == "mark-labels-show":
            fmt["showMarkLabels"] = (val == "true")
    if all(v is None for v in fmt.values()):
        return None
    return fmt


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
    enc: Dict[str, Optional[str]] = {
        "color": None, "size": None, "text": None,
        "shape": None, "detail": None, "label": None,
        "tooltip": None, "wedgeSize": None, "path": None,
    }
    node = pane.find("encodings") if pane is not None else None
    if node is None:
        return enc
    # Tableau tags map to IR encoding channels (wedge-size -> pie angle, lod -> detail)
    tag_to_key = {
        "color": "color", "size": "size", "text": "text",
        "shape": "shape", "lod": "detail", "label": "label",
        "tooltip": "tooltip", "wedge-size": "wedgeSize", "path": "path",
    }
    for tag, key in tag_to_key.items():
        child = node.find(tag)
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
            "title": _formatted_text_skeleton(
                db.find(".//layout-options/title/formatted-text"), calc_map, param_map),
            "background": _dashboard_background(db),
            "zones": zones, "buttons": buttons,
        })
    return dashboards


def _dashboard_background(db: ET.Element) -> Optional[str]:
    """Return the dashboard background colour (#hex) if explicitly set."""
    for f in db.findall(".//style//format"):
        if X.attr(f, "attr") == "background-color":
            val = X.attr(f, "value")
            if val and val.startswith("#"):
                return val
    return None


def extract_actions(root: ET.Element, calc_map: Optional[Dict] = None) -> List[Dict]:
    """Return dashboard actions (filter / highlight / url) -> PBI interactions.

    Tableau <action> elements drive cross-viz behaviour: filter actions become
    Power BI cross-filtering, highlight actions become cross-highlighting, URL
    actions become drillthrough/links. Each record names the source sheet and
    target so the report layer can wire interactions deterministically.
    """
    calc_map = calc_map or {}
    out: List[Dict] = []
    seen = set()
    for actions in root.iter("actions"):
        for act in actions.findall("action"):
            name = X.strip_brackets(X.attr(act, "caption") or X.attr(act, "name") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            cmd = act.find(".//command")
            cmd_name = (X.attr(cmd, "command", "") or "").lower()
            atype = ("filter" if "filter" in cmd_name else
                     "highlight" if "highlight" in cmd_name else
                     "url" if "url" in cmd_name else "other")
            src = act.find("source")
            target = None
            if cmd is not None:
                for p in cmd.findall("param"):
                    if X.attr(p, "name") == "target":
                        target = X.attr(p, "value")
            activation = act.find("activation")
            out.append({
                "name": name,
                "type": atype,
                "sourceSheet": X.attr(src, "worksheet") if src is not None else None,
                "sourceDashboard": X.attr(src, "dashboard") if src is not None else None,
                "target": target,
                "activation": X.attr(activation, "type") if activation is not None else None,
            })
    return out


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
