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
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def sanitize(name: str) -> str:
    """Page names must match ^[\\w-]+$."""
    return re.sub(r"[^\w-]+", "", name.replace(" ", "")) or "Page"


def resolve_visual_type(ws_name: str, ir: Dict, decisions: Dict) -> str:
    """Prefer LLM decision; else IR inference; else default to table."""
    for vd in decisions.get("visualDecisions", []):
        if vd["worksheet"] == ws_name:
            return vd["visualType"]
    for ws in ir.get("worksheets", []):
        if ws["name"] == ws_name and ws.get("inferredVisualType"):
            return ws["inferredVisualType"]
    return "tableEx"


def primary_entity(decisions: Dict) -> str:
    for t in decisions.get("tables", []):
        if t.get("role") == "fact":
            return t["name"]
    tables = decisions.get("tables", [])
    return tables[0]["name"] if tables else "Table"


def build_visual(zone: Dict, ir: Dict, decisions: Dict, z: int, scale) -> Optional[Dict]:
    """Build one visual.json dict from a classified dashboard zone."""
    sx, sy = scale
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
                                   default_value=default)
        ent, prop, title, mode = B.resolve_slicer(zone, ir, decisions)
        return P.slicer_visual(f"slicer_{B.slug(prop)}_{z}", pos, ent, prop, title, mode=mode)
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
    vtype = resolve_visual_type(ws_name, ir, decisions)
    mlist = B.measure_list(decisions)
    mset = set(mlist)
    cols = B.column_names(ir)
    valf = ws.get("valueField") if ws else None
    # Caption-only worksheets (dynamic <caption>, no real shelves) -> textbox.
    caption = ws.get("caption") if ws else None
    if caption and not (ws.get("dimensions") or ws.get("values")):
        return P.textbox_visual(f"caption_{z}", pos, caption, size=10, bold=False,
                                hex_color="#666666")
    if caption and ws_name and "caption" in ws_name.lower():
        return P.textbox_visual(f"caption_{z}", pos, caption, size=10, bold=False,
                                hex_color="#666666")
    # Skip empty worksheets (no dims/values/caption) so they don't become cards.
    has_data = bool(ws and (ws.get("dimensions") or ws.get("values")))
    if vtype == "card":
        m = valf if valf in mset else None
        return P.card_visual(name, pos, entity, m) if m else None
    if not has_data:
        return None
    if vtype in ("barChart", "columnChart", "lineChart", "areaChart"):
        valbind = B.value_binding(valf, entity, mset, mlist, cols, ir)
        fp = B.field_param_for_ws(ws_name, decisions)
        if fp is not None:
            catbind = {"entity": fp["name"], "prop": fp["name"]}
        else:
            catbind = B.category_binding(ws, entity, cols, ir)
        return P.chart_visual(name, pos, vtype, catbind, valbind, ws_name)
    tcols = B.table_columns(ws, ir, entity, mset, cols)
    return P.table_visual(name, pos, tcols, ws_name)


def build_page(dashboard: Dict, ir: Dict, decisions: Dict, pages_dir: str) -> str:
    """Write one page folder (page.json + visuals/*) and return its page name."""
    page_name = sanitize(dashboard["name"])
    page_dir = os.path.join(pages_dir, page_name)
    pw, ph = dashboard["size"]["w"], dashboard["size"]["h"]
    write_json(os.path.join(page_dir, "page.json"),
               P.page_json(page_name, dashboard["name"], pw, ph))
    scale = (pw / COORD_SPACE, ph / COORD_SPACE)
    z = 100
    for zone in dashboard.get("zones", []):
        visual = build_visual(zone, ir, decisions, z, scale)
        if visual is None:
            continue
        write_json(os.path.join(page_dir, "visuals", visual["name"], "visual.json"), visual)
        z += 1
    return page_name


def emit(ir: Dict, decisions: Dict, analysis_path: str) -> str:
    model_name = decisions.get("modelName") or ir["workbook"]["pascalName"]
    base = os.path.dirname(os.path.abspath(analysis_path))
    report_dir = os.path.join(base, f"{model_name}.Report")
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
