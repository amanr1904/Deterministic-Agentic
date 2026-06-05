# PBIP Generator Skill

## Purpose

Generate a valid Power BI Project (.pbip) semantic model folder that can be opened in Power BI Desktop without errors. Uses TMSL format (model.bim) for the semantic model definition.

## Reference

- https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset
- https://learn.microsoft.com/en-us/analysis-services/tmsl/database-object-tmsl

## CRITICAL: Single-Source Star Schema (Natural Key Pattern)

When the Tableau workbook uses a SINGLE data source (e.g., one CSV or one database table), use the **Natural Key Star Schema** pattern:

### Rules:
1. **NEVER use `Table.NestedJoin` referencing other table names** in M partitions. This creates circular dependencies in TMSL that prevent data loading.
2. **Each table loads the SAME source independently** — every M partition reads the source file on its own.
3. **Use absolute file paths** in `File.Contents()` — relative paths may not resolve in PBIP context.
4. **Use natural keys (text values) for relationships** — NOT surrogate integer keys. The dimension's key column = the distinct text values from the source column.
5. **Fact table keeps all original columns** — relationships use the existing text columns directly.
6. **DimDate** is generated via M (no file dependency) for time intelligence.
7. **All measures go on the fact table.**

### Generic Pattern for Each Dimension:
```
Dimension Table M Query:
  1. Load source file independently
  2. Select the dimension column
  3. Get distinct values
  4. Remove nulls/blanks
  5. Rename to DimName (e.g., "TypeName", "RatingName")
  6. Optionally add enrichment columns (e.g., RatingCategory)

Relationship:
  FactTable.[original_column] → DimTable.[DimKey]  (natural text key)
```

### Many-to-Many Pattern (e.g., comma-separated genres):
```
Bridge Table M Query:
  1. Load source file independently
  2. Select fact_key + multi-value column
  3. Split multi-value column by delimiter
  4. Trim whitespace
  5. Remove nulls

Relationships:
  BridgeTable.[fact_key] → FactTable.[fact_key]
  BridgeTable.[dim_natural_key] → DimTable.[dim_natural_key]
```

### Why Natural Keys Work:
- No cross-table M dependencies (every query is self-contained)
- Power BI VertiPaq compresses text keys efficiently
- Dimension "to" side always has unique values (guaranteed by DISTINCT)
- No fragile surrogate key generation logic to keep in sync

## PBIP Folder Structure

### Output Location

All PBIP artifacts MUST be generated in the `Output/{WorkbookName}/` folder at the workspace root. Each workbook gets its own subfolder (e.g., `Output/Netflix/`, `Output/Loan Portfolio/`, `Output/Q3 Buyer/`). Never place PBIP files directly in the workspace root.

### Data Source Location

Data files (CSV, Excel) are located in the `Data/` folder, organized in subfolders per workbook:
```
Data/
├── Netflix/
│   ├── Netfix Workbook.twb
│   └── netflix_titles.csv
├── Loan/
│   ├── Loan Portfolio Analysis.twb
│   ├── loan.csv
│   └── customer.csv
├── Q3 Buyer/
│   ├── (Active) 2021 Q3 Dealer Buying Event.twb
│   └── Q3LaunchData 1.csv
└── Sales and Customer/
    ├── Sales & Customer Dashboards.twb
    ├── Orders.csv
    └── ...
```

M queries in TMDL partitions MUST use absolute file paths pointing to the data files in the `Data/{subfolder}/` directory.

### Option A: TMDL Format (PREFERRED — used when `PBI_tmdlInDataset` preview feature is enabled)

```
Output/{WorkbookName}/{ModelName}.pbip                    # Required - project entry point
Output/{WorkbookName}/{ModelName}.Report/
├── definition.pbir                 # Required - report definition pointing to semantic model
└── report.json                     # Required - minimal report metadata
Output/{WorkbookName}/{ModelName}.SemanticModel/
├── definition.pbism                # Required - model definition metadata
├── diagramLayout.json              # Diagram metadata (can be {})
└── definition/
    ├── database.tmdl               # REQUIRED - compatibility level
    ├── model.tmdl                  # REQUIRED - model config + ref tables
    ├── expressions.tmdl            # Shared M expressions (if any)
    ├── relationships.tmdl          # All relationships
    └── tables/
        ├── FactTable.tmdl          # One file per table
        ├── DimTable1.tmdl
        └── ...
```

