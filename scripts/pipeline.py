"""pipeline.py — deterministic orchestrator for the hybrid migration pipeline.

The pipeline follows an 8-stage flow. Deterministic stages run as Python child
processes here; the two Agent stages are a single LLM gap-fill (decisions.json)
that sits between the `prepare` and `generate` phases:

    1. Workbook Analyzer        (deterministic)  parse_twb.py
    2. Complexity Classifier    (deterministic)  parse_twb.py
    3. Metadata Extraction      (deterministic)  parse_twb.py -> analysis.json
       + DAX pre-translation    (deterministic)  map_dax.py  -> dax-partial.json
  --[ AGENT GAP-FILL: decisions.json ]------------------------------------------
    4. Visual Intent Generator  (agent)          ambiguous chart types
    6. DAX Generator            (agent)          complex DAX (LOD/table-calcs)
  ------------------------------------------------------------------------------
    5. Visual Factory           (deterministic)  emit_pbir.py -> Report
    7. PBIP Generator           (deterministic)  emit_tmdl.py -> SemanticModel
    8. Validation Engine        (deterministic)  tmdl-validate + validate_pbip.py

Two phases bracket the single LLM gap-fill step (decisions.json):

  prepare  <twb>                  Stages 1-3 (deterministic)
                                  -> analysis.json + dax-partial.json + gaps report
  [ AGENT writes decisions.json — Stages 4 + 6 ]
  generate <analysis> --decisions Stages 5 + 7 + 8 (deterministic)
                                  -> Report + SemanticModel + validation

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
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOAD_CONST = os.path.join(HERE, "load_constitution.py")
PARSE = os.path.join(HERE, "twb", "parse_twb.py")
MAPDAX = os.path.join(HERE, "dax", "map_dax.py")
CLASSIFY = os.path.join(HERE, "classify", "classify.py")
MERGE = os.path.join(HERE, "merge", "merge_decisions.py")
RECONCILE = os.path.join(HERE, "dax", "reconcile.py")
EMIT_TMDL = os.path.join(HERE, "emit", "emit_tmdl.py")
EMIT_PBIR = os.path.join(HERE, "emit", "emit_pbir.py")
VALIDATE_BINDINGS = os.path.join(HERE, "emit", "validate_bindings.py")
VALIDATE = os.path.join(
    HERE, "..", "plugins", "pbip", "skills", "pbip", "scripts", "validate_pbip.py")
SEM_VALIDATE = os.path.join(HERE, "validate_semantics.py")
BIN_DIR = os.path.join(HERE, "..", "plugins", "pbip", "hooks", "bin")


def _tmdl_validate_binary() -> str:
    """Resolve the tmdl-validate binary for the current OS/architecture.

    The hooks/bin folder ships native binaries for windows-x64, linux-x64,
    darwin-x64 and darwin-arm64; pick the right one so the pipeline is not
    Windows-only.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    is_arm = machine in ("arm64", "aarch64")
    if system == "windows":
        name = "tmdl-validate-windows-x64.exe"
    elif system == "darwin":
        name = "tmdl-validate-darwin-arm64" if is_arm else "tmdl-validate-darwin-x64"
    else:  # linux and other POSIX systems
        name = "tmdl-validate-linux-x64"
    return os.path.join(BIN_DIR, name)


TMDL_VALIDATE = _tmdl_validate_binary()


def banner(stage: str, name: str, mode: str) -> None:
    """Print a labeled stage header so the run log mirrors the 8-stage flow."""
    print(f"\n{'=' * 70}")
    print(f"  STAGE {stage} — {name}  [{mode}]")
    print(f"{'=' * 70}")


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


def _output_dir_for(output_root: str, twb: str) -> str:
    """Return Output/{PascalName}/ for the given workbook path."""
    import re
    name = os.path.splitext(os.path.basename(twb))[0]
    pascal = "".join(w[:1].upper() + w[1:]
                     for w in re.split(r"[^0-9A-Za-z]+", name) if w)
    return os.path.join(output_root, pascal)


