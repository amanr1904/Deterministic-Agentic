"""add_filter_panel.py — Inject a bookmark-driven filter panel into a PBIP report.

Reproduces the Tableau "Show/Close Dashboard Filters" slide-out drawer using
native Power BI bookmarks. For every page that has slicer visuals it:

  1. Auto-detects the slicer_* visuals (or uses the names in decisions.json).
  2. Draws a dark drawer rectangle behind them + a "FILTERS" header.
  3. Adds a ☰ open button (aligned with the nav bar) and a ✕ close button.
  4. Writes a Show/Hide bookmark pair into definition/bookmarks/.

The two buttons apply the two bookmarks via visualLink type='Bookmark', so the
drawer toggles open/closed exactly like the Tableau source — no custom code.

Config (decisions.json → filterPanel, all optional):
    enabled        bool   default true  (set false to opt out)
    slicerNames    [str]  explicit slicer visual names (else auto-detect)
    panelColor     HEX    drawer background       (default #0D2A36)
    openButton     {x,y,width,height}  ☰ button geometry
    padding        int    px around slicer bbox   (default 16)

Usage:
    python scripts/emit/add_filter_panel.py <output_dir>
    python scripts/emit/add_filter_panel.py Output/SalesCustomerDashboards

Options:
    --panel-color HEX  Drawer background color [overrides decisions.json]
    --force            Inject even if filterPanel.enabled == false
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import pbir_blocks as P

_DEFAULT_PANEL_COLOR = "#0D2A36"
_DEFAULT_PADDING     = 16


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _resolve_cfg(output_dir: str, cli_color: str | None
                 ) -> tuple[str, bool, dict]:
    """Return (panel_color, enabled, fp_cfg) by merging decisions.json + CLI."""
    color   = _DEFAULT_PANEL_COLOR
    enabled = True
    fp_cfg: dict = {}

    decisions_path = os.path.join(output_dir, "decisions.json")
    if os.path.isfile(decisions_path):
        try:
            d = load_json(decisions_path)
            fp_cfg  = d.get("filterPanel") or {}
            color   = fp_cfg.get("panelColor", color)
            enabled = fp_cfg.get("enabled", True)
        except Exception:
            pass

    if cli_color:
        color = cli_color
    return color, enabled, fp_cfg


def _detect_slicers(visuals_dir: str, explicit: list[str] | None) -> list[dict]:
    """Return [{name, pos, field}] for every slicer visual in *visuals_dir*.

    When *explicit* names are supplied only those are used; otherwise every
    visual whose visualType is "slicer" is auto-detected. *field* is the bound
    column/measure name (used to map slicers to filter-panel sections).
    """
    found: list[dict] = []
    if not os.path.isdir(visuals_dir):
        return found
    for vname in sorted(os.listdir(visuals_dir)):
        vpath = os.path.join(visuals_dir, vname, "visual.json")
        if not os.path.isfile(vpath):
            continue
        try:
            vj = load_json(vpath)
        except Exception:
            continue
        vtype = (vj.get("visual") or {}).get("visualType", "")
        name  = vj.get("name", vname)
        if explicit:
            if name in explicit:
                found.append({"name": name, "pos": vj.get("position", {}),
                              "field": _slicer_field(vj)})
        elif vtype == "slicer":
            found.append({"name": name, "pos": vj.get("position", {}),
                          "field": _slicer_field(vj)})
    return found


def _slicer_field(vj: dict) -> str:
    """Return the column/measure Property a slicer is bound to (or "")."""
    try:
        projections = (vj["visual"]["query"]["queryState"]["Values"]
                       ["projections"])
        fld = projections[0]["field"]
        node = fld.get("Column") or fld.get("Measure") or {}
        return node.get("Property", "")
    except Exception:
        return ""


def _build_section_layout(slicers: list[dict],
                          sections_cfg: list[dict] | None) -> list[dict]:
    """Map detected slicers to ordered sections by field name.

    *sections_cfg* is the decisions.json ``filterPanel.sections`` list of
    ``{"label": str|None, "fields": [field, …]}``. Returns
    ``[{"label", "slicers": [name, …]}]`` ordered per the config, with any
    unmatched slicers appended as a trailing label-less group so nothing is
    dropped. Returns ``[]`` when no config is supplied (flat panel).
    """
    if not sections_cfg:
        return []
    by_field = {s["field"]: s["name"] for s in slicers if s.get("field")}
    used: set[str] = set()
    layout: list[dict] = []
    for sec in sections_cfg:
        names: list[str] = []
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



def _panel_bounds(slicers: list[dict], padding: int) -> tuple[int, int, int, int]:
    """Compute the drawer rectangle (x, y, w, h) around the slicer bounding box.

    Leaves extra headroom at the top for the FILTERS header / ✕ button.
    """
    xs0 = min(s["pos"].get("x", 0) for s in slicers)
    ys0 = min(s["pos"].get("y", 0) for s in slicers)
    xs1 = max(s["pos"].get("x", 0) + s["pos"].get("width", 0) for s in slicers)
    ys1 = max(s["pos"].get("y", 0) + s["pos"].get("height", 0) for s in slicers)
    header_room = 52
    x = max(0, int(xs0 - padding))
    y = max(0, int(ys0 - header_room))
    w = int((xs1 - xs0) + padding * 2)
    h = int((ys1 - ys0) + header_room + padding)
    return x, y, w, h


# Tableau "Vertical Cont. (Filter)" proportions (of the dashboard, 0..100000):
# x=78500 (78.5%), w=21417 (21.4%), full height. Reproduced as a right-edge,
# full-height drawer when a section container layout is requested.
_DRAWER_WIDTH_FRAC = 0.214


def _container_bounds(page_w: int, page_h: int) -> tuple[int, int, int, int]:
    """Right-edge, full-height drawer rectangle (Tableau filter container)."""
    w = max(240, int(page_w * _DRAWER_WIDTH_FRAC))
    x = page_w - w
    return x, 0, w, page_h


def add_filter_panel(output_dir: str,
                     cli_color: str | None = None,
                     force: bool = False) -> int:
    """Inject the filter panel toggle into every eligible page. Returns page count."""
    output_dir = os.path.normpath(output_dir)
    model_name = os.path.basename(output_dir)
    report_def = os.path.join(output_dir, f"{model_name}.Report", "definition")
    pages_dir  = os.path.join(report_def, "pages")

    pages_meta = os.path.join(pages_dir, "pages.json")
    if not os.path.isfile(pages_meta):
        print(f"ERROR: pages.json not found at {pages_meta}", file=sys.stderr)
        return 0

    panel_color, enabled, fp_cfg = _resolve_cfg(output_dir, cli_color)
    if not enabled and not force:
        print("Filter panel disabled in decisions.json "
              "(filterPanel.enabled=false). Use --force to override.")
        return 0

    page_names: list[str] = load_json(pages_meta).get("pageOrder", [])
    explicit  = fp_cfg.get("slicerNames")
    padding   = int(fp_cfg.get("padding", _DEFAULT_PADDING))
    open_btn  = fp_cfg.get("openButton") or {}
    header_color = fp_cfg.get("slicerHeaderColor", "#FFFFFF")
    sections_cfg = fp_cfg.get("sections")
    section_color = fp_cfg.get("sectionLabelColor", "#24C6FC")

    all_bookmark_ids: list[str] = []
    processed = 0

    for pn in page_names:
        visuals_dir = os.path.join(pages_dir, pn, "visuals")
        slicers = _detect_slicers(visuals_dir, explicit)
        if not slicers:
            print(f"  {pn}: no slicers — skipped.")
            continue

        # Page size (for default open-button placement + container drawer).
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
            px, py, pw, ph = _container_bounds(page_w, page_h)
        else:
            px, py, pw, ph = _panel_bounds(slicers, padding)

        ob_x = int(open_btn.get("x", page_w - 78))
        ob_y = int(open_btn.get("y", 6))
        ob_w = int(open_btn.get("width", 70))
        ob_h = int(open_btn.get("height", 70))
        open_btn_pos = {"x": ob_x, "y": ob_y, "z": 9600,
                        "height": ob_h, "width": ob_w, "tabOrder": 9600}

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
            print(f"  Wrote {vis['name']} -> {pn}")

        for bm in chrome["bookmarks"]:
            write_json(os.path.join(report_def, "bookmarks",
                                    f"{bm['name']}.bookmark.json"), bm)
            all_bookmark_ids.append(bm["name"])

        # Recolor the drawer's slicer headers (white + transparent bg) so they
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

        processed += 1
        print(f"  {pn}: panel + {len(slicers)} slicer(s), "
              f"{len(section_layout)} section(s), 2 bookmark(s).")

    if all_bookmark_ids:
        write_json(os.path.join(report_def, "bookmarks", "bookmarks.json"),
                   P.bookmarks_metadata(all_bookmark_ids))
        print(f"\nFilter panel injected: {processed} page(s), "
              f"{len(all_bookmark_ids)} bookmark(s) total.")
    else:
        print("\nNo eligible pages — nothing written.")
    return processed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inject a bookmark-driven filter panel into a PBIP report.")
    parser.add_argument("output_dir",
                        help="Workbook output folder, e.g. Output/SalesCustomerDashboards")
    parser.add_argument("--panel-color", default=None, metavar="HEX",
                        help="Drawer background color [overrides decisions.json]")
    parser.add_argument("--force", action="store_true",
                        help="Inject even if filterPanel.enabled=false in decisions.json")
    args = parser.parse_args(argv)

    processed = add_filter_panel(args.output_dir,
                                 cli_color=args.panel_color,
                                 force=args.force)
    return 0 if processed else 1


if __name__ == "__main__":
    raise SystemExit(main())
