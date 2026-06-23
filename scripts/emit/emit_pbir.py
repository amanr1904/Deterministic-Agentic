"""emit_pbir.py — Stage 13 deterministic PBIR report generator.

Consumes analysis.json (IR) + decisions.json and writes a complete
{Model}.Report/ folder in enhanced PBIR folder format. Tableau zone coordinates
are scaled to Power BI pixels; field bindings come from pbir_bind. Each
visual.json root carries $schema/name/position/visual, plus an optional
filterConfig when the visual is part of a Tableau show/hide toggle group.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbir_blocks as P  # noqa: E402
import pbir_bind as B  # noqa: E402
import topn as T  # noqa: E402
import date_levels as D  # noqa: E402

PBIR = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "version": "4.0",
}
REPORT = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
    "themeCollection": {}, "settings": {"useStylableVisualContainerHeader": True},
}
VERSION = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "version": "2.0.0",
}
PLATFORM_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"

# Tableau stores dashboard zone geometry in a normalized 0..100000 coordinate
# space (per axis). Scale into the page's pixel size so visuals land on-canvas.
COORD_SPACE = 100000.0

# Tableau show/hide containers collapse the inactive states of a parameter-driven
# toggle into near-zero-height slivers (e.g. the Daily bar / Data Table views that
# only appear when a parameter selects them). Any data visual whose rendered
# height is below this many pixels is one of those collapsed states; suppress it
# so it does not overlap the active visual. A genuine visual is never this short.
MIN_VISUAL_PX = 16

# Many Tableau dashboards float a filter/parameter panel over the right edge of a
# full-width content grid. Scaling content across the whole canvas then slides it
# UNDER that rail. We instead compress content into the area left of the rail and
# keep the rail at its real right-hand position, leaving this pixel gap between.
RAIL_GAP = 16
# A zone counts as part of the rail only if its left edge sits within this many
# Tableau coordinate units of the rail column's x (so content labels that merely
# happen to start at a large x — e.g. table header captions — stay with content).
RAIL_X_TOL = 2000


def _rail_left_tableau(dashboard: Dict) -> Optional[float]:
    """Detect a right-edge floating filter rail; return its Tableau x or None.

    Heuristic: two or more filter/paramctrl zones whose left edges align on the
    right third of the dashboard indicate a dedicated filter column.
    """
    xs = [z.get("x", 0) for z in dashboard.get("zones", [])
          if z.get("type") in ("filter", "paramctrl")]
    if len(xs) >= 2 and min(xs) > 0.6 * COORD_SPACE:
        return min(xs)
    return None


def _logical_id(seed: str) -> str:
    import hashlib
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-9{h[17:20]}-{h[20:32]}"


def load_json(path: str) -> Dict:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _long_path(path: str) -> str:
    """Return a Windows extended-length path (``\\\\?\\`` prefix) so file ops are
    not capped at the 260-char MAX_PATH limit. Deeply-nested PBIR visual folders
    (``...Report/definition/pages/<Page>/visuals/<visual>/visual.json``) easily
    exceed 260 chars on long workspace roots; without this the writer raises
    ``WinError 206`` and silently leaves later pages empty. No-op off Windows."""
    if os.name != "nt":
        return path
    abs = os.path.abspath(path)
    if abs.startswith("\\\\?\\"):
        return abs
    if abs.startswith("\\\\"):  # UNC path
        return "\\\\?\\UNC\\" + abs[2:]
    return "\\\\?\\" + abs


def write_json(path: str, data: Dict) -> None:
    target = _long_path(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    # Always write UTF-8 WITHOUT BOM — Power BI Desktop rejects BOM in PBIR files.
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _visual_dir(name: str) -> str:
    """Short, deterministic, collision-free *folder* name for a visual.

    Power BI Desktop enforces the 260-char Windows MAX_PATH when READING a
    .pbip (PBIProjectUtils.EnsureNotLong) — the ``\\\\?\\`` write trick does not
    help on open. Deep ``pages/<Page>/visuals/<folder>/visual.json`` paths must
    therefore stay short on disk. The descriptive logical id lives in
    visual.json's ``name`` and ALL cross-references (bookmarks, visual groups,
    page navigation) use that id, NOT the folder — so the folder can be
    aggressively shortened without breaking anything. Names <=16 chars pass
    through unchanged (readable); longer ones collapse to
    ``<prefix7>_<sha1[:8]>`` (16 chars), unique via the full-name hash."""
    safe = re.sub(r"[^0-9A-Za-z_-]+", "", name) or "v"
    if len(safe) <= 16:
        return safe
    import hashlib
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{safe[:7]}_{h}"


def sanitize(name: str) -> str:
    """Page names must match ^[\\w-]+$."""
    return re.sub(r"[^\w-]+", "", name.replace(" ", "")) or "Page"


def _rmtree_robust(path: str) -> None:
    """Remove a directory tree, clearing read-only bits (Windows/OneDrive)."""
    import stat

    def _onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if hasattr(shutil, "rmtree"):
        try:
            shutil.rmtree(_long_path(path), onerror=_onerror)
        except TypeError:  # Python 3.12+ renamed the callback
            shutil.rmtree(_long_path(path), onexc=lambda f, p, e: _onerror(f, p, e))


# Unambiguous Tableau mark class -> Power BI visualType. Choosing a Power BI
# visual is a Power-BI-stage decision (NOT XML translation), so this mapping
# lives here, in the report emitter, rather than in the parser.
MARK_MAP = {
    "Bar": "barChart", "Line": "lineChart", "Area": "areaChart", "Pie": "pieChart",
    "Square": "treemap", "Circle": "scatterChart", "Text": "tableEx",
    "Gantt": "ganttChart", "Map": "map",
}
MAP_MARKS = {"Map", "Multipolygon", "Polygon", "Filled Map"}


def mark_to_visual(ws: Dict) -> Optional[str]:
    """Derive a Power BI visualType from the worksheet's Tableau mark FACTS.

    Uses only verbatim parser facts (markClass, resolved field counts, encodings,
    orientation). Returns None when the mark is 'Automatic' and the shape is still
    ambiguous, so the LLM/decisions layer can choose.
    """
    mark_class = ws.get("markClass") or "Automatic"
    if mark_class in MAP_MARKS:
        return "map"
    if mark_class == "Text":
        return "tableEx"
    if mark_class in MARK_MAP:
        return MARK_MAP[mark_class]
    enc = ws.get("encodings") or {}
    n_dim = len(ws.get("dimensions") or [])
    n_val = len(ws.get("values") or [])
    has_date = ws.get("categoryDateLevel") is not None
    orientation = ws.get("orientation")
    if mark_class == "Automatic":
        if n_dim == 0 and n_val == 0:
            return "card"
        if enc.get("color") and enc.get("size") and enc.get("text"):
            return "treemap"
        if n_dim == 0 and n_val >= 1:
            return "card"
        if n_val >= 2 and n_dim >= 1:
            return "tableEx"
        if has_date and n_val >= 1:
            return "lineChart"
        if n_dim >= 1 and n_val >= 1:
            return "columnChart" if orientation == "vertical" else "barChart"
        if n_dim >= 1 and n_val == 0:
            return "tableEx"
    return None


def resolve_visual_type(ws_name: str, ir: Dict, decisions: Dict) -> str:
    """Prefer LLM decision; else derive from Tableau mark facts; else table."""
    for vd in decisions.get("visualDecisions", []):
        if vd["worksheet"] == ws_name:
            return vd["visualType"]
    for ws in ir.get("worksheets", []):
        if ws["name"] == ws_name:
            return mark_to_visual(ws) or "tableEx"
    return "tableEx"


def visual_decision(ws_name: str, decisions: Dict) -> Dict:
    """Return the decisions.visualDecisions entry for a worksheet (or {})."""
    for vd in decisions.get("visualDecisions", []):
        if vd["worksheet"] == ws_name:
            return vd
    return {}


# Tableau-friendly aliases mapped to the concrete Power BI cartesian visualType.
CHART_TYPE_MAP = {
    "columnChart": "clusteredColumnChart",
    "barChart": "clusteredBarChart",
    "stackedColumn": "stackedColumnChart",
    "stackedBar": "stackedBarChart",
}
CARTESIAN = {
    "clusteredColumnChart", "clusteredBarChart", "stackedColumnChart",
    "stackedBarChart", "stackedAreaChart", "lineChart", "areaChart",
    "columnChart", "barChart",
}


def primary_entity(decisions: Dict) -> str:
    for t in decisions.get("tables", []):
        if t.get("role") == "fact":
            return t["name"]
    tables = decisions.get("tables", [])
    return tables[0]["name"] if tables else "Table"


def _date_level_prop(prop: Optional[str], level: Optional[str],
                     date_cols: Set[str]) -> Optional[str]:
    """Rewrite a base date category column to its truncated-grain part column.

    When a worksheet places a date field on a shelf at a year/quarter/month/week
    grain, the model (emit_tmdl) emits a derived column named e.g.
    'Order Date (Week)'. The report must bind to that same derived column, never
    the raw date. Generic across workbooks; both emitters call D.part_column_name.
    """
    if prop and prop in date_cols and D.needs_part(level):
        return D.part_column_name(prop, level)
    return prop


def _build_kpi_stack(name: str, pos: Dict, x: int, y: int, w: int, h: int,
                     z: int, vd: Dict, entity: str, theme,
                     ws: Optional[Dict] = None,
                     date_cols: Optional[Set[str]] = None) -> List[Dict]:
    """Return [card_visual, pct_card_visual, sparkline_visual] for a KPI zone."""
    date_cols = date_cols or set()
    card_h  = round(h * 0.30)
    pct_h   = round(h * 0.15)
    spark_h = h - card_h - pct_h
    title_text = vd.get("kpiTitle", "KPI")
    total_m = vd.get("kpiMeasure", "Total Sales")
    pct_m   = vd.get("kpiPctMeasure", "% Diff Sales")
    sec_v   = vd.get("secondaryValue")
    # card — big CY number
    card = P.card_visual(
        f"card_{name}", P.position(x, y, w, card_h, z),
        entity, total_m, title=title_text, theme=theme,
    )
    # % diff card
    pct = P.card_visual(
        f"pct_{name}", P.position(x, y + card_h, w, pct_h, z + 1),
        entity, pct_m, title=None, theme=theme,
    )
    # sparkline — keep original type (lineChart)
    sec_bind = ({"entity": entity, "prop": sec_v, "isMeasure": True}) if sec_v else None
    add_binds = [{"entity": entity, "prop": av, "isMeasure": True}
                 for av in (vd.get("additionalValues") or [])]
    # Category: prefer the IR base date column at its truncated grain so we bind
    # the derived part column the model exposes (e.g. 'Order Date (Month)'). A
    # stale decision categoryField naming a non-existent column is ignored.
    level = ws.get("categoryDateLevel") if ws else None
    base = (ws.get("categoryField") if ws and ws.get("categoryField") in date_cols
            else vd.get("categoryField") or (ws.get("categoryField") if ws else None)
            or "Order Date")
    cat_prop = _date_level_prop(base, level, date_cols)
    catbind  = {"entity": entity, "prop": cat_prop}
    valbind  = {"entity": entity, "prop": total_m, "isMeasure": True}
    vfilter = (P.filter_config(P.column_not_blank_filter(entity, cat_prop))
               if D.is_part_column(cat_prop) else None)
    spark = P.chart_visual(
        f"spark_{name}", P.position(x, y + card_h + pct_h, w, spark_h, z + 2),
        "lineChart", catbind, valbind, title_text, theme=theme,
        secondary_value=sec_bind, additional_values=add_binds or None,
        hide_value_axis=True, hide_labels=True, visual_filter=vfilter,
    )
    return [card, pct, spark]


<<<<<<< HEAD
def _col_caption(ir: Dict, prop: str) -> Optional[str]:
    """Friendly caption for a column name ('type' -> 'Type'), else None."""
    for c in ir.get("columns", []):
        if c.get("name") == prop and c.get("caption"):
            return c["caption"]
    return None


def _ws_theme(base: Optional[Dict], ws: Optional[Dict]) -> Optional[Dict]:
    """Overlay a worksheet's own Tableau formatting onto the dashboard theme.

    The dashboard-wide ``decisions.theme`` sets the baseline (page background,
    foreground). Each Tableau worksheet, however, carries its OWN title colour /
    font / size and text colour (the Netflix sheets use red 'Tableau Bold' titles
    on a black card). Those are parsed into ``ws.formatting`` — overlay them here
    so every visual's title and text match its source sheet instead of a single
    global colour. Returns the base unchanged when the sheet has no formatting.
    """
    if not ws:
        return base
    fmt = ws.get("formatting") or {}
    t = dict(base or {})
    if fmt.get("titleColor"):
        t["titleColor"] = fmt["titleColor"]
    if fmt.get("titleFontName"):
        # 'Tableau Bold'/'Tableau Book' are Tableau-only fonts not installed in
        # Power BI — map to the closest Segoe face so the title still renders bold.
        fn = str(fmt["titleFontName"]).lower()
        t["titleFont"] = "Segoe UI Bold" if "bold" in fn else "Segoe UI Semibold"
    if fmt.get("titleFontSize"):
        try:
            t["titleFontSize"] = int(round(float(fmt["titleFontSize"])))
        except (TypeError, ValueError):
            pass
    if fmt.get("fontColor"):
        t["foreground"] = fmt["fontColor"]
    if fmt.get("background"):
        t.setdefault("visualBackground", fmt["background"])
    return t


def _tooltip_binds(ws: Optional[Dict], vd: Dict, decisions: Dict, ir: Dict,
                   entity: str, mset: set, cols, primary: Optional[str],
                   exclude: set) -> List[Dict]:
    """Tableau's default tooltip = every marks-card field. Build the projections.

    Returns the extra measures (the worksheet's values beyond the plotted Y, plus
    any explicit decisions.tooltips) AND every marks-card DIMENSION not already on
    an axis/legend/location. So the Power BI hover lists the same fields Tableau
    shows, instead of only the plotted measure(s).
    """
    out: List[Dict] = []
    seen: set = set()
    for v in ((ws.get("values") if ws else []) or []):
        if v in mset and v != primary and v not in seen:
            seen.add(v)
            out.append({"entity": entity, "prop": v, "isMeasure": True})
    for t in (vd.get("tooltips") or []):
        if t in mset and t != primary and t not in seen:
            seen.add(t)
            out.append({"entity": entity, "prop": t, "isMeasure": True})
    for tf in ((ws.get("tooltipFields") if ws else []) or []):
        if tf.get("isMeasure"):
            continue
        fld = tf.get("field")
        if not fld or fld in exclude or fld in seen or fld not in cols:
            continue
        seen.add(fld)
        out.append({"entity": B._field_entity(fld, decisions, ir),
                    "prop": fld, "isMeasure": False})
    return out


def build_visual(zone: Dict, ir: Dict, decisions: Dict, z: int, scale) -> Optional[Dict]:
    """Build one visual.json dict from a classified dashboard zone."""
    sx, sy = scale
=======
def build_visual(zone: Dict, ir: Dict, decisions: Dict, z: int, geom) -> Optional[Dict]:
    """Build one visual.json dict from a classified dashboard zone.

    ``geom`` is the pre-scaled pixel rectangle ``(x, y, w, h, raw_h)`` computed by
    ``build_page`` (which compresses content to the left of any floating filter
    rail and clamps it on-canvas). ``raw_h`` is the unclamped scaled height, used
    only for the collapsed-sliver test.
    """
    x, y, w, h, raw_h = geom
>>>>>>> main
    theme = decisions.get("theme")
    pos = P.position(x, y, w, h, z)
    entity = primary_entity(decisions)
    ztype = zone.get("type")
    if ztype == "text":
        # suppressTextZones: drop standalone Tableau text tiles (page titles,
        # section labels, floating table-header strips, legend captions). Power BI
        # visuals carry their own titles and the filter panel emits its own group
        # labels, so these tiles are redundant clutter. Generic across workbooks.
        if decisions.get("suppressTextZones"):
            return None
        txt = zone.get("text") or ""
        return P.textbox_visual(f"text_{z}", pos, txt) if txt else None
    if ztype in ("filter", "paramctrl"):
        # Slicers inherit the referenced worksheet's title formatting (Tableau
        # filter cards use the same red bold header as the sheet titles).
        sl_theme = _ws_theme(theme, B.ws_by_name(ir, zone.get("worksheet")))
        fp = B.field_param_by_field(zone.get("field"), decisions)
        if fp is not None:
            default = (fp.get("fields") or [{}])[0].get("label")
            return P.slicer_visual(f"slicer_{B.slug(fp['name'])}_{z}", pos,
                                   fp["name"], fp["name"], fp["name"],
                                   default_value=default, theme=sl_theme)
        ent, prop, title, mode = B.resolve_slicer(zone, ir, decisions)
        # Prefer the column's friendly caption ('type' -> 'Type') for the header.
        title = _col_caption(ir, prop) or title
        return P.slicer_visual(f"slicer_{B.slug(prop)}_{z}", pos, ent, prop, title,
                               mode=mode, theme=sl_theme)
    ws_name = zone.get("worksheet") or ""
    # A field parameter collapses several toggle worksheets into one chart; the
    # non-primary ones (e.g. the Daily duplicate) are suppressed here.
    if ws_name in B.suppressed_worksheets(decisions):
        return None
    # Suppress Tableau show/hide collapsed slivers (inactive parameter states)
    # so they never overlap the active visual. Generic across workbooks.
    if raw_h < MIN_VISUAL_PX:
        return None
    ws = B.ws_by_name(ir, ws_name)
<<<<<<< HEAD
    # Overlay this worksheet's own Tableau title/text formatting (red title, font,
    # text colour) onto the dashboard theme so each visual matches its source sheet.
    theme = _ws_theme(theme, ws)
    name = f"visual_{sanitize(ws_name or 'zone')}_{z}".lower()
=======
    name = f"visual_{sanitize(ws_name or 'zone')[:18]}_{z}".lower()
>>>>>>> main
    vd = visual_decision(ws_name, decisions)
    vtype = resolve_visual_type(ws_name, ir, decisions)
    mlist = B.measure_list(decisions)
    mset = set(mlist)
    cols = B.column_names(ir)
    date_cols = {c["name"] for c in ir.get("columns", [])
                 if c.get("dataType") in ("date", "datetime")}
    valf = ws.get("valueField") if ws else None

    def value_bind() -> Dict:
        v = vd.get("value")
        # Value bound to a plain (non-measure) column, optionally from another
        # table (e.g. a pre-aggregated calc table that backs a histogram).
        if v and vd.get("valueColumn"):
            return {"entity": vd.get("valueEntity") or entity, "prop": v,
                    "isMeasure": False}
        if v and v in mset:
            return {"entity": entity, "prop": v, "isMeasure": True}
        return B.value_binding(valf, entity, mset, mlist, cols, ir)

    # Caption-only worksheets (dynamic <caption>, no real shelves) -> textbox.
    caption = ws.get("caption") if ws else None
    if caption and not (ws.get("dimensions") or ws.get("values")):
        return P.textbox_visual(f"caption_{z}", pos, caption, size=10, bold=False,
                                hex_color="#666666")
    if caption and ws_name and "caption" in ws_name.lower():
        return P.textbox_visual(f"caption_{z}", pos, caption, size=10, bold=False,
                                hex_color="#666666")

    # Single-value card: measure value, else a text/dimension column value.
    if vtype == "card":
        m = vd.get("value") if vd.get("value") in mset else (valf if valf in mset else None)
        if m:
            return P.card_visual(name, pos, entity, m, title=ws_name, theme=theme)
        col = vd.get("textColumn") or B.card_column(ws, ir, cols)
        if col and col in cols:
            return P.card_text_visual(name, pos, entity, col, title=ws_name, theme=theme)
        return None

    # Pie / donut: category from color encoding, value measure, branded slices.
    if vtype in ("pieChart", "donutChart"):
        cat = vd.get("category") or B.color_field(ws, ir, cols)
<<<<<<< HEAD
        catbind = {"entity": entity, "prop": cat or B.first_dim_col(ir)}
        vb = value_bind()
        tips = _tooltip_binds(ws, vd, decisions, ir, entity, mset, cols,
                              vb.get("prop"), {catbind["prop"]})
        return P.pie_visual(name, pos, catbind, vb, ws_name, theme=theme,
=======
        cprop = cat or B.first_dim_col(ir)
        catbind = {"entity": B.entity_for_field(cprop, entity, decisions, ir), "prop": cprop}
        return P.pie_visual(name, pos, catbind, value_bind(), ws_name, theme=theme,
>>>>>>> main
                            donut=(vtype == "donutChart"),
                            series_colors=vd.get("seriesColors"),
                            tooltips=tips or None)

    # Treemap: category area sized by a measure (Tableau color+size+text squares).
    if vtype == "treemap":
        cat = vd.get("category") or B.color_field(ws, ir, cols)
        catbind = {"entity": entity, "prop": cat or B.first_dim_col(ir)}
        vb = value_bind()
        tips = _tooltip_binds(ws, vd, decisions, ir, entity, mset, cols,
                              vb.get("prop"), {catbind["prop"]})
        return P.treemap_visual(name, pos, catbind, vb, ws_name, theme=theme,
                                series_colors=vd.get("seriesColors"),
                                single_color=vd.get("color"),
                                tooltips=tips or None)


    # Filled choropleth map: location column + measure-driven saturation.
    if vtype in ("filledMap", "map"):
        loc = vd.get("location") or B.geo_column(ir) or B.first_dim_col(ir)
<<<<<<< HEAD
        locbind = {"entity": entity, "prop": loc}
        vb = value_bind()
        tips = _tooltip_binds(ws, vd, decisions, ir, entity, mset, cols,
                              vb.get("prop"), {loc})
        return P.map_visual(name, pos, locbind, vb, ws_name, theme=theme,
                            gradient=vd.get("gradient"), tooltips=tips or None)
=======
        locbind = {"entity": B.entity_for_field(loc, entity, decisions, ir), "prop": loc}
        return P.map_visual(name, pos, locbind, value_bind(), ws_name, theme=theme,
                            gradient=vd.get("gradient"))
>>>>>>> main

    # Skip empty worksheets (no dims/values/caption) so they don't become cards.
    has_data = bool(ws and (ws.get("dimensions") or ws.get("values")))
    if not has_data and not vd.get("category"):
        return None

    # KPI stack: card (big number) + pct card (% diff) + sparkline
    if vd.get("kpiStack"):
        return _build_kpi_stack(name, pos, x, y, w, h, z, vd, entity, theme,
                                ws, date_cols)

    if vtype in CARTESIAN:
        mapped = CHART_TYPE_MAP.get(vtype, vtype)
        # categoryIsMeasure: treat the category field as a Measure (for histograms)
        if vd.get("category") and vd.get("categoryIsMeasure"):
            catbind = {"entity": entity, "prop": vd["category"], "isMeasure": True}
        elif vd.get("category"):
            catbind = {"entity": B.entity_for_field(vd["category"], entity, decisions, ir),
                       "prop": vd["category"]}
        else:
            catbind = None  # resolved below
        valbind = value_bind()
        fp = B.field_param_for_ws(ws_name, decisions)
        if catbind is None:
            if fp is not None:
                catbind = {"entity": fp["name"], "prop": fp["name"]}
            else:
                catbind = B.category_binding(ws, entity, cols, ir, decisions)
        series = vd.get("series")
        seriesbind = ({"entity": B.entity_for_field(series, entity, decisions, ir),
                       "prop": series} if series else None)
        sort = None
        sd = vd.get("sort")
        if sd == "valueDesc":
            sort = P.measure_sort(entity, valbind["prop"]) if valbind.get("isMeasure") else None
        elif sd == "categoryAsc":
            sort = P.column_sort(catbind["entity"], catbind["prop"])
        # Secondary / additional measures (e.g. PY lines on KPI sparklines)
        sec_v = vd.get("secondaryValue")
        sec_bind = {"entity": entity, "prop": sec_v, "isMeasure": True} if sec_v and sec_v in mset else None
        add_binds = [{"entity": entity, "prop": av, "isMeasure": True}
                     for av in (vd.get("additionalValues") or []) if av in mset]
<<<<<<< HEAD
        # Tooltip fields: Tableau shows the mark-card measures on hover. Auto-add
        # the worksheet's extra measures (beyond the plotted Y) plus any explicit
        # decisions.tooltips, so the PBI hover matches Tableau's tooltip.
        # Tooltip fields: Tableau shows the mark-card measures AND dimensions on
        # hover. _tooltip_binds returns the extra measures (ws.values beyond the
        # plotted Y + decisions.tooltips) plus every marks-card dimension not on
        # the axis/series, so the PBI tooltip matches Tableau field-for-field.
        cat_prop = catbind.get("prop") if catbind else None
        ser_prop = series if series else None
        primary = valbind.get("prop")
        tooltips = _tooltip_binds(ws, vd, decisions, ir, entity, mset, cols,
                                  primary, {cat_prop, ser_prop})
=======
        # y2Values: measures bound to the secondary (right) Y axis — dual-axis charts
        # e.g. {"y2Values": ["CY Profit", "PY Profit"]} in decisions.json
        y2_binds = [{"entity": entity, "prop": yv, "isMeasure": True}
                    for yv in (vd.get("y2Values") or []) if yv in mset] or None
        # Top-N: Tableau groupfilter (count=N end=top) -> rank-measure Advanced filter.
        # Plus drop the null-date bucket for derived date-part categories (mirrors
        # Tableau omitting nulls from a continuous date axis).
        filt_entries = []
        tn = ws.get("topN") if ws else None
        if tn and tn.get("field"):
            rank_name, _rdax, rcount = T.spec(tn, entity)
            filt_entries.append(P.measure_le_filter(entity, rank_name, rcount))
        if (catbind and not catbind.get("isMeasure")
                and D.is_part_column(catbind.get("prop"))):
            filt_entries.append(
                P.column_not_blank_filter(catbind["entity"], catbind["prop"]))
        vfilter = P.filter_config(*filt_entries)
>>>>>>> main
        return P.chart_visual(name, pos, mapped, catbind, valbind, ws_name, theme=theme,
                              series=seriesbind, series_colors=vd.get("seriesColors"),
                              single_color=vd.get("color"), sort=sort,
                              secondary_value=sec_bind, additional_values=add_binds or None,
                              y2_values=y2_binds,
                              hide_value_axis=bool(vd.get("hideValueAxis")),
                              hide_labels=bool(vd.get("hideLabels")),
<<<<<<< HEAD
                              tooltips=tooltips or None)
    # Matrix (pivotTable): Tableau cross-tab / highlight table with row + column
    # dimensions and measure cells. Resolves each field to its owning entity.
    if vtype in ("matrix", "pivotTable"):
        def _bind(spec):
            if isinstance(spec, dict):
                ent = spec.get("entity") or B._field_entity(spec.get("prop"), decisions, ir)
                return {"entity": ent, "prop": spec["prop"],
                        "isMeasure": spec.get("isMeasure", spec.get("prop") in mset)}
            ent = entity if spec in mset else B._field_entity(spec, decisions, ir)
            return {"entity": ent, "prop": spec, "isMeasure": spec in mset}
        rows = [_bind(r) for r in (vd.get("rows") or [])]
        cols_m = [_bind(c) for c in (vd.get("columns") or [])]
        vals = [_bind(v) for v in (vd.get("values") or [])]
        if rows and vals:
            return P.matrix_visual(name, pos, rows, cols_m or None, vals, ws_name, theme=theme)

=======
                              visual_filter=vfilter)
>>>>>>> main
    # tableColumns override from decisions.json (for Top N / custom column sets)
    if vd.get("tableColumns"):
        tcols = [{"entity": tc["entity"], "prop": tc["prop"],
                  "isMeasure": tc.get("isMeasure", False)}
                 for tc in vd["tableColumns"]]
    else:
        tcols = B.table_columns(ws, ir, entity, mset, cols, decisions)
    return P.table_visual(name, pos, tcols, ws_name, theme=theme)


def build_page(dashboard: Dict, ir: Dict, decisions: Dict, pages_dir: str) -> str:
    """Write one page folder (page.json + visuals/*) and return its page name."""
    page_name = sanitize(dashboard["name"])
    page_dir = os.path.join(pages_dir, page_name)
    pw, ph = dashboard["size"]["w"], dashboard["size"]["h"]
    theme = decisions.get("theme") or {}
    write_json(os.path.join(page_dir, "page.json"),
               P.page_json(page_name, dashboard["name"], pw, ph,
                           background=theme.get("pageBackground"),
                           outspace=theme.get("outspace")))
<<<<<<< HEAD
    scale = (pw / COORD_SPACE, ph / COORD_SPACE)

    # Tableau show/hide toggle groups: several worksheets stacked in the same spot
    # whose visibility is driven by a parameter. In Power BI we overlay all members
    # at the active member's rect and filter each by a flag measure so the slicer
    # selection reveals exactly one. Member worksheets are emitted here, not in the
    # normal zone loop (skipped below) and never suppressed as collapsed slivers.
    overlays = decisions.get("visualOverlays", [])
    overlay_members = {m["worksheet"] for ov in overlays for m in ov.get("members", [])}
    zone_by_ws = {zn.get("worksheet"): zn for zn in dashboard.get("zones", [])}
    entity = primary_entity(decisions)

    z = 100
    for zone in dashboard.get("zones", []):
        if zone.get("type") == "viz" and zone.get("worksheet") in overlay_members:
            continue  # emitted by the overlay pass below
        result = build_visual(zone, ir, decisions, z, scale)
=======
    sx, sy = pw / COORD_SPACE, ph / COORD_SPACE
    rail = _rail_left_tableau(dashboard)
    # Content (non-rail) zones are compressed into the area LEFT of the floating
    # filter rail so they never slide underneath it; rail zones keep their real
    # right-hand position. With no rail, content spans the full canvas width.
    content_sx = ((round(rail * sx) - RAIL_GAP) / COORD_SPACE) if rail else sx
    z = 100
    for zone in dashboard.get("zones", []):
        in_rail = rail is not None and abs(zone.get("x", 0) - rail) <= RAIL_X_TOL
        zsx = sx if in_rail else content_sx
        raw_h = zone.get("h", 0) * sy
        gx = round(zone.get("x", 0) * zsx)
        gy = round(zone.get("y", 0) * sy)
        gw = max(round(zone.get("w", 0) * zsx), 80)
        gh = max(round(raw_h), 40)
        # Clamp fully on-canvas so nothing renders off the page edge.
        gx = max(0, min(gx, pw - 1))
        gy = max(0, min(gy, ph - 1))
        gw = min(gw, pw - gx)
        gh = min(gh, ph - gy)
        result = build_visual(zone, ir, decisions, z, (gx, gy, gw, gh, raw_h))
>>>>>>> main
        if result is None:
            continue
        # kpiStack returns a list of 3 visuals: [card, pct_card, sparkline]
        visuals = result if isinstance(result, list) else [result]
        for visual in visuals:
            write_json(os.path.join(page_dir, "visuals", _visual_dir(visual["name"]), "visual.json"), visual)
            z += 1

    for ov in overlays:
        pos_zone = zone_by_ws.get(ov.get("positionWorksheet"))
        if pos_zone is None:
            continue
        for member in ov.get("members", []):
            synth = dict(pos_zone, worksheet=member["worksheet"], type="viz")
            result = build_visual(synth, ir, decisions, z, scale)
            if result is None:
                continue
            visuals = result if isinstance(result, list) else [result]
            for visual in visuals:
                visual["filterConfig"] = P.measure_filter_config(entity, member["filterMeasure"])
                write_json(os.path.join(page_dir, "visuals", visual["name"], "visual.json"), visual)
                z += 1
    return page_name


# ---------------------------------------------------------------------------
# Agent-authored visuals ("--visuals agent"): the deterministic side writes the
# report shell + per-page _zones.json manifests; an agent then authors each
# visuals/{name}/visual.json. Positions are pre-computed here and MUST be copied
# verbatim by the agent so geometry stays identical to the factory output.
# ---------------------------------------------------------------------------

def _model_summary(ir: Dict, decisions: Dict) -> Dict:
    """Exact table/column/measure names the agent may bind to (queryRef source)."""
    measures_by_table: Dict[str, List[str]] = {}
    for m in decisions.get("measures", []):
        measures_by_table.setdefault(m["table"], []).append(m["name"])
    fact = primary_entity(decisions)
    ir_cols = [c["name"] for c in ir.get("columns", [])]
    tables: List[Dict] = []
    for t in decisions.get("tables", []):
        is_fact = t.get("role") == "fact" or t["name"] == fact
        tables.append({
            "name": t["name"],
            "role": t.get("role"),
            "columns": ir_cols if is_fact else (t.get("keyColumns") or []),
            "measures": measures_by_table.get(t["name"], []),
        })
    for fp in decisions.get("fieldParameters", []):
        tables.append({"name": fp["name"], "role": "fieldParameter",
                       "columns": [fp["name"]], "measures": []})
    return {"entity": fact, "tables": tables}


def _suggest_visual_name(zone: Dict, z: int) -> str:
    """Deterministic visual/folder name suggestion (matches the page-name regex)."""
    ztype = zone.get("type")
    if ztype in ("filter", "paramctrl"):
        base = f"slicer_{sanitize(zone.get('field') or 'field')[:18]}"
    elif ztype == "text":
        base = "text"
    else:
        base = f"visual_{sanitize(zone.get('worksheet') or 'zone')[:18]}"
    return f"{base}_{z}".lower()


def _zone_manifest_entry(zone: Dict, ir: Dict, decisions: Dict, z: int,
                         scale) -> Optional[Dict]:
    """One manifest zone: fixed geometry + binding context for the agent.

    Mirrors the suppression rules in build_visual so the agent never authors a
    visual the factory path would have dropped (collapsed slivers, field-param
    duplicate worksheets).
    """
    sx, sy = scale
    ztype = zone.get("type")
    ws_name = zone.get("worksheet") or ""
    if ws_name and ws_name in B.suppressed_worksheets(decisions):
        return None
    if round(zone.get("h", 0) * sy) < MIN_VISUAL_PX:
        return None
    x, y = round(zone["x"] * sx), round(zone["y"] * sy)
    w, h = max(round(zone["w"] * sx), 80), max(round(zone["h"] * sy), 40)
    entry: Dict = {
        "name": _suggest_visual_name(zone, z),
        "zoneType": ztype,
        "position": P.position(x, y, w, h, z),
    }
    if ztype == "text":
        entry["text"] = zone.get("text") or ""
        entry["suggestedVisualType"] = "textbox"
        return entry
    if ztype in ("filter", "paramctrl"):
        entry["field"] = zone.get("field")
        entry["suggestedVisualType"] = "slicer"
        return entry
    if ws_name:
        entry["worksheet"] = ws_name
        ws = B.ws_by_name(ir, ws_name)
        if ws:
            entry["ir"] = {
                "markClass": ws.get("markClass"),
                "rows": ws.get("rows"),
                "cols": ws.get("cols"),
                "encodings": ws.get("encodings"),
                "dimensions": ws.get("dimensions"),
                "values": ws.get("values"),
                "categoryField": ws.get("categoryField"),
                "categoryDateLevel": ws.get("categoryDateLevel"),
                "topN": ws.get("topN"),
                "inferredVisualType": ws.get("inferredVisualType"),
                "caption": ws.get("caption"),
            }
        vd = visual_decision(ws_name, decisions)
        if vd:
            entry["decision"] = vd
        entry["suggestedVisualType"] = resolve_visual_type(ws_name, ir, decisions)
    return entry


def build_page_shell(dashboard: Dict, ir: Dict, decisions: Dict,
                     pages_dir: str) -> str:
    """Write page.json + a _zones.json manifest (no visual bodies). Agent mode."""
    page_name = sanitize(dashboard["name"])
    page_dir = os.path.join(pages_dir, page_name)
    pw, ph = dashboard["size"]["w"], dashboard["size"]["h"]
    theme = decisions.get("theme") or {}
    write_json(os.path.join(page_dir, "page.json"),
               P.page_json(page_name, dashboard["name"], pw, ph,
                           background=theme.get("pageBackground"),
                           outspace=theme.get("outspace")))
    scale = (pw / COORD_SPACE, ph / COORD_SPACE)
    zones: List[Dict] = []
    z = 100
    for zone in dashboard.get("zones", []):
        entry = _zone_manifest_entry(zone, ir, decisions, z, scale)
        if entry is None:
            continue
        zones.append(entry)
        z += 1
    manifest = {
        "page": page_name,
        "displayName": dashboard["name"],
        "pageSize": {"w": pw, "h": ph},
        "model": _model_summary(ir, decisions),
        "constraints": {
            "visualJsonRootKeys": ["$schema", "name", "position", "visual"],
            "positionIsFixed": True,
            "visualNameRegex": "^[a-zA-Z0-9_][a-zA-Z0-9_-]*$",
            "schemaBase": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/",
        },
        "outputPattern": "visuals/{name}/visual.json",
        "zones": zones,
    }
    write_json(os.path.join(page_dir, "_zones.json"), manifest)
    return page_name


def emit(ir: Dict, decisions: Dict, analysis_path: str,
         visuals_mode: str = "agent") -> str:
    model_name = decisions.get("modelName") or ir["workbook"]["pascalName"]
    base = os.path.dirname(os.path.abspath(analysis_path))
    report_dir = os.path.join(base, f"{model_name}.Report")
    # Wipe any prior report so stale/orphan visual folders never accumulate.
    if os.path.isdir(report_dir):
        _rmtree_robust(report_dir)
    defin = os.path.join(report_dir, "definition")
    pages_dir = os.path.join(defin, "pages")
    # Clear any pages from a previous run so renamed/renumbered visual folders do
    # not linger as orphans (e.g. an unfiltered toggle visual left after enabling
    # an overlay group). Regeneration must be deterministic.
    if os.path.isdir(pages_dir):
        shutil.rmtree(pages_dir)
    os.makedirs(pages_dir, exist_ok=True)

    pbir = dict(PBIR, datasetReference={"byPath": {"path": f"../{model_name}.SemanticModel"}})
    write_json(os.path.join(report_dir, "definition.pbir"), pbir)
    write_json(os.path.join(defin, "report.json"), REPORT)
    write_json(os.path.join(defin, "version.json"), VERSION)
    write_json(os.path.join(report_dir, ".platform"), {
        "$schema": PLATFORM_SCHEMA,
        "metadata": {"type": "Report", "displayName": model_name},
        "config": {"version": "2.0", "logicalId": _logical_id(model_name + ".rpt")},
    })

    page_names: List[str] = []
    page_display: Dict[str, str] = {}
    for dashboard in ir.get("dashboards", []):
        if visuals_mode == "agent":
            pn = build_page_shell(dashboard, ir, decisions, pages_dir)
        else:
            pn = build_page(dashboard, ir, decisions, pages_dir)
        page_names.append(pn)
        page_display[pn] = dashboard.get("name", pn)
    if not page_names:
        page_names = ["Page1"]
        page_display = {"Page1": "Page 1"}
        write_json(os.path.join(pages_dir, "Page1", "page.json"),
                   P.page_json("Page1", "Page 1", 1280, 720))
    write_json(os.path.join(pages_dir, "pages.json"),
               P.pages_json(page_names, page_names[0]))

    # Inject navigation bar — controlled by decisions["navBar"]["enabled"].
    # Defaults to enabled when 2+ pages exist; agents can disable per-report
    # by setting navBar.enabled = false in decisions.json.
    nav_cfg = decisions.get("navBar") or {}
    if nav_cfg.get("enabled", True):
        theme = decisions.get("theme") or {}
        _inject_nav_bar(pages_dir, page_names, page_display,
                        active_color=nav_cfg.get("activeColor")
                                     or theme.get("navActiveColor", "#1F77B4"),
                        inactive_color=nav_cfg.get("inactiveColor")
                                       or theme.get("navInactiveColor", "#2C3E50"),
                        orientation=nav_cfg.get("orientation", "vertical"),
                        btn_w=nav_cfg.get("buttonWidth"),
                        btn_h=nav_cfg.get("buttonHeight"),
                        btn_gap=nav_cfg.get("buttonGap"),
                        origin_x=nav_cfg.get("originX"),
                        origin_y=nav_cfg.get("originY"))

    # Inject filter panel toggle — controlled by decisions["filterPanel"].
    # Reproduces the Tableau show/close-filters slide-out drawer with native
    # bookmarks. Opt out per-report via filterPanel.enabled = false. Skipped in
    # agent mode: the drawer restyles/repositions slicer visual.json files that
    # the agent has not authored yet.
    fp_cfg = decisions.get("filterPanel") or {}
    if visuals_mode != "agent" and fp_cfg.get("enabled", True):
        _inject_filter_panel(os.path.dirname(pages_dir), page_names, fp_cfg)

    return report_dir


def _inject_filter_panel(definition_dir: str, page_names: List[str],
                         fp_cfg: Dict) -> None:
    """Write the filter-panel drawer visuals + show/hide bookmarks.

    Generic: for every page that has slicer visuals it draws a drawer behind
    them, adds the open/close toggle buttons, and emits a Show/Hide bookmark
    pair. Slicers are auto-detected (visualType == 'slicer') unless
    filterPanel.slicerNames lists them explicitly. The two bookmarks toggle the
    drawer via visualLink type='Bookmark'. Nothing is written for pages without
    slicers, so single-table reports are unaffected.
    """
    pages_dir   = os.path.join(definition_dir, "pages")
    panel_color = fp_cfg.get("panelColor", "#0D2A36")
    padding     = int(fp_cfg.get("padding", 16))
    explicit    = fp_cfg.get("slicerNames")
    open_btn    = fp_cfg.get("openButton") or {}
    header_color = fp_cfg.get("slicerHeaderColor", "#FFFFFF")
    sections_cfg = fp_cfg.get("sections")
    section_color = fp_cfg.get("sectionLabelColor", "#24C6FC")
    show_header = fp_cfg.get("showHeader", True)
    show_section_labels = fp_cfg.get("showSectionLabels", True)

    all_ids: List[str] = []
    for pn in page_names:
        visuals_dir = os.path.join(pages_dir, pn, "visuals")
        slicers = _collect_slicers(visuals_dir, explicit)
        if not slicers:
            continue

        page_w, page_h = 1280, 720
        pj_path = os.path.join(pages_dir, pn, "page.json")
        if os.path.isfile(pj_path):
            try:
                pj = load_json(pj_path)
                page_w = pj.get("width", page_w)
                page_h = pj.get("height", page_h)
            except Exception:
                pass

        section_layout = _build_section_layout(slicers, sections_cfg)

        if section_layout:
            # Tableau-style container: full-height right drawer, slicers stacked.
            pw = max(240, int(page_w * 0.214))
            px, py, ph = page_w - pw, 0, page_h
        else:
            xs0 = min(s["pos"].get("x", 0) for s in slicers)
            ys0 = min(s["pos"].get("y", 0) for s in slicers)
            xs1 = max(s["pos"].get("x", 0) + s["pos"].get("width", 0) for s in slicers)
            ys1 = max(s["pos"].get("y", 0) + s["pos"].get("height", 0) for s in slicers)
            header_room = 52
            px = max(0, int(xs0 - padding))
            py = max(0, int(ys0 - header_room))
            pw = int((xs1 - xs0) + padding * 2)
            ph = int((ys1 - ys0) + header_room + padding)

        open_btn_pos = {
            "x": int(open_btn.get("x", page_w - 78)),
            "y": int(open_btn.get("y", 6)), "z": 9600,
            "height": int(open_btn.get("height", 70)),
            "width": int(open_btn.get("width", 70)), "tabOrder": 9600}

        chrome = P.filter_panel_chrome(
            pn, [s["name"] for s in slicers],
            panel_x=px, panel_y=py, panel_w=pw, panel_h=ph,
            open_btn_pos=open_btn_pos, bg_color=panel_color,
            section_layout=section_layout or None,
            section_label_color=section_color,
            show_header=show_header,
            show_section_labels=show_section_labels)
        if not chrome:
            continue

        for vis in chrome["visuals"]:
            write_json(os.path.join(visuals_dir, _visual_dir(vis["name"]), "visual.json"), vis)
        for bm in chrome["bookmarks"]:
            write_json(os.path.join(definition_dir, "bookmarks",
                                    f"{bm['name']}.bookmark.json"), bm)
            all_ids.append(bm["name"])

        # Restyle the drawer's slicer headers (white + transparent bg) so they
        # read on the dark panel, and reposition them into the container stack.
        new_positions = chrome.get("slicer_positions") or {}
        for s in slicers:
            spath = os.path.join(visuals_dir, s.get("folder") or _visual_dir(s["name"]), "visual.json")
            try:
                sj = load_json(spath)
            except Exception:
                continue
            sj = P.restyle_slicer_for_panel(sj, header_color)
            if s["name"] in new_positions:
                sj["position"] = new_positions[s["name"]]
            write_json(spath, sj)

    if all_ids:
        write_json(os.path.join(definition_dir, "bookmarks", "bookmarks.json"),
                   P.bookmarks_metadata(all_ids))


def _build_section_layout(slicers: List[Dict],
                          sections_cfg: Optional[List[Dict]]) -> List[Dict]:
    """Map detected slicers to ordered sections by bound field name.

    *sections_cfg* is filterPanel.sections: ``[{"label", "fields": [...]}]``.
    Returns ``[{"label", "slicers": [name, …]}]`` ordered per the config with
    any unmatched slicers appended label-less. ``[]`` when no config (flat panel).
    """
    if not sections_cfg:
        return []
    by_field = {s["field"]: s["name"] for s in slicers if s.get("field")}
    used: set = set()
    layout: List[Dict] = []
    for sec in sections_cfg:
        names: List[str] = []
        for f in sec.get("fields", []):
            nm = by_field.get(f)
            if nm and nm not in used:
                names.append(nm)
                used.add(nm)
        if names:
            layout.append({"label": sec.get("label"), "slicers": names})
    leftover = [s["name"] for s in slicers if s["name"] not in used]
    if leftover:
        layout.append({"label": None, "slicers": leftover})
    return layout


def _collect_slicers(visuals_dir: str, explicit: Optional[List[str]]) -> List[Dict]:
    """Return [{name, pos, field}] for slicer visuals in *visuals_dir*."""
    out: List[Dict] = []
    if not os.path.isdir(visuals_dir):
        return out
    for vname in sorted(os.listdir(visuals_dir)):
        vpath = os.path.join(visuals_dir, vname, "visual.json")
        if not os.path.isfile(vpath):
            continue
        try:
            vj = load_json(vpath)
        except Exception:
            continue
        name  = vj.get("name", vname)
        vtype = (vj.get("visual") or {}).get("visualType", "")
        if explicit:
            if name in explicit:
                out.append({"name": name, "folder": vname, "pos": vj.get("position", {}),
                            "field": _slicer_field(vj)})
        elif vtype == "slicer":
            out.append({"name": name, "folder": vname, "pos": vj.get("position", {}),
                        "field": _slicer_field(vj)})
    return out


def _slicer_field(vj: Dict) -> str:
    """Return the column/measure Property a slicer is bound to (or "")."""
    try:
        proj = (vj["visual"]["query"]["queryState"]["Values"]["projections"][0]
                ["field"])
        node = proj.get("Column") or proj.get("Measure") or {}
        return node.get("Property", "")
    except Exception:
        return ""


def _inject_nav_bar(pages_dir: str, page_names: List[str],
                    page_display: Dict[str, str],
                    active_color: str = "#1F77B4",
                    inactive_color: str = "#2C3E50",
                    orientation: str = "vertical",
                    btn_w: Optional[int] = None,
                    btn_h: Optional[int] = None,
                    btn_gap: Optional[int] = None,
                    origin_x: Optional[int] = None,
                    origin_y: Optional[int] = None) -> None:
    """Write nav-bar actionButton visual.json files into every page's visuals/ folder.

    Generic: works on any report. orientation='horizontal' matches a top-bar
    Tableau layout; 'vertical' (default) places buttons in a left sidebar.
    Geometry params (btn_w/btn_h/btn_gap/origin_x/origin_y) are passed from
    decisions["navBar"] to faithfully reproduce Tableau button positions.
    """
    if len(page_names) < 2:
        return
    all_pages = []
    for pn in page_names:
        page_json_path = os.path.join(pages_dir, pn, "page.json")
        display = page_display.get(pn, pn)
        if os.path.isfile(page_json_path):
            try:
                pj = load_json(page_json_path)
                display = pj.get("displayName", display)
            except Exception:
                pass
        all_pages.append({"name": pn, "displayName": display})

    for pg in all_pages:
        visuals = P.nav_bar_visuals(
            pg["name"], all_pages,
            active_color=active_color,
            inactive_color=inactive_color,
            orientation=orientation,
            btn_w=btn_w,
            btn_h=btn_h,
            btn_gap=btn_gap,
            origin_x=origin_x,
            origin_y=origin_y,
        )
        visuals_dir = os.path.join(pages_dir, pg["name"], "visuals")
        for v in visuals:
            write_json(os.path.join(visuals_dir, _visual_dir(v["name"]), "visual.json"), v)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Emit PBIR report from IR + decisions.")
    parser.add_argument("analysis", help="path to analysis.json")
    parser.add_argument("--decisions", required=True, help="path to decisions.json")
    parser.add_argument("--visuals", choices=["factory", "agent"], default="agent",
                        help="agent = report shell + per-page _zones.json manifests "
                             "for an agent to author each visual.json (default); "
                             "factory = deterministic visual.json")
    args = parser.parse_args(argv)
    for p in (args.analysis, args.decisions):
        if not os.path.isfile(p):
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 2
    ir = load_json(args.analysis)
    report_dir = emit(ir, load_json(args.decisions), args.analysis,
                      visuals_mode=args.visuals)
    note = "  (shell + _zones.json manifests — agent authors visuals)" \
        if args.visuals == "agent" else ""
    print(f"Wrote report: {report_dir}{note}\n"
          f"  pages: {len(ir.get('dashboards', [])) or 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
