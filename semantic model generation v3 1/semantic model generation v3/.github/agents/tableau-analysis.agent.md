---
description: Analyze any Tableau workbook (.twb/.twbx) file in the workspace to extract metadata. After analysis, hands off to migration-constitution agent which runs the full end-to-end pipeline for Power BI project generation (semantic model + report visuals).

handoffs:
  - label: Generate Full Power BI Project (Model + Report)
    agent: migration-constitution
    prompt: "Run the full end-to-end migration pipeline: read universal constitution → feature branch → specify → clarify → DAX → star-schema → plan → tasks → PBIP generation → report visual migration. The constitution at .specify/memory/constitution.md is a shared rulebook — read it, do NOT regenerate it. The report constitution at .specify/memory/report-constitution.md is also universal — read it, do NOT regenerate it. Read workbook analysis from .specify/memory/{WorkbookName}/tableau-analysis-output.md. Generate BOTH semantic model AND report visuals."
  - label: Migrate Visuals Only (if model already exists)
    agent: report-visual-migration
    prompt: "Run the full visual migration pipeline: extract visuals → read universal report constitution → specify → clarify → plan → tasks → generate report visuals. Read analysis from .specify/memory/{WorkbookName}/tableau-analysis-output.md. Read universal report rules from .specify/memory/report-constitution.md (do NOT overwrite)."
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Skill Reference

Read `.github/skills/tableau-analysis/SKILL.md` before proceeding.

## Steps

### 1. Locate Tableau Files

- Use `file_search` with `Data/**/*.twb` and `Data/**/*.twbx` to find workbooks in the Data folder
- If user specified a file, use that directly
- The `Data/` folder contains subfolders per workbook (e.g., `Data/Netflix/`, `Data/Loan/`, `Data/Q3 Buyer/`)
- Each subfolder has the `.twb` file and its associated data files (CSV, Excel, etc.)

### 2. Parse the Workbook (XML)

Read the `.twb` in sections and extract:
- First ~100 lines → workbook version, platform, build
- `<datasource name='Parameters'>` → parameters (name, datatype, range, default)
- Each `<datasource>` → caption, connection type, source files, tables
- `<column>` elements → caption, name, datatype, role (dimension/measure), type, semantic-role
- `<column>` with nested `<calculation>` → calculated fields (caption, formula, table-calc settings)
- `<worksheet name='...'>` → worksheet names + **visual metadata** (see Step 2b)
- `<dashboard name='...'>` → dashboard names + **zone layout** (see Step 2c)
- `<relation type='join'>` or `<relation type='collection'>` → relationships/joins

### 2b. Extract Visual Metadata Per Worksheet (MANDATORY)

**CRITICAL**: For each `<worksheet>`, extract the visual encoding details from `<table><panes><pane>`:

1. **Mark Type**: `<mark class='...'>` → Bar, Line, Pie, Square, Area, Circle, Text, Map, Automatic
2. **Field Shelves**:
   - `<rows>` → fields on Y-axis (vertical)
   - `<cols>` → fields on X-axis (horizontal)
3. **Encodings** from `<pane><encodings>`:
   - `<color column='...'>` → color/legend field
   - `<size column='...'>` → size field
   - `<text column='...'>` → data label field
   - `<wedge-size column='...'>` → pie slice measure
4. **Hierarchy detection**: If `<rows>` contains `/` separators (e.g., `region / subregion / state`), note the drill path

Output this as a **Worksheet Visual Details** table in the analysis:
```markdown
## Worksheet Visual Details
| Worksheet | Mark Type | Rows (Y-axis) | Cols (X-axis) | Color | Size | Text/Label |
|-----------|-----------|---------------|---------------|-------|------|------------|
| {name} | {mark_class} | {fields} | {fields} | {field} | {field} | {field} |
```

**Automatic mark inference**: When `mark class="Automatic"`, infer:
- Color + Size on same measure + text on dimension → Treemap
- Date on cols + measure on rows → Line chart
- Single measure, no dimensions → Card/KPI
- Dimensions on rows only + measures on text → Table
- Dimension on one axis + measure on other → Bar/Column chart

### 2c. Extract Dashboard Zone Layout (MANDATORY)

**CRITICAL**: For each `<dashboard>`, extract position data from `<zones><zone>`:

