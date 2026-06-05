---
description: Orchestrate the full Tableau → Power BI migration pipeline — read universal constitution → feature branch → specify → clarify → DAX measures → star schema → plan → tasks → implement (PBIP generation) → report visual migration. Constitution is a shared rulebook read (never regenerated) per workbook. Follows speckit workflow: spec → plan → tasks → implement → report.

handoffs:
  - label: Write Feature Specification
    agent: speckit.specify
    prompt: "Create a comprehensive feature specification for the Tableau to Power BI migration based on the analysis output and constitution rules."
  - label: Clarify Spec Requirements
    agent: speckit.clarify
    prompt: "Clarify and validate all requirements in the feature specification against the migration constitution."
  - label: Generate DAX Measures
    agent: dax-measures
    prompt: "Generate DAX measures for the semantic model based on the specified requirements and calculated fields."
  - label: Design Star Schema
    agent: star-schema
    prompt: "Design a star schema structure following the constitution rules, with dimension and fact tables."
  - label: Create Implementation Plan
    agent: speckit.plan
    prompt: "Create a detailed implementation plan for the PBIP generation and deployment."
  - label: Generate Tasks
    agent: speckit.tasks
    prompt: "Break down the implementation plan into actionable tasks."
  - label: Generate PBIP File (Implement)
    agent: pbip-generator
    prompt: "Generate the Power BI Project (PBIP) file with the semantic model, DAX measures, and star schema design."
  - label: Migrate Visuals to Power BI Report
    agent: report-visual-migration
    prompt: "Migrate Tableau visuals to Power BI reports, applying the visual migration strategy."
  - label: Cross-Artifact Consistency Analysis
    agent: speckit.analyze
    prompt: "Cross-check spec, plan, and tasks for consistency — validate star schema design vs DAX measures vs TMDL output for column mapping gaps, relationship mismatches, and naming inconsistencies."
---

## User Input

```text
$ARGUMENTS
```

## Skill References

Before proceeding, read these skills for guidance:
- `.github/skills/dax-measures/SKILL.md`
- `.github/skills/star-schema/SKILL.md`
- `.github/skills/pbip-generator/SKILL.md`
- `.github/skills/report-visual-generation/SKILL.md`
- `.github/skills/tableau-visual-extraction/SKILL.md`

### Plugin Validation References (read for validation steps):
- `plugins/pbip/skills/tmdl/SKILL.md` — TMDL syntax, indentation, quoting, nesting
- `plugins/pbip/skills/pbip/SKILL.md` — PBIP structure, encoding (UTF-8 no BOM), thick vs thin
- `plugins/pbip/skills/pbir-format/SKILL.md` — PBIR JSON format, visual.json properties, schema patterns
- `plugins/reports/skills/create-pbi-report/SKILL.md` — report creation best practices
- `plugins/reports/skills/pbi-report-design/SKILL.md` — layout, spacing, visual hierarchy

## Execution — Full Pipeline (ALL stages MANDATORY)

**⚠️ CRITICAL RULE — SUBAGENT ENFORCEMENT ⚠️**

**YOU MUST USE THE `runSubagent` TOOL for every stage that specifies an agent. This is NON-NEGOTIABLE.**

- Stage 4 → CALL `runSubagent` with `agentName: "speckit.specify"`
- Stage 5 → CALL `runSubagent` with `agentName: "speckit.clarify"`
- Stage 6 → CALL `runSubagent` with `agentName: "dax-measures"`
- Stage 7 → CALL `runSubagent` with `agentName: "star-schema"`
- Stage 8 → CALL `runSubagent` with `agentName: "speckit.plan"`
- Stage 9 → CALL `runSubagent` with `agentName: "speckit.tasks"`
- Stage 10 → CALL `runSubagent` with `agentName: "pbip-generator"`
- Stage 12 → CALL `runSubagent` with `agentName: "speckit.analyze"`
- Stage 13 → CALL `runSubagent` with `agentName: "report-visual-migration"`

**DO NOT:**
- ❌ Write spec content yourself — CALL speckit.specify
- ❌ Write DAX measures yourself — CALL dax-measures
- ❌ Design star schema yourself — CALL star-schema
- ❌ Write plan/tasks yourself — CALL speckit.plan / speckit.tasks
- ❌ Generate TMDL/PBIP files yourself — CALL pbip-generator
- ❌ Generate report visuals yourself — CALL report-visual-migration
- ❌ Skip any agent call because "you can do it faster"
- ❌ Summarize what an agent would do instead of calling it

