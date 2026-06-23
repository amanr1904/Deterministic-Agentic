"""merge_decisions.py — assemble fragments into the complete decisions.json (Stage 6.9).

This is the deterministic "merge" step the user asked to be done by script, not the
agent. It folds three deterministic/agent fragments into the single artifact that
emit_tmdl.py and emit_pbir.py consume:

  * dax-partial.json   — deterministic measures (source="template")
  * schema-easy.json   — the single-flat schema fragment (when star_det built it),
                         else the agent's schema comes from agent-fragment.json
  * agent-fragment.json — the one batched agent call's output: remaining measures
                         (source="llm"), any calculated columns, and (for the
                         non-single-flat case) the star schema

Guarantees the emitted decisions.json is COMPLETE before generation:
  * measure ``source`` is normalized to the contract enum (template|llm)
  * duplicate measures are de-duped with template (deterministic) precedence
  * any measure/column homed to a non-existent table is re-routed to the fact
    (mirrors emit_tmdl's reassign_orphan_measures defense, applied up-front)
  * the result is schema-validated, then reconcile.py confirms no pending measure
    was dropped (exit 4 signals the orchestrator to escalate to the Opus fallback)

Exit codes: 0 = clean, 2 = validation/usage error, 4 = pending measures missing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONTRACTS = os.path.join(_HERE, os.pardir, "contracts")
_RECONCILE = os.path.join(_HERE, os.pardir, "dax", "reconcile.py")


def _norm(name: str) -> str:
    return re.sub(r"[^0-9a-z]", "", (name or "").lower())


def _load(path: str) -> Optional[Dict]:
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _fact_table(tables: List[Dict]) -> Optional[str]:
    for t in tables:
        if t.get("role") == "fact":
            return t.get("name")
    return tables[0].get("name") if tables else None


def _normalize_measure(m: Dict, default_source: str) -> Dict:
    src = m.get("source", default_source)
    if src not in ("template", "llm"):
        src = "template" if src == "template" else "llm"
    return {
        "table": m.get("table"),
        "name": m.get("name"),
        "dax": m.get("dax"),
        "formatString": m.get("formatString"),
        "displayFolder": m.get("displayFolder"),
        "description": m.get("description"),
        "source": src,
    }


def _dedup_measures(det: List[Dict], agent: List[Dict]) -> List[Dict]:
    """Combine with deterministic (template) precedence over agent (llm) duplicates."""
    out: List[Dict] = []
    seen = set()
    for m in det:
        key = _norm(m.get("name", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    for m in agent:
        key = _norm(m.get("name", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


def merge(ir: Dict,
          dax_partial: Optional[Dict],
          schema_easy: Optional[Dict],
          agent_fragment: Optional[Dict]) -> Dict:
    """Pure assembly of the complete decisions dict from the fragments."""
    model = ir.get("workbook", {}).get("pascalName", "Model")
    dax_partial = dax_partial or {}
    agent_fragment = agent_fragment or {}

    # Schema: prefer the deterministic single-flat fragment; else the agent's design.
    schema_src = schema_easy if schema_easy is not None else agent_fragment
    strategy = schema_src.get("tableStrategy", "single-flat")
    tables = list(schema_src.get("tables", []))
    relationships = list(schema_src.get("relationships", []))
    fact = _fact_table(tables) or model

    det = [_normalize_measure(m, "template") for m in dax_partial.get("measures", [])]
    agent_m = [_normalize_measure(m, "llm") for m in agent_fragment.get("measures", [])]
    measures = _dedup_measures(det, agent_m)

    valid = {t.get("name") for t in tables}
    for m in measures:
        if m.get("table") not in valid:
            m["table"] = fact

    calc_cols = list(agent_fragment.get("calculatedColumns", []))
    for c in calc_cols:
        if c.get("table") not in valid:
            c["table"] = fact

    measures.sort(key=lambda m: (0 if m["source"] == "template" else 1,
                                 (m.get("name") or "").lower()))
    calc_cols.sort(key=lambda c: (c.get("name") or "").lower())

    return {
        "decisionsVersion": "1.0",
        "modelName": model,
        "tableStrategy": strategy,
        "tables": tables,
        "relationships": relationships,
        "measures": measures,
        "calculatedColumns": calc_cols,
        "visualDecisions": [],
        "fieldParameters": [],
    }


def validate(decisions: Dict) -> List[str]:
    """Schema-validate the decisions dict. Returns a list of error strings (empty=ok).

    Uses jsonschema when available; otherwise falls back to a minimal required-key
    check so the merge still hard-fails on a structurally broken artifact.
    """
    schema_path = os.path.join(_CONTRACTS, "decisions_schema.json")
    schema = _load(schema_path)
    try:
        import jsonschema  # type: ignore
    except Exception:
        errors: List[str] = []
        for key in ("modelName", "tableStrategy", "tables", "measures"):
            if key not in decisions:
                errors.append(f"missing required key: {key}")
        for m in decisions.get("measures", []):
            for key in ("table", "name", "dax"):
                if not m.get(key):
                    errors.append(f"measure missing {key}: {m.get('name')}")
        return errors
    validator = jsonschema.Draft7Validator(schema)
    return [f"{'/'.join(str(p) for p in e.path)}: {e.message}"
            for e in validator.iter_errors(decisions)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble fragments into the complete decisions.json and validate.")
    parser.add_argument("analysis", help="path to analysis.json (IR)")
    parser.add_argument("--agent-fragment",
                        help="path to agent-fragment.json (defaults to alongside analysis.json)")
    parser.add_argument("--out", help="output decisions.json path (defaults alongside analysis.json)")
    parser.add_argument("--skip-reconcile", action="store_true",
                        help="skip the reconcile cross-check (tests only)")
    args = parser.parse_args(argv)

    ir = _load(args.analysis)
    if ir is None:
        print(f"ERROR: file not found: {args.analysis}", file=sys.stderr)
        return 2

    out_dir = os.path.dirname(os.path.abspath(args.analysis))
    dax_partial = _load(os.path.join(out_dir, "dax-partial.json"))
    schema_easy = _load(os.path.join(out_dir, "schema-easy.json"))
    frag_path = args.agent_fragment or os.path.join(out_dir, "agent-fragment.json")
    agent_fragment = _load(frag_path)

    decisions = merge(ir, dax_partial, schema_easy, agent_fragment)

    errors = validate(decisions)
    if errors:
        print("ERROR: decisions.json failed schema validation:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    out_path = args.out or os.path.join(out_dir, "decisions.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(decisions, fh, indent=2, ensure_ascii=False)
    print(f"merge: wrote {out_path} "
          f"(tables={len(decisions['tables'])} measures={len(decisions['measures'])})")

    if args.skip_reconcile:
        return 0

    rc = subprocess.call([sys.executable, _RECONCILE, args.analysis,
                          "--decisions", out_path])
    return 4 if rc == 4 else 0


if __name__ == "__main__":
    raise SystemExit(main())
