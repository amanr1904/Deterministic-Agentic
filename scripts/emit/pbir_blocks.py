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


def _num(value) -> Dict:
    """Wrap a number as a PBIR double literal (e.g. 14 -> '14D')."""
    return {"expr": {"Literal": {"Value": f"{value}D"}}}


def container_objects(title: Optional[str], theme: Optional[Dict],
                      title_size: int = 14) -> Dict:
    """Build visualContainerObjects (title + themed background/border).

    When a theme carries titleColor/visualBackground/border the visual inherits
    the dark-card styling (red centered title, dark fill, subtle border) that
    matches the source dashboard. With no theme only title show/text is emitted.
    """
    t = theme or {}
    title_props: Dict = {"show": literal(bool(title))}
    if title:
        title_props["text"] = literal(title)
        if t.get("titleColor"):
            title_props["fontColor"] = color(t["titleColor"])
            title_props["fontSize"] = _num(title_size)
            title_props["alignment"] = literal("center")
            title_props["fontFamily"] = literal(t.get("titleFont", "Segoe UI Semibold"))
    obj: Dict = {"title": [{"properties": title_props}]}
    if t.get("visualBackground"):
        obj["background"] = [{"properties": {
            "show": literal(True), "color": color(t["visualBackground"])}}]
    if t.get("border"):
        obj["border"] = [{"properties": {
            "show": literal(True), "color": color(t["border"]), "radius": _num(5)}}]
    return obj


def _series_datapoint(series: Dict, label: str, hex_value: str) -> Dict:
    """A per-category dataPoint fill keyed to one series value (Movie/TV Show)."""
    return {
        "properties": {"fill": color(hex_value)},
        "selector": {"data": [{"scopeId": {"Comparison": {
            "ComparisonKind": 0,
            "Left": {"Column": {
                "Expression": {"SourceRef": {"Entity": series["entity"]}},
                "Property": series["prop"]}},
            "Right": {"Literal": {"Value": f"'{label}'"}}}}}]},
    }