**DO:**
- ✅ Call `runSubagent` tool with the agent name, a detailed prompt, and a short description
- ✅ Wait for the agent's result before proceeding to the next stage
- ✅ Pass ALL relevant context (file paths, workbook name, subfolder) in the prompt

**If `runSubagent` tool is unavailable or fails, STOP and report the error — NEVER fall back to doing the work inline.**

**Workflow order follows speckit convention: Specify → Clarify → Design → Plan → Tasks → Implement**

### Stage 1: Read Analysis Context

Read `.specify/memory/{WorkbookName}/tableau-analysis-output.md` to understand:
- Datasources (connection types, file paths, tables)
- Columns (names, datatypes, roles, semantic roles)
- Calculated fields (formulas)
- Parameters (ranges, defaults)
- Worksheets and dashboards
- Relationships/joins

> **Memory Scoping**: All workbook-specific artifacts are stored in `.specify/memory/{WorkbookName}/` (e.g., `.specify/memory/SalesCustomerDashboards/`). Universal constitutions remain at `.specify/memory/` root. The `{WorkbookName}` matches the Output folder name (PascalCase, no spaces).

### Stage 2: Read & Validate Universal Constitutions

Two universal constitutions exist — one for the semantic model, one for the report layer. Both are shared across ALL workbook migrations and NEVER overwritten per workbook.

**Actions:**
1. Read `.specify/memory/constitution.md` — universal migration principles (star schema, naming conventions, DAX standards, relationships, M query safety, PBIP structure, validation checklist)
2. Read `.specify/memory/report-constitution.md` — universal report visual rules (layout, typography, theme defaults, slicer standards, chart type mappings, border/title standards)
3. Validate that the current workbook's characteristics (from Stage 1) are compatible with the constitution rules:
   - Confirm data source type is covered (CSV, SQL Server, PostgreSQL, Excel, etc.)
   - Confirm naming convention can be applied (table/column names map cleanly)
   - Confirm relationship strategy matches (single-source → natural keys, multi-source → surrogate keys)
   - Confirm parameter types have mappings (integer → What-If, string → disconnected slicer, date → DimDate slicer)
4. If a rule cannot be applied (edge case not covered), append a note to the workbook-specific spec (Stage 4) — do NOT modify either constitution

**NEVER overwrite or regenerate `.specify/memory/constitution.md` or `.specify/memory/report-constitution.md`** — they are the shared authorities for all migrations in this workspace.

If the constitution file does not exist yet (first-time setup), create it using the universal template from `.specify/templates/constitution-template.md` with the standard Tableau→PBI migration principles. Once created, it remains unchanged for all subsequent workbook migrations.

If the report constitution does not exist yet, create it using `.github/skills/report-visual-generation/report-constitution-template.md`. Once created, it remains unchanged.

### Stage 3: Create Feature Branch & Directory

Run the speckit feature creation script to create a properly named branch and directory:

```powershell
cd "{REPO_ROOT}"
.\.specify\scripts\powershell\create-new-feature.ps1 -Json -ShortName "{workbook-short-name}-pbi" "Migrate {workbook_name} Tableau workbook to Power BI semantic model"
```

Parse the JSON output to get `BRANCH_NAME`, `SPEC_FILE`, `FEATURE_NUM`.

Then write `.specify/feature.json`:
```json
{
  "feature_directory": "specs/{BRANCH_NAME}"
}
```

This ensures ALL downstream speckit scripts (`check-prerequisites.ps1`, `setup-plan.ps1`) can find the feature directory.

**If `create-new-feature.ps1` fails** (e.g., branch already exists), use `-AllowExistingBranch`:
```powershell
.\.specify\scripts\powershell\create-new-feature.ps1 -Json -AllowExistingBranch -ShortName "{workbook-short-name}-pbi" "Migrate {workbook_name} Tableau workbook to Power BI semantic model"
```

**If git is unavailable**: Create `specs/{NNN}-{workbook-short-name}-pbi/` manually and write `feature.json`.

### Stage 4: Write Specification (via speckit.specify agent)

