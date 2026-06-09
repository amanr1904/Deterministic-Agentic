# PBIP M Queries Skill

## Purpose

M (Power Query) templates per data source type and the M safety rules that prevent data-loading errors. Single-responsibility companion to the PBIP generation pipeline.

## When to Use

- During PBIP generation, when writing partition `source = let ... in ...` M code
- Whenever building multi-value split logic or first-value extraction

## Source Type Detection (from Tableau connection class)

| Tableau `class` | M Query Pattern |
|---|---|
| `textscan` / `textclean` | CSV — `Csv.Document(File.Contents(...))` |
| `sqlserver` | SQL Server — `Sql.Database(...)` |
| `postgres` | PostgreSQL — `PostgreSQL.Database(...)` |
| `excel-direct` | Excel — `Excel.Workbook(File.Contents(...))` |
| `mysql` | MySQL — `MySQL.Database(...)` |
| `oracle` | Oracle — `Oracle.Database(...)` |
| `snowflake` | Snowflake — `Snowflake.Databases(...)` |
| `bigquery` | BigQuery — `GoogleBigQuery.Database(...)` |
| other ODBC | Generic — `Odbc.DataSource(...)` |

## CSV

```m
let
    Source = Csv.Document(File.Contents("{ABSOLUTE_PATH}"), [Delimiter=",", Columns={N}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Types" = Table.TransformColumnTypes(#"Promoted Headers", {column_type_list})
in
    #"Changed Types"
```

## SQL Server

```m
let
    Source = Sql.Database("{SERVER}", "{DATABASE}"),
    Navigation = Source{[Schema="{SCHEMA}", Item="{TABLE}"]}[Data],
    #"Changed Types" = Table.TransformColumnTypes(Navigation, {column_type_list})
in
    #"Changed Types"
```
- `Sql.Database` for import. Custom SQL: `Sql.Database("{server}", "{db}", [Query="SELECT ..."])`. Schema defaults to `dbo`.

## PostgreSQL

```m
let
    Source = PostgreSQL.Database("{SERVER}:{PORT}", "{DATABASE}"),
    Navigation = Source{[Schema="{SCHEMA}", Name="{TABLE}"]}[Data],
    #"Changed Types" = Table.TransformColumnTypes(Navigation, {column_type_list})
in
    #"Changed Types"
```
- Port defaults 5432, schema defaults `public`. Custom SQL via `[Query="SELECT ..."]`.

## Excel

```m
let
    Source = Excel.Workbook(File.Contents("{ABSOLUTE_PATH}"), null, true),
    Navigation = Source{[Item="{SHEET}", Kind="Sheet"]}[Data],
    #"Promoted Headers" = Table.PromoteHeaders(Navigation, [PromoteAllScalars=true]),
    #"Changed Types" = Table.TransformColumnTypes(#"Promoted Headers", {column_type_list})
in
    #"Changed Types"
```
- Third param `true` enables header detection. `Kind="Sheet"` / `"Table"` / `"DefinedName"` (named ranges).

## ODBC

```m
let
    Source = Odbc.DataSource("{CONNECTION_STRING}"),
    Navigation = Source{[Name="{TABLE}", Schema="{SCHEMA}"]}[Data],
    #"Changed Types" = Table.TransformColumnTypes(Navigation, {column_type_list})
in
    #"Changed Types"
```

## Data Type Mapping

| Source Type | TMSL dataType | Format String |
|---|---|---|
| string | string | |
| integer | int64 | 0 |
| real/float | double | #,##0.00 |
| boolean | boolean | |
| date | dateTime | yyyy-MM-dd |
| datetime | dateTime | yyyy-MM-dd HH:mm:ss |
| percentage | double | 0.00%;-0.00% |
| currency | double | $#,##0.00 |

## ⚠️ M Safety Rules (CRITICAL)

1. **NEVER use `Table.TransformColumns` with row field access** (`[col]`) — it passes only the CELL value; `[other_col]` inside causes "cannot apply field access to type Text". Use `Table.AddColumn` when you need other columns.
2. **NEVER reference other table/query names** in M (e.g. `Table.NestedJoin(..., DimType, ...)`) — creates circular dependencies. Each partition must be self-contained.
3. **Use absolute file paths** — `File.Contents("C:\\full\\path\\file.csv")`.
4. **Use `QuoteStyle.Csv`** (not `QuoteStyle.None`) — quoted CSV fields fail otherwise.
5. **Null-check before text functions** — check `[col] = null or [col] = ""` BEFORE `Text.BeforeDelimiter`, etc.

### First value from comma-separated field
```m
Table.AddColumn(PreviousStep, "NewCol", each
    if [original_col] = null or [original_col] = ""
    then null
    else if Text.Contains([original_col], ",")
    then Text.Trim(Text.BeforeDelimiter([original_col], ","))
    else Text.Trim([original_col]),
    type text)
```

### Split multi-value column (many-to-many)
```m
Table.ExpandListColumn(
    Table.TransformColumns(PreviousStep, {{"col",
        Splitter.SplitTextByDelimiter(",", QuoteStyle.Csv),
        let itemType = (type nullable text) meta [Serialized.Text = true] in type {itemType}
    }}), "col")
```

## Anti-Hallucination

- Use only the absolute paths/servers/schemas from the analysis output; never fabricate connection details.
