<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/002-q3-dealer-buying-pbi/plan.md
<!-- SPECKIT END -->

# Tableau → Power BI Semantic Model Migration Pipeline

## Overview

This workspace contains an automated end-to-end agentic pipeline that converts any Tableau workbook (.twb) into a complete Power BI project (.pbip) — including both the semantic model AND report visuals. When a user places a Tableau workbook in the workspace and runs the `tableau-analysis` agent, the full pipeline executes automatically.

## Pipeline Flow

```
tableau-analysis → migration-constitution (orchestrates ALL remaining stages internally, including report generation)
```

The `migration-constitution` agent is a self-contained orchestrator that runs all 14 stages:
1. Read analysis context
2. Generate/read constitution
3. Create feature branch & speckit directory
4. Write specification (via `speckit.specify` subagent)
5. Clarify ambiguities (via `speckit.clarify` subagent)
6. Generate DAX measures (via `dax-measures` subagent)
7. Design star schema (via `star-schema` subagent)
8. Write plan (via `speckit.plan` subagent)
9. Write tasks (via `speckit.tasks` subagent)
10. Generate PBIP semantic model (via `pbip-generator` subagent) — **read `plugins/pbip/skills/tmdl/SKILL.md` for syntax rules**
11. Validate semantic model artifacts — **run `tmdl-validate` + `validate_pbip.py` from `plugins/pbip/`**
12. Cross-artifact consistency analysis (via `speckit.analyze` subagent)
13. **Generate report visuals** (via `report-visual-migration` subagent) — **read `plugins/pbip/skills/pbir-format/SKILL.md` for schema rules**
14. Final end-to-end validation (model + report) — **run `validate_pbip.py` on project root, fix any errors**

### Entry Point: `tableau-analysis`
- Discovers and parses `.twb` file from the `Data/` folder (organized in subfolders)
- Extracts: datasources, columns, calculated fields, parameters, worksheets, dashboards
- Detects source type (CSV, SQL Server, PostgreSQL, Excel, etc.)
- Saves output to `.specify/memory/tableau-analysis-output.md`
- Hands off to `migration-constitution`

### Orchestrator: `migration-constitution`
- Runs ALL stages automatically without user interaction
- **ALL designated agents MUST be called via `runSubagent()` — NEVER do an agent's work inline**
- Creates speckit feature branch + `feature.json` for path resolution
- Calls 9 subagents via `runSubagent()`: speckit.specify, speckit.clarify, dax-measures, star-schema, speckit.plan, speckit.tasks, pbip-generator, speckit.analyze, report-visual-migration
- Saves all generated PBIP artifacts to the `Output/{WorkbookName}/` folder
- **Reads plugin skills** (`plugins/pbip/skills/tmdl/SKILL.md`, `plugins/pbip/skills/pbir-format/SKILL.md`) before generating files
- **Runs plugin validators** (`tmdl-validate`, `validate_pbip.py`) after generation — errors must be fixed before presenting output to user
- Validates all generated artifacts (both model and report)

### Supporting Agents (called by orchestrator):
- `dax-measures` — Generates DAX from Tableau calculated fields
- `star-schema` — Designs fact/dimension tables and relationships
- `pbip-generator` — Generates the .pbip folder structure (semantic model)
- `report-visual-migration` — Extracts Tableau visuals and generates Power BI report pages

## Supported Source Types

| Source | Detection | M Query Pattern |
|--------|-----------|-----------------|
| CSV | `textclean`/`textscan` class | `Csv.Document(File.Contents(...))` |
| SQL Server | `sqlserver` class | `Sql.Database(...)` |
| PostgreSQL | `postgres` class | `PostgreSQL.Database(...)` |
| Excel | `excel-direct` class | `Excel.Workbook(File.Contents(...))` |
| MySQL | `mysql` class | `MySQL.Database(...)` |
| Generic ODBC | other | `Odbc.DataSource(...)` |

## Folder Convention

| Folder | Purpose |
|--------|---------|
| `Data/` | **Input folder** — Place Tableau workbooks (`.twb`/`.twbx`) and their data files (CSV, Excel) here, organized in subfolders per workbook |
| `Output/` | **Output folder** — All generated PBIP artifacts (`.pbip`, `.Report/`, `.SemanticModel/`) are saved here, organized in subfolders per workbook |

### Data Folder Structure
```
Data/
├── {Workbook1}/
│   ├── {workbook}.twb
│   ├── data1.csv
│   └── data2.csv
├── {Workbook2}/
│   ├── {workbook}.twb
│   └── data.csv
```