def prepare(args) -> int:
    """Deterministic phase — flow stages 1-3 (+ constitution snapshot + DAX pre-pass).

    Stages 1 (Workbook Analyzer), 2 (Complexity Classifier) and 3 (Metadata
    Extraction) are all produced by parse_twb.py in a single pass that writes
    analysis.json. map_dax.py then pre-translates the trivial DAX so the agent's
    Stage 6 (DAX Generator) only handles the complex remainder.
    """
    # Stage 0 — deterministic constitution snapshot (hard-stop if files missing).
    banner("0", "Constitution Snapshot", "deterministic")
    out_dir = _output_dir_for(args.output_root, args.twb)
    rc = run([sys.executable, LOAD_CONST, out_dir])
    if rc != 0:
        return rc
    # Stages 1-3 — Workbook Analyzer + Complexity Classifier + Metadata Extraction.
    banner("1-3", "Workbook Analyzer + Complexity Classifier + Metadata Extraction",
           "deterministic")
    rc = run([sys.executable, PARSE, args.twb, "--output-root", args.output_root])
    if rc != 0:
        return rc
    analysis = analysis_path_for(args.output_root, args.twb)
    # Stage 6 (deterministic half) — pre-translate trivial Tableau calcs to DAX.
    banner("6", "DAX Generator — deterministic pre-translation", "deterministic")
    rc = run([sys.executable, MAPDAX, analysis])
    if rc != 0:
        return rc
    # Stage 6.5 — binary-route remaining work and emit the agent's self-contained
    # to-do list (classification.json, schema-easy.json, agent-todo.json).
    rc = run([sys.executable, CLASSIFY, analysis])
    if rc != 0:
        return rc
    _print_gaps(analysis)
    return 0


def _print_gaps(analysis: str) -> None:
    """Tell the agent exactly what the batched gap-fill call must author.

    Sources the routing from classification.json (authoritative binary route) and
    points the agent at agent-todo.json, the self-contained work list it reads.
    """
    with open(analysis, encoding="utf-8-sig") as fh:
        ir = json.load(fh)
    ambiguous = [w["name"] for w in ir.get("worksheets", [])
<<<<<<< HEAD
                 if (w.get("markClass") or "Automatic") == "Automatic"]
    partial_path = os.path.join(os.path.dirname(analysis), "dax-partial.json")
    complex_calcs = []
    if os.path.isfile(partial_path):
        with open(partial_path, encoding="utf-8-sig") as fh:
            complex_calcs = [p["caption"] for p in json.load(fh).get("pending", [])]
=======
                 if w.get("inferredVisualType") is None]
>>>>>>> main
    out_dir = os.path.dirname(analysis)
    cls_path = os.path.join(out_dir, "classification.json")
    schema_route, agent_measures = "agent", []
    if os.path.isfile(cls_path):
        with open(cls_path, encoding="utf-8-sig") as fh:
            cls = json.load(fh)
        schema_route = cls.get("schema", {}).get("route", "agent")
        agent_measures = [m["caption"] for m in cls.get("measures", [])
                          if m.get("route") == "agent"]
    print("\n=== AGENT GAP-FILL REQUIRED (one batched call -> agent-fragment.json) ===")
    print(f"  folder              : {out_dir}")
    print(f"  schema route        : {schema_route}")
    print(f"  agent DAX measures  : {len(agent_measures)} -> {agent_measures}")
    print(f"  ambiguous visuals   : {len(ambiguous)} -> {ambiguous}")
    print("  read: agent-todo.json (self-contained work list)")
    print("  write: agent-fragment.json (see scripts/contracts/fragment_schema.json)")
    print("  then: python pipeline.py merge <analysis>  -> assembles decisions.json")


def merge_cmd(args) -> int:
    """Stage 6.9: assemble dax-partial + schema-easy + agent-fragment -> decisions.json.

    Deterministic merge done by script (not the agent). Exit 4 means a pending
    measure is still missing -> the orchestrator escalates to the Opus fallback.
    """
    cmd = [sys.executable, MERGE, args.analysis]
    if args.agent_fragment:
        cmd += ["--agent-fragment", args.agent_fragment]
    if args.out:
        cmd += ["--out", args.out]
    return run(cmd)


