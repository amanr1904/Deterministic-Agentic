# Data Model: Sales & Customer Dashboards

> Aligned with `.specify/memory/SalesCustomerDashboards/star-schema-output.md` and
> `.specify/memory/SalesCustomerDashboards/dax-measures-output.md`. Table names are
> **unprefixed** (`Orders`, `Customers`, `Location`, `Products`) so the spec (FR-002/003)
> and every DAX measure resolve verbatim; `DimDate` and `Select Year` keep descriptive names.

## Entity Overview

6 tables: 1 fact (`Orders`) + 3 dimensions (`Customers`, `Location`, `Products`) + 1 generated date table (`DimDate`) + 1 disconnected parameter table (`Select Year`).

---

## Orders (Fact Table)

**Source**: `Data/Sales and Customer/Orders.csv` (semicolon-delimited, UTF-8 / 65001)
**Grain**: One row per order line item (unique Row ID)
**M typing culture**: `"de-DE"` (en_DE decimals/dates)

| Column | Data Type | Role | Hidden | Notes |
|--------|-----------|------|--------|-------|
| Row ID | Int64 | Degenerate dimension | Yes | Technical row id |
| Order ID | Text | Degenerate dimension | No | Used by `DISTINCTCOUNT` |
| Order Date | Date | FK → DimDate[Date] (active) | No | Transaction date |
| Ship Date | Date | FK → DimDate[Date] (inactive) | No | Fulfillment date |
| Ship Mode | Text | Attribute | No | Standard/Second/First/Same Day |
| Customer ID | Text | FK → Customers[Customer ID] | Yes | Natural key |
| Segment | Text | Attribute | No | Consumer/Corporate/Home Office |
| Postal Code | Int64 | FK → Location[Postal Code] | Yes | Natural key |
| Product ID | Text | FK → Products[Product ID] | Yes | Natural key |
| Sales | Decimal | Measure column | No | Revenue amount |
| Quantity | Int64 | Measure column | No | Units sold |
| Discount | Decimal | Measure column | No | Discount % |
| Profit | Decimal | Measure column | No | Profit amount |

**M Query Parameters**: `Delimiter = ";"`, `QuoteStyle = QuoteStyle.Csv`, `Encoding = 65001`, `Columns = 13`, type culture `"de-DE"`.

---

## Customers (Dimension)

**Source**: `Data/Sales and Customer/Customers.csv` (semicolon-delimited, Windows-1252 / 1252)
**Key**: Customer ID (text natural key, hidden)

| Column | Data Type | Role | Hidden | Notes |
|--------|-----------|------|--------|-------|
| Customer ID | Text | Primary key (→ Orders[Customer ID]) | Yes | e.g., "CG-12520" |
| Customer Name | Text | Display attribute | No | Full name; grouping field |

---

## Location (Dimension)

**Source**: `Data/Sales and Customer/Location.csv` (semicolon-delimited, UTF-8 / 65001)
**Key**: Postal Code (Int64 natural key, hidden)

| Column | Data Type | Role | Hidden | Data Category |
|--------|-----------|------|--------|---------------|
| Postal Code | Int64 | Primary key (→ Orders[Postal Code]) | Yes | PostalCode |
| City | Text | Attribute / slicer | No | City |
| State | Text | Attribute / slicer | No | StateOrProvince |
| Region | Text | Attribute / slicer | No | **(none — business region, not geo)** |
| Country/Region | Text | Attribute | No | Country |

**Hierarchy**: Geography → Country/Region > Region > State > City

---

## Products (Dimension)

**Source**: `Data/Sales and Customer/Products.csv` (semicolon-delimited, Windows-1252 / 1252)
**Key**: Product ID (text natural key, hidden)

| Column | Data Type | Role | Hidden | Notes |
|--------|-----------|------|--------|-------|
| Product ID | Text | Primary key (→ Orders[Product ID]) | Yes | e.g., "FUR-BO-10001798" |
| Category | Text | Attribute / slicer | No | Furniture/Office Supplies/Technology |
| Sub-Category | Text | Attribute / slicer | No | 17 sub-categories |
| Product Name | Text | Display attribute | No | Full product description |

**Hierarchy**: Product → Category > Sub-Category > Product Name

---

## DimDate (Generated Date Dimension)

**Source**: DAX calculated table via `CALENDAR` over full calendar years of `Orders[Order Date]`
**Key**: Date (date) — **Mark as Date Table: Yes**