### Output Folder Structure
```
Output/
├── {WorkbookName}/
│   ├── {ModelName}.pbip
│   ├── {ModelName}.Report/
│   │   ├── definition.pbir
│   │   └── report.json
│   ├── {ModelName}.SemanticModel/
│   │   ├── definition.pbism
│   │   ├── diagramLayout.json
│   │   └── definition/
│   │       ├── database.tmdl
│   │       ├── model.tmdl
│   │       ├── relationships.tmdl
│   │       └── tables/
```

### Memory Folder Structure (`.specify/memory/`)
```
.specify/memory/
├── constitution.md                          ← UNIVERSAL (never overwritten per workbook)
├── report-constitution.md                   ← UNIVERSAL (never overwritten per workbook)
├── {WorkbookName}/                          ← Per-workbook scoped artifacts
│   ├── tableau-analysis-output.md
│   ├── dax-measures-output.md
│   ├── star-schema-output.md
│   ├── tableau-visuals-output.md
│   └── theme-overrides.md (optional)
```

**Memory Scoping Rules:**
- `constitution.md` and `report-constitution.md` are **universal** — shared across ALL workbook migrations, NEVER overwritten per workbook
- All other memory artifacts (analysis, DAX, star schema, visuals) are **workbook-scoped** — stored in `.specify/memory/{WorkbookName}/`
- `{WorkbookName}` is the PascalCase output folder name (e.g., `SalesCustomerDashboards`, `NetflixAnalysis`)

## How to Use

1. Place any `.twb` file (with its data files) in a subfolder under `Data/`
2. Invoke the `tableau-analysis` agent (or ask "analyze the Tableau workbook")
3. The full pipeline runs automatically — no manual steps needed
4. Result: a complete `.pbip` semantic model saved to `Output/{WorkbookName}/` folder, ready for Power BI Desktop

## Speckit Integration

- Feature branch: Created via `.specify/scripts/powershell/create-new-feature.ps1`
- Feature tracking: `.specify/feature.json` enables path resolution for all scripts
- Artifacts in `specs/{branch-name}/`: spec.md, plan.md, tasks.md
- Memory artifacts in `.specify/memory/`: analysis, constitution, DAX, star schema

---

## Visual Migration Pipeline (Report Layer)

After the semantic model is generated, the report visual migration runs **automatically** as part of the same pipeline (Stage 12). It can also be invoked separately if only the report layer needs regeneration.

### Pipeline Flow

```
report-visual-migration (orchestrates ALL stages internally)
```

The `report-visual-migration` agent runs 8 stages:
1. Extract Tableau visual metadata (chart types, positions, encodings, filters)
2. Generate report constitution (layout rules, theme, typography, alignment)
3. Write visual specification (Power BI visual types, positions, data bindings)
4. Clarify ambiguities (chart type alternatives, layout adaptations)
5. Write implementation plan
6. Write tasks
7. Implement — generate `report.json` with full `visualContainers`
8. Validate (JSON structure, data bindings, layout rules)

### Entry Point: `report-visual-migration`
- Called automatically by `migration-constitution` (Stage 12), OR can be invoked manually
- Reads `.twb` file from `Data/` folder to extract worksheets/dashboards visual metadata
- Saves visual extraction to `.specify/memory/tableau-visuals-output.md`
- Generates report constitution at `.specify/memory/report-constitution.md`
- Produces final report with pre-built visuals in `Output/{WorkbookName}/`

### Report Constitution Rules (Default)
- **Edge Padding**: 25px from top and sides
- **Inter-Visual Gap**: 20px between visuals
- **Font**: Aptos, 10pt for data
- **Theme**: Professional (white/light gray, subtle borders)
- **Table Alignment**: Numbers LEFT, Text RIGHT, Dates LEFT
- **Data Format**: Preserve source format from Tableau

### Skills Used (decomposed into focused single-responsibility skills):

**Routers:**
- `.github/skills/tableau-visual-extraction/SKILL.md` — extraction router (parse TWB visual XML)
- `.github/skills/report-visual-generation/SKILL.md` — generation router (generate Power BI report)
- `.github/skills/report-visual-generation/report-constitution-template.md` — formatting rule defaults

**Focused extraction skills:** `tableau-mark-mapping`, `tableau-worksheet-extraction`, `tableau-dashboard-extraction`, `tableau-format-translation`
**Focused generation skills:** `report-theme-colors`, `report-layout-gapping`, `report-borders-titles`, `report-slicers`, `report-visual-json`, `report-navigation-buttons`, `report-pbir-folder-format`, `report-load-failure-rules` (all under `.github/skills/`)

