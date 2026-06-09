---
description: Generate a Power BI Project (.pbip) semantic model folder structure using TMDL format. Creates all necessary files (definition.pbism, model.bim or TMDL definition folder) that can be opened in Power BI Desktop without errors.
---

## User Input

```text
$ARGUMENTS
```

## Skill References

Read these before proceeding. The generation guide is decomposed into focused skills so no rule is skipped.

**Router + focused generation skills:**
- `.github/skills/pbip-generator/SKILL.md` — generation router (which focused skill to read per task)
- `.github/skills/pbip-structure/SKILL.md` — PBIP folder + entry files (.pbip / .pbir / .pbism / report.json)
- `.github/skills/pbip-tmdl-syntax/SKILL.md` — TMDL syntax, indentation, measure-line rule, quoting, nesting
- `.github/skills/pbip-star-schema-keys/SKILL.md` — natural-key star schema + many-to-many bridge patterns
- `.github/skills/pbip-m-queries/SKILL.md` — M query templates per source + M safety rules
- `.github/skills/pbip-validation/SKILL.md` — validation rules (schema, model integrity, M, plugin validators)

**Plugin references (validation + deeper format detail):**
- `plugins/pbip/skills/tmdl/SKILL.md` — TMDL syntax, indentation, quoting, nesting rules
- `plugins/pbip/skills/pbip/SKILL.md` — PBIP project structure, encoding, thick vs thin
- `plugins/pbip/skills/pbir-format/SKILL.md` — PBIR JSON format reference (for Report/ folder)

## Steps

### 1. Read Context

- Read `.github/skills/pbip-generator/SKILL.md` (router) and the focused skill for each step
- Read `.specify/memory/star-schema-output.md` for table structure and relationships
- Read `.specify/memory/dax-measures-output.md` for measures and calculated columns
- Read `.specify/memory/tableau-analysis-output.md` for source column details
- Read `.specify/memory/tableau-analysis-output.md` for source column details **and the Row-Level Security (RLS) section** — if RLS was detected, you MUST generate `definition/roles/*.tmdl` (see Step 7f)

### 1b. Determine Data Source Strategy

- Count unique data source files from the Tableau analysis
- Locate data files in the `Data/` folder (each workbook has a subfolder, e.g., `Data/Netflix/`, `Data/Loan/`)
- Use `list_dir` on the relevant `Data/{subfolder}/` to find the actual CSV/Excel files
- **If SINGLE source file** (one CSV, one table): Use the **Natural Key Star Schema** pattern from SKILL.md:
  - Each dimension table loads the same source INDEPENDENTLY (no cross-table M references)
  - Use natural text keys for relationships (the original column values)
  - Fact table keeps all original columns; relationships use existing text columns
  - For many-to-many (comma-separated values): create a bridge table that splits values independently
  - DimDate generated via M (no file dependency)
- **If MULTIPLE source files/tables**: Each table loads from its own source. Can use surrogate keys if sources are independent.
- **NEVER use `Table.NestedJoin` referencing other table names** in M partitions — this creates circular dependencies.
- **ALWAYS use absolute file paths** in `File.Contents()` — resolve the full path to data files in `Data/{subfolder}/`.

### 2. Determine Model Name

Use the Tableau workbook name (without extension) in PascalCase as the model name (e.g., `LoanPortfolioAnalysis`).

### 3. Generate Full PBIP Folder Structure (TMDL Format)

Create ALL of the following in the `Output/{WorkbookName}/` folder:

```
Output/{WorkbookName}/{Name}.pbip
Output/{WorkbookName}/{Name}.Report/
├── definition.pbir
└── report.json
Output/{WorkbookName}/{Name}.SemanticModel/
├── definition.pbism
├── diagramLayout.json
└── definition/
    ├── database.tmdl
    ├── model.tmdl
    ├── expressions.tmdl      (if shared expressions needed)
    ├── relationships.tmdl
    ├── roles/                (ONLY if RLS detected in analysis)
    │   └── {RoleName}.tmdl
    └── tables/
        ├── {FactTable}.tmdl
        ├── {DimTable1}.tmdl
        └── ...
```

> **IMPORTANT**: All PBIP output files MUST be created inside the `Output/{WorkbookName}/` directory at the workspace root. Never create PBIP artifacts in the workspace root directly.

