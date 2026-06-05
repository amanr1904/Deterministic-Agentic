# Specification: Q3 Dealer Buying Event Tableau → Power BI Migration

## Overview
Migrate the "(Active) 2021 Q3 Dealer Buying Event.twb" Tableau workbook (Harley-Davidson dealer launch report) to a Power BI semantic model (.pbip) and report. The source is a single denormalized Excel sheet exported to `Data/Q3 Buyer/Q3LaunchData 1.csv` (~193,928 rows, 52 columns including pre-materialized aliases).

## Source Analysis
- **Workbook**: `Data/Q3 Buyer/(Active) 2021 Q3 Dealer Buying Event.twb`
- **Tableau Version**: 18.1 (Build 2020.4.1)
- **Datasource**: Single Excel sheet (`Sheet1`) — connection class `excel-direct`. CSV replacement: `Q3LaunchData 1.csv`
- **Parameters**: 2 — `Rows Displayed` (integer list 5/10/20/50/All) and `Rank Sort Measure` (string list, 4 ranking options)
- **Calculated Fields**: 23 (mostly drill-path aliases; 4 real calcs: `Master Style`, `Style Count`, `Region`, `Measure for Rank` + 4 table calcs: `Rank`, `Rank (Order $)`, `Rank Filter`, `% of Total`)
- **Worksheets**: 49
- **Dashboards**: 5 (Launch Report Dashboard, Delivery Season Summary, Data Detail, Slide View 1, Slide View 2)

## Model Design (Single-Table Rule per Constitution §0)

Tableau uses a **single flat table** with no joins → do NOT decompose. Keep `LaunchData` as one table; add a generated `DimDate` and two disconnected parameter tables.

### Tables (4 total)
1. **LaunchData** — single fact table (grain: one row per Item Code × Sales Area × Date × Reorder Type combination). 44 useful columns retained after dropping 8 Tableau drill-alias duplicates (trailing-space columns + redundant pre-materialized Measure for Rank / Style Count column).
2. **DimDate** — generated calendar covering 2020-01-01 to 2022-12-31 (encompasses source `Date` range), with Year, Month, MonthName, Quarter + Date Hierarchy.
3. **Parameter_RowsDisplayed** — disconnected: rows 5, 10, 20, 50, 10000 (10000 = "All").
4. **Parameter_RankSortMeasure** — disconnected: 4 string values matching the Tableau parameter.

### Columns dropped (Tableau drill-alias duplicates already in CSV)
`Delivery Month `, `Delivery Season `, `Region `, `Sales Area `, `Style Code `, `Style Description ` (all trailing-space copies), plus `Measure for Rank` (recreated as DAX) and `Style Count` column (recreated as DAX measure).

### Relationships (1)
- **LaunchData[Date] → DimDate[Date]** (many-to-one, single direction)

Parameter tables are disconnected (no relationship — values consumed via `SELECTEDVALUE`).

## DAX Measures (LaunchData table)

### Core Metrics
| Measure | Formula | Format | Folder |
|---------|---------|--------|--------|
| Total Order $ | `SUM(LaunchData[Order $ (USD)])` | `$#,##0` | Core Metrics |
| Total Order $ (Dealer Net) | `SUM(LaunchData[Order $ (U.S. Dealer Net)])` | `$#,##0` | Core Metrics |
| Total Order $ (MSRP) | `SUM(LaunchData[Order $ (U.S. MSRP)])` | `$#,##0` | Core Metrics |
| Total Order $ (Cost) | `SUM(LaunchData[Order $ (U.S. Cost)])` | `$#,##0` | Core Metrics |
| Total Margin $ | `SUM(LaunchData[Margin $])` | `$#,##0` | Core Metrics |
| Total Order Quantity | `SUM(LaunchData[Order Quantity])` | `#,##0` | Core Metrics |
| Total Quantity (Units) | `SUM(LaunchData[Sum of Quantity (Units)])` | `#,##0` | Core Metrics |
| Total Extra Quantity (Units) | `SUM(LaunchData[Sum of Extra Quantity (Units)])` | `#,##0` | Core Metrics |
| Style Count | `DISTINCTCOUNT(LaunchData[Master Style])` | `#,##0` | Core Metrics |
| Avg MSRP | `AVERAGE(LaunchData[MSRP])` | `$#,##0.00` | Core Metrics |
| Avg Dealer Net | `AVERAGE(LaunchData[Dnet])` | `$#,##0.00` | Core Metrics |

### Percentages (Table-calc replacements)
| Measure | Formula | Format | Folder |
|---------|---------|--------|--------|
| Order $ % of Total | `DIVIDE([Total Order $], CALCULATE([Total Order $], ALLSELECTED(LaunchData)), 0)` | `0.00%` | Ratios |
| Order Qty % of Total | `DIVIDE([Total Order Quantity], CALCULATE([Total Order Quantity], ALLSELECTED(LaunchData)), 0)` | `0.00%` | Ratios |
| Margin % | `DIVIDE([Total Margin $], [Total Order $], 0)` | `0.00%` | Ratios |

