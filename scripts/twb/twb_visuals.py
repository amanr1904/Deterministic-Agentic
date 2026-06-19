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

# Mark classes that draw geographic shapes -> Power BI map.
MAP_MARKS = {"Map", "Multipolygon", "Polygon", "Filled Map"}

# Tableau <column-instance> derivation -> DAX aggregation. The derivation is the
# AUTHORITATIVE signal that a field is used as a measure (value) on a sheet, even
# when the underlying column is dimension-typed (e.g. CountD of an id column).
DERIVATION_AGG = {
    "Sum": "SUM", "Avg": "AVG", "Count": "COUNT", "CountD": "COUNTD",
    "Min": "MIN", "Max": "MAX", "Median": "MEDIAN", "Attr": "ATTR",
    "StdDev": "STDEV", "Var": "VAR",
}
# Date-truncation derivations -> a date grain (these stay DIMENSIONS, not values).
DATE_DERIV_LEVEL = {
    "Year": "year", "Quarter": "quarter", "Month": "month", "Week": "week",
    "Day": "day", "Trunc Year": "year", "Trunc Quarter": "quarter",
    "Trunc Month": "month", "Trunc Week": "week", "Trunc Day": "day",
}
_HASH_SUFFIX = re.compile(r"\s*\(copy\)(\s*\(copy\))*(_\d{6,})?$|_\d{12,}$")


def _clean_field(name: str, calc_map: Dict) -> str:
    """Resolve a raw column token to a friendly field name.

    Maps internal Calculation_<id> -> caption, and strips Tableau duplicate-field
    noise ((copy) and _<long-digits> suffixes) so shelves read like Tableau's UI.
    """
    name = X.strip_brackets(name)
    if name in calc_map:
        return calc_map[name]
    stripped = _HASH_SUFFIX.sub("", name).strip()
    return calc_map.get(stripped, stripped or name)


def _column_instances(ws: ET.Element, calc_map: Dict) -> List[Dict]:
    """Parse a worksheet's <datasource-dependencies>/<column-instance> block.

    This is the authoritative per-sheet field list: each entry names the source
    column, its aggregation (derivation) and value/dimension type. Far more
    reliable than scraping the rows/cols shelf text, which is what the parser
    used before (and which lost every aggregated measure).
    """
    out: List[Dict] = []
    seen = set()
    for ci in ws.findall(".//datasource-dependencies/column-instance"):
        col = X.attr(ci, "column")
        deriv = X.attr(ci, "derivation", "None")
        typ = X.attr(ci, "type", "")
        iname = X.attr(ci, "name", "")
        if not col or iname in seen:
            continue
        seen.add(iname)
        agg = DERIVATION_AGG.get(deriv)
        date_level = DATE_DERIV_LEVEL.get(deriv)
        is_measure = bool(agg) or (typ == "quantitative" and not date_level)
        out.append({
            "field": _clean_field(col, calc_map),
            "column": X.strip_brackets(col),
            "agg": agg,
            "type": typ,
            "instanceName": iname,
            "isMeasure": is_measure,
            "dateLevel": date_level,
        })
    return out


def _topn_filter(ws: ET.Element, calc_map: Dict) -> Optional[Dict]:
    """Extract a Tableau Top-N filter (groupfilter count/end='top') if present."""
    for filt in ws.findall(".//filter"):
        top = filt.find(".//groupfilter[@end='top']")
        if top is None:
            top = filt.find(".//groupfilter[@end='bottom']")
        if top is None:
            continue
        count = top.get("count")
        if not count:
            continue
        order = top.find(".//groupfilter[@function='order']")
        direction = (X.attr(order, "direction") or "DESC").upper() if order is not None else "DESC"
        by_expr = X.attr(order, "expression") if order is not None else None
        field = F.resolve_ref(X.attr(filt, "column"), calc_map)
        return {
            "field": field,
            "n": int(count) if count.isdigit() else count,
            "direction": "TOP" if X.attr(top, "end") == "top" else "BOTTOM",
            "byMeasure": by_expr,
            "sortDirection": direction,
        }
    return None


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
        instances = _column_instances(ws, calc_map)
        fields = _resolve_fields(instances, rows, cols, encodings, calc_map, measures)
        rows_text = (ws.findtext(".//rows") or "")
        cols_text = (ws.findtext(".//cols") or "")
        orientation = _orientation(
            [ci for ci in instances if ci["isMeasure"]], rows_text, cols_text)
        sheets.append({
            "name": name, "datasource": _primary_ds(ws), "markClass": mark_class,
            "rows": rows, "cols": cols, "encodings": encodings,
            "categoryField": fields["category"], "valueField": fields["value"],
            "categoryDateLevel": fields["categoryDateLevel"],
            "dimensions": fields["dimensions"], "values": fields["values"],
            "measures": fields["measures"],
            "axes": _axes(fields, orientation),
            "orientation": orientation,
            "caption": _worksheet_caption(ws, calc_map, param_map),
            "title": _worksheet_title(ws, calc_map, param_map),
            "filters": _worksheet_filters(ws, calc_map),
            "filterDetails": _worksheet_filter_details(ws, calc_map),
            "topN": _topn_filter(ws, calc_map),
            "sort": _worksheet_sort(ws, calc_map),
            "formatting": _worksheet_formatting(ws),
            "inferredVisualType": _infer_type(
                mark_class, fields, encodings, orientation),
        })
    return sheets