### 4. Generate {Name}.pbip

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
  "version": "1.0",
  "artifacts": [
    {
      "report": {
        "path": "{Name}.Report"
      }
    }
  ],
  "settings": {
    "enableAutoRecovery": true
  }
}
```

> **CRITICAL**: `$schema` is REQUIRED. ONLY a `"report"` artifact. NEVER add `"dataset"` or `"semanticModel"` — the schema rejects additional properties.

### 5. Generate Report Folder

**definition.pbir:**
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
  "version": "4.0",
  "datasetReference": {
    "byPath": {
      "path": "../{Name}.SemanticModel"
    }
  }
}
```

> **CRITICAL**: No `"byConnection": null`. Version must be `"4.0"`.

**report.json (PBIR-Legacy format — uses `"sections"` NOT `"pages"`):**
```json
{
  "config": "{\"version\":\"5.53\",\"themeCollection\":{},\"activeSectionIndex\":0,\"linguisticSchemaSyncVersion\":2}",
  "layoutOptimization": 0,
  "publicCustomVisuals": [],
  "sections": [
    {
      "name": "ReportSection1",
      "displayName": "Page 1",
      "displayOption": 1,
      "width": 1280,
      "height": 720,
      "visualContainers": []
    }
  ]
}
```

> **CRITICAL**: `themeCollection` MUST be `{}`. NEVER include `baseTheme` — causes ThemeService crash.
> **CRITICAL**: MUST use `"sections"` array (PBIR-Legacy). NEVER use `"pages"` — visuals won't render.
> **CRITICAL**: Do NOT put `"$schema"` at top level of report.json. Top-level `"config"` is a stringified JSON string.
> **CRITICAL**: Each section needs `"displayOption": 1`, `"width": 1280`, `"height": 720`.

### 6. Generate definition.pbism

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {}
}
```

> **CRITICAL**: Version `"4.2"` (NOT `"1.0"`). `settings` MUST be empty `{}`. No `datasetReference`.

### 7. Generate TMDL definition/ folder

Create the `definition/` folder inside `{Name}.SemanticModel/` with:

#### 7a. database.tmdl (MANDATORY)
```tmdl
database
	compatibilityLevel: 1567
```

> **CRITICAL**: NEVER use `createOrReplace` or `database DatabaseName` syntax. TMDL is NOT TMSL. The file must start with just `database` (no name), with `compatibilityLevel` indented below it.

#### 7b. model.tmdl (MANDATORY — must have ref table for EVERY table)
```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: en-US
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

annotation PBI_QueryOrder = ["{comma-separated table names}"]

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_ProTooling = ["DevMode"]

ref table {FactTableName}
ref table {DimTable1}
ref table {DimTable2}
...
```
> **CRITICAL**: Every table file in `tables/` MUST have a matching `ref table` line. Missing refs = table not found error.

#### 7c. expressions.tmdl (if using shared M expressions)
```tmdl
expression {ExprName} =
		let
			Source = Csv.Document(...)
		in
			Result
	lineageTag: {guid}
```
> **CRITICAL INDENTATION**: M body at 2 tabs, content at 3 tabs, properties at 1 tab.
> **NEVER use `queryGroup:`** unless the group is defined in model.tmdl.

#### 7d. relationships.tmdl
```tmdl
relationship {guid}
	fromColumn: {FactTable}.{FKCol}
	toColumn: {DimTable}.{PKCol}
	crossFilteringBehavior: oneDirection
```

#### 7e. tables/{TableName}.tmdl (one file per table)
Each table has columns, measures, and one partition:
```tmdl
table {TableName}
	lineageTag: {guid}

	column {ColName}
		dataType: string
		lineageTag: {guid}
		summarizeBy: none
		sourceColumn: {SourceCol}

	column 'Calculated Col' = IF([Status] = "Active", 1, 0)
		dataType: int64
		lineageTag: {guid}
		summarizeBy: sum
		isDataTypeInferred: false

	measure 'Single Line Measure' = COUNTROWS({TableName})
		lineageTag: {guid}
		displayFolder: {Folder}
		formatString: #,##0

	measure 'Multi Line Measure' =
			VAR _Val = SUM({TableName}[Amount])
			RETURN
			    DIVIDE(_Val, COUNTROWS({TableName}))
		lineageTag: {guid}
		displayFolder: {Folder}
		formatString: #,##0.00

	partition {TableName} = m
		mode: import
		source =
			let
				Source = ...
			in
				Result
