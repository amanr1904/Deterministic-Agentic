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


def build_visual(zone: Dict, ir: Dict, decisions: Dict, z: int, geom) -> Optional[Dict]:
    """Build one visual.json dict from a classified dashboard zone.

    ``geom`` is the pre-scaled pixel rectangle ``(x, y, w, h, raw_h)`` computed by
    ``build_page`` (which compresses content to the left of any floating filter
    rail and clamps it on-canvas). ``raw_h`` is the unclamped scaled height, used
    only for the collapsed-sliver test.
    """
    x, y, w, h, raw_h = geom
    theme = decisions.get("theme")
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
    if raw_h < MIN_VISUAL_PX:
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
        cprop = cat or B.first_dim_col(ir)
        catbind = {"entity": B.entity_for_field(cprop, entity, decisions, ir), "prop": cprop}
        return P.pie_visual(name, pos, catbind, value_bind(), ws_name, theme=theme,
                            donut=(vtype == "donutChart"),
                            series_colors=vd.get("seriesColors"))

    # Filled choropleth map: location column + measure-driven saturation.
    if vtype in ("filledMap", "map"):
        loc = vd.get("location") or B.geo_column(ir) or B.first_dim_col(ir)
        locbind = {"entity": B.entity_for_field(loc, entity, decisions, ir), "prop": loc}
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
        return P.chart_visual(name, pos, mapped, catbind, valbind, ws_name, theme=theme,
                              series=seriesbind, series_colors=vd.get("seriesColors"),
                              single_color=vd.get("color"), sort=sort,
                              secondary_value=sec_bind, additional_values=add_binds or None,
                              hide_value_axis=bool(vd.get("hideValueAxis")),
                              hide_labels=bool(vd.get("hideLabels")))
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