def _resolve_fields(instances: List[Dict], rows: List[str], cols: List[str],
                    enc: Dict, calc_map: Dict, measures: set) -> Dict:
    """Pick category/value/dimensions/values from column-instances when present.

    The <column-instance> block is authoritative (it carries the aggregation), so
    it is preferred. When a worksheet has no dependency block we fall back to the
    legacy shelf-text heuristic in twb_fields.summarize.
    """
    if instances:
        meas = _dedupe([ci["field"] for ci in instances if ci["isMeasure"]])
        dims = _dedupe([ci["field"] for ci in instances if not ci["isMeasure"]])
        measures_detail = _dedupe_measures(
            {"field": ci["field"], "agg": ci["agg"] or "SUM", "column": ci["column"]}
            for ci in instances if ci["isMeasure"])
        date_level = next(
            (ci["dateLevel"] for ci in instances
             if not ci["isMeasure"] and ci["dateLevel"]), None)
        return {
            "category": dims[0] if dims else None,
            "value": meas[0] if meas else None,
            "dimensions": dims, "values": meas,
            "measures": measures_detail, "categoryDateLevel": date_level,
        }
    legacy = F.summarize(rows, cols, enc, calc_map, measures)
    return {
        "category": legacy["category"], "value": legacy["value"],
        "dimensions": legacy["dimensions"], "values": legacy["values"],
        "measures": [{"field": v, "agg": "SUM", "column": v}
                     for v in legacy["values"]],
        "categoryDateLevel": legacy["categoryDateLevel"],
    }


def _axes(fields: Dict, orientation: Optional[str]) -> Dict:
    """Make the 'what vs what' of the chart explicit (category vs value axes).

    Restates the resolved shelf fields as a plain category/value axis pair so the
    report layer (and a human reader) can see, at a glance, what sits on each
    axis: the category axis (X for vertical charts), its date grain if any, and
    the ordered measures plotted on the value axis (Y).
    """
    return {
        "category": fields.get("category"),
        "categoryLevel": fields.get("categoryDateLevel"),
        "values": list(fields.get("values") or []),
        "orientation": orientation,
    }


def _dedupe(items: List[Optional[str]]) -> List[str]:
    seen: List[str] = []
    for it in items:
        if it and it not in seen:
            seen.append(it)
    return seen


def _dedupe_measures(items) -> List[Dict]:
    seen: List[Dict] = []
    names = set()
    for it in items:
        if it["field"] and it["field"] not in names:
            names.add(it["field"])
            seen.append(it)
    return seen


def _orientation(measure_instances: List[Dict], rows_text: str,
                 cols_text: str) -> Optional[str]:
    """Bars are horizontal when the measure sits on Columns, vertical on Rows."""
    for ci in measure_instances:
        tok = ci.get("instanceName", "").strip("[]")
        if not tok:
            continue
        if tok in (cols_text or ""):
            return "horizontal"
        if tok in (rows_text or ""):
            return "vertical"
    return None


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


def _worksheet_filter_details(ws: ET.Element, calc_map: Dict) -> List[Dict]:
    """Capture every filter's column, type and include/exclude selection (metadata).

    Combines two XML sources so no filter column is missed: the <filter> elements
    (which carry the class + member logic) and the <slices> list (the complete set
    of columns filtered on the sheet). Reads only the filter DEFINITION, never the
    data. Internal pseudo-filters (:Measure Names) and action-generated filters are
    skipped — those are captured separately in actions[]. Member values capped.
    """
    by_field: Dict[str, Dict] = {}
    order: List[str] = []

    def _add(field: Optional[str], fclass, scope, values, rng):
        if not field or field.startswith(":"):
            return
        if field not in by_field:
            order.append(field)
            by_field[field] = {"field": field, "filterClass": fclass,
                               "scope": scope, "values": values, "range": rng}
        else:  # enrich an existing slice-only entry with <filter> detail
            rec = by_field[field]
            rec["filterClass"] = rec["filterClass"] or fclass
            rec["scope"] = rec["scope"] or scope
            rec["values"] = rec["values"] or values
            rec["range"] = rec["range"] or rng

    # 1) rich <filter> elements (type + member logic)
    for filt in ws.findall(".//filter"):
        col = X.attr(filt, "column")
        if not col or "Action (" in col:
            continue
        scope, values, rng = _filter_logic(filt)
        _add(F.resolve_ref(col, calc_map), X.attr(filt, "class"), scope, values, rng)

    # 2) <slices> columns (the complete filtered-column list)
    for col in ws.findall(".//slices/column"):
        ref = (col.text or "").strip()
        if not ref or "Action (" in ref:
            continue
        _add(F.resolve_ref(ref, calc_map), None, None, None, None)

    return [by_field[f] for f in order]


