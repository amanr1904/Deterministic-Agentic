"""add_nav_bar.py — Inject a navigation bar into an existing PBIP report.

Reads pages.json to discover all pages, then writes actionButton visual.json
files into each page's visuals/ folder. Existing nav_* folders are overwritten
so the script is idempotent.

Color precedence (highest wins):
  1. CLI --active-color / --inactive-color flags
  2. decisions.json → navBar.activeColor / navBar.inactiveColor
  3. decisions.json → theme.navActiveColor / theme.navInactiveColor  (legacy)
  4. Built-in defaults (#1F77B4 / #2C3E50)

If decisions.json → navBar.enabled == false the script prints a notice and exits
cleanly (respects the per-report opt-out set by the agent).

Usage:
    python scripts/emit/add_nav_bar.py <output_dir>
    python scripts/emit/add_nav_bar.py Output/SalesCustomerDashboards

Options:
    --active-color   HEX  Fill color for the current-page (active) button
    --inactive-color HEX  Fill color for other-page (clickable) buttons
    --force               Inject even if navBar.enabled == false in decisions.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import pbir_blocks as P

_DEFAULT_ACTIVE   = "#1F77B4"
_DEFAULT_INACTIVE = "#2C3E50"


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _resolve_colors(output_dir: str,
                    cli_active: str | None,
                    cli_inactive: str | None) -> tuple[str, str, bool, dict]:
    """Return (active_color, inactive_color, nav_enabled, nav_cfg) by merging all sources."""
    active   = _DEFAULT_ACTIVE
    inactive = _DEFAULT_INACTIVE
    enabled  = True
    nav_cfg: dict = {}

    # Try decisions.json in the output folder.
    decisions_path = os.path.join(output_dir, "decisions.json")
    if os.path.isfile(decisions_path):
        try:
            d = load_json(decisions_path)
            theme   = d.get("theme") or {}
            nav_cfg = d.get("navBar") or {}

            # Layer 3 — legacy theme keys.
            active   = theme.get("navActiveColor",   active)
            inactive = theme.get("navInactiveColor", inactive)

            # Layer 2 — dedicated navBar block (overrides theme).
            active   = nav_cfg.get("activeColor",   active)
            inactive = nav_cfg.get("inactiveColor", inactive)

            # Enabled flag from decisions.
            enabled  = nav_cfg.get("enabled", True)
        except Exception:
            pass

    # Layer 1 — explicit CLI flags (highest priority).
    if cli_active:
        active = cli_active
    if cli_inactive:
        inactive = cli_inactive

    return active, inactive, enabled, nav_cfg


def add_nav_bar(output_dir: str,
                cli_active: str | None = None,
                cli_inactive: str | None = None,
                force: bool = False) -> int:
    """Inject nav-bar buttons into every page of the report in *output_dir*.

    Returns the number of pages processed, or 0 if skipped/not needed.
    """
    output_dir = os.path.normpath(output_dir)
    model_name = os.path.basename(output_dir)
    pages_dir  = os.path.join(output_dir, f"{model_name}.Report",
                              "definition", "pages")

    pages_meta = os.path.join(pages_dir, "pages.json")
    if not os.path.isfile(pages_meta):
        print(f"ERROR: pages.json not found at {pages_meta}", file=sys.stderr)
        return 0

    pm         = load_json(pages_meta)
    page_names: list[str] = pm.get("pageOrder", [])

    if len(page_names) < 2:
        print("Only one page — no navigation bar needed.")
        return 0

    active_color, inactive_color, enabled, nav_cfg = _resolve_colors(
        output_dir, cli_active, cli_inactive)

    if not enabled and not force:
        print("Nav bar disabled in decisions.json (navBar.enabled=false). "
              "Use --force to override.")
        return 0

    # Build the pages list with display names from each page's page.json.
    all_pages: list[dict] = []
    for pn in page_names:
        page_json_path = os.path.join(pages_dir, pn, "page.json")
        display = pn
        if os.path.isfile(page_json_path):
            try:
                pj = load_json(page_json_path)
                display = pj.get("displayName", pn)
            except Exception:
                pass
        all_pages.append({"name": pn, "displayName": display})

    # Write nav buttons for each page.
    for pg in all_pages:
        buttons = P.nav_bar_visuals(
            pg["name"], all_pages,
            active_color=active_color,
            inactive_color=inactive_color,
            orientation=nav_cfg.get("orientation", "vertical"),
            btn_w=nav_cfg.get("buttonWidth"),
            btn_h=nav_cfg.get("buttonHeight"),
            btn_gap=nav_cfg.get("buttonGap"),
            origin_x=nav_cfg.get("originX"),
            origin_y=nav_cfg.get("originY"),
        )
        visuals_dir = os.path.join(pages_dir, pg["name"], "visuals")
        for btn in buttons:
            write_json(os.path.join(visuals_dir, btn["name"], "visual.json"), btn)
            print(f"  Wrote {btn['name']} -> {pg['name']}")

    total_buttons = len(all_pages) * len(all_pages)
    print(f"\nNav bar injected: {len(page_names)} page(s), "
          f"{total_buttons} button(s) total.")
    return len(page_names)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inject a navigation bar into an existing PBIP report."
    )
    parser.add_argument("output_dir",
                        help="Path to the workbook output folder, "
                             "e.g. Output/SalesCustomerDashboards")
    parser.add_argument("--active-color", default=None, metavar="HEX",
                        help="Fill color for the active (current page) button "
                             "[overrides decisions.json]")
    parser.add_argument("--inactive-color", default=None, metavar="HEX",
                        help="Fill color for inactive (other page) buttons "
                             "[overrides decisions.json]")
    parser.add_argument("--force", action="store_true",
                        help="Inject even if navBar.enabled=false in decisions.json")
    args = parser.parse_args(argv)

    processed = add_nav_bar(
        args.output_dir,
        cli_active=args.active_color,
        cli_inactive=args.inactive_color,
        force=args.force,
    )
    return 0 if processed else 1


if __name__ == "__main__":
    raise SystemExit(main())
