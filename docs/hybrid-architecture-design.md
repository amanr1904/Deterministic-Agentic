# Hybrid Deterministic + Agentic Architecture — Design Plan

**Status**: Implemented — the deterministic engine lives in `scripts/` (`pipeline.py`,
`twb/parse_twb.py`, `dax/map_dax.py`, `emit/emit_tmdl.py`, `emit/emit_pbir.py`) with the
contracts in `scripts/contracts/`. This document is retained as the design rationale.
**Goal**: Cut token consumption by moving mechanical work off the LLM, while keeping agents for genuine reasoning.
**Date**: 2026-06-16

---

## 1. Problem statement

The current pipeline is **fully agentic**: all 14 stages run through `runSubagent()`. Agents
ingest raw `.twb` XML, decode entities, compute layout coordinates, and emit TMDL/PBIR
boilerplate token-by-token. This is expensive because:

- The model reads large structured inputs (`.twb` XML, CSV headers, prior outputs) into context.
- The model **re-derives deterministic output** (folder scaffolds, JSON schemas, TMDL syntax)
  that a script could emit byte-for-byte.
- Each stage re-reads upstream artifacts (analysis → DAX → schema → plan → tasks → TMDL),
  multiplying context cost.

Only ~5 of 14 stages need an LLM. The rest are mechanical.

---

## 2. Core idea — an Intermediate Representation (IR)

Insert a **deterministic parser** that converts `.twb` → a compact `analysis.json` (the IR),
and **deterministic generators** that turn `IR + decisions` → PBIP files. The LLM only fills a
small `decisions.json` (the genuine reasoning gaps) and writes spec/plan prose.

```
.twb ──[parse_twb.py]──► analysis.json (IR)
                              │
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
   [LLM gap-fill]      deterministic           deterministic
   decisions.json       defaults                validators
        │                     │                      │
        └──────────┬──────────┘                      │
                   ▼                                  │
   IR + decisions ──[emit_tmdl.py]──► *.SemanticModel │
   IR + decisions ──[emit_pbir.py]──► *.Report ───────┘
                   ▼
            [validate_pbip.py / tmdl-validate]  (already exist)
```

**Principle**: The LLM never reads raw `.twb` XML and never writes boilerplate. It reads the
slim IR and emits only what cannot be computed deterministically.

---

## 3. Stage classification

| Stage | Today | Proposed | Rationale |
|-------|-------|----------|-----------|
| 1 Tableau analysis | Agent reads raw XML | **Deterministic** `parse_twb.py` → IR | Pure XML parse, entity decode, source-class detection. **Biggest single win.** |
| 2 Read constitution | Agent | **Deterministic** static read | Never regenerated |
| 3 Feature branch | PS script | **Deterministic** (unchanged) | Already a script |
| 4 Specify | Agent | **Agentic (slim)** — fed IR, not XML | Prose reasoning |
| 5 Clarify | Agent | **Agentic / optional** | Many answers default from IR |
| 6 DAX measures | Agent | **Hybrid** — template-map trivial calcs; LLM for complex | ~60–70% are 1:1 |
| 7 Star schema | Agent | **Hybrid** — deterministic single-table rule + key detection; LLM for multi-source design | Rule §0 is mechanical |
| 8 Plan | Agent | **Agentic (slim)** template-driven | |
| 9 Tasks | Agent | **Deterministic template** or thin agent | Largely boilerplate |
| 10 PBIP generation | Agent writes TMDL | **Deterministic** `emit_tmdl.py` | Templating. **Huge win.** |
| 11 Validate model | PS/Python | **Deterministic** (unchanged) | Already a script |
| 12 Analyze | Agent | **Hybrid** — deterministic cross-ref diff + LLM summary | Most checks are diffs |
| 13 Report visuals | Agent writes PBIR | **Hybrid** — deterministic zone→coordinate math + JSON emit; LLM for ambiguous marks | Position math is arithmetic |
| 14 Final validate | Python | **Deterministic** (unchanged) | Already a script |

**Net effect**: Stages 1, 2, 10, 13 (token-heaviest) move mostly off the LLM. The agent's job
shrinks to a small `decisions.json` + spec/plan prose.

---

## 4. The IR contract — `analysis.json`

A single, versioned schema is the contract between the deterministic parser and everything
downstream. Draft shape:

```jsonc
{
  "irVersion": "1.0",
  "workbook": { "name": "...", "pascalName": "...", "version": "...", "platform": "..." },
  "dataSources": [
    {
      "name": "...", "connectionClass": "textclean",
      "sourceType": "CSV",                     // resolved: CSV/Excel/SqlServer/Postgres/...
      "files": ["Data/Loan/loan.csv"],
      "server": null, "database": null, "schema": null,
      "tables": ["loan"]
    }
  ],
  "columns": [
    { "datasource": "...", "name": "...", "caption": "...",
      "dataType": "string", "role": "dimension|measure",
      "semanticRole": "...", "format": "$#,##0" }
  ],
  "calculatedFields": [
    { "caption": "...", "formula": "...", "isTableCalc": false,
      "complexity": "trivial|complex",        // classifier output (see §6)
      "suggestedDaxKind": "measure|column" }
  ],
  "parameters": [
    { "name": "...", "dataType": "...", "default": "...", "domainType": "list|range",
      "values": ["..."] }
  ],
  "worksheets": [
    { "name": "...", "markClass": "Bar", "rows": ["..."], "cols": ["..."],
      "encodings": { "color": "...", "size": "...", "text": "..." },
      "inferredVisualType": "barChart|table|lineChart|card|..." }   // null if ambiguous
  ],
  "dashboards": [
    { "name": "...", "size": { "w": 1366, "h": 860 },
      "zones": [ { "type": "viz|filter|paramctrl", "worksheet": "...",
                   "x": 0, "y": 0, "w": 0, "h": 0 } ],
      "buttons": [ { "action": "goto-sheet|toggle", "target": "...",
                     "tooltip": "...", "x": 0, "y": 0, "w": 0, "h": 0 } ] }
  ],
  "sets": [], "groups": [], "bins": [], "blending": null,
  "rls": { "detected": false, "type": null, "securedTable": null,
           "mappingTable": null, "userColumn": null }
}
```

This replaces the free-form `tableau-analysis-output.md` as the **machine-readable** source of
truth. A human-readable markdown can still be rendered from it for review (deterministically).

---

## 5. The decisions contract — `decisions.json`

The **only** thing the LLM produces for code-generation stages. Everything else is computed.

```jsonc
{
  "modelName": "LoanPortfolioAnalysis",
  "tableStrategy": "single-flat|star-schema",
  "tables": [ { "name": "...", "role": "fact|dim|param|date", "keyColumns": ["..."] } ],
  "relationships": [ { "from": "Dim[Key]", "to": "Fact[Key]", "crossFilter": "single" } ],
  "measures": [
    { "name": "...", "dax": "...", "formatString": "...", "displayFolder": "...",
      "source": "template|llm" } 
  ],
  "calculatedColumns": [ { "table": "...", "name": "...", "dax": "..." } ],
  "visualDecisions": [
    { "worksheet": "...", "visualType": "barChart",   // resolves IR ambiguity
      "reason": "Automatic + Measure Names on cols → table" } 
  ]
}
```

Deterministic generators consume `analysis.json + decisions.json` and never ask the LLM again.

---

## 6. DAX translation — the hybrid split (Stage 6)

A lookup-based **`map_dax.py`** handles the trivial majority; the LLM handles the rest.

**Deterministic (template) cases:**

| Tableau | DAX |
|---------|-----|
| `SUM([x])` | `SUM(T[x])` |
| `AVG([x])` | `AVERAGE(T[x])` |
| `COUNT([x])` / `COUNTD([x])` | `COUNT` / `DISTINCTCOUNT` |
| `MIN`/`MAX`/`MEDIAN` | direct equivalents |
| `[a] / [b]` | `DIVIDE([a],[b])` |
| Simple `IF`/`CASE` on a column | `IF` / `SWITCH` |

**LLM cases** (flagged `complexity: "complex"` by the parser): LOD `{FIXED/INCLUDE/EXCLUDE}`,
table calcs (`WINDOW_*`, `RUNNING_*`, `LOOKUP`, `INDEX`), nested context, multi-step `IF` with
parameters. The agent receives only these flagged formulas — not the whole workbook.

---

## 7. Report layout — the hybrid split (Stage 13)