```

> **CRITICAL — TMDL Expression Syntax**: NEVER use `expression = <value>` as a property. In TMDL, expressions are part of the DECLARATION using `=`:
> - Measures: `measure 'Name' = <DAX expression>` (expression ON the declaration line or indented below for multi-line)
> - Calculated columns: `column 'Name' = <DAX expression>` (NO `sourceColumn`, NO `expression` property)
> - Multi-line expressions: put `=` at end of declaration, indent expression body with 3 tabs, then properties at 2 tabs
> - Properties (lineageTag, formatString, displayFolder) come AFTER the expression, at 2-tab indent

#### 7f. roles/{RoleName}.tmdl (ONLY when RLS detected in analysis)
 
Read the **Row-Level Security (RLS)** section of `.specify/memory/{WorkbookName}/tableau-analysis-output.md`. If `Detected: No` / `None`, SKIP this step entirely (do NOT create a `roles/` folder).
 
If RLS is detected, create `definition/roles/{RoleName}.tmdl` for each suggested role. The role name must be quoted only if it contains spaces/special chars.
 
**Dynamic RLS** (user mapping table — the preferred pattern). The mapping table (e.g. `User_Access`) MUST exist as a model table and be related to the secured/fact table on the entitlement column. Filter the mapping table by the current user:
 
```tmdl
role {RoleName}
  modelPermission: read
 
  tablePermission {MappingTable} = '{MappingTable}'[{UserColumn}] = USERPRINCIPALNAME()
```
 
**Static per-value RLS** (one role per distinct entitlement value):
 
```tmdl
role {RoleName}
  modelPermission: read
 
  tablePermission {SecuredTable} = '{SecuredTable}'[{Column}] = "{Value}"
```
 
> **CRITICAL TMDL rules for roles**:
> - File path is `definition/roles/{RoleName}.tmdl` (one file per role).
> - `role` declaration takes the role name directly (no `createRole`/TMSL syntax).
> - `modelPermission: read` is REQUIRED — never `none` for a security role.
> - `tablePermission {Table} = <DAX boolean>` — the DAX is a filter predicate evaluated per row of `{Table}`.
> - Use `USERPRINCIPALNAME()` (returns the signed-in UPN/email) to match Tableau's `USERNAME()`. Use `USERNAME()` only for the older DOMAIN\\user form.
> - Reference columns with single-quoted table name + bracketed column: `'User_Access'[Username]`.
> - The DAX filter must NOT reference measures. Keep it a simple column predicate.
>
> **MANDATORY for dynamic RLS to actually filter data**: the mapping table must propagate its filter to the fact table. In `relationships.tmdl`, ensure a relationship `{MappingTable}.[{entitlement}]` → `{SecuredTable}.[{entitlement}]`. If the entitlement value must reach the fact through a shared dimension, set `crossFilteringBehavior: bothDirections` on that relationship so the user filter flows to the fact rows. Verify the mapping table is listed as a `ref table` in `model.tmdl` and has its own `tables/{MappingTable}.tmdl` partition loading the user-access source file.

### 8. Generate diagramLayout.json

```json
{}
```

### 10. Validate Structure

> Validation rules derived from `plugins/pbip/hooks/validate-tmdl.sh` and `plugins/pbip/hooks/validate-pbir.sh`.

**Structural checks:**
- **Both Report/ and SemanticModel/ folders exist inside `Output/{WorkbookName}/`** (CRITICAL — PBI Desktop fails without Report)
- Every table referenced in a relationship exists
- Every measure references valid table/column names
- No duplicate table or column names
- All required fields present in model.bim
- Valid JSON syntax throughout
- Relationships do NOT include fromCardinality/toCardinality/isActive (use defaults only)
- Calculated tables (GENERATESERIES) use `"sourceColumn": "Value"` (no brackets)
- M query `File.Contents()` paths point to absolute paths of data files in the `Data/` folder

**TMDL validation (from `plugins/pbip/hooks/validate-tmdl.sh`):**
- Indentation uses tabs (not spaces) — one tab per nesting level
- Object nesting is correct (columns/measures inside table, levels inside hierarchy)
- Names are quoted ONLY when containing spaces, dots, equals, colons, or starting with digit
- `///` (triple-slash) is immediately followed by a declaration (no blank line)
- Expression/M name namespace doesn't collide with table names
- Every `ref table` in model.tmdl has a matching `tables/{Name}.tmdl` file
- **RLS roles** (if analysis detected RLS): each `definition/roles/{RoleName}.tmdl` starts with `role {Name}`, has `modelPermission: read`, and a `tablePermission {Table} = <DAX>` whose table/column references resolve to real model objects. The secured/mapping table is included as a `ref table` and joined so the user filter reaches the fact (bi-directional cross-filter where needed). If analysis reported `RLS: None`, NO `roles/` folder should exist.