def generate(args) -> int:
    """Stage 10 + 13 + validation: emit model and report, then validate."""
    # Guard: no pending measure may be silently dropped. If the agent omitted any,
    # this fails (exit 4) and writes measures-todo.json so the agent re-authors them.
    rc = run([sys.executable, RECONCILE, args.analysis, "--decisions", args.decisions])
    if rc != 0:
        return rc
    rc = run([sys.executable, EMIT_TMDL, args.analysis, "--decisions", args.decisions])
    if rc != 0:
        return rc
    # Stage 5 — Visual Factory (Report PBIR) or agent-mode shell + manifests.
    label = ("Visual Factory — Report shell + _zones.json (agent fills visuals)"
             if mode == "agent" else "Visual Factory — Report (PBIR)")
    banner("5", label, "deterministic")
    cmd = [sys.executable, EMIT_PBIR, args.analysis, "--decisions", args.decisions,
           "--visuals", mode]
    rc = run(cmd)
    if rc != 0:
        return rc
    if mode == "agent":
        _print_visual_gaps(args.analysis, args.decisions)
    # Stage 8 — Validation Engine.
    banner("8", "Validation Engine", "deterministic")
    project_dir = os.path.dirname(os.path.abspath(args.analysis))
    model_name = _model_name(args.decisions, project_dir)
    sm_def = os.path.join(project_dir, f"{model_name}.SemanticModel", "definition")
    if os.path.isfile(TMDL_VALIDATE):
        run([TMDL_VALIDATE, sm_def])
<<<<<<< HEAD
    rc_pbip = run([sys.executable, VALIDATE, project_dir])
    # Semantic check: every relationship/measure reference must resolve, types
    # must match, no reserved VAR names, no illegal PBIR properties. This is the
    # check that catches "won't open in Desktop" errors the syntax validators miss.
    rc_sem = run([sys.executable, SEM_VALIDATE, project_dir])
    return rc_sem if rc_sem != 0 else rc_pbip
=======
    # Guard: every report visual field must bind to a column/measure that actually
    # exists on its table (catches fact columns mis-bound to a synthetic DimDate).
    rc = run([sys.executable, VALIDATE_BINDINGS, project_dir])
    if rc != 0:
        return rc
    return run([sys.executable, VALIDATE, project_dir])
>>>>>>> main


def _print_visual_gaps(analysis: str, decisions: str) -> None:
    """Tell the agent where the manifests are and the rules for each visual.json."""
    project_dir = os.path.dirname(os.path.abspath(analysis))
    model_name = _model_name(decisions, project_dir)
    pages_dir = os.path.join(project_dir, f"{model_name}.Report",
                             "definition", "pages")
    print("\n=== AGENT VISUAL AUTHORING REQUIRED (Stage 5b) ===")
    print(f"  manifests : {pages_dir}{os.sep}<page>{os.sep}_zones.json")
    print("  for each zone -> write visuals/{name}/visual.json (use the suggested name)")
    print("  position    : copy verbatim from the manifest (do NOT recompute)")
    print("  root keys   : ONLY $schema, name, position, visual")
    print("  bindings    : queryRef must match model.tables[].columns/measures")
    print("  read        : plugins/pbip/skills/pbir-format/SKILL.md")


def _model_name(decisions_path: str, project_dir: str) -> str:
    with open(decisions_path, encoding="utf-8-sig") as fh:
        return json.load(fh).get("modelName") or os.path.basename(project_dir)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid migration orchestrator.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare", help="Stages 1-3 + DAX pre-pass (deterministic)")
    p_prep.add_argument("twb")
    p_prep.add_argument("--output-root", default="Output")
    p_prep.set_defaults(func=prepare)

    p_merge = sub.add_parser("merge", help="Stage 6.9: assemble decisions.json from fragments")
    p_merge.add_argument("analysis")
    p_merge.add_argument("--agent-fragment", help="path to agent-fragment.json")
    p_merge.add_argument("--out", help="output decisions.json path")
    p_merge.set_defaults(func=merge_cmd)

    p_gen = sub.add_parser("generate", help="Stage 10 + 13 + validation")
    p_gen.add_argument("analysis")
    p_gen.add_argument("--decisions", required=True)
    p_gen.add_argument("--visuals", choices=["factory", "agent"], default="agent",
                       help="agent = report shell + _zones.json manifests for "
                            "agent-authored visual.json (default, Stage 5b); "
                            "factory = deterministic visuals")
    p_gen.set_defaults(func=generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