### How to Use (Standalone — if only report needs regeneration)

1. Ensure a semantic model (.pbip) already exists in `Output/{WorkbookName}/` for the workbook
2. Invoke the `report-visual-migration` agent (or ask "migrate visuals from Tableau to Power BI")
3. The pipeline extracts visuals, applies formatting rules, and generates report.json
4. Result: a complete `.Report/report.json` in `Output/{WorkbookName}/` with visuals ready for Power BI Desktop

> **Note**: When using the full pipeline via `tableau-analysis`, report generation happens automatically — no separate invocation needed.

---

---

## Validation via Plugins (MANDATORY)

After generating or editing any PBIP artifacts, run the validation tools from the `plugins/` folder **before** presenting the output to the user. This catches schema violations, TMDL syntax errors, broken references, and report binding issues that would otherwise only surface when opening in Power BI Desktop.

### Plugin Folder Layout

```
plugins/
├── pbip/                              # Project-level validation
│   ├── hooks/bin/tmdl-validate-windows-x64.exe  # TMDL structural linter
│   ├── skills/pbip/scripts/validate_pbip.py     # Cross-cutting PBIP validator
│   ├── skills/tmdl/SKILL.md                     # TMDL authoring rules
│   ├── skills/pbir-format/SKILL.md              # PBIR JSON format reference
│   └── skills/pbir-format/references/           # Schema patterns, visual-json, page, report
├── reports/                           # Report-specific skills
│   ├── skills/create-pbi-report/      # Report creation patterns
│   ├── skills/review-report/          # Report design review
│   └── skills/pbi-report-design/      # Layout, spacing, accessibility
└── semantic-models/                   # Semantic model skills
    ├── skills/dax/                    # DAX best practices
    ├── skills/power-query/            # M query patterns
    ├── skills/review-semantic-model/  # Model audit rules
    └── skills/standardize-naming-conventions/  # Naming standards
```

### When to Validate

Run validation at these pipeline stages:
- **Stage 10** (after PBIP semantic model generation) → TMDL validation + `validate_pbip.py`
- **Stage 11** (semantic model validation) → full `validate_pbip.py` on the `.SemanticModel/` folder
- **Stage 12** (after report generation) → PBIR JSON validation + `validate_pbip.py` on `.Report/`
- **Stage 13** (end-to-end) → full `validate_pbip.py` on the project root
- **After any inline fix** (e.g., fixing measures, editing M queries) → re-run relevant validator

### Validation Commands (run in terminal)

#### 1. TMDL Structural Syntax (all .tmdl files)
```powershell
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\{WorkbookName}\{Name}.SemanticModel\definition"
```
Checks: indentation, property ordering, quoting, nesting rules, referential integrity.

#### 2. Cross-Cutting PBIP Validator (project structure)
```powershell
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\{WorkbookName}"
```
Checks: `.pbip` root, `.platform` files, `definition.pbir` binding (byPath target exists), page name regex, orphan pages, theme resource resolution, semantic model format detection.

Exit codes: 0=clean, 1=warnings, 2=errors, 3=usage error.

#### 3. Report JSON Syntax (quick check — all JSON in .Report/)
```powershell
Get-ChildItem "Output\{WorkbookName}\{Name}.Report" -Recurse -Include "*.json","*.pbir" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }
```

### Validation Skills to Read (for format rules)

Before generating TMDL or PBIR files, read the relevant skill for format rules:

| Task | Skill to load |
|------|---------------|
| Writing/editing `.tmdl` files | `plugins/pbip/skills/tmdl/SKILL.md` |
| Writing/editing PBIR JSON (visual.json, page.json, report.json) | `plugins/pbip/skills/pbir-format/SKILL.md` |
| PBIP project structure (definition.pbir, .pbip, .platform) | `plugins/pbip/skills/pbip/SKILL.md` |
| Report design review | `plugins/reports/skills/review-report/` |
| Semantic model review (DAX, naming) | `plugins/semantic-models/skills/review-semantic-model/` |

### Error Handling

- If `validate_pbip.py` returns exit code 2 (errors), **fix the errors before proceeding** to the next stage
- If `tmdl-validate` reports syntax issues, fix indentation/property order before continuing
- If JSON validation fails, correct the malformed file immediately
- Log all validation findings in `pipeline-state.json` under `validation_results`

