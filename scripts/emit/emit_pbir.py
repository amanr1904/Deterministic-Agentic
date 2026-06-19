"""emit_pbir.py — Stage 13 deterministic PBIR report generator.

Consumes analysis.json (IR) + decisions.json and writes a complete
{Model}.Report/ folder in enhanced PBIR folder format. Tableau zone coordinates
are scaled to Power BI pixels; field bindings come from pbir_bind. Every
visual.json root carries ONLY $schema/name/position/visual.
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


def resolve_visual_type(ws_name: str, ir: Dict, decisions: Dict) -> str:
    """Prefer LLM decision; else IR inference; else default to table."""
    for vd in decisions.get("visualDecisions", []):
        if vd["worksheet"] == ws_name:
            return vd["visualType"]
    for ws in ir.get("worksheets", []):
        if ws["name"] == ws_name and ws.get("inferredVisualType"):
            return ws["inferredVisualType"]
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
        fp = B.field_param_by_field(zone.get("field"), decisions)
        if fp is not None:
            default = (fp.get("fields") or [{}])[0].get("label")
            return P.slicer_visual(f"slicer_{B.slug(fp['name'])}_{z}", pos,
                                   fp["name"], fp["name"], fp["name"],
                                   default_value=default, theme=theme)
        ent, prop, title, mode = B.resolve_slicer(zone, ir, decisions)
        return P.slicer_visual(f"slicer_{B.slug(prop)}_{z}", pos, ent, prop, title,
                               mode=mode, theme=theme)
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
        return P.pie_visual(name, pos, catbind, value_bind(), ws_name, theme=theme,
                            donut=(vtype == "donutChart"),
                            series_colors=vd.get("seriesColors"))

    # Filled choropleth map: location column + measure-driven saturation.
    if vtype in ("filledMap", "map"):
        loc = vd.get("location") or B.geo_column(ir) or B.first_dim_col(ir)
        locbind = {"entity": entity, "prop": loc}
        return P.map_visual(name, pos, locbind, value_bind(), ws_name, theme=theme,
                            gradient=vd.get("gradient"))

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
        # y2Values: measures bound to the secondary (right) Y axis — dual-axis charts
        # e.g. {"y2Values": ["CY Profit", "PY Profit"]} in decisions.json
        y2_binds = [{"entity": entity, "prop": yv, "isMeasure": True}
                    for yv in (vd.get("y2Values") or []) if yv in mset] or None
        return P.chart_visual(name, pos, mapped, catbind, valbind, ws_name, theme=theme,
                              series=seriesbind, series_colors=vd.get("seriesColors"),
                              single_color=vd.get("color"), sort=sort,
                              secondary_value=sec_bind, additional_values=add_binds or None,
                              y2_values=y2_binds,
                              hide_value_axis=bool(vd.get("hideValueAxis")),
                              hide_labels=bool(vd.get("hideLabels")))
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
    z = 100
    for zone in dashboard.get("zones", []):
        result = build_visual(zone, ir, decisions, z, scale)
        if result is None:
            continue
        # kpiStack returns a list of 3 visuals: [card, pct_card, sparkline]
        visuals = result if isinstance(result, list) else [result]
        for visual in visuals:
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
    # bookmarks. Opt out per-report via filterPanel.enabled = false.
    fp_cfg = decisions.get("filterPanel") or {}
    if fp_cfg.get("enabled", True):
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
            section_label_color=section_color)
        if not chrome:
            continue

        for vis in chrome["visuals"]:
            write_json(os.path.join(visuals_dir, vis["name"], "visual.json"), vis)
        for bm in chrome["bookmarks"]:
            write_json(os.path.join(definition_dir, "bookmarks",
                                    f"{bm['name']}.bookmark.json"), bm)
            all_ids.append(bm["name"])

        # Restyle the drawer's slicer headers (white + transparent bg) so they
        # read on the dark panel, and reposition them into the container stack.
        new_positions = chrome.get("slicer_positions") or {}
        for s in slicers:
            spath = os.path.join(visuals_dir, s["name"], "visual.json")
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
                out.append({"name": name, "pos": vj.get("position", {}),
                            "field": _slicer_field(vj)})
        elif vtype == "slicer":
            out.append({"name": name, "pos": vj.get("position", {}),
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
            write_json(os.path.join(visuals_dir, v["name"], "visual.json"), v)


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
