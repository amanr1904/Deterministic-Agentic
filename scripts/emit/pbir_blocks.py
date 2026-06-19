"""pbir_blocks.py — PBIR JSON visual builders (enhanced folder format).

Builds visual.json / page.json dictionaries that conform to the PBIR
visualContainer schema. Per the format rules, a visual.json root may ONLY carry
$schema / name / position / visual — no filters or extra properties. Color and
boolean values use the Literal expression wrapper Power BI Desktop requires.
"""
from __future__ import annotations

import re
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
    # Use visualBackground from theme; fall back to white so visuals never inherit
    # a dark page/dashboard background color that makes text unreadable.
    vis_bg = t.get("visualBackground") or "#FFFFFF"
    obj["background"] = [{"properties": {
        "show": literal(True), "color": color(vis_bg)}}]
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
                 y2_values: Optional[List[Dict]] = None,
                 hide_value_axis: bool = False,
                 hide_labels: bool = False) -> Dict:
    """Build a cartesian chart (bar/column/line/area) visual.json dict.

    secondary_value / additional_values add more Y projections (e.g. PY lines on
    KPI sparklines, Profit lines on trend charts).
    y2_values adds projections to the Y2 (secondary/right) axis — use for dual-axis
    charts where two measure groups have different scales (e.g. Sales on Y, Profit on Y2).
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
    if y2_values:
        qs["Y2"] = {"projections": [binding_projection(yv) for yv in y2_values]}
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
    # Secondary Y axis — shown when y2_values present
    if y2_values:
        y2_props: Dict = {"show": literal(True)}
        if fg:
            y2_props["labelColor"] = color(fg)
        objects["valueAxis2"] = [{"properties": y2_props}]
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
                   bold: bool = True, hex_color: str = "#004263",
                   align: Optional[str] = None) -> Dict:
    """Build a textbox visual with a single styled paragraph run.

    *align* optionally sets the paragraph horizontal alignment
    ("left" | "center" | "right") — used for the Tableau-style centered
    filter-panel section labels.
    """
    run = {"value": text, "textStyle": {
        "fontSize": f"{size}pt", "fontWeight": "bold" if bold else "normal",
        "color": hex_color}}
    paragraph: Dict = {"textRuns": [run]}
    if align:
        paragraph["horizontalTextAlignment"] = align
    paragraphs = [paragraph]
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


# ── Navigation bar ─────────────────────────────────────────────────────────────

NAV_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"

# Default palette — override via decisions["navBar"]["activeColor"] / ["inactiveColor"].
_NAV_ACTIVE   = "#1F77B4"   # highlighted (current page)
_NAV_INACTIVE = "#2C3E50"   # clickable (other pages)

# ── Vertical (sidebar) defaults — left strip ──────────────────────────────────
_NAV_V_BTN_H   = 45     # px per button
_NAV_V_BTN_GAP = 2      # px between buttons
_NAV_V_X       = 2      # left margin
_NAV_V_Y0      = 2      # top of first button
_NAV_V_MIN_W   = 60     # px minimum width
_NAV_V_MAX_W   = 150    # px maximum width
_NAV_CHARS_PER_PX = 7   # rough px/character at 9pt

# ── Horizontal (top-bar) defaults — top-right strip ──────────────────────────
# These defaults are overridden per-report via decisions["navBar"] when the
# exact Tableau button positions are known.
_NAV_H_BTN_W   = 91     # px per button (Tableau source: ~7584/100000 * 1200)
_NAV_H_BTN_H   = 70     # px height     (Tableau source: ~8750/100000 * 800)
_NAV_H_BTN_GAP = 0      # px between buttons (Tableau buttons are flush)
_NAV_H_X0      = 940    # x of first button (Tableau: 78333/100000 * 1200 ≈ 940)
_NAV_H_Y       = 6      # y top            (Tableau: 750/100000 * 800 ≈ 6)


def _nav_btn_name(page_name: str, active: bool) -> str:
    """Return a safe visual name for a nav button.

    Replaces any non-word character with '_', lowercases, and appends
    '_active' for the current-page indicator. Safe for any page name.
    """
    import re
    safe = re.sub(r"[^\w]+", "_", page_name).strip("_").lower()
    return f"nav_{safe}_active" if active else f"nav_{safe}"


def nav_button(name: str, pos: Dict, label: str,
               active: bool = False,
               target_page: Optional[str] = None,
               active_color: str = _NAV_ACTIVE,
               inactive_color: str = _NAV_INACTIVE) -> Dict:
    """Build an actionButton visual.json for a page-navigation bar.

    When *active* is True the button represents the current page (no link, bright
    fill, bold white text). When *active* is False it navigates to *target_page*
    via ``visualContainerObjects.visualLink`` (dark fill, dim text).
    """
    fill_color = active_color if active else inactive_color
    text_color = "#FFFFFF" if active else "#CCCCCC"
    objects: Dict = {
        "icon": [{"properties": {"show": literal(False)}}],
        "outline": [{"properties": {"show": literal(False)}}],
        "fill": [{"properties": {
            "show": literal(True),
            "fillColor": color(fill_color),
        }}],
        "text": [{"properties": {
            "show": literal(True),
            "text": literal(label),
            "fontColor": color(text_color),
            "fontSize": _num(9),
            **({"fontWeight": literal("bold")} if active else {}),
        }}],
    }
    vco: Dict = {
        "title": [{"properties": {"show": literal(False)}}],
        "background": [{"properties": {
            "show": literal(True), "color": color(fill_color),
        }}],
        "border": [{"properties": {"show": literal(False)}}],
    }
    if not active and target_page:
        vco["visualLink"] = [{"properties": {
            "show": literal(True),
            "type": literal("PageNavigation"),
            "navigationSection": literal(target_page),
        }}]
    return {
        "$schema": NAV_SCHEMA,
        "name": name,
        "position": pos,
        "visual": {
            "visualType": "actionButton",
            "objects": objects,
            "visualContainerObjects": vco,
        },
    }


def nav_bar_visuals(current_page: str, all_pages: List[Dict],
                    active_color: str = _NAV_ACTIVE,
                    inactive_color: str = _NAV_INACTIVE,
                    orientation: str = "vertical",
                    btn_w: Optional[int] = None,
                    btn_h: Optional[int] = None,
                    btn_gap: Optional[int] = None,
                    origin_x: Optional[int] = None,
                    origin_y: Optional[int] = None,
                    z_base: int = 9500) -> List[Dict]:
    """Return a list of nav_button dicts (one per page) for *current_page*.

    *all_pages* is a list of ``{"name": str, "displayName": str}`` dicts in
    page order. Buttons are laid out based on *orientation*:

    - ``"vertical"``   — stacked in a left sidebar strip (default).
    - ``"horizontal"`` — placed side-by-side in a top-right header bar, matching
                         the Tableau source layout (e.g. Sales & Customer Dashboards).

    Geometry parameters (btn_w/btn_h/btn_gap/origin_x/origin_y) override the
    orientation defaults and are driven by decisions["navBar"] so each report
    can match its Tableau source exactly.

    Only emitted when there are 2+ pages — single-page reports need no nav bar.
    """
    if len(all_pages) < 2:
        return []

    if orientation == "horizontal":
        # Use caller-supplied values or horizontal defaults.
        bw    = btn_w   if btn_w   is not None else _NAV_H_BTN_W
        bh    = btn_h   if btn_h   is not None else _NAV_H_BTN_H
        bgap  = btn_gap if btn_gap is not None else _NAV_H_BTN_GAP
        ox    = origin_x if origin_x is not None else _NAV_H_X0
        oy    = origin_y if origin_y is not None else _NAV_H_Y
    else:
        # Vertical: dynamic width from longest label, fixed height.
        max_label_len = max(len(pg.get("displayName") or pg["name"]) for pg in all_pages)
        bw   = btn_w   if btn_w   is not None else max(_NAV_V_MIN_W, min(_NAV_V_MAX_W, max_label_len * _NAV_CHARS_PER_PX))
        bh   = btn_h   if btn_h   is not None else _NAV_V_BTN_H
        bgap = btn_gap if btn_gap is not None else _NAV_V_BTN_GAP
        ox   = origin_x if origin_x is not None else _NAV_V_X
        oy   = origin_y if origin_y is not None else _NAV_V_Y0

    visuals: List[Dict] = []
    for i, pg in enumerate(all_pages):
        is_active = pg["name"] == current_page
        if orientation == "horizontal":
            x = ox + i * (bw + bgap)
            y = oy
        else:
            x = ox
            y = oy + i * (bh + bgap)
        z = z_base + i
        pos = {"x": x, "y": y, "z": z,
               "height": bh, "width": bw, "tabOrder": z}
        btn_name = _nav_btn_name(pg["name"], is_active)
        label = pg.get("displayName") or pg["name"]
        visuals.append(nav_button(
            btn_name, pos, label,
            active=is_active,
            target_page=None if is_active else pg["name"],
            active_color=active_color,
            inactive_color=inactive_color,
        ))
    return visuals


# ═══════════════════════════════════════════════════════════════════════════
# Filter panel toggle (bookmark-driven slide-out drawer)
# ═══════════════════════════════════════════════════════════════════════════
# Reproduces the Tableau "Show/Close Dashboard Filters" toggle button + slide-out
# filter drawer using native Power BI bookmarks. Two bookmarks per page form a
# show/hide pair; two actionButtons (open ☰ / close ✕) apply them. The drawer is
# a dark rectangle behind the page's slicer visuals plus a "FILTERS" header.
#
# WORKFLOW (where each piece lives in the .Report folder):
#   definition/bookmarks/bookmarks.json          ← ordered list of bookmark ids
#   definition/bookmarks/{id}.bookmark.json       ← one per show/hide state
#   definition/pages/{page}/visuals/panel_bg/…    ← drawer background rectangle
#   definition/pages/{page}/visuals/panel_header/ ← "FILTERS" title
#   definition/pages/{page}/visuals/btn_filters_open/   ← ☰ button (applies "shown")
#   definition/pages/{page}/visuals/btn_filters_close/  ← ✕ button (applies "hidden")
#   (the slicer_* visuals already emitted by Stage 13 become the drawer contents)
#
# BOOKMARK RULE (display.mode enum has NO "visible"): a bookmark lists ONLY the
# visuals it HIDES (mode:"hidden"); any visual it should reveal is simply OMITTED
# from visualContainers. So:
#   • "Filters Hidden" (default) → hides drawer bg + header + slicers + ✕ button
#   • "Filters Shown"            → hides only the ☰ button

BOOKMARK_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/1.4.0/schema.json"
BOOKMARKS_META_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmarksMetadata/1.0.0/schema.json"

_PANEL_BG_COLOR     = "#0D2A36"   # dark teal drawer (matches Tableau source)
_PANEL_HEADER_COLOR = "#FFFFFF"
_PANEL_BTN_COLOR    = "#0D2A36"   # toggle-button fill
_PANEL_BTN_TEXT     = "#FFFFFF"

# Drawer chrome layout metrics (px) — relative offsets from the panel's own
# runtime x/y/width, so they scale to any report's drawer geometry.
_PANEL_PAD            = 8    # top inset for the header + close button
_PANEL_HDR_X          = 14   # header left inset from the drawer edge
_PANEL_HDR_H          = 34   # header height
_PANEL_HDR_W_INSET    = 60   # header width reduction (leaves room for the ✕)
_PANEL_CLOSE_BTN_SIZE = 30   # ✕ button is a 30×30 px square
_PANEL_CLOSE_MARGIN   = 10   # gap from the drawer's right edge

# ── Stacked-container layout (Tableau "Vertical Cont. (Filter)") metrics ─────
# When a section_layout is supplied the slicers are arranged in a vertical stack
# inside the drawer with cyan section labels (PRODUCT / LOCATION), reproducing
# the Tableau source's filter container exactly.
_PANEL_SECTION_COLOR  = "#24C6FC"  # cyan section labels (Tableau #24c6fc)
_PANEL_INNER_PAD      = 16   # left/right inset for the stacked content
_PANEL_CONTENT_TOP    = 60   # first item y offset (below the FILTERS title)
_PANEL_SECTION_LBL_H  = 22   # section label height
_PANEL_STACK_SLICER_H = 58   # each stacked slicer's height
_PANEL_STACK_GAP      = 8    # gap between consecutive stacked items
_PANEL_SECTION_GAP    = 14   # extra gap above a section label


def _slug(text: str) -> str:
    """Lowercase alphanumeric slug for deterministic visual names."""
    return re.sub(r"[^0-9a-z]+", "", text.lower()) or "x"


def _bookmark_id(seed: str) -> str:
    """Return a deterministic 20-char hex id (matches ^[\\w-]+$) from *seed*.

    Deterministic so regenerating a report yields stable bookmark file names
    rather than churning ids on every run.
    """
    import hashlib
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


def panel_rectangle_visual(name: str, pos: Dict,
                           fill_color: str = _PANEL_BG_COLOR) -> Dict:
    """Build a filled rectangle SHAPE used as the drawer backdrop.

    Must be a ``shape`` visual (tileShape ``rectangle``) — NOT an actionButton.
    An actionButton renders as an opaque chrome element that floats above any
    data visuals (slicers) it overlaps regardless of z-order, so the slicers
    placed on top of the drawer disappear behind it. A ``shape`` visual instead
    participates in normal z-ordering, so a backdrop sent behind the slicers
    (lower z) lets the slicers render on top — the canonical Power BI slicer
    panel pattern. The visible color is set via ``visualContainerObjects.
    background.color`` (the documented fill path for shapes); ``objects.fill``
    stays off, matching a known-good Desktop export.
    """
    objects: Dict = {
        "shape": [{"properties": {"tileShape": literal("rectangle")}}],
        "rotation": [{"properties": {
            "shapeAngle": {"expr": {"Literal": {"Value": "0L"}}}}}],
        "fill": [{"properties": {"show": literal(False)}}],
        "outline": [{"properties": {"show": literal(False)}}],
    }
    return {
        "$schema": VC_SCHEMA,
        "name": name,
        "position": pos,
        "visual": {
            "visualType": "shape",
            "objects": objects,
            "visualContainerObjects": {
                "title": [{"properties": {"show": literal(False)}}],
                "background": [{"properties": {
                    "show": literal(True),
                    "color": color(fill_color),
                    "transparency": {"expr": {"Literal": {"Value": "0D"}}},
                }}],
                "border": [{"properties": {"show": literal(False)}}],
            },
            "drillFilterOtherVisuals": True,
        },
    }


def bookmark_button(name: str, pos: Dict, bookmark_id: str, label: str,
                    fill_color: str = _PANEL_BTN_COLOR,
                    text_color: str = _PANEL_BTN_TEXT,
                    font_size: int = 14) -> Dict:
    """Build an actionButton that applies *bookmark_id* when clicked.

    The action lives in ``visualContainerObjects.visualLink`` with
    ``type:'Bookmark'`` and ``bookmark:'<id>'`` — the bookmark analogue of the
    PageNavigation links the nav bar uses. *label* is rendered as the glyph
    (e.g. "☰" to open, "✕" to close).
    """
    objects: Dict = {
        "icon": [{"properties": {"show": literal(False)}}],
        "outline": [{"properties": {"show": literal(False)}}],
        "fill": [{"properties": {
            "show": literal(True),
            "fillColor": color(fill_color),
        }}],
        "text": [{"properties": {
            "show": literal(True),
            "text": literal(label),
            "fontColor": color(text_color),
            "fontSize": _num(font_size),
            "fontWeight": literal("bold"),
        }}],
    }
    vco: Dict = {
        "title": [{"properties": {"show": literal(False)}}],
        "background": [{"properties": {
            "show": literal(True), "color": color(fill_color)}}],
        "border": [{"properties": {"show": literal(False)}}],
        "visualLink": [{"properties": {
            "show": literal(True),
            "type": literal("Bookmark"),
            "bookmark": literal(bookmark_id),
        }}],
    }
    return {
        "$schema": NAV_SCHEMA,
        "name": name,
        "position": pos,
        "visual": {
            "visualType": "actionButton",
            "objects": objects,
            "visualContainerObjects": vco,
        },
    }


def make_bookmark(bm_id: str, display_name: str, page_name: str,
                  hidden_visuals: List[str],
                  target_visuals: List[str]) -> Dict:
    """Build one ``{id}.bookmark.json`` dict for a filter-panel state.

    *hidden_visuals* are set to ``display.mode:"hidden"``; every visual the
    bookmark should REVEAL is intentionally absent from ``visualContainers`` (the
    schema has no "visible" mode). *target_visuals* scopes the bookmark so it
    only touches the panel + its toggle buttons, leaving the rest of the page
    untouched. ``suppressData`` keeps slicer selections intact across toggles.
    """
    visual_containers = {
        v: {"singleVisual": {"display": {"mode": "hidden"}}}
        for v in hidden_visuals
    }
    return {
        "$schema": BOOKMARK_SCHEMA,
        "name": bm_id,
        "displayName": display_name,
        "options": {
            "targetVisualNames": target_visuals,
            "applyOnlyToTargetVisuals": True,
            "suppressData": True,
            "suppressActiveSection": True,
        },
        "explorationState": {
            "version": "1.3",
            "activeSection": page_name,
            "sections": {
                page_name: {"visualContainers": visual_containers}
            },
        },
    }


def bookmarks_metadata(bookmark_ids: List[str]) -> Dict:
    """Build the ``bookmarks.json`` metadata listing bookmark ids in order."""
    return {
        "$schema": BOOKMARKS_META_SCHEMA,
        "items": [{"name": bid} for bid in bookmark_ids],
    }


def restyle_slicer_for_panel(visual: Dict,
                             header_color: str = _PANEL_HEADER_COLOR) -> Dict:
    """Mutate a slicer visual.json dict so it reads on the dark filter drawer.

    The default slicer header uses the theme's (dark) title color, which is
    invisible against the dark teal panel. This recolors the header label to
    *header_color* (white), bolds it, and makes the slicer's own container
    background transparent so the panel color shows behind the label — matching
    the Tableau source drawer. The dropdown control + item text are left as-is
    (they sit on the slicer's own light dropdown box). Returns *visual* mutated
    in place for convenience.
    """
    vis = visual.get("visual") or {}
    objects = vis.setdefault("objects", {})

    # Header label → white + bold.
    header_props: Dict = {"fontColor": color(header_color),
                          "fontWeight": literal("bold")}
    existing = objects.get("header")
    if existing and isinstance(existing, list) and existing[0].get("properties"):
        existing[0]["properties"].update(header_props)
    else:
        objects["header"] = [{"properties": {"show": literal(True),
                                             **header_props}}]

    # Make the slicer container transparent so the drawer color shows through.
    vco = vis.setdefault("visualContainerObjects", {})
    vco["background"] = [{"properties": {"show": literal(False)}}]
    vco["border"] = [{"properties": {"show": literal(False)}}]
    return visual


def filter_panel_chrome(page_name: str, slicer_names: List[str],
                        panel_x: int, panel_y: int,
                        panel_w: int, panel_h: int,
                        open_btn_pos: Dict,
                        bg_color: str = _PANEL_BG_COLOR,
                        z_base: int = 9000,
                        section_layout: Optional[List[Dict]] = None,
                        section_label_color: str = _PANEL_SECTION_COLOR) -> Dict:
    """Build the full filter-panel toggle for one page.

    Returns a dict with the visuals to add to the page and the two bookmark
    documents::

        {
          "visuals":          [panel_bg, panel_header, btn_open, btn_close, *labels],
          "bookmarks":        [shown_bookmark, hidden_bookmark],
          "ids":              {"shown": <id>, "hidden": <id>},
          "slicer_positions": {slicer_name: position_dict, …},
        }

    *slicer_names* are the existing slicer visual names that live inside the
    drawer. *open_btn_pos* is the ☰ button geometry (typically aligned with the
    nav bar). The ✕ close button is placed at the panel's top-right corner.

    When *section_layout* is supplied the drawer becomes a true **container**:
    the slicers are arranged in a vertical stack and cyan section labels are
    inserted between groups — reproducing the Tableau "Vertical Cont. (Filter)"
    drawer (FILTERS title → PRODUCT → LOCATION). Each entry is
    ``{"label": str | None, "slicers": [name, …]}``; ``label`` ``None`` renders
    the group with no header (e.g. the Year parameter at the top). The caller
    applies the returned ``slicer_positions`` to reposition the slicer visuals.

    Returns ``None`` when there are no slicers to toggle.
    """
    if not slicer_names:
        return None

    bg_name     = "filter_panel_bg"
    header_name = "filter_panel_header"
    open_name   = "btn_filters_open"
    close_name  = "btn_filters_close"

    shown_id  = _bookmark_id(f"{page_name}|filters|shown")
    hidden_id = _bookmark_id(f"{page_name}|filters|hidden")

    # ── Drawer backdrop ──────────────────────────────────────────────────────
    bg_pos = {"x": panel_x, "y": panel_y, "z": z_base,
              "height": panel_h, "width": panel_w, "tabOrder": z_base}
    panel_bg = panel_rectangle_visual(bg_name, bg_pos, bg_color)

    # ── "FILTERS" header ─────────────────────────────────────────────────────
    hdr_pos = {"x": panel_x + _PANEL_HDR_X, "y": panel_y + _PANEL_PAD,
               "z": z_base + 1, "height": _PANEL_HDR_H,
               "width": panel_w - _PANEL_HDR_W_INSET, "tabOrder": z_base + 1}
    panel_header = textbox_visual(header_name, hdr_pos, "FILTERS",
                                  size=16, bold=True,
                                  hex_color=_PANEL_HEADER_COLOR)

    # ── ✕ close button (top-right of drawer) ─────────────────────────────────
    close_pos = {
        "x": panel_x + panel_w - _PANEL_CLOSE_BTN_SIZE - _PANEL_CLOSE_MARGIN,
        "y": panel_y + _PANEL_PAD, "z": z_base + 2,
        "height": _PANEL_CLOSE_BTN_SIZE, "width": _PANEL_CLOSE_BTN_SIZE,
        "tabOrder": z_base + 2}
    btn_close = bookmark_button(close_name, close_pos, hidden_id, "\u2715",
                                fill_color=bg_color, font_size=14)

    # ── ☰ open button (aligned with nav bar) ─────────────────────────────────
    btn_open = bookmark_button(open_name, open_btn_pos, shown_id, "\u2630",
                               fill_color=_PANEL_BTN_COLOR, font_size=18)

    # ── Stacked container layout (section labels + slicer positions) ─────────
    section_visuals: List[Dict] = []
    section_names:   List[str] = []
    slicer_positions: Dict[str, Dict] = {}
    if section_layout:
        content_x = panel_x + _PANEL_INNER_PAD
        content_w = panel_w - _PANEL_INNER_PAD * 2
        y = panel_y + _PANEL_CONTENT_TOP
        z = z_base + 3
        for sec in section_layout:
            label = sec.get("label")
            members = [s for s in sec.get("slicers", []) if s in slicer_names]
            if not members:
                continue
            if label:
                y += _PANEL_SECTION_GAP
                lbl_name = f"filter_panel_sec_{_slug(label)}"
                lbl_pos = {"x": content_x, "y": y, "z": z,
                           "height": _PANEL_SECTION_LBL_H, "width": content_w,
                           "tabOrder": z}
                section_visuals.append(textbox_visual(
                    lbl_name, lbl_pos, label, size=11, bold=True,
                    hex_color=section_label_color, align="center"))
                section_names.append(lbl_name)
                z += 1
                y += _PANEL_SECTION_LBL_H + _PANEL_STACK_GAP
            for sname in members:
                slicer_positions[sname] = {
                    "x": content_x, "y": y, "z": z,
                    "height": _PANEL_STACK_SLICER_H, "width": content_w,
                    "tabOrder": z}
                z += 1
                y += _PANEL_STACK_SLICER_H + _PANEL_STACK_GAP

    drawer_visuals = ([bg_name, header_name, close_name]
                      + section_names + list(slicer_names))
    all_targets = drawer_visuals + [open_name]

    # "Filters Hidden" (default state) hides the whole drawer + ✕, reveals ☰.
    bm_hidden = make_bookmark(
        hidden_id, "Filters Hidden", page_name,
        hidden_visuals=drawer_visuals, target_visuals=all_targets)
    # "Filters Shown" hides only the ☰ button, reveals the drawer.
    bm_shown = make_bookmark(
        shown_id, "Filters Shown", page_name,
        hidden_visuals=[open_name], target_visuals=all_targets)

    return {
        "visuals": [panel_bg, panel_header, btn_open, btn_close] + section_visuals,
        "bookmarks": [bm_shown, bm_hidden],
        "ids": {"shown": shown_id, "hidden": hidden_id},
        "slicer_positions": slicer_positions,
    }