def measure_sort(entity: str, measure: str, direction: str = "Descending") -> Dict:
    """A default sortDefinition ordering a chart by a measure."""
    return {"sort": [{"field": {"Measure": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": measure}},
        "direction": direction}], "isDefaultSort": True}


def column_sort(entity: str, col: str, direction: str = "Ascending") -> Dict:
    """A default sortDefinition ordering a chart by a category column."""
    return {"sort": [{"field": {"Column": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": col}},
        "direction": direction}], "isDefaultSort": True}


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
                  default_value: Optional[str] = None,
                  theme: Optional[Dict] = None) -> Dict:
    """Build a slicer visual.json dict (Dropdown list or Between range).

    mode='Between' produces a numeric/date range slicer so two such slicers on
    the same column act as independent lower/upper bounds (Start / End dates).
    default_value pre-selects one item (used for field-parameter toggles so the
    bound visual opens on one field instead of showing every field at once).
    """
    t = theme or {}
    hdr_color = t.get("titleColor", header_color)
    data_props = {"mode": literal(mode)}
    objects = {
        "data": [{"properties": data_props}],
        "header": [{"properties": {
            "show": literal(True), "text": literal(title),
            "fontColor": color(hdr_color),
        }}],
    }
    if t.get("foreground"):
        objects["items"] = [{"properties": {"fontColor": color(t["foreground"])}}]
    if mode != "Between":
        objects["selection"] = [{"properties": {"singleSelect": literal(single)}}]
    if default_value is not None and mode != "Between":
        objects["general"] = [{"properties": {
            "filter": _slicer_default_filter(entity, prop, default_value)}}]
    vco = {"title": [{"properties": {"show": literal(False)}}]}
    if t.get("visualBackground"):
        vco["background"] = [{"properties": {
            "show": literal(True), "color": color(t["visualBackground"])}}]
    if t.get("border"):
        vco["border"] = [{"properties": {
            "show": literal(True), "color": color(t["border"]), "radius": _num(5)}}]
    return {
        "$schema": VC_SCHEMA, "name": name, "position": pos,
        "visual": {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [projection(entity, prop)]}}},
            "objects": objects,
            "visualContainerObjects": vco,
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
                 value: Dict, title: Optional[str] = None,
                 theme: Optional[Dict] = None, series: Optional[Dict] = None,
                 series_colors: Optional[Dict] = None,
                 single_color: Optional[str] = None,
                 sort: Optional[Dict] = None, data_labels: bool = True,
                 secondary_value: Optional[Dict] = None,
                 additional_values: Optional[List[Dict]] = None,
                 hide_value_axis: bool = False,
                 hide_labels: bool = False) -> Dict:
    """Build a cartesian chart (bar/column/line/area) visual.json dict.

    secondary_value / additional_values add more Y projections (e.g. PY lines on
    KPI sparklines, Profit lines on trend charts).
    hide_value_axis hides the Y axis (clean sparkline look).
    hide_labels suppresses data point labels.
    """
    all_values = [binding_projection(value)]
    if secondary_value:
        all_values.append(binding_projection(secondary_value))
    for av in (additional_values or []):
        all_values.append(binding_projection(av))
    qs = {"Category": {"projections": [binding_projection(category)]},
          "Y": {"projections": all_values}}
    if series:
        qs["Series"] = {"projections": [binding_projection(series)]}
    query: Dict = {"queryState": qs}
    if sort:
        query["sortDefinition"] = sort
    objects: Dict = {}
    if series and series_colors:
        objects["dataPoint"] = [_series_datapoint(series, lbl, clr)
                                for lbl, clr in series_colors.items()]
    elif single_color:
        objects["dataPoint"] = [{"properties": {
            "fill": color(single_color), "showAllDataPoints": literal(True)}}]
    fg = (theme or {}).get("foreground")
    # Category axis — always show
    ax_props: Dict = {"show": literal(True)}
    if fg:
        ax_props["labelColor"] = color(fg)
        ax_props["titleColor"] = color(fg)
    objects["categoryAxis"] = [{"properties": ax_props}]
    # Value axis — hide for sparklines
    if hide_value_axis:
        objects["valueAxis"] = [{"properties": {"show": literal(False)}}]
    elif fg:
        objects["valueAxis"] = [{"properties": {
            "show": literal(True), "labelColor": color(fg), "titleColor": color(fg)}}]
    if series and fg:
        objects["legend"] = [{"properties": {
            "show": literal(True), "labelColor": color(fg)}}]
    # Data labels
    show_labels = not hide_labels and data_labels
    labels: Dict = {"show": literal(show_labels)}
    if show_labels and fg:
        labels["color"] = color(fg)
    objects["labels"] = [{"properties": labels}]
    visual = {"visualType": visual_type, "query": query, "objects": objects,
              "visualContainerObjects": container_objects(title, theme)}
    return {"$schema": VC_SCHEMA, "name": name, "position": pos, "visual": visual}


def pie_visual(name: str, pos: Dict, category: Dict, value: Dict,
               title: Optional[str] = None, theme: Optional[Dict] = None,
               donut: bool = False, series_colors: Optional[Dict] = None) -> Dict:
    """Build a pie/donut visual.json dict (Category legend + Y values)."""
    query = {"queryState": {
        "Category": {"projections": [binding_projection(category)]},
        "Y": {"projections": [binding_projection(value)]}}}
    objects: Dict = {}
    if series_colors:
        objects["dataPoint"] = [_series_datapoint(category, lbl, clr)
                                for lbl, clr in series_colors.items()]
    fg = (theme or {}).get("foreground")
    legend = {"show": literal(True)}
    labels = {"show": literal(True),
              "labelStyle": literal("Category, percent of total")}
    if fg:
        legend["labelColor"] = color(fg)
        labels["color"] = color(fg)
    objects["legend"] = [{"properties": legend}]
    objects["labels"] = [{"properties": labels}]
    visual = {"visualType": "donutChart" if donut else "pieChart",
              "query": query, "objects": objects,
              "visualContainerObjects": container_objects(title, theme)}
    return {"$schema": VC_SCHEMA, "name": name, "position": pos, "visual": visual}