def _filter_logic(filt: ET.Element):
    """Return (scope, values, range) for a <filter>: include/exclude + members.

    Categorical filters list selected members via <groupfilter function='member'>;
    an 'except'/'exclusions' wrapper means EXCLUDE. Quantitative/range filters
    carry numeric <min>/<max>. Member values are capped at 25 (this is the filter
    definition, not data extraction).
    """
    members: List[str] = []
    scope: Optional[str] = None
    for gf in filt.findall(".//groupfilter"):
        fn = (X.attr(gf, "function") or "").lower()
        if fn in ("except", "exclusions"):
            scope = "exclude"
        elif fn == "member":
            if scope is None:
                scope = "include"
            mem = X.attr(gf, "member")
            if mem:
                members.append(mem.strip('"').strip("[]"))
    rng = None
    mn, mx = filt.findtext(".//min"), filt.findtext(".//max")
    if mn is not None or mx is not None:
        rng = {"min": mn, "max": mx}
    values = members[:25] if members else None
    return scope, values, rng


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
        "markColor": None, "background": None,
        "fontName": None, "fontSize": None, "fontColor": None,
        "alignment": None, "titleColor": None, "titleFontSize": None,
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
                elif elem == "table" and attr == "background-color" and val:
                    fmt["background"] = val
                # Font + alignment (first value wins; title scoped separately)
                if attr == "font-family" and val and not fmt["fontName"]:
                    fmt["fontName"] = val
                elif attr == "font-size" and val:
                    if elem == "title" and not fmt["titleFontSize"]:
                        fmt["titleFontSize"] = val
                    elif not fmt["fontSize"]:
                        fmt["fontSize"] = val
                elif attr == "text-align" and val and not fmt["alignment"]:
                    fmt["alignment"] = val
                elif attr == "color" and val:
                    if elem == "title" and not fmt["titleColor"]:
                        fmt["titleColor"] = val
                    elif not fmt["fontColor"]:
                        fmt["fontColor"] = val
    for f in ws.findall(".//panes/pane/style//format"):
        attr, val = X.attr(f, "attr"), X.attr(f, "value")
        if attr == "stroke-color":
            fmt["markStroke"] = val
        elif attr == "mark-labels-show":
            fmt["showMarkLabels"] = (val == "true")
        elif attr == "mark-color" and val:
            fmt["markColor"] = val
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


def _infer_type(mark_class: str, fields: Dict,
                enc: Dict[str, Optional[str]], orientation: Optional[str]) -> Optional[str]:
    """Return a Power BI visualType, or None when still genuinely ambiguous.

    Driven by the resolved field counts (from column-instances) instead of raw
    shelf text, so count/distinct measures and KPI cards are now classified.
    """
    if mark_class in MAP_MARKS:
        return "map"
    if mark_class == "Text":
        return "tableEx"
    if mark_class in MARK_MAP:
        return MARK_MAP[mark_class]
    n_dim = len(fields.get("dimensions") or [])
    n_val = len(fields.get("values") or [])
    has_date = fields.get("categoryDateLevel") is not None
    if mark_class == "Automatic":
        if n_dim == 0 and n_val == 0:
            return "card"
        if enc.get("color") and enc.get("size") and enc.get("text"):
            return "treemap"
        if n_dim == 0 and n_val >= 1:
            return "card"                      # single-number KPI
        if n_val >= 2 and n_dim >= 1:
            return "tableEx"                   # multi-measure summary table
        if has_date and n_val >= 1:
            return "lineChart"                 # measure over a date axis
        if n_dim >= 1 and n_val >= 1:
            return "columnChart" if orientation == "vertical" else "barChart"
        if n_dim >= 1 and n_val == 0:
            return "tableEx"
    return None  # leave for the LLM to resolve via decisions.json


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
