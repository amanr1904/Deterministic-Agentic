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
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbir_blocks as P  # noqa: E402
import pbir_bind as B  # noqa: E402

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


def _logical_id(seed: str) -> str:
    import hashlib
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return f"{h[:8]}-{h[8:12]}-4{h[13:16]}-9{h[17:20]}-{h[20:32]}"


def load_json(path: str) -> Dict:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Always write UTF-8 WITHOUT BOM — Power BI Desktop rejects BOM in PBIR files.
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


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
            shutil.rmtree(path, onerror=_onerror)
        except TypeError:  # Python 3.12+ renamed the callback
            shutil.rmtree(path, onexc=lambda f, p, e: _onerror(f, p, e))


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


def _build_kpi_stack(name: str, pos: Dict, x: int, y: int, w: int, h: int,
                     z: int, vd: Dict, entity: str, theme) -> List[Dict]:
    """Return [card_visual, pct_card_visual, sparkline_visual] for a KPI zone."""
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
    spark_vd = dict(vd)
    spark_vd.pop("kpiStack", None)
    sec_bind = ({"entity": entity, "prop": sec_v, "isMeasure": True}) if sec_v else None
    add_binds = [{"entity": entity, "prop": av, "isMeasure": True}
                 for av in (vd.get("additionalValues") or [])]
    catbind  = {"entity": entity, "prop": vd.get("categoryField", "Order Date")}
    valbind  = {"entity": entity, "prop": total_m, "isMeasure": True}
    spark = P.chart_visual(
        f"spark_{name}", P.position(x, y + card_h + pct_h, w, spark_h, z + 2),
        "lineChart", catbind, valbind, title_text, theme=theme,
        secondary_value=sec_bind, additional_values=add_binds or None,
        hide_value_axis=True, hide_labels=True,
    )
    return [card, pct, spark]


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
    theme = decisions.get("theme")
    x, y = round(zone["x"] * sx), round(zone["y"] * sy)
    w, h = max(round(zone["w"] * sx), 80), max(round(zone["h"] * sy), 40)
    pos = P.position(x, y, w, h, z)
    entity = primary_entity(decisions)
    ztype = zone.get("type")
    if ztype == "text":
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
    if round(zone.get("h", 0) * sy) < MIN_VISUAL_PX:
        return None
    ws = B.ws_by_name(ir, ws_name)
    # Overlay this worksheet's own Tableau title/text formatting (red title, font,
    # text colour) onto the dashboard theme so each visual matches its source sheet.
    theme = _ws_theme(theme, ws)
    name = f"visual_{sanitize(ws_name or 'zone')}_{z}".lower()
    vd = visual_decision(ws_name, decisions)
    vtype = resolve_visual_type(ws_name, ir, decisions)
    mlist = B.measure_list(decisions)
    mset = set(mlist)
    cols = B.column_names(ir)
    valf = ws.get("valueField") if ws else None

    def value_bind() -> Dict:
        v = vd.get("value")
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
        catbind = {"entity": entity, "prop": cat or B.first_dim_col(ir)}
        vb = value_bind()
        tips = _tooltip_binds(ws, vd, decisions, ir, entity, mset, cols,
                              vb.get("prop"), {catbind["prop"]})
        return P.pie_visual(name, pos, catbind, vb, ws_name, theme=theme,
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
        locbind = {"entity": entity, "prop": loc}
        vb = value_bind()
        tips = _tooltip_binds(ws, vd, decisions, ir, entity, mset, cols,
                              vb.get("prop"), {loc})
        return P.map_visual(name, pos, locbind, vb, ws_name, theme=theme,
                            gradient=vd.get("gradient"), tooltips=tips or None)

    # Skip empty worksheets (no dims/values/caption) so they don't become cards.
    has_data = bool(ws and (ws.get("dimensions") or ws.get("values")))
    if not has_data and not vd.get("category"):
        return None

    # KPI stack: card (big number) + pct card (% diff) + sparkline
    if vd.get("kpiStack"):
        return _build_kpi_stack(name, pos, x, y, w, h, z, vd, entity, theme)

    if vtype in CARTESIAN:
        mapped = CHART_TYPE_MAP.get(vtype, vtype)
        # categoryIsMeasure: treat the category field as a Measure (for histograms)
        if vd.get("category") and vd.get("categoryIsMeasure"):
            catbind = {"entity": entity, "prop": vd["category"], "isMeasure": True}
        elif vd.get("category"):
            catbind = {"entity": entity, "prop": vd["category"]}
        else:
            catbind = None  # resolved below
        valbind = value_bind()
        fp = B.field_param_for_ws(ws_name, decisions)
        if catbind is None:
            if fp is not None:
                catbind = {"entity": fp["name"], "prop": fp["name"]}
            else:
                catbind = B.category_binding(ws, entity, cols, ir)
        series = vd.get("series")
        seriesbind = {"entity": entity, "prop": series} if series else None
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
        return P.chart_visual(name, pos, mapped, catbind, valbind, ws_name, theme=theme,
                              series=seriesbind, series_colors=vd.get("seriesColors"),
                              single_color=vd.get("color"), sort=sort,
                              secondary_value=sec_bind, additional_values=add_binds or None,
                              hide_value_axis=bool(vd.get("hideValueAxis")),
                              hide_labels=bool(vd.get("hideLabels")),
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

    # tableColumns override from decisions.json (for Top N / custom column sets)
    if vd.get("tableColumns"):
        tcols = [{"entity": tc["entity"], "prop": tc["prop"],
                  "isMeasure": tc.get("isMeasure", False)}
                 for tc in vd["tableColumns"]]
    else:
        tcols = B.table_columns(ws, ir, entity, mset, cols)
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
        if result is None:
            continue
        # kpiStack returns a list of 3 visuals: [card, pct_card, sparkline]
        visuals = result if isinstance(result, list) else [result]
        for visual in visuals:
            write_json(os.path.join(page_dir, "visuals", visual["name"], "visual.json"), visual)
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


def emit(ir: Dict, decisions: Dict, analysis_path: str) -> str:
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
    for dashboard in ir.get("dashboards", []):
        page_names.append(build_page(dashboard, ir, decisions, pages_dir))
    if not page_names:
        page_names = ["Page1"]
        write_json(os.path.join(pages_dir, "Page1", "page.json"),
                   P.page_json("Page1", "Page 1", 1280, 720))
    write_json(os.path.join(pages_dir, "pages.json"),
               P.pages_json(page_names, page_names[0]))
    return report_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Emit PBIR report from IR + decisions.")
    parser.add_argument("analysis", help="path to analysis.json")
    parser.add_argument("--decisions", required=True, help="path to decisions.json")
    args = parser.parse_args(argv)
    for p in (args.analysis, args.decisions):
        if not os.path.isfile(p):
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 2
    ir = load_json(args.analysis)
    report_dir = emit(ir, load_json(args.decisions), args.analysis)
    print(f"Wrote report: {report_dir}\n  pages: {len(ir.get('dashboards', [])) or 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