### Option B: TMSL Format (model.bim JSON)

```
Output/{WorkbookName}/{ModelName}.pbip                    # Required - project entry point
Output/{WorkbookName}/{ModelName}.Report/
├── definition.pbir                 # Required - report definition pointing to semantic model
└── report.json                     # Required - minimal report metadata
Output/{WorkbookName}/{ModelName}.SemanticModel/
├── definition.pbism                # Required - model definition metadata
├── model.bim                       # Required - TMSL semantic model (JSON)
├── diagramLayout.json              # Diagram metadata
└── .pbi/
    └── editorSettings.json         # Editor settings
```

> **IMPORTANT**: Use TMDL (Option A) as the default. Only use TMSL (Option B) if specifically requested.

---

## TMDL Format Rules (CRITICAL)

### database.tmdl (MANDATORY)
```tmdl
database
	compatibilityLevel: 1567
```
> This file MUST exist. Without it, Power BI Desktop cannot parse the model.

### model.tmdl (MANDATORY — must include ref table declarations)
```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: en-US
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

annotation PBI_QueryOrder = ["{TableList}"]

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_ProTooling = ["DevMode"]

ref table {FactTableName}
ref table {DimTable1Name}
ref table {DimTable2Name}
...
```

> **CRITICAL RULES:**
> - `dataAccessOptions` with `legacyRedirects` and `returnErrorValuesAsNull` is REQUIRED
> - Every table that exists in the `tables/` folder MUST have a corresponding `ref table` line
> - `PBI_QueryOrder` annotation MUST list ALL table names as a JSON array string
> - Do NOT include `discourageImplicitMeasures: true` — it prevents measure creation in Desktop
> - Do NOT include `queryGroup` declarations unless you have expressions that reference them

### expressions.tmdl (Shared M Expressions)

**INDENTATION IS CRITICAL** — M expression body must be at 2-tab indent, properties at 1-tab:
```tmdl
expression {ExpressionName} =
		let
			Source = Csv.Document(...)
		in
			Result
	lineageTag: {guid}
```

> **CRITICAL INDENTATION RULES:**
> - The M body (`let`/`in` and content) MUST be at **2 tabs** from the start
> - Body content (variable assignments) MUST be at **3 tabs**
> - TMDL properties (`lineageTag:`) MUST be at **1 tab**
> - If `lineageTag` is at the same indent as `let`/`in`, the parser treats it as M code → syntax error
>
> **CRITICAL: Do NOT use `queryGroup:` property** unless you've defined the query group in `model.tmdl`. Referencing a non-existent query group causes: "Property QueryGroup refers to an object which cannot be found"

### Table .tmdl files (in tables/ folder)

Each table file follows this structure:
```tmdl
table {TableName}
	lineageTag: {guid}

	column {ColumnName}
		dataType: string
		lineageTag: {guid}
		summarizeBy: none
		sourceColumn: {SourceColumnName}

	measure {MeasureName} = {ENTIRE DAX ON SAME LINE}
		displayFolder: {FolderName}
		formatString: #,##0
		lineageTag: {guid}

	partition {TableName} = m
		mode: import
		source =
			let
				Source = {M Expression}
			in
				Result
```

> **CRITICAL MEASURE RULE**: The ENTIRE DAX expression MUST be on the SAME LINE as `measure 'Name' =`. Properties (`displayFolder`, `formatString`, `lineageTag`) go on subsequent lines at one deeper indent (2 tabs). If DAX is on the next line at the same indent as properties, the TMDL parser cannot distinguish DAX from properties and treats `displayFolder: ...` as DAX code → "syntax for 'displayFolder' is incorrect" error.
>
> **Correct:**
> ```tmdl
> 	measure 'Total Sales' = SUM(FactOrders[Sales])
> 		formatString: $#,##0
> 		displayFolder: Sales
> 		lineageTag: {guid}
> ```
>
> **WRONG (causes error):**
> ```tmdl
> 	measure 'Total Sales' =
> 		SUM(FactOrders[Sales])
> 		formatString: $#,##0
> 		displayFolder: Sales
> 		lineageTag: {guid}
> ```
>
> For complex DAX with VAR/RETURN, put it ALL on one line:
> ```tmdl
> 	measure 'CY Sales' = VAR _Year = [Selected Year] RETURN CALCULATE(SUM(FactOrders[Sales]), DimDate[Year] = _Year)
> 		formatString: $#,##0
> 		displayFolder: Sales
> 		lineageTag: {guid}
> ```