def map_visual(name: str, pos: Dict, location: Dict, value: Dict,
               title: Optional[str] = None, theme: Optional[Dict] = None,
               gradient: Optional[List[str]] = None) -> Dict:
    """Build a filledMap visual.json dict (Location category + Size measure).

    gradient=[minHex, maxHex] shades the choropleth by the measure via a
    linearGradient2 FillRule (light -> brand red for title density).
    """
    query = {"queryState": {
        "Category": {"projections": [binding_projection(location)]},
        "Size": {"projections": [binding_projection(value)]}}}
    objects: Dict = {}
    if gradient:
        fill_hex = gradient[-1] if isinstance(gradient, list) and gradient else "#E50914"
        objects["dataPoint"] = [{"properties": {
            "fill": color(fill_hex),
            "showAllDataPoints": {"expr": {"Literal": {"Value": "true"}}}}}]
    visual = {"visualType": "filledMap", "query": query, "objects": objects,
              "visualContainerObjects": container_objects(title, theme)}
    return {"$schema": VC_SCHEMA, "name": name, "position": pos, "visual": visual}


def table_visual(name: str, pos: Dict, columns: List[Dict],
                 title: Optional[str] = None,
                 theme: Optional[Dict] = None) -> Dict:
    """Build a tableEx visual.json dict from a list of {entity, prop} columns."""
    projections = [binding_projection(c) for c in columns]
    visual = {"visualType": "tableEx",
              "query": {"queryState": {"Values": {"projections": projections}}},
              "visualContainerObjects": container_objects(title, theme)}
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


def card_visual(name: str, pos: Dict, entity: str, measure: str,
                title: Optional[str] = None, theme: Optional[Dict] = None) -> Dict:
    """Build a single-value card bound to a measure."""
    proj = {"field": {"Measure": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": measure}},
        "queryRef": f"{entity}.{measure}", "nativeQueryRef": measure}
    objects = _card_label_objects(theme)
    return {"$schema": VC_SCHEMA, "name": name, "position": pos,
            "visual": {"visualType": "card",
                       "query": {"queryState": {"Values": {"projections": [proj]}}},
                       "objects": objects,
                       "visualContainerObjects": container_objects(title, theme, title_size=13)}}


def card_text_visual(name: str, pos: Dict, entity: str, column: str,
                     title: Optional[str] = None,
                     theme: Optional[Dict] = None) -> Dict:
    """Build a card bound to a text/dimension column (shows the value text).

    The column is wrapped in a Min aggregation (QueryAggregateFunction=3) so the
    card always collapses to a single value: when a title is selected it shows
    that title's value, and with no selection it shows a representative (first
    alphabetical) value instead of a blank "(multiple values)" card.
    """
    proj = {
        "field": {"Aggregation": {
            "Expression": {"Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": column}},
            "Function": 3}},
        "queryRef": f"Min({entity}.{column})",
        "nativeQueryRef": f"First {column}",
    }
    objects = _card_label_objects(theme)
    return {"$schema": VC_SCHEMA, "name": name, "position": pos,
            "visual": {"visualType": "card",
                       "query": {"queryState": {"Values": {"projections": [proj]}}},
                       "objects": objects,
                       "visualContainerObjects": container_objects(title, theme, title_size=13)}}


def _card_label_objects(theme: Optional[Dict]) -> Dict:
    """Card value label styling (light bold value, hidden category label)."""
    fg = (theme or {}).get("foreground")
    label = {"show": literal(True), "bold": literal(True), "fontSize": _num(20)}
    if fg:
        label["color"] = color(fg)
    return {"labels": [{"properties": label}],
            "categoryLabels": [{"properties": {"show": literal(False)}}]}


def page_json(name: str, display: str, width: int, height: int,
              background: Optional[str] = None,
              outspace: Optional[str] = None) -> Dict:
    """Build a page.json dict (optionally with a dark canvas + outspace)."""
    page = {"$schema": PAGE_SCHEMA, "name": name, "displayName": display,
            "displayOption": "FitToPage", "height": height, "width": width}
    objects: Dict = {}
    if background:
        objects["background"] = [{"properties": {
            "color": color(background),
            "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}]
    if outspace:
        objects["outspace"] = [{"properties": {
            "color": color(outspace),
            "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}]
    if objects:
        page["objects"] = objects
    return page


def pages_json(order: List[str], active: str) -> Dict:
    """Build the pages.json metadata dict."""
    return {"$schema": PAGES_SCHEMA, "pageOrder": order, "activePageName": active}