```
runSubagent(
  agentName: "speckit.specify",
  prompt: "Migrate '{workbook_name}' Tableau workbook to Power BI semantic model (.pbip). Source: {datasource_count} datasources ({connection_types}), {calc_field_count} calculated fields, {parameter_count} parameters. Source columns: {list key columns from analysis}. Calculated fields to migrate: {list from analysis}. Parameters to migrate: {list from analysis}. Data loading: {source_type} files from Data/{subfolder}/ folder. Output location: All PBIP artifacts will be saved to the Output/{workbook-subfolder}/ folder. Success criteria: PBIP opens in Power BI Desktop without errors, all tables load data, relationships resolve, measures calculate correctly. Constitution rules to follow: .specify/memory/constitution.md (star schema, naming, DAX standards, relationships, M query safety).",
  description: "Write migration specification"
)
```

This creates the workbook-specific `specs/{NNN}-{short-name}/spec.md` and updates `.specify/feature.json`.

### Stage 5: Clarification (via speckit.clarify agent)

```
runSubagent(
  agentName: "speckit.clarify",
  prompt: "Clarify the specification for the '{workbook_name}' Tableau → Power BI migration. Auto-resolve these common decisions based on the universal constitution (.specify/memory/constitution.md): Measure vs calculated column → Prefer measures (DAX best practice per constitution §3). Unclear joins → Use natural keys for single-source, surrogate keys for multi-source (constitution §4). Table calc patterns → Map to RANKX/OFFSET/visual calculations (constitution §3 mappings). Data categories → Apply geographic roles from Tableau semantic-roles. Multi-value fields → Bridge tables with natural keys (constitution §1). Rating/category grouping → Calculated column in dimension table. Append a ## Clarifications section with all decisions and rationale.",
  description: "Clarify migration spec"
)
```

### Stage 6: Generate DAX Measures (via dax-measures agent)

```
runSubagent(
  agentName: "dax-measures",
  prompt: "Generate DAX measures for the '{workbook_name}' Tableau → Power BI migration. Read .specify/memory/{WorkbookName}/tableau-analysis-output.md for all calculated fields to migrate. Read .specify/memory/constitution.md for DAX standards (§3). Follow .github/skills/dax-measures/SKILL.md for detailed instructions. Map each Tableau calculated field to equivalent DAX (measures, calculated columns, What-If parameters). Apply DAX best practices: DIVIDE(), COUNTROWS, VAR/RETURN, display folders. Handle patterns: simple aggregations → DAX measures; IF/CASE → IF()/SWITCH(TRUE()); table calculations (RANK, LOOKUP, WINDOW) → RANKX/OFFSET/MAXX; LOD expressions → CALCULATE with REMOVEFILTERS/VALUES; Parameters with range → What-If parameter (GENERATESERIES disconnected table); Parameters with list → Field parameter or slicer table. Also generate standard aggregate measures for the fact table (row counts, distinct counts, percentages using DIVIDE(), MIN/MAX/AVG for numeric fields). Save output to .specify/memory/{WorkbookName}/dax-measures-output.md.",
  description: "Generate DAX measures"
)
```

### Stage 7: Design Star Schema (via star-schema agent)

```
runSubagent(
  agentName: "star-schema",
  prompt: "Design a star schema for the '{workbook_name}' Tableau → Power BI migration. Read .specify/memory/{WorkbookName}/tableau-analysis-output.md for source tables, columns, relationships. Read .specify/memory/constitution.md for star schema rules (§1). Follow .github/skills/star-schema/SKILL.md for detailed instructions. Identify fact table grain (one row = ?). Identify dimension candidates (categorical/descriptive columns). Determine key strategy: single source → natural keys, multi-source/joins → keep existing table structure with join keys. Handle many-to-many fields (comma-separated) → Bridge tables. Always create DimDate if any date fields exist. Define all relationships (from/to table, from/to column, direction, cardinality). Save output to .specify/memory/{WorkbookName}/star-schema-output.md.",
  description: "Design star schema"
)
```

### Stage 8: Write Plan (via speckit.plan agent)

```
runSubagent(
  agentName: "speckit.plan",
  prompt: "Create an implementation plan for the '{workbook_name}' Tableau → Power BI migration. Technical context: Power BI PBIP format using TMDL, M queries for data loading, DAX measures. Constitution: Read .specify/memory/constitution.md for all design principles (this is the universal rulebook — do NOT modify it). Data source strategy: {source_type} → {M query pattern from constitution §5}. Design artifacts already generated: .specify/memory/{WorkbookName}/star-schema-output.md, .specify/memory/{WorkbookName}/dax-measures-output.md. Phase 0: Research — M query patterns for {source_type}, TMDL syntax. Phase 1: Design — star schema validation, DAX measure verification, relationship integrity. Phase 2: Implementation — PBIP file generation (definition.pbism, model.tmdl, table TMDL files, relationships.tmdl).",
  description: "Write implementation plan"
)
```