> **Partition indentation:** `partition` at 1 tab, `mode:`/`source =` at 2 tabs, M body at 3 tabs, M content at 4 tabs.

### relationships.tmdl

```tmdl
relationship {guid}
	fromColumn: {FactTable}.{FKColumn}
	toColumn: {DimTable}.{PKColumn}
	crossFilteringBehavior: oneDirection
```

> Do NOT include `fromCardinality`, `toCardinality`, or `isActive` — Power BI infers these.

---

## CRITICAL: Report Artifact Required

Power BI Desktop REQUIRES both a Report AND SemanticModel folder. The `.pbip` references the Report, which in turn references the SemanticModel. All files are generated in the `Output/{WorkbookName}/` folder.

### Output/{WorkbookName}/{ModelName}.pbip
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
  "version": "1.0",
  "artifacts": [
    {
      "report": {
        "path": "{ModelName}.Report"
      }
    }
  ],
  "settings": {
    "enableAutoRecovery": true
  }
}
```

> **CRITICAL**: The `artifacts` array MUST contain ONLY a `"report"` entry. NEVER add a `"dataset"` or `"semanticModel"` entry — the schema does not allow it. The semantic model is referenced from `definition.pbir`, NOT from `.pbip`. The `path` is relative to the `.pbip` file location (inside `Output/{WorkbookName}/`).

### definition.pbir (in Output/{WorkbookName}/{ModelName}.Report/ folder)
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
  "version": "4.0",
  "datasetReference": {
    "byPath": {
      "path": "../{ModelName}.SemanticModel"
    }
  }
}
```

> **CRITICAL**: Do NOT include `"byConnection": null` — it's not needed and may cause schema validation issues. Use version `"4.0"` (NOT `"1.0"`). The relative path `../` correctly points to the sibling SemanticModel folder within `Output/{WorkbookName}/`.

### report.json (in Report folder) — PBIR-Legacy Format

> **CRITICAL FORMAT**: report.json MUST use `"sections"` array (PBIR-Legacy format). NEVER use `"pages"` — that is the newer PBIR format which requires a different folder structure and will cause visuals to NOT render.

**Minimal report.json (no visuals yet):**
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

> **CRITICAL RULES:**
> - `themeCollection` MUST be `{}` (empty). NEVER include `baseTheme` — causes ThemeService crash.
> - Top-level `"config"` is a **stringified JSON string** — NOT a `"$schema"` at top level.
> - Each section MUST have `"displayOption": 1`, `"width": 1280`, `"height": 720`.
> - Do NOT include `"$schema"` at the top level of report.json — it is NOT a schema-validated file.
> - Every `visualContainers` entry MUST include `"filters": "[]"` field.

