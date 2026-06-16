"""pipeline.py — deterministic orchestrator for the hybrid migration pipeline.

Two phases bracket the single LLM gap-fill step (decisions.json):

  prepare  <twb>                  Stage 1 + 6 (deterministic)
                                  -> analysis.json + dax-partial.json + gaps report
  [ AGENT writes decisions.json from analysis.json + dax-partial.json ]
  generate <analysis> --decisions Stage 10 + 13 + 11/14 (deterministic)
                                  -> SemanticModel + Report + validation

This keeps raw .twb XML and TMDL/PBIR boilerplate entirely off the LLM; the agent
only authors the small decisions.json (complex DAX, ambiguous charts, design).

Usage:
    python pipeline.py prepare  "Data/Midnight Census/Midnight Census Dashboard.twb"
    python pipeline.py generate "Output/MidnightCensusDashboard/analysis.json" \
        --decisions "Output/MidnightCensusDashboard/decisions.json"
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARSE = os.path.join(HERE, "twb", "parse_twb.py")
MAPDAX = os.path.join(HERE, "dax", "map_dax.py")
EMIT_TMDL = os.path.join(HERE, "emit", "emit_tmdl.py")
EMIT_PBIR = os.path.join(HERE, "emit", "emit_pbir.py")
VALIDATE = os.path.join(
    HERE, "..", "plugins", "pbip", "skills", "pbip", "scripts", "validate_pbip.py")
TMDL_VALIDATE = os.path.join(
    HERE, "..", "plugins", "pbip", "hooks", "bin", "tmdl-validate-windows-x64.exe")


def run(cmd: list) -> int:
    """Run a child process, streaming output; return its exit code."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    return subprocess.call(cmd)


def analysis_path_for(output_root: str, twb: str) -> str:
    name = os.path.splitext(os.path.basename(twb))[0]
    import re
    pascal = "".join(w[:1].upper() + w[1:]
                     for w in re.split(r"[^0-9A-Za-z]+", name) if w)
    return os.path.join(output_root, pascal, "analysis.json")


def prepare(args) -> int:
    """Stage 1 + 6: parse the workbook and pre-translate trivial DAX."""
    rc = run([sys.executable, PARSE, args.twb, "--output-root", args.output_root])
    if rc != 0:
        return rc
    analysis = analysis_path_for(args.output_root, args.twb)
    rc = run([sys.executable, MAPDAX, analysis])
    if rc != 0:
        return rc
    _print_gaps(analysis)
    return 0


def _print_gaps(analysis: str) -> None:
    """Tell the agent exactly what decisions.json must still resolve."""
    with open(analysis, encoding="utf-8-sig") as fh:
        ir = json.load(fh)
    ambiguous = [w["name"] for w in ir.get("worksheets", [])
                 if w.get("inferredVisualType") is None]
    complex_calcs = [c["caption"] for c in ir.get("calculatedFields", [])
                     if c["complexity"] == "complex"]
    out_dir = os.path.dirname(analysis)
    print("\n=== AGENT GAP-FILL REQUIRED (write decisions.json here) ===")
    print(f"  folder              : {out_dir}")
    print(f"  complex DAX (LLM)   : {len(complex_calcs)} -> {complex_calcs}")
    print(f"  ambiguous visuals   : {len(ambiguous)} -> {ambiguous}")
    print("  read: analysis.json + dax-partial.json")
    print("  write: decisions.json (see scripts/contracts/decisions_schema.json)")


def generate(args) -> int:
    """Stage 10 + 13 + validation: emit model and report, then validate."""
    rc = run([sys.executable, EMIT_TMDL, args.analysis, "--decisions", args.decisions])
    if rc != 0:
        return rc
    rc = run([sys.executable, EMIT_PBIR, args.analysis, "--decisions", args.decisions])
    if rc != 0:
        return rc
    project_dir = os.path.dirname(os.path.abspath(args.analysis))
    model_name = _model_name(args.decisions, project_dir)
    sm_def = os.path.join(project_dir, f"{model_name}.SemanticModel", "definition")
    if os.path.isfile(TMDL_VALIDATE):
        run([TMDL_VALIDATE, sm_def])
    return run([sys.executable, VALIDATE, project_dir])


def _model_name(decisions_path: str, project_dir: str) -> str:
    with open(decisions_path, encoding="utf-8-sig") as fh:
        return json.load(fh).get("modelName") or os.path.basename(project_dir)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid migration orchestrator.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Stage 1 + 6 (deterministic)")
    p_prep.add_argument("twb")
    p_prep.add_argument("--output-root", default="Output")
    p_prep.set_defaults(func=prepare)

    p_gen = sub.add_parser("generate", help="Stage 10 + 13 + validation")
    p_gen.add_argument("analysis")
    p_gen.add_argument("--decisions", required=True)
    p_gen.set_defaults(func=generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