### Stage 9: Generate Tasks (via speckit.tasks agent)

```
runSubagent(
  agentName: "speckit.tasks",
  prompt: "Generate tasks for the '{workbook_name}' Tableau → Power BI migration. Context: Plan and spec are in the feature directory (read .specify/feature.json for path). Design artifacts: .specify/memory/{WorkbookName}/star-schema-output.md, .specify/memory/{WorkbookName}/dax-measures-output.md. Phase 1 Setup: Validate constitution compliance, confirm design artifacts exist. Phase 2 PBIP Generation: Generate {ModelName}.pbip, {ModelName}.Report/, {ModelName}.SemanticModel/ with all TMDL files. Phase 3 Validation: JSON parsing, M query safety, relationship integrity, PBIP schema compliance. All tasks must reference the universal constitution at .specify/memory/constitution.md as the rulebook (never modify it).",
  description: "Generate implementation tasks"
)
```

### Stage 10: Implement — Generate PBIP (via pbip-generator agent)

This is the **implementation stage** — equivalent to `speckit.implement`. All design is complete (spec, plan, tasks, DAX measures, star schema). Now generate the actual PBIP files.

```
runSubagent(
  agentName: "pbip-generator",
  prompt: "Generate a Power BI Project (.pbip) semantic model. Read .specify/memory/{WorkbookName}/star-schema-output.md for table structure and relationships. Read .specify/memory/{WorkbookName}/dax-measures-output.md for measures. Read .specify/memory/{WorkbookName}/tableau-analysis-output.md for source connection details. Read .specify/memory/constitution.md for naming conventions, M query rules, and PBIP structure requirements. Read plugins/pbip/skills/tmdl/SKILL.md for TMDL syntax rules. Create a valid .pbip folder structure that opens in Power BI Desktop without errors. Detect the absolute path to data files in the Data/ folder using the workspace root. IMPORTANT: Save ALL generated PBIP files to the Output/{WorkbookName}/ folder (Output/{WorkbookName}/{ModelName}.pbip, Output/{WorkbookName}/{ModelName}.Report/, Output/{WorkbookName}/{ModelName}.SemanticModel/). Include .platform files with correct metadata.type, metadata.displayName, and config.logicalId (GUID). definition.pbism version MUST be '4.2'. definition.pbir version MUST be '4.0'. .pbip MUST have $schema and MUST NOT have 'dataset' artifact.",
  description: "Generate PBIP semantic model"
)
```

### Stage 11: Validate Semantic Model (MANDATORY — run plugin validators)

> Validation rules derived from `plugins/pbip/hooks/validate-tmdl.sh`, `plugins/pbip/hooks/validate-pbir.sh`, and `plugins/pbip/hooks/validate-report-binding.sh`.

**MANDATORY: Run the actual plugin validators in the terminal:**

```powershell
# 1. TMDL structural syntax validator
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\{WorkbookName}\{ModelName}.SemanticModel\definition"

# 2. Cross-cutting PBIP project validator
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\{WorkbookName}"
```

**If either validator reports errors, FIX THEM before proceeding to Stage 12.**

Additional checks:
2. **TMDL structural validation (from plugin hooks):**
   - Indentation uses tabs (one tab per nesting level)
   - Object nesting: columns/measures inside table, levels inside hierarchy
   - Names quoted only when containing spaces/dots/equals/colons or starting with digit
   - `///` triple-slash immediately followed by declaration (no blank line between)
   - M expression names don't collide with table names
   - Every `ref table` in model.tmdl has a matching `tables/{Name}.tmdl` file
   - database.tmdl starts with just `database` (no name, no `createOrReplace`)
   - Measures use `measure 'Name' = <DAX>` syntax (not `expression = ...`)
3. **CRITICAL — Validate entry point file versions** (read each file and verify):
   - `definition.pbism` MUST contain `"version": "4.2"` and `"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"`. If version is `"1.0"`, PBI Desktop will look for `model.bim` instead of the `definition/` TMDL folder and fail with "Missing required artifact 'model.bim'". FIX IMMEDIATELY if wrong.
   - `definition.pbir` MUST contain `"version": "4.0"` and `"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"`.
   - `.pbip` MUST contain `"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"`.