### definition.pbism (in SemanticModel folder)
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {}
}
```

> **CRITICAL**: Use version `"4.2"` (NOT `"1.0"`). Do NOT include `"datasetReference"` — the `.pbism` is a manifest, not a reference pointer. Keep `settings` as an empty object.

## model.bim Schema (TMSL)

```json
{
  "compatibilityLevel": 1567,
  "model": {
    "culture": "en-US",
    "dataAccessOptions": { "legacyRedirects": true, "returnErrorValuesAsNull": true },
    "defaultPowerBIDataSourceVersion": "powerBI_V3",
    "tables": [...],
    "relationships": [...],
    "annotations": [...]
  }
}
```

### Table Object
```json
{
  "name": "TableName",
  "columns": [
    {
      "name": "ColumnName",
      "dataType": "string|int64|double|boolean|dateTime",
      "sourceColumn": "SourceColumnName",
      "formatString": "0.00",
      "dataCategory": "State|City|Country|",
      "isHidden": false,
      "summarizeBy": "none|sum|count|average"
    }
  ],
  "measures": [
    {
      "name": "MeasureName",
      "expression": "DAX expression",
      "formatString": "#,##0",
      "displayFolder": "FolderName",
      "description": "Description"
    }
  ],
  "partitions": [
    {
      "name": "TableName",
      "mode": "import",
      "source": {
        "type": "m",
        "expression": ["let", "  Source = Csv.Document(...)", "in", "  Source"]
      }
    }
  ]
}
```

### Relationship Object
```json
{
  "name": "FromTable_ToTable",
  "fromTable": "FactTable",
  "fromColumn": "DimKey",
  "toTable": "DimTable",
  "toColumn": "Key",
  "crossFilteringBehavior": "oneDirection"
}
```
Note: Do NOT include `fromCardinality`, `toCardinality`, or `isActive` — Power BI infers these from the data. Including invalid cardinality values causes load errors.

### Data Type Mapping
| Source Type | TMSL dataType | Format String |
|-------------|---------------|---------------|
| string | string | |
| integer | int64 | 0 |
| real/float | double | #,##0.00 |
| boolean | boolean | |
| date | dateTime | yyyy-MM-dd |
| datetime | dateTime | yyyy-MM-dd HH:mm:ss |
| percentage | double | 0.00%;-0.00% |
| currency | double | $#,##0.00 |

### M Query Template for CSV Sources
```
let
    Source = Csv.Document(File.Contents("{ABSOLUTE_PATH_TO_FILE}"), [Delimiter=",", Columns={N}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Types" = Table.TransformColumnTypes(#"Promoted Headers", {column_type_list})
in
    #"Changed Types"
```

### M Query Template for SQL Server Sources
```
let
    Source = Sql.Database("{SERVER_NAME}", "{DATABASE_NAME}"),
    Navigation = Source{[Schema="{SCHEMA}", Item="{TABLE_NAME}"]}[Data],
    #"Changed Types" = Table.TransformColumnTypes(Navigation, {column_type_list})
in
    #"Changed Types"
```
Notes:
- Use `Sql.Database` for import mode (recommended)
- Use `Sql.Database("{server}", "{db}", [Query="SELECT ..."])` for custom SQL
- Schema defaults to "dbo" if not specified

### M Query Template for PostgreSQL Sources
```
let
    Source = PostgreSQL.Database("{SERVER_NAME}:{PORT}", "{DATABASE_NAME}"),
    Navigation = Source{[Schema="{SCHEMA}", Name="{TABLE_NAME}"]}[Data],
    #"Changed Types" = Table.TransformColumnTypes(Navigation, {column_type_list})
in
    #"Changed Types"
```
Notes:
- Port defaults to 5432
- Schema defaults to "public"
- Can use `[Query="SELECT ..."]` for custom SQL

### M Query Template for Excel Sources
```
let
    Source = Excel.Workbook(File.Contents("{ABSOLUTE_PATH_TO_FILE}"), null, true),
    Navigation = Source{[Item="{SHEET_NAME}", Kind="Sheet"]}[Data],
    #"Promoted Headers" = Table.PromoteHeaders(Navigation, [PromoteAllScalars=true]),
    #"Changed Types" = Table.TransformColumnTypes(#"Promoted Headers", {column_type_list})
in
    #"Changed Types"
```
Notes:
- Third parameter `true` enables header detection
- Use `Kind="Sheet"` for worksheets, `Kind="Table"` for Excel tables
- Named ranges: `Source{[Item="{RANGE_NAME}", Kind="DefinedName"]}[Data]`

### M Query Template for ODBC Sources
```
let
    Source = Odbc.DataSource("{CONNECTION_STRING}"),
    Navigation = Source{[Name="{TABLE_NAME}", Schema="{SCHEMA}"]}[Data],
    #"Changed Types" = Table.TransformColumnTypes(Navigation, {column_type_list})
in
    #"Changed Types"
```

### Source Type Detection from Tableau Connection Class
| Tableau `class` attribute | M Query Pattern |
|--------------------------|-----------------|
| `textscan` or `textclean` | CSV — `Csv.Document(File.Contents(...))` |
| `sqlserver` | SQL Server — `Sql.Database(...)` |
| `postgres` | PostgreSQL — `PostgreSQL.Database(...)` |
| `excel-direct` | Excel — `Excel.Workbook(File.Contents(...))` |
| `mysql` | MySQL — `MySQL.Database(...)` |
| `oracle` | Oracle — `Oracle.Database(...)` |
| `snowflake` | Snowflake — `Snowflake.Databases(...)` |
| `bigquery` | BigQuery — `GoogleBigQuery.Database(...)` |
| Other ODBC | Generic — `Odbc.DataSource(...)` |

### M Query Safety Rules (CRITICAL)

1. **NEVER use `Table.TransformColumns` with row field access** — `Table.TransformColumns` passes only the CELL value (scalar) to the transform function. Using `[column_name]` inside it causes "cannot apply field access to type Text" error. Use `Table.AddColumn` instead when you need access to other columns in the same row.
2. **NEVER reference other table/query names** in M expressions (e.g., `Table.NestedJoin(..., DimType, ...)`) — this creates circular dependencies. Each partition must be self-contained.
3. **Use absolute file paths** — `File.Contents("C:\\full\\path\\file.csv")` not relative paths.
4. **Use `QuoteStyle.Csv`** not `QuoteStyle.None` — CSV files with quoted fields will fail otherwise.
5. **Handle nulls in `Table.AddColumn`** — check `[col] = null or [col] = ""` BEFORE calling text functions like `Text.BeforeDelimiter` on that column.
6. **For extracting first value from comma-separated field:**
```m
Table.AddColumn(PreviousStep, "NewCol", each
    if [original_col] = null or [original_col] = ""
    then null
    else if Text.Contains([original_col], ",")
    then Text.Trim(Text.BeforeDelimiter([original_col], ","))
    else Text.Trim([original_col]),
    type text)
```
7. **For splitting multi-value columns (many-to-many):**
```m
Table.ExpandListColumn(
    Table.TransformColumns(PreviousStep, {{"col",
        Splitter.SplitTextByDelimiter(",", QuoteStyle.Csv),
        let itemType = (type nullable text) meta [Serialized.Text = true] in type {itemType}
    }}), "col")
```

## Validation Rules

### PBIP Schema Rules (prevents "schema does not allow additional properties" errors)
1. `.pbip` artifacts array: ONLY objects with `"report"` property — NEVER `"dataset"` or `"semanticModel"`
2. `.pbism`: ONLY `"version"` + `"settings": {}` — NEVER `"datasetReference"`, `"compatibilityLevel"`, or anything inside `settings`
3. `.pbir`: version MUST be `"4.0"` (not `"1.0"`) — uses `"datasetReference"` with `"byPath"`
4. `.pbi/editorSettings.json`: ONLY `"version": "1.0"` — no other properties
5. `report.json`: REQUIRED in Report folder or PBI Desktop won't load the project

### Model Rules
6. Every table in relationships MUST exist in tables array
7. Every column referenced in relationships MUST exist in that table
8. All measure expressions MUST reference valid table/column names
9. No duplicate table names or column names within a table
10. model.bim MUST be valid JSON (use proper escaping for DAX quotes)
11. compatibilityLevel MUST be 1567 or higher for modern features
12. Each table MUST have at least one partition
13. **MUST create both Report/ and SemanticModel/ folders** — PBI Desktop fails without Report/definition.pbir
14. Relationships: do NOT specify fromCardinality/toCardinality/isActive (use defaults)
15. Calculated tables via GENERATESERIES produce a column named `Value` — use `"sourceColumn": "Value"` (no brackets)
16. Relationship "to" columns MUST contain unique values (use keys, not repeated dimension attributes)

### M Query Rules (prevents data loading errors)
17. NEVER use `Table.TransformColumns` with row field access (`[col]`) — use `Table.AddColumn` instead
18. NEVER reference other query/table names in M expressions — each partition is self-contained
19. ALWAYS use absolute file paths in `File.Contents()`
20. ALWAYS use `QuoteStyle.Csv` for CSV files
21. ALWAYS null-check columns before applying text functions

## Output

Create the full folder structure with valid files in the workspace root:
- `{Name}.pbip`
- `{Name}.Report/definition.pbir`
- `{Name}.Report/report.json`
- `{Name}.SemanticModel/definition.pbism`
- `{Name}.SemanticModel/model.bim`
- `{Name}.SemanticModel/diagramLayout.json`
- `{Name}.SemanticModel/.pbi/editorSettings.json`
