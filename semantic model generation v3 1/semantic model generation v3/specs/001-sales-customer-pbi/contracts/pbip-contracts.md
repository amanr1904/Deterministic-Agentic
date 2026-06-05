# Contracts: PBIP Semantic Model — Sales & Customer Dashboards

## File: definition.pbism

```json
{
  "version": "4.0",
  "settings": {}
}
```

---

## File: database.tmdl

Required properties:
- `compatibilityLevel`: 1604
- `model`: reference to model definition

---

## File: model.tmdl

Required properties:
- `culture`: `en-US`
- `defaultPowerBIDataSourceVersion`: `powerBI_V3`
- Annotation: `PBI_QueryOrder` (JSON array of table names in load order)

---

## File: relationships.tmdl

5 relationship declarations with properties:
- `fromColumn` / `toColumn`: Table[Column] references (Customers/Location/Products/DimDate → Orders)
- `crossFilteringBehavior`: `oneDirection`
- `fromCardinality`: `many`
- `toCardinality`: `one`
- `isActive`: `true` or `false`

---

## File: tables/{Name}.tmdl

Each table file contains:
- Table declaration with partition (M expression or DAX expression)
- Column declarations with: `dataType`, `sourceColumn`, `summarizeBy`, `lineageTag`
- Measure declarations (on the `Orders` fact table) with: `expression`, `formatString`, `displayFolder`, `lineageTag`
- Optional: `dataCategory` for geographic columns, `isHidden` for internal columns

### M Query Partition Contract (CSV tables)

```m
Csv.Document(
    File.Contents("<absolute_path>"),
    [Delimiter = ";", QuoteStyle = QuoteStyle.Csv, Encoding = <65001|1252>]
)
```
Followed by: `Table.PromoteHeaders`, `Table.TransformColumnTypes` with `"de-DE"` culture.

### DAX Calculated Table Contract (Select Year)

```dax
DATATABLE("Year", INTEGER, {{2020}, {2021}, {2022}, {2023}})
```

---

## File: definition.pbir

```json
{
  "version": "4.0",
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/definition/1.2.0/schema.json",
  "datasetReference": {
    "byPath": {
      "path": "../SalesCustomerDashboards.SemanticModel"
    }
  }
}
```

---

## File: report.json

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
  "themeCollection": {},
  "settings": {
    "useEnhancedTooltips": true
  }
}
```

**Forbidden properties**: `modelExtensions`, `publicCustomVisuals`, `sections`, `baseTheme`

---

## File: page.json (per page)

Required properties:
- `$schema`: page schema URL
- `name`: regex `^[\w-]+$` (no spaces/special chars)
- `displayName`: human-readable title
- `displayOption`: `"SixteenByNine"` or `"FourByThree"`

---

## File: visual.json (per visual)

Required properties:
- `$schema`: `https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json`
- `name`: unique GUID-like identifier
- `position`: `{ x, y, z, width, height, tabOrder }`
- `visual` or `visualGroup`: visual type definition

**Forbidden at root level**: `filters`, `filterConfig`, or any unlisted property