| Column | Data Type | Notes |
|--------|-----------|-------|
| Date | Date | PK; relationship key; date-table marker column |
| Year | Int64 | `YEAR(Date)` |
| Quarter | Int64 | `QUARTER(Date)` (1–4) |
| Month | Int64 | `MONTH(Date)` (1–12); Sort-By for MonthName |
| MonthName | Text | `FORMAT(Date,"MMMM")`; **Sort By Month** |
| Day | Int64 | `DAY(Date)` |
| DayOfWeek | Int64 | `WEEKDAY(Date)` (1=Sun…7=Sat) |
| WeekNum | Int64 | `WEEKNUM(Date)` — required by KPI Avg week axis |

**Hierarchy**: Date → Year > Quarter > Month (label MonthName) > Day
**Axis usage**: KPI Sales/Profit Avg iterate `ALLSELECTED(DimDate[WeekNum])`; Min/Max measures iterate `ALLSELECTED(DimDate[MonthName])`.

---

## Select Year (Disconnected Parameter Table)

**Source**: DAX `DATATABLE` — **no relationships**
**Authority**: sole CY/PY source — `CY = SELECTEDVALUE('Select Year'[Year], 2023)`, `PY = CY − 1`

| Column | Data Type | Values | Default |
|--------|-----------|--------|---------|
| Year | Int64 | 2020, 2021, 2022, 2023 | 2023 |

**Usage**: single-select slicer bound to `'Select Year'[Year]`. `DimDate` is **never** used to derive CY/PY.

---

## Relationships

| # | From (Dim) | From Column | To (Fact) | To Column | Cardinality | Cross-Filter | Active |
|---|-----------|-------------|-----------|-----------|-------------|--------------|--------|
| 1 | Customers | Customer ID | Orders | Customer ID | 1:* | Single | Yes |
| 2 | Location | Postal Code | Orders | Postal Code | 1:* | Single | Yes |
| 3 | Products | Product ID | Orders | Product ID | 1:* | Single | Yes |
| 4 | DimDate | Date | Orders | Order Date | 1:* | Single | Yes |
| 5 | DimDate | Date | Orders | Ship Date | 1:* | Single | No (optional) |

**Notes**:
- Relationship 5 (Ship Date) is inactive — activate via `USERELATIONSHIP(Orders[Ship Date], DimDate[Date])`; may be omitted if not required.
- `Select Year` has NO relationships (disconnected parameter).
- All active relationships are single-direction (dimension → fact); no bidirectional filtering.
- Unmatched FK rows are preserved with blank dimension attributes (single-direction relationship does not drop fact rows).

---

## Measures (36 total)

| Display Folder | Count | Measures |
|----------------|-------|----------|
| Base Metrics | 5 | Total Sales, Total Profit, Total Quantity, Total Orders, Total Customers |
| Parameters | 2 | Current Year, Previous Year |
| Year-over-Year\Current Year | 6 | CY Sales, CY Profit, CY Quantity, CY Orders, CY Customers, CY Sales per Customer |
| Year-over-Year\Previous Year | 6 | PY Sales, PY Profit, PY Quantity, PY Orders, PY Customers, PY Sales per Customer |
| Year-over-Year\% Change | 6 | % Diff Sales, % Diff Profit, % Diff Quantity, % Diff Customers, % Diff Orders, % Diff Sales per Customers |
| KPI Indicators | 3 | KPI Sales Avg, KPI Profit Avg, KPI CY Less PY |
| KPI Indicators\Min Max | 6 | Min/Max Sales, Min/Max Profit, Min/Max Quantity, Min/Max Customers, Min/Max Orders, Min/Max Sales per Customers |
| LOD Equivalents | 2 | Nr of Orders per Customers, Grand Total CY Sales |

**Format strings**: currency KPIs use K-scaling (`\$#,##0,"K";-\$#,##0,"K"`); % Diff use ▲/▼ arrows (`▲ 0.0%;▼ -0.0%`); counts use `#,##0`.
**Authority rule**: CY/PY filter `Orders[Order Date]` via `FILTER(ALL(Orders[Order Date]), YEAR(...) = _CY)` — no measure inside a `CALCULATE` boolean filter, no `DimDate` dependence.
**Full DAX definitions**: `.specify/memory/SalesCustomerDashboards/dax-measures-output.md`.

---

## Validation Rules

- All foreign keys in `Orders` should have matching values in the dimension tables (referential integrity assumed; unmatched rows handled gracefully).
- `DimDate` must cover the full range of `Order Date` (and `Ship Date` if the inactive relationship is used).
- `Select Year` values (2020–2023) align with years present in the data; default 2023.
- No circular relationship paths; no bidirectional filtering on standard dim→fact relationships.
- All 36 measures evaluate without error when the Select Year slicer has a selection.
