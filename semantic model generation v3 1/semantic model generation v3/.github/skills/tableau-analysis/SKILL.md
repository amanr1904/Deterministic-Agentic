# Tableau Workbook Analysis Skill

## Purpose

Analyze any Tableau workbook file (`.twb` or `.twbx`) present in the workspace and extract comprehensive metadata including datasources, columns, calculated fields, parameters, worksheets, dashboards, and relationships. This skill is generic and works with any Tableau workbook regardless of its content or domain.

## When to Use

- User asks to analyze a Tableau workbook
- User wants to extract metadata from a `.twb` or `.twbx` file
- User needs a summary of datasources, fields, calculations, or visualizations in a Tableau file
- User wants to understand the structure of a Tableau workbook before migration
- As a prerequisite step before generating a Power BI migration constitution

## Instructions

### Step 1: Locate Tableau Files

Search the `Data/` folder for Tableau workbooks:
- Use `file_search` with glob patterns `Data/**/*.twb` and `Data/**/*.twbx`
- Workbooks are organized in subfolders under `Data/` (e.g., `Data/Netflix/`, `Data/Loan/`, `Data/Q3 Buyer/`, `Data/Sales and Customer/`)
- If a `.twbx` file is found, note that it is a packaged workbook (ZIP containing a `.twb` and data extracts)
- Do NOT hardcode any specific file name — always discover dynamically
- Data files (CSV, Excel) are co-located with the `.twb` in the same subfolder

### Step 2: Parse the TWB XML Structure

A `.twb` file is XML. Extract the following metadata sections:

#### 2.1 Workbook Metadata
- `version` attribute on `<workbook>` element
- `source-build` and `source-platform` attributes

#### 2.2 Parameters
- Look for `<datasource name='Parameters'>` 
- Extract each `<column>` inside with:
  - `caption` (display name)
  - `datatype` (integer, string, real, date, etc.)
  - `param-domain-type` (range, list, all)
  - Default value from `<calculation formula='...' />`
  - Range constraints from `<range min='' max='' granularity='' />`

#### 2.3 Datasources
- Each `<datasource>` element (excluding the Parameters datasource)
- Extract:
  - `caption` (display name)
  - `name` (internal ID)
  - Connection type from `<connection class='...'>`
  - File paths from `<named-connection>` elements
  - Tables/relations from `<relation>` elements

#### 2.4 Columns & Fields
For each datasource, extract `<column>` elements:
- `caption` (display name)
- `name` (internal field name)
- `datatype` (string, integer, real, boolean, date, datetime)
- `role` (dimension or measure)
- `type` (nominal, ordinal, quantitative)
- `semantic-role` if present (geographic roles like `[State].[Name]`)

#### 2.5 Calculated Fields
Identify columns with nested `<calculation>` elements:
- `caption` (calculated field name)
- `formula` (the Tableau calculation expression — decode XML entities like `&quot;`, `&gt;`, `&lt;`, `&amp;`, `&#13;&#10;`)
- `datatype` and `role`
- Table calculation settings from `<table-calc>` if present (ordering-type, ordering-field)

#### 2.6 Worksheets
- Each `<worksheet name='...'>` element
- Extract the worksheet name

#### 2.7 Dashboards
- Each `<dashboard name='...'>` element
- Extract the dashboard name (decode `&amp;` etc.)

#### 2.8 Relationships / Joins
- Look for `<relation type='join'>` elements inside datasource connections
- Extract join type, left/right tables, and join clauses from `<clause>` elements
- Also check for multi-table `<relation type='collection'>` (logical model)

### Step 3: Output Format

Present the extracted metadata in a structured markdown format:

```markdown
# Tableau Workbook Analysis: {workbook_name}

## Workbook Info
- **Version**: ...
- **Source Build**: ...
- **Platform**: ...

## Parameters
| Name | Data Type | Domain Type | Default | Range/Values |
|------|-----------|-------------|---------|--------------|

## Datasources
### {Datasource Caption}
- **Connection Type**: ...
- **Source File(s)**: ...
- **Tables**: ...

#### Dimensions
| Display Name | Field Name | Data Type | Semantic Role |
|--------------|------------|-----------|---------------|

#### Measures
| Display Name | Field Name | Data Type |
|--------------|------------|-----------|

## Calculated Fields
| Name | Formula | Data Type | Type | Table Calc |
|------|---------|-----------|------|------------|

## Worksheets
1. ...

## Dashboards
1. ...

## Relationships
| Left Table | Right Table | Join Type | Condition |
|------------|-------------|-----------|-----------|
```

### Step 4: Save Analysis Output

**MANDATORY**: After extracting metadata, save the full structured output to `.specify/memory/tableau-analysis-output.md`. This file serves as the input context for the automatic constitution generation step.

### Step 5: Hand Off to Migration Pipeline

After saving, **automatically** call the `migration-constitution` agent which handles the rest:
1. **Constitution** — Power BI best practices (star schema, DAX, naming, relationships, performance, parameters, semantic layer, traceability)
2. **Specify** — Detailed migration spec (tables, columns, measures, relationships, parameters)
3. **Clarify** — Resolve ambiguities (measure vs column, unclear joins, table calcs, data categories)

### Step 6: Additional Analysis (if requested)
- Identify unused fields, complex calculations (LOD, nested table calcs)
- Note data blending, sets, groups, bins, filter definitions

## Notes

- GENERIC — never hardcode file names, discover dynamically via file search
- Decode XML entities in formulas and names
- For `.twbx` (ZIP), extract the `.twb` inside
- Bracket notation: `[field_name]`, internal calcs: `[Calculation_XXXX]`
- Cross-datasource: `[datasource_name].[field_name]`
- Pipeline (constitution → specify → clarify) is AUTOMATIC — no confirmation needed
- Ref: https://learn.microsoft.com/en-us/power-bi/guidance/