**PBIR validation (from `plugins/pbip/hooks/validate-pbir.sh`):**
- All JSON files pass `jq empty` (valid JSON)
- No spaces in folder names (pages/visuals won't render)
- `$schema` URLs start with `https://developer.microsoft.com/json-schemas/fabric/item/report/definition/`
- visual.json has: `$schema`, `name`, `position`, and either `visual` or `visualGroup`
- Visual/page names match `^[a-zA-Z0-9_][a-zA-Z0-9_-]*$` (word chars + hyphens only)
- page.json has: `$schema`, `name`, `displayName`, `displayOption`
- report.json has: `$schema`, `themeCollection`
- definition.pbir has: `$schema`, `version`, `datasetReference`

### 10b. Validate M Queries (CRITICAL — prevents data loading errors)

Check every M partition expression for these common errors:
- **NO `Table.TransformColumns` with `[field]` access** — `TransformColumns` passes scalar cell value only. If you need to reference another column in the same row, use `Table.AddColumn` instead.
- **NO cross-table references** (e.g., `Table.NestedJoin(..., DimType, ...)`) — each partition must be self-contained, loading data independently.
- **Absolute file paths** — verify `File.Contents()` uses full path, not relative.
- **Null safety** — any `Text.BeforeDelimiter`, `Text.Trim`, `Text.Contains` call must be guarded: check `[col] = null or [col] = ""` first.
- **QuoteStyle.Csv** — never `QuoteStyle.None` for CSV files with quoted values.
- **Correct pattern for extracting first value from comma-delimited column:**
  ```
  each if [col] = null or [col] = "" then null
       else if Text.Contains([col], ",") then Text.Trim(Text.BeforeDelimiter([col], ","))
       else Text.Trim([col])
  ```

### 10c. Validate PBIP Schema Files

Check these exact schemas (ANY deviation causes "schema does not allow additional properties" error):
- `.pbip`: artifacts array contains ONLY `{"report": {"path": "..."}}` — never dataset/semanticModel
- `.pbism`: exactly `{"version": "1.0", "settings": {}}` — nothing else
- `.pbir`: version must be `"4.0"` with `datasetReference.byPath`
- `editorSettings.json`: exactly `{"version": "1.0"}` — nothing else
- `report.json`: must exist with `$schema` and `themeCollection`

### 11. Present Results

Confirm the PBIP folder was generated in the `Output/{WorkbookName}/` directory and list all created files.
Provide the user with: "Open `Output/{WorkbookName}/{Name}.pbip` in Power BI Desktop to view the model."

## Notes

- Generic — reads from star schema and DAX outputs, never hardcodes
- **Input**: Data files (CSV, Excel) are in the `Data/` folder, organized in subfolders per workbook
- **Output**: All PBIP artifacts are created in the `Output/{WorkbookName}/` folder
- model.bim MUST be valid TMSL JSON (parseable by Power BI Desktop)
- **MUST generate Report folder** — Power BI Desktop requires it to open .pbip files
- Ref: https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset
- Tables use Import mode partitions with M query expressions
- All measures include formatString, displayFolder, description
- Relationships: only name/fromTable/fromColumn/toTable/toColumn/crossFilteringBehavior
- Do NOT use fromCardinality, toCardinality, or isActive in relationships