### Parameter-driven Ranking
| Measure | Formula | Format | Folder |
|---------|---------|--------|--------|
| Selected Rows Displayed | `SELECTEDVALUE(Parameter_RowsDisplayed[Rows Displayed], 10)` | `#,##0` | Ranking |
| Selected Rank Sort Measure | `SELECTEDVALUE(Parameter_RankSortMeasure[Rank Sort Measure], "Order $ (Decending)")` | — | Ranking |
| Measure for Rank | `VAR sel = [Selected Rank Sort Measure] RETURN SWITCH(sel, "Order $ (Accending)", -[Total Order $], "Order Units (Accending)", -[Total Order Quantity], "Order $ (Decending)", [Total Order $], "Order Units (Decending)", [Total Order Quantity])` | `0` | Ranking |
| Rank (Parameter) | `RANKX(ALLSELECTED(LaunchData[Base Part Number]), [Measure for Rank], , DESC, Dense)` | `0` | Ranking |
| Rank (Order $) | `RANKX(ALLSELECTED(LaunchData[Base Part Number]), [Total Order $], , DESC, Dense)` | `0` | Ranking |
| Top N Filter | `IF([Rank (Parameter)] <= [Selected Rows Displayed], 1, 0)` | `0` | Ranking |

### Time Intelligence
| Measure | Formula | Format | Folder |
|---------|---------|--------|--------|
| Order $ YTD | `CALCULATE([Total Order $], DATESYTD(DimDate[Date]))` | `$#,##0` | Time Intelligence |
| Order $ MTD | `CALCULATE([Total Order $], DATESMTD(DimDate[Date]))` | `$#,##0` | Time Intelligence |

### Calculated Columns (on LaunchData)
| Column | Formula | Notes |
|--------|---------|-------|
| `Region (Derived)` | `SWITCH(TRUE(), LaunchData[Sales Area] = "Canada", "Canada", LaunchData[Sales Area] = "United States of America", "USA", LaunchData[Macro Area])` | Mirrors Tableau Region calc; CSV `Region` column also retained for parity |

> Master Style is already pre-materialized in the CSV (column index 20). No DAX needed.

## Report Layout (5 pages, one per Tableau dashboard)

Theme: Professional light (white canvas, #F5F5F5 visual backgrounds, #E0E0E0 borders, 1280×720 FitToPage).

### Page 1 — Launch Report Dashboard (main)
- Slicers (top): Delivery Season, Region, Rank Sort Measure, Rows Displayed
- KPI cards: Total Order $, Total Order Quantity, Style Count, Margin %
- Bar charts: Order $ by Product Category, Order $ by Garment Type, Order $ by Product Gender, Order $ by Region (MacroArea)
- Table: Top Parts (Item Code, Style Description, Total Order $, Order Qty, Rank) filtered by Top N Filter = 1
- Line chart: Sales by Date (Order $ over Date)

### Page 2 — Delivery Season Summary
- Slicer: Delivery Season
- Cards: Total Order $, Style Count
- Stacked column: Order $ by Delivery Season × Product Category
- Donut: Order $ % by Delivery Season

### Page 3 — Data Detail
- Slicers: Delivery Season, Region, Product Category
- Full-width table: all key dimension columns + Total Order $, Order Quantity

### Page 4 — Slide View 1
- Cards: Total Order $, Total Order Quantity, Style Count
- Bar: Top 10 Categories by Order $
- Line: Order $ trend over Date

### Page 5 — Slide View 2
- Cards: Margin %, Avg MSRP, Avg Dealer Net
- Bar: Order $ by Region
- Donut: Order Quantity by Product Gender

## Data Source
- CSV path: `C:\Users\AmanRajMAQSoftware\OneDrive - MAQ Software\Documents\semantic model generation v2\Data\Q3 Buyer\Q3LaunchData 1.csv`
- M Query: `Csv.Document(File.Contents(...), [Delimiter=",", Columns=52, Encoding=65001, QuoteStyle=QuoteStyle.Csv])` → promote headers → type cast → remove duplicate alias columns.

## Acceptance Criteria
1. All 4 tables created with correct columns and data types
2. LaunchData → DimDate relationship established (many-to-one, single direction)
3. All DAX measures defined in correct display folders with correct format strings
4. 5 report pages each with required visuals, slicers, borders, and titles
5. `validate_pbip.py` exits 0 on the project root
6. `tmdl-validate` reports no errors on the SemanticModel definition folder
7. PBIP opens in Power BI Desktop without errors
