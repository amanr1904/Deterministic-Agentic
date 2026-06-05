# Research: Sales & Customer Dashboards Migration

## Phase 0 — Technical Research

### 1. M Query Patterns for Semicolon CSV with German Locale

**Decision**: Use `Csv.Document` with explicit `Delimiter=";"`, `QuoteStyle=QuoteStyle.Csv`, and `Encoding=65001` (UTF-8).

**Rationale**: The Tableau workbook specifies `locale='en_DE'` with `separator=';'`. German locale uses comma as decimal separator and semicolons as field delimiters. The M query must handle this explicitly since Power BI defaults to comma-delimited.

**Pattern**:
```m
let
    Source = Csv.Document(
        File.Contents("C:\path\to\file.csv"),
        [Delimiter = ";", QuoteStyle = QuoteStyle.Csv, Encoding = 65001]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    TypedColumns = Table.TransformColumnTypes(PromotedHeaders, {
        {"NumericCol", type number},
        {"DateCol", type date},
        {"TextCol", type text}
    }, "de-DE")
in
    TypedColumns
```

**Key parameters**:
- `Delimiter = ";"` — semicolon field separator
- `QuoteStyle = QuoteStyle.Csv` — standard CSV quoting (constitution §5 requirement)
- `Encoding = 65001` — UTF-8 for Orders.csv and Location.csv
- `Culture = "de-DE"` in `Table.TransformColumnTypes` — parse comma decimals correctly
- Windows-1252 files (Customers.csv, Products.csv): Use `Encoding = 1252`

**Alternatives considered**:
- `Culture` parameter in Csv.Document → not available; culture applied at type conversion step
- `Encoding = 0` (auto-detect) → unreliable; explicit encoding preferred

---

### 2. TMDL Syntax for Relationships

**Decision**: Define all relationships in a single `relationships.tmdl` file using TMDL relationship declaration syntax.

**Rationale**: TMDL separates relationships from table definitions for clarity. Each relationship specifies from/to table.column, cardinality, and cross-filter direction.

**Pattern**:
```tmdl
relationship <guid>
	fromColumn: Orders.'Customer ID'
	toColumn: Customers.'Customer ID'
	crossFilteringBehavior: oneDirection
	fromCardinality: many
	toCardinality: one
	isActive: true
```

**Key rules** (from TMDL skill):
- Property names use camelCase
- String values with spaces must be quoted with single quotes
- `crossFilteringBehavior: oneDirection` (not `singleDirection`)
- Inactive relationships: `isActive: false` — consumed via `USERELATIONSHIP()` in DAX
- No `securityFilteringBehavior` property needed for Import mode standard relationships

---

### 3. DimDate as a DAX CALENDAR Calculated Table

**Decision**: Generate `DimDate` as a **DAX calculated table** using `CALENDAR` over the full calendar years spanning `MIN(Orders[Order Date])` → `MAX(Orders[Order Date])`, marked as the model's date table.

**Rationale**: A DAX `CALENDAR` table auto-adapts to the loaded data range (snapped to Jan 1 / Dec 31) without hardcoded boundaries and without cross-query M references. It keeps all date attributes in one declarative expression and is marked as the date table for time intelligence. Required axis columns are `WeekNum` (KPI Avg week axis) and `MonthName` (Min/Max month axis, Sort-By Month).

**Pattern** (DAX):
```dax
DimDate =
VAR _MinDate = MIN(Orders[Order Date])
VAR _MaxDate = MAX(Orders[Order Date])
VAR _Start = DATE(YEAR(_MinDate), 1, 1)
VAR _End = DATE(YEAR(_MaxDate), 12, 31)
RETURN
    ADDCOLUMNS(
        CALENDAR(_Start, _End),
        "Year", YEAR([Date]),
        "Quarter", QUARTER([Date]),
        "Month", MONTH([Date]),
        "MonthName", FORMAT([Date], "MMMM"),
        "Day", DAY([Date]),
        "DayOfWeek", WEEKDAY([Date]),
        "WeekNum", WEEKNUM([Date])
    )
```

**Important**: `MonthName` must use Sort-By-Column = `Month` so chart axes order Jan→Dec. Mark `DimDate` as a date table on the `Date` column.

---

### 4. Select Year as DAX Calculated Table

**Decision**: Define the disconnected `Select Year` table using a `DATATABLE` DAX expression as a calculated table in TMDL.

**Rationale**: Disconnected parameter tables with static values are best expressed as DAX calculated tables (constitution §7). It is the sole CY/PY authority via `SELECTEDVALUE('Select Year'[Year], 2023)`.

**Pattern** (TMDL):
```tmdl
table 'Select Year'

	calculatedTableExpression =
		DATATABLE(
			"Year", INTEGER,
			{
				{2020},
				{2021},
				{2022},
				{2023}
			}
		)

	column Year
		dataType: int64
		summarizeBy: none
		isNameInferred: true
		sourceColumn: [Year]
```

---

### 5. Encoding Strategy per File

**Decision**: Orders.csv and Location.csv use UTF-8 (Encoding=65001); Customers.csv and Products.csv use Windows-1252 (Encoding=1252).

**Rationale**: The Tableau analysis explicitly identifies character sets per file.

| File | Encoding | Encoding Value |
|------|----------|----------------|
| Orders.csv | UTF-8 | 65001 |
| Customers.csv | Windows-1252 | 1252 |
| Location.csv | UTF-8 | 65001 |
| Products.csv | Windows-1252 | 1252 |

---

### 6. Navigation Buttons in PBIR Format

**Decision**: Use `actionButton` visual type with `PageNavigation` action for cross-page navigation; Bookmark action for filter toggle.

**Rationale**: Power BI PBIR format supports actionButton visuals with navigation actions. Toggle requires bookmarks (created manually in Desktop).

**Alternatives considered**:
- Image visual with action → Less accessible, no hover states
- Buttons group → actionButton is the standard pattern

**Limitation**: Bookmark toggle requires manual bookmark creation in Power BI Desktop post-generation. The PBIP can define the button but not the bookmark state.

---

### 7. Cross-Filter Actions (Tableau → Power BI)

**Decision**: Tableau "on-select (auto-clear)" filter actions map to Power BI's default cross-filtering behavior (no extra configuration needed).

**Rationale**: Power BI visuals cross-filter each other natively when on the same page with related data. No explicit action configuration is needed in the report JSON.

---

## Research Summary

All NEEDS CLARIFICATION items from Technical Context are now resolved:

| Item | Resolution |
|------|-----------|
| CSV German locale M pattern | `Delimiter=";"`, culture in TransformColumnTypes, per-file encoding |
| TMDL relationship syntax | Single `relationships.tmdl` file, camelCase properties, oneDirection |
| DimDate generation | DAX `CALENDAR` calculated table over full calendar years of `Orders[Order Date]`, marked as date table |
| Select Year implementation | DAX `DATATABLE` calculated table in `Select Year.tmdl`, disconnected |
| File encodings | UTF-8 for Orders/Location, Windows-1252 for Customers/Products |
| Navigation buttons | actionButton visual + PageNavigation action |
| Cross-filter actions | Native Power BI cross-filtering (no config needed) |
