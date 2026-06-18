"""parse_twb.py — Stage 1 deterministic Tableau parser (CLI entry point).

Replaces the token-heavy "agent reads raw XML" stage. Converts a .twb file into
analysis.json (the IR) written INSIDE Output/{WorkbookName}/. The agent later
reads this slim IR instead of the raw workbook XML.

Usage:
    python parse_twb.py "Data/Midnight Census/Midnight Census Dashboard.twb"
    python parse_twb.py <twb> --output-root Output
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twb_xml as X  # noqa: E402
import twb_datasources as DS  # noqa: E402
import twb_visuals as V  # noqa: E402
import twb_fields as F  # noqa: E402
import twb_meta as M  # noqa: E402

IR_VERSION = "1.0"


def build_ir(twb_path: str) -> Dict:
    """Parse a .twb file and assemble the full IR dictionary."""
    root = X.load_twb(twb_path)
    wb_name = os.path.splitext(os.path.basename(twb_path))[0]
    pascal = X.to_pascal_case(wb_name)
    active = V.worksheet_datasources(root)
    calc_fields = DS.extract_calculated_fields(root)
    columns = DS.extract_columns(root)
    parameters = DS.extract_parameters(root)
    calc_map = F.build_calc_map(calc_fields)
    param_map = F.build_param_map(parameters)
    measures = F.measure_captions(calc_fields, columns)

    return {
        "irVersion": IR_VERSION,
        "workbook": {
            "name": wb_name,
            "pascalName": pascal,
            "sourcePath": twb_path.replace("\\", "/"),
            "version": X.attr(root, "version", ""),
            "platform": X.attr(root, "platform", ""),
        },
        "dataSources": DS.extract_datasources(root, active),
        "columns": columns,
        "calculatedFields": calc_fields,
        "parameters": parameters,
        "worksheets": V.extract_worksheets(root, calc_map, measures, param_map),
        "dashboards": V.extract_dashboards(root, calc_map, param_map),
        "actions": V.extract_actions(root, calc_map),
        "physicalTables": M.extract_physical_tables(root),
        "columnTableMap": M.extract_column_table_map(root),
        "relationships": M.extract_relationships(root),
        "hierarchies": M.extract_hierarchies(root),
        "sets": _extract_sets(root),
        "groups": M.extract_groups(root),
        "bins": M.extract_bins(root),
        "theme": M.extract_theme(root),
        "blending": _detect_blending(root),
        "rls": _detect_rls(root),
    }


def _extract_sets(root) -> list:
    """Lightweight set extraction (name + source field + members)."""
    sets = []
    seen = set()
    for grp in root.iter("group"):
        name = X.attr(grp, "name", "")
        if X.attr(grp, "hidden") == "true" or grp.get("user:auto-column"):
            continue
        if "Set]" not in name:
            continue
        clean = X.strip_brackets(name)
        if clean in seen:
            continue
        seen.add(clean)
        members = [X.strip_brackets(X.attr(m, "member"))
                   for m in grp.iter("groupfilter")
                   if X.attr(m, "function") == "member"]
        sets.append({
            "name": clean,
            "sourceField": clean.split("(")[0].strip() or None,
            "members": [m for m in members if m] or None,
        })
    return sets


def _detect_blending(root) -> Dict:
    """Count real datasources to flag potential data blending."""
    real = [ds for ds in X.iter_datasources(root)
            if X.attr(ds, "name") != "Parameters"]
    active = V.worksheet_datasources(root)
    if len(active) > 1:
        return {"blended": True, "datasources": sorted(active)}
    return {"blended": False, "datasources": [ds for ds in active]} if real else None


def _detect_rls(root) -> Dict:
    """Scan calculated-field formulas for Tableau RLS user functions."""
    signals = ("USERNAME(", "FULLNAME(", "ISMEMBEROF(", "ISUSERNAME(", "ISFULLNAME(")
    for field in DS.extract_calculated_fields(root):
        upper = field["formula"].upper()
        if any(sig in upper for sig in signals):
            rtype = "Group-based" if "ISMEMBEROF(" in upper else "Dynamic"
            return {
                "detected": True, "type": rtype,
                "securedTable": None, "mappingTable": None, "userColumn": None,
                "signalField": field["caption"],
            }
    return {"detected": False, "type": None, "securedTable": None,
            "mappingTable": None, "userColumn": None, "signalField": None}


def resolve_output_dir(ir: Dict, output_root: str) -> str:
    """Output/{PascalName}/ — created if missing."""
    target = os.path.join(output_root, ir["workbook"]["pascalName"])
    os.makedirs(target, exist_ok=True)
    return target


def write_ir(ir: Dict, output_dir: str) -> str:
    """Write analysis.json into the workbook output folder."""
    path = os.path.join(output_dir, "analysis.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ir, fh, indent=2, ensure_ascii=False)
    return path


def _summary(ir: Dict) -> str:
    return (
        f"  workbook       : {ir['workbook']['name']} -> {ir['workbook']['pascalName']}\n"
        f"  dataSources    : {len(ir['dataSources'])}\n"
        f"  columns        : {len(ir['columns'])}\n"
        f"  calcFields     : {len(ir['calculatedFields'])} "
        f"({sum(1 for c in ir['calculatedFields'] if c['complexity'] == 'complex')} complex)\n"
        f"  parameters     : {len(ir['parameters'])}\n"
        f"  worksheets     : {len(ir['worksheets'])} "
        f"({sum(1 for w in ir['worksheets'] if w['inferredVisualType'] is None)} ambiguous)\n"
        f"  dashboards     : {len(ir['dashboards'])}\n"
        f"  physTables     : {len(ir['physicalTables'])}\n"
        f"  relationships  : {len(ir['relationships'])}\n"
        f"  hierarchies    : {len(ir['hierarchies'])}\n"
        f"  groups/bins    : {len(ir['groups'])}/{len(ir['bins'])}\n"
        f"  RLS detected   : {ir['rls']['detected']}"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Parse a .twb into analysis.json (IR).")
    parser.add_argument("twb", help="path to the .twb file")
    parser.add_argument("--output-root", default="Output", help="root output folder")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.twb):
        print(f"ERROR: file not found: {args.twb}", file=sys.stderr)
        return 2

    ir = build_ir(args.twb)
    out_dir = resolve_output_dir(ir, args.output_root)
    path = write_ir(ir, out_dir)
    print(f"Wrote IR: {path}\n{_summary(ir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