1. **Dashboard size**: `<size maxwidth='...' maxheight='...'>`
2. **Zone positions**: For each zone with `type='viz'`, `type='filter'`, or `type='paramctrl'`:
   - `name` → which worksheet is embedded
   - `x`, `y`, `w`, `h` → pixel position and size
   - `type` → viz (chart), filter (slicer), paramctrl (parameter)
3. **Navigation buttons**: For each zone with `type-v2='dashboard-object'` containing a `<button>` child:
   - `action` attribute → `tabdoc:goto-sheet window-id="..."` means page navigation
   - `<toggle-action>` child → show/hide toggle (e.g., filter panel visibility)
   - `<button-visual-state>` → tooltip text, image path
   - `x`, `y`, `w`, `h` → button position and size
   - Parent container `friendly-name` (e.g., "Horizontal Cont. (Button)") → button group layout

Output as:
```markdown
## Dashboard Layout: {dashboard_name}
- **Size**: {width} × {height} px

| Zone | Type | Worksheet/Filter | x | y | w | h |
|------|------|-----------------|---|---|---|---|
| 1 | viz | {worksheet_name} | {x} | {y} | {w} | {h} |
| 2 | filter | {filter_field} | {x} | {y} | {w} | {h} |

### Navigation Buttons
| Button | Action | Tooltip | Target | x | y | w | h |
|--------|--------|---------|--------|---|---|---|---|
| 1 | goto-sheet | {tooltip_text} | {target_dashboard_name} | {x} | {y} | {w} | {h} |
| 2 | toggle | {tooltip_text} | show/hide {target_zones} | {x} | {y} | {w} | {h} |
```

**Button Action Types**:
- `tabdoc:goto-sheet window-id="..."` → Page navigation button (maps to Power BI page navigation action)
- `<toggle-action>tabdoc:toggle-button-click-action...</toggle-action>` → Toggle visibility (maps to Power BI bookmark + button)
- Resolve `window-id` to the target dashboard name by matching against `<window class='dashboard' name='...'>`

This data is **essential** for the report-visual-migration agent to generate correctly-typed and correctly-positioned visuals.

### 2d. Extract Sets, Groups, Bins, Blending & Formats (MANDATORY)

These constructs drive downstream DAX and MUST be captured (write `None` when absent — never fabricate):

1. **Sets** — `<group name='[... Set]'>` with `<groupfilter>` children. Record set name, source field, type (Fixed list vs Computed/top-N), and members/condition.
2. **Groups** — `<group name='[... (group)]'>` or `<calculation class='categorical-bin'>`. Record group field, source dimension, and each alias → member values.
3. **Bins** — `<column>` with `<calculation class='bin' decimal-bin-size='...'>`. Record bin field, source field, bin size.
4. **Data Blending** — Count real `<datasource>` elements (excluding `Parameters`). If more than one and worksheets reference fields across them (or `<datasource-dependencies>` exist), record primary + secondary datasources and the linking field(s). If only one, write `Single datasource — no blending`.
5. **Field Formatting** — Capture each field's display format string verbatim (e.g. `$#,##0`, `0.0%`, `mmmm yyyy`, `[h]:mm:ss`). Write `Default` when none.

Output as:
```markdown
## Sets
| Set Name | Source Field | Type | Members / Condition |
|----------|--------------|------|---------------------|

## Groups
| Group Field | Source Dimension | Alias | Member Values |
|-------------|------------------|-------|---------------|

## Bins
| Bin Field | Source Field | Bin Size |
|-----------|--------------|----------|

## Data Blending
| Primary Datasource | Secondary Datasource | Linking Field(s) |
|--------------------|----------------------|------------------|

## Field Formatting
| Field | Tableau Format String | Kind |
|-------|-----------------------|------|
```

### 3. Decode XML Entities

- `&quot;` → `"`, `&gt;` → `>`, `&lt;` → `<`, `&amp;` → `&`, `&#13;&#10;` → newline

### 4. Identify Data Source Type

Determine the connection type for each datasource:
- `class='textclean'` or `class='textscan'` → CSV file
- `class='excel-direct'` or `class='excel'` → Excel file
- `class='sqlserver'` → SQL Server
- `class='postgres'` → PostgreSQL
- `class='mysql'` → MySQL
- `class='oracle'` → Oracle
- `class='snowflake'` → Snowflake
- `class='databricks'` → Databricks
- `class='bigquery'` → BigQuery