- **Deterministic**: Tableau zone `x/y/w/h` (in Tableau's coordinate space) → Power BI logical
  pixels via a fixed scale transform; gap/padding rules from `report-constitution.md`; PBIR
  `visual.json` / `page.json` scaffolds; navigation-button wiring.
- **LLM**: only `inferredVisualType == null` cases (`mark class="Automatic"` ambiguity) and any
  chart-type substitution that needs judgement. Resolved into `decisions.json.visualDecisions`.

---

## 8. Proposed directory layout

```
scripts/                      # deterministic engine (implemented)
  pipeline.py                 # two-phase orchestrator (prepare / generate)
  contracts/
    ir_schema.json            # the IR contract (single source of truth)
    decisions_schema.json     # the decisions contract
  twb/
    parse_twb.py              # .twb → analysis.json            (Stage 1)
    twb_xml.py                # XML load + shared helpers
    twb_datasources.py        # datasource/column/param/calc extraction
    twb_visuals.py            # worksheet/dashboard extraction
    twb_fields.py             # calc/param maps + complexity flag
  dax/
    map_dax.py                # trivial Tableau calc → DAX       (Stage 6 partial)
  emit/
    emit_tmdl.py              # IR + decisions → .SemanticModel  (Stage 10)
    emit_pbir.py              # IR + decisions → .Report         (Stage 13)
    tmdl_blocks.py / pbir_blocks.py / pbir_bind.py / field_param.py / date_levels.py

plugins/pbip/skills/pbip/scripts/validate_pbip.py   # unchanged
plugins/pbip/hooks/bin/tmdl-validate-*              # unchanged (per-OS binaries)
```

Agents keep their `.agent.md` files but their **instructions change**: from *"read the XML and
produce TMDL"* to *"run `parse_twb.py`; fill gaps in `decisions.json`; run `emit_tmdl.py`."*

---

## 9. Orchestration change

`migration-constitution` becomes a **thin coordinator** that mostly shells out to scripts and
invokes subagents only for the reasoning gaps:

```
1.  run parse_twb.py                      → analysis.json        [deterministic]
2.  read constitution.md                  (static)              [deterministic]
3.  create-new-feature.ps1                → branch              [deterministic]
4.  runSubagent speckit.specify           (fed IR)              [LLM]
5.  runSubagent speckit.clarify           (optional)            [LLM]
6.  run map_dax.py; runSubagent dax-measures for FLAGGED only   [hybrid]
7.  run derive_schema.py; runSubagent star-schema if multi-src  [hybrid]
8.  runSubagent speckit.plan              (fed IR)              [LLM]
9.  run emit_tasks.py  (or thin agent)                          [deterministic]
10. run emit_tmdl.py                      → .SemanticModel      [deterministic]
11. run validate_pbip.py + tmdl-validate                       [deterministic]
12. run cross-ref diff; runSubagent speckit.analyze for summary [hybrid]
13. run emit_pbir.py; runSubagent for ambiguous marks only      [hybrid]
14. run validate_pbip.py (project root)                         [deterministic]
```

---

## 10. Rollout plan (incremental, low-risk)

Each phase is independently shippable and validated against the **existing** outputs in
`Output/` (golden-file regression — the new deterministic path must reproduce them).

- **Phase 0 — Contracts**: write `ir_schema.json` + `decisions_schema.json`. No behavior change.
- **Phase 1 — Parser**: `parse_twb.py`; validate IR against all 4 existing workbooks; render
  markdown and diff against current `tableau-analysis-output.md`. Wire Stage 1 to the script.
- **Phase 2 — TMDL emitter**: `emit_tmdl.py`; regenerate each `*.SemanticModel/` and diff
  against committed output; must pass `tmdl-validate` + `validate_pbip.py` with zero errors.
- **Phase 3 — DAX hybrid**: `map_dax.py`; route only flagged formulas to the agent.
- **Phase 4 — PBIR emitter**: `emit_pbir.py`; regenerate `*.Report/` and diff.
- **Phase 5 — Schema/tasks/analyze**: `derive_schema.py`, `emit_tasks.py`, cross-ref diff.
- **Phase 6 — Slim the agents**: rewrite `.agent.md` instructions to the script-first flow;
  remove inline XML-reading / boilerplate-writing guidance.

**Acceptance per phase**: byte-or-semantic-equivalent to the committed `Output/` artifacts, and
zero validator errors.

---

## 11. Expected token savings (qualitative)

| Lever | Effect |
|-------|--------|
| No raw `.twb` XML in context (Stage 1, 13) | Removes the single largest input |
| No TMDL/JSON boilerplate generation (Stage 10, 13) | Removes the largest output |
| Slim IR instead of re-reading prose artifacts | Smaller context per downstream stage |
| Only flagged DAX to LLM (Stage 6) | ~60–70% fewer formula tokens |
| Deterministic tasks/validation/analyze diff | Near-zero LLM cost |

The remaining LLM spend concentrates on irreducible reasoning: complex DAX, spec/plan prose,
ambiguous chart inference, multi-source design.

---

## 12. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Parser misses edge-case TWB XML variants | Golden-file regression against all 4 workbooks; `complexity`/`inferredVisualType=null` escape hatch routes hard cases to the LLM |
| IR schema churn breaks generators | Version the IR (`irVersion`); generators assert on version |
| Deterministic output drifts from Desktop-valid output | Every phase gated by existing validators (`tmdl-validate`, `validate_pbip.py`) |
| Over-templating loses nuance the LLM provided | Keep the gap-fill (`decisions.json`) escape hatch for any field the parser can't resolve |
| Two sources of truth (md vs json) | `analysis.json` is canonical; markdown is rendered from it, never hand-edited |

---

## 13. Open questions — resolved

1. **Language**: Python for all new scripts (matches `validate_pbip.py`). **Resolved: Python.**
2. **IR location**: `analysis.json` is written to `Output/{WorkbookName}/` alongside
   `dax-partial.json` and `decisions.json`. **Resolved: `Output/{WorkbookName}/`.**
3. **Markdown artifacts**: the IR JSON is canonical; human-readable markdown is optional and
   rendered, never hand-edited. **Resolved: JSON canonical.**
4. **Regression baseline**: committed `Output/` artifacts are treated as golden; the
   deterministic path must reproduce them and pass the validators.
5. **Scope of agent slimming**: the token-heavy path (Stages 1, 6, 10, 13) is script-first;
   remaining `.agent.md` files invoke the scripts rather than re-deriving their output.
```