4. **PBIR structural validation (from plugin hooks):**
   - All JSON files are valid (no syntax errors)
   - No spaces in folder names under `.Report/` (pages/visuals won't render)
   - All `$schema` URLs start with `https://developer.microsoft.com/json-schemas/fabric/item/report/definition/`
   - Visual/page names match `^[a-zA-Z0-9_][a-zA-Z0-9_-]*$`
   - report.json has: `$schema`, `themeCollection`, `settings.useStylableVisualContainerHeader: true`
   - If `themeCollection.baseTheme` is used, `reportVersionAtImport` MUST be an object (`{"visual":"1.8.95","report":"2.0.95","page":"1.3.95"}`), NEVER a string
   - definition.pbir `byPath` target directory exists
5. **Encoding validation:** ALL files must be UTF-8 WITHOUT BOM (PowerShell `Set-Content -Encoding UTF8` adds BOM — use `[System.IO.File]::WriteAllText()` with `UTF8Encoding($false)`)
6. Count tables, columns, measures, relationships
7. Report:
   - Pipeline stages completed (semantic model)
   - Feature branch name
   - Spec/plan/tasks location: `specs/{NNN}-{name}/`
   - PBIP files generated in `Output/{WorkbookName}/` folder

### Stage 12: Cross-Artifact Consistency Analysis (via speckit.analyze agent)

```
runSubagent(
  agentName: "speckit.analyze",
  prompt: "Cross-check spec, plan, and tasks for '{workbook_name}' — additionally validate star schema design (.specify/memory/{WorkbookName}/star-schema-output.md) vs DAX measures (.specify/memory/{WorkbookName}/dax-measures-output.md) vs generated TMDL files (Output/{WorkbookName}/{ModelName}.SemanticModel/definition/) for column mapping gaps, relationship mismatches, measure naming inconsistencies, and missing table references.",
  description: "Analyze cross-artifact consistency"
)
```

### Stage 13: Generate Report Visuals (via report-visual-migration agent)

This stage completes the **end-to-end pipeline** by migrating Tableau dashboard visuals into Power BI report visuals.

```
runSubagent(
  agentName: "report-visual-migration",
  prompt: "Run the full visual migration pipeline for the '{workbook_name}' workbook. CRITICAL: You MUST parse the actual .twb XML file at Data/{subfolder}/{workbook}.twb to extract mark types, field shelves (rows/cols), encodings (color/size/text/wedge-size), and dashboard zone positions. Do NOT rely solely on .specify/memory/{WorkbookName}/tableau-analysis-output.md — that file only has datasource metadata, NOT visual details. Use PowerShell [xml] parsing to read mark class, pane encodings, and dashboard zones. Save extraction to .specify/memory/{WorkbookName}/tableau-visuals-output.md BEFORE generating any visuals. Read .specify/memory/report-constitution.md for universal report layout rules (do NOT overwrite it — it is shared across all migrations). If the workbook has theme overrides, save them to .specify/memory/{WorkbookName}/theme-overrides.md. Read plugins/pbip/skills/pbir-format/SKILL.md for PBIR JSON schema rules. The semantic model TMDL files are at Output/{WorkbookName}/{ModelName}.SemanticModel/definition/ — use these for exact table/column/measure names. Generate the report in Output/{WorkbookName}/{ModelName}.Report/ using the Enhanced PBIR Folder Format. Execute ALL stages: visual extraction (parse TWB XML) → apply universal report constitution → specify → clarify → plan → tasks → implement (generate report visuals). VALIDATION: Every Tableau worksheet must have a corresponding Power BI visual with the CORRECT type (Line=lineChart, Pie=pieChart, Square+size=treemap, etc).",
  description: "Migrate report visuals"
)
```

### Stage 14: Final End-to-End Validation (MANDATORY — run plugin validators)

**MANDATORY: Run the actual plugin validators in the terminal after report generation:**

```powershell
# 1. TMDL structural syntax validator (re-run to confirm no regressions)
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\{WorkbookName}\{ModelName}.SemanticModel\definition"

# 2. Cross-cutting PBIP project validator (validates model + report)
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\{WorkbookName}"

# 3. JSON syntax check on all report files
Get-ChildItem "Output\{WorkbookName}\{ModelName}.Report" -Recurse -Include "*.json","*.pbir" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }
```

**If ANY validator reports errors, FIX THEM before presenting output to user.**

1. Verify BOTH semantic model AND report artifacts exist in `Output/{WorkbookName}/`
2. Confirm report `definition.pbir` points to correct SemanticModel path
3. **Validate ALL JSON entry point files have mandatory `$schema`** (read and verify each):
   - `.pbip` → must have `$schema`
   - `definition.pbir` → must have `$schema`, version `"4.0"`
   - `definition.pbism` → must have `$schema`, version `"4.2"`
   - `definition/version.json` → must have `$schema` (`versionMetadata/1.0.0`), version `"2.0.0"`
   - `definition/pages/pages.json` → must have `$schema`
   - `definition/pages/{page}/page.json` → must have `$schema`
   - Each `visual.json` → must have `$schema`
   If ANY file is missing `$schema`, fix it immediately before reporting success.
4. Validate all visual `queryRef` values match actual model tables/columns/measures
5. Report:
   - ALL pipeline stages completed (semantic model + report)
   - PBIP files generated in `Output/{WorkbookName}/` folder
   - How to open: "Open `Output/{WorkbookName}/{Name}.pbip` in Power BI Desktop"
   - Summary: {N} tables, {N} measures, {N} relationships, {N} report pages, {N} visuals

## Error Recovery

| Failure | Recovery |
|---------|----------|
| `create-new-feature.ps1` fails | Use `-AllowExistingBranch`, or create dirs manually |
| `setup-plan.ps1` fails | Read `feature.json` → write plan to that dir |
| `check-prerequisites.ps1` fails | Read `feature.json` → use that path |
| Subagent returns incomplete output | Re-invoke the same agent with more specific prompt |
| Validator reports errors | Fix errors in generated files, then re-run validator |
| Git unavailable | Skip branch, create `specs/{workbook}-pbi/` directly |
| Data file not found | Use workspace-relative path detection via `list_dir` |

## Notes

- Full pipeline is AUTOMATIC — all 14 stages execute in sequence without user interaction
- **⚠️ ALL 9 designated agents MUST be called via the `runSubagent` TOOL** — this is the single most important rule of this agent
- **NEVER do an agent's work inline** — if a stage has a designated agent listed above, you MUST invoke `runSubagent` with that agent name
- **NEVER skip a `runSubagent` call** because you think you can do it faster or the work is simple
- **NEVER fall back to inline execution** — if `runSubagent()` fails, retry or report the error; do NOT replicate the agent's work yourself
- **Format**: Every `runSubagent` call needs: `agentName` (exact string), `prompt` (detailed with all file paths and context), `description` (2-5 words)
- **ALL validators MUST be executed** — `tmdl-validate-windows-x64.exe` and `validate_pbip.py` are run in the terminal at Stage 11 and Stage 14
- **End-to-end**: Produces BOTH semantic model (TMDL) AND report visuals (PBIR) in a single invocation
- **Input**: Tableau workbooks and data files are read from the `Data/` folder (organized in subfolders per workbook)
- **Output**: All PBIP artifacts (model + report) are generated in the `Output/{WorkbookName}/` folder (one subfolder per workbook)
- **Follows speckit workflow**: Spec (4-5) → Design (6-7) → Plan (8) → Tasks (9) → Implement/PBIP (10) → Validate (11) → Analyze (12) → Report Visuals (13) → Final Validate (14)
- **Constitution is UNIVERSAL** — `.specify/memory/constitution.md` is shared across ALL workbook migrations, never overwritten per workbook
- **Spec/Plan/Tasks are WORKBOOK-SPECIFIC** — each workbook gets its own `specs/{NNN}-{name}/` directory via speckit agents
- PBIP generation (Stage 10) is the **implementation step** — only runs after spec, plan, and tasks are complete
- Cross-artifact analysis (Stage 12) validates consistency between spec/plan/tasks and generated artifacts
- Report visual generation (Stage 13) runs AFTER the semantic model is validated — uses TMDL files for data bindings
- DAX measures + star schema are **design artifacts** generated between spec and plan to inform the implementation plan
- Scripts always run from repo root directory
- M queries in TMDL must reference data file absolute paths from the `Data/{subfolder}/` directory
- Ref: https://learn.microsoft.com/en-us/power-bi/guidance/