### Key Validation Rules (Quick Reference)

From `plugins/pbip/skills/tmdl/SKILL.md`:
- `///` (triple-slash) sets Description; must immediately precede a declaration
- Indentation is semantic (tabs, one per level)
- Only quote names with spaces, special chars, or starting with digits
- CALCULATE boolean filters must NOT use measure references directly — use VAR pattern

From `plugins/pbip/skills/pbir-format/SKILL.md`:
- `visualContainer/2.4.0` schema: `$schema`, `name`, `position` + (`visual` | `visualGroup`) — **NO OTHER top-level properties allowed**
- **NEVER add `filters`, `filterConfig`, or any other property at the visual.json root** — PBI Desktop rejects them with "Property has not been defined and the schema does not allow additional properties"
- For Top N / measure-based filtering, rely on DAX logic (e.g., `IF([Rank] <= SELECTEDVALUE(...), 1, 0)`) and let users add visual filters in Desktop UI
- `visualContainerObjects.title` only allows: `show`, `text` (NOT color/fontSize)
- Color format: `{"solid": {"color": {"expr": {"Literal": {"Value": "'#RRGGBB'"}}}}}`
- Boolean format: `{"expr": {"Literal": {"Value": "true"}}}`
- Page names must match `^[\w-]+$` (no spaces, dots, or special punctuation)

From `plugins/pbip/hooks/README.md`:
- Required fields: `visual.json` needs `$schema`, `name`, `position` + `visual`/`visualGroup`
- Required fields: `page.json` needs `$schema`, `name`, `displayName`, `displayOption`
- Required fields: `report.json` needs `$schema`, `themeCollection`
- Required fields: `definition.pbir` needs `$schema`, `version`, `datasetReference`

---

## Subagent Execution Rules (MANDATORY)

**ALL designated agents MUST be called via `runSubagent()` — NEVER skip an agent or do its work inline.**

**⚠️ THIS IS THE #1 MOST VIOLATED RULE — READ CAREFULLY:**
- The `migration-constitution` agent MUST call the `runSubagent` tool 9 times (once per designated agent)
- Writing spec/plan/tasks/DAX/schema/PBIP content directly is FORBIDDEN — these are the agents' jobs
- If you find yourself writing a spec, measures, schema, plan, tasks, TMDL, or report visuals inline, STOP — you are violating this rule
- The ONLY work `migration-constitution` does itself is: reading files, running validators in terminal, and calling `runSubagent`

### Required Format

Every subagent call MUST use the `runSubagent` tool with these parameters:
- `agentName`: exact agent name string (e.g., `"speckit.specify"`)
- `prompt`: detailed instructions with ALL file paths and context the agent needs
- `description`: 2-5 word summary

### Designated Subagents (9 total, called by migration-constitution)

| Stage | Agent | Purpose |
|-------|-------|---------|
| 4 | `speckit.specify` | Write migration specification |
| 5 | `speckit.clarify` | Clarify migration spec |
| 6 | `dax-measures` | Generate DAX measures |
| 7 | `star-schema` | Design star schema |
| 8 | `speckit.plan` | Write implementation plan |
| 9 | `speckit.tasks` | Generate implementation tasks |
| 10 | `pbip-generator` | Generate PBIP semantic model |
| 12 | `speckit.analyze` | Cross-artifact consistency analysis |
| 13 | `report-visual-migration` | Migrate report visuals |

### Entry Point Handoff

| Agent | Calls | Purpose |
|-------|-------|---------|
| `tableau-analysis` | `migration-constitution` | Hand off after TWB analysis |

### Rules

1. **NEVER do an agent's work inline** — if a stage has a designated agent, you MUST call it via `runSubagent()`
2. **NEVER fall back to inline execution** — if `runSubagent()` fails, retry or report the error; do NOT replicate the agent's work yourself
3. **Prompt must be self-contained** — include all file paths, context references, and success criteria in the prompt
4. **Description must be 2-5 words** — concise summary for logging
5. **No inline alternatives** — there is no "or inline" option; subagent calls are the ONLY path

---

## Key References

- Power BI Guidance: https://learn.microsoft.com/en-us/power-bi/guidance/
- Star Schema: https://learn.microsoft.com/en-us/power-bi/guidance/star-schema
- DAX Best Practices: https://maqsoftware.com/insights/dax-best-practices
- PBIP Format: https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset
- Relationships: https://learn.microsoft.com/en-us/power-bi/guidance/relationships-active-inactive
- Report JSON Schema: https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