Record the connection class, server, database, schema, and table names for each datasource.

### 5. Save Analysis Output

**MANDATORY**: Save extracted metadata to `.specify/memory/{WorkbookName}/tableau-analysis-output.md` in structured markdown.

> **Memory Scoping**: `{WorkbookName}` is the PascalCase output folder name (e.g., `SalesCustomerDashboards`, `NetflixAnalysis`). Create the directory `.specify/memory/{WorkbookName}/` if it does not exist before saving.

Include a **Data Source Summary** section:
```markdown
## Data Source Summary
| Datasource | Connection Type | Source Details |
|-----------|----------------|----------------|
| {name} | CSV / SQL Server / etc. | file path or server/database/table |
```

### 6. Present Results

Output structured markdown:
```
# Tableau Workbook Analysis: {filename}
## Workbook Info
## Parameters
## Data Source Summary
## Datasources
### {name} — Dimensions | Measures
## Calculated Fields
## Worksheet Visual Details    ← NEW (mark types, field shelves, encodings)
## Dashboard Layout             ← NEW (zone positions, sizes)
## Navigation Buttons           ← NEW (goto-sheet, toggle buttons per dashboard)
## Sets / Groups / Bins         ← NEW (None when absent)
## Data Blending                ← NEW (Single datasource when one source)
## Field Formatting             ← NEW (Tableau format strings)
## Worksheets
## Dashboards
## Relationships
```

### 7. Hand Off to Migration Constitution Agent

**AUTOMATICALLY** invoke `runSubagent` — use EXACTLY this format:

```
runSubagent(
  agentName: "migration-constitution",
  prompt: "Run the full end-to-end migration pipeline using the analysis saved at .specify/memory/{WorkbookName}/tableau-analysis-output.md. Execute ALL 14 stages: constitution → feature branch → specify → clarify → DAX measures → star schema → plan → tasks → PBIP generation → validate → analyze → report visual migration → final validate. This is an end-to-end pipeline — generate BOTH the semantic model AND the report visuals automatically. MANDATORY: You MUST call the `runSubagent` tool 9 times — once for each designated agent (speckit.specify, speckit.clarify, dax-measures, star-schema, speckit.plan, speckit.tasks, pbip-generator, speckit.analyze, report-visual-migration). Do NOT write specs, DAX, schemas, plans, tasks, TMDL, or reports yourself — delegate ALL generation work to the designated agents via runSubagent tool calls. Memory files are scoped: workbook-specific artifacts in .specify/memory/{WorkbookName}/, universal constitutions (constitution.md, report-constitution.md) at .specify/memory/ root.",
  description: "Run full migration pipeline"
)
```

**CRITICAL**: This MUST be a real `runSubagent()` tool call — not a description of what to do. The migration-constitution agent handles all 14 stages internally, calling 9 sub-agents via `runSubagent()`.

**If runSubagent fails** (tool access issue), present the handoff button so the user can continue manually with the `migration-constitution` agent.

## Important Notes

- Generic — works with ANY `.twb`/`.twbx`, never hardcode file names
- **Input source**: Always look for workbooks in the `Data/` folder (organized in subfolders per workbook)
- **Data files** (CSV, Excel, etc.) are co-located with the `.twb` in the same subfolder under `Data/`
- Always identify connection type for proper M query generation downstream
- For `.twbx` files (ZIP), extract the `.twb` inside first
- Tableau brackets: `[field_name]`, internal calcs: `[Calculation_XXXX]`
- Cross-datasource: `[datasource_id].[field_name]`
- Parameters datasource named `'Parameters'` — list separately
- The handoff to migration-constitution is AUTOMATIC — do not skip or ask

## Anti-Hallucination Guardrails

- **Extract only what the XML contains.** Never invent tables, fields, calculated fields, sets, groups, bins, or relationships. Every item must trace to a concrete element.
- **Write `None` for empty categories** instead of fabricating plausible entries.
- **Copy formulas and format strings verbatim** (after entity decoding) — do not rewrite or guess them.
- **Label ambiguous items `UNVERIFIED`** rather than filling gaps with assumptions.
- **Do not perform downstream work** (DAX, schema design, visuals) in this agent — only extract metadata, then hand off.
