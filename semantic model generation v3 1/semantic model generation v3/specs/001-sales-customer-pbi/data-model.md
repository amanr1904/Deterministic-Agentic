# Data Model: Sales & Customer Dashboards

## Entity Overview

6 tables: 1 fact + 4 dimensions + 1 disconnected parameter table.

---

## FactOrders (Fact Table)

**Source**: `Data/Sales and Customer/Orders.csv` (semicolon-delimited, UTF-8)  
**Grain**: One row per order line item (unique Row ID)  
**Row Count**: ~10,000 rows

| Column | Data Type | Role | Notes |
|--------|-----------|------|-------|
| Row ID | Int64 | Degenerate dimension | Unique identifier |
| Order ID | Text | Degenerate dimension | Multi-line orders share ID |
| Order Date | Date | FK → DimDate[Date] (active) | Transaction date |
| Ship Date | Date | FK → DimDate[Date] (inactive) | Fulfillment date |
| Ship Mode | Text | Attribute | Standard/Second/First/Same Day |
| Customer ID | Text | FK → DimCustomer[Customer ID] | Natural key |
| Segment | Text | Attribute | Consumer/Corporate/Home Office |
| Postal Code | Text | FK → DimLocation[Postal Code] | Natural key |
| Product ID | Text | FK → DimProduct[Product ID] | Natural key |
| Sales | Decimal | Measure column | Revenue amount |
| Quantity | Int64 | Measure column | Units sold |
| Discount | Decimal | Measure column | Discount % |
| Profit | Decimal | Measure column | Profit amount |

**M Query Parameters**: `Delimiter = ";"`, `QuoteStyle = QuoteStyle.Csv`, `Encoding = 65001`, `Culture = "de-DE"`

---

## DimCustomer (Dimension)

**Source**: `Data/Sales and Customer/Customers.csv` (semicolon-delimited, Windows-1252)  
**Key**: Customer ID (text, natural key)  
**Row Count**: ~793 rows

| Column | Data Type | Role | Notes |
|--------|-----------|------|-------|
| Customer ID | Text | Primary key | e.g., "CG-12520" |
| Customer Name | Text | Display attribute | Full name |

---

## DimLocation (Dimension)

**Source**: `Data/Sales and Customer/Location.csv` (semicolon-delimited, UTF-8)  
**Key**: Postal Code (text, natural key)  
**Row Count**: ~631 rows

| Column | Data Type | Role | Data Category |
|--------|-----------|------|---------------|
| Postal Code | Text | Primary key | PostalCode |
| City | Text | Attribute | City |
| State | Text | Attribute | StateOrProvince |
| Region | Text | Attribute | — |
| Country/Region | Text | Attribute | Country |

**Hierarchy**: Geography → Country/Region > Region > State > City > Postal Code

---

## DimProduct (Dimension)

**Source**: `Data/Sales and Customer/Products.csv` (semicolon-delimited, Windows-1252)  
**Key**: Product ID (text, natural key)  
**Row Count**: ~1862 rows

| Column | Data Type | Role | Notes |
|--------|-----------|------|-------|
| Product ID | Text | Primary key | e.g., "FUR-BO-10001798" |
| Category | Text | Attribute | Furniture/Office Supplies/Technology |
| Sub-Category | Text | Attribute | 17 sub-categories |
| Product Name | Text | Attribute | Full product description |

**Hierarchy**: Product Category → Category > Sub-Category > Product Name

---

## DimDate (Generated Dimension)

**Source**: M query (List.Dates pattern), fixed range 2020-01-01 to 2023-12-31  
**Key**: Date (date, natural key)  
**Row Count**: 1,461 rows  
**Mark as Date Table**: Yes (on Date column)

| Column | Data Type | Role | Notes |
|--------|-----------|------|-------|
| Date | Date | Primary key | Contiguous daily |
| Year | Int64 | Attribute | 2020–2023 |
| Quarter | Int64 | Attribute | 1–4 |
| QuarterLabel | Text | Display | "Q1"–"Q4" |
| Month | Int64 | Attribute | 1–12 |
| MonthName | Text | Display | January–December |
| MonthShort | Text | Display | Jan–Dec |
| Day | Int64 | Attribute | 1–31 |
| WeekNum | Int64 | Attribute | ISO week number |
| DayOfWeek | Int64 | Attribute | 1–7 |
| DayName | Text | Display | Monday–Sunday |
| YearMonth | Text | Sort key | "2023-01" format |

**Hierarchy**: Date → Year > Quarter > Month > Day

---

## SelectYear (Disconnected Parameter Table)

**Source**: DAX DATATABLE expression  
**Key**: Year (Int64)  
**Relationships**: NONE (disconnected)

| Column | Data Type | Role | Notes |
|--------|-----------|------|-------|
| Year | Int64 | Slicer value | 2020, 2021, 2022, 2023 |

**Usage**: Single-select slicer → `SELECTEDVALUE(SelectYear[Year])` in YoY measures.

---

## Relationships

| # | From Table | From Column | To Table | To Column | Cardinality | Cross-Filter | Active |
|---|-----------|-------------|----------|-----------|-------------|--------------|--------|
| 1 | DimCustomer | Customer ID | FactOrders | Customer ID | 1:* | Single | Yes |
| 2 | DimLocation | Postal Code | FactOrders | Postal Code | 1:* | Single | Yes |
| 3 | DimProduct | Product ID | FactOrders | Product ID | 1:* | Single | Yes |
| 4 | DimDate | Date | FactOrders | Order Date | 1:* | Single | Yes |
| 5 | DimDate | Date | FactOrders | Ship Date | 1:* | Single | No |

**Notes**:
- Relationship 5 (Ship Date) is inactive — use `USERELATIONSHIP(FactOrders[Ship Date], DimDate[Date])` when needed
- SelectYear has NO relationships (disconnected parameter)
- All relationships are single-direction (dimension → fact)
- No bidirectional filtering anywhere

---

## Measures (39 total, 8 display folders)

| Folder | Count | Key Measures |
|--------|-------|-------------|
| Core Metrics | 8 | Total Sales, Total Profit, Total Quantity, Order Count, Customer Count |
| Year-over-Year\Current Year | 6 | CY Sales, CY Profit, CY Quantity, CY Customers, CY Orders, CY Sales per Customer |
| Year-over-Year\Previous Year | 6 | PY Sales, PY Profit, PY Quantity, PY Customers, PY Orders, PY Sales per Customer |
| Year-over-Year\% Change | 6 | % Diff Sales, % Diff Profit, % Diff Quantity, % Diff Customers, % Diff Orders, % Diff Sales per Customers |
| KPI Indicators | 3 | KPI Sales Avg, KPI Profit Avg, KPI CY Less PY |
| KPI Indicators\Min Max | 6 | Min/Max Sales, Min/Max Profit, Min/Max Quantity, Min/Max Customers, Min/Max Orders, Min/Max Sales Per Customers |
| Parameters | 2 | Current Year, Previous Year |
| LOD Equivalents | 2 | Nr of Orders per Customer, Grand Total CY Sales |

**Full DAX definitions**: See `.specify/memory/dax-measures-output.md`

---

## Validation Rules

- All foreign keys in FactOrders must have matching values in dimension tables (referential integrity assumed)
- DimDate must cover full range of Order Date AND Ship Date values
- SelectYear values (2020–2023) must align with years present in the data
- No circular relationship paths
- All measures must evaluate without error when year slicer has a selection
