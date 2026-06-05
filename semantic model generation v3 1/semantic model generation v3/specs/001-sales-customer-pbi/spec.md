# Feature Specification: Sales & Customer Dashboards — Tableau to Power BI Migration

**Feature Branch**: `001-sales-customer-pbi`  
**Created**: 2026-06-04  
**Status**: Draft  
**Input**: User description: "Migrate 'Sales & Customer Dashboards' Tableau workbook to Power BI semantic model (.pbip)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load and Model Source Data (Priority: P1)

A Power BI analyst opens the generated `.pbip` project in Power BI Desktop. The four source CSV files (Orders, Customers, Location, Products) load correctly with proper data types, a generated `DimDate` date dimension is present, and the star-schema relationships resolve without errors.

**Why this priority**: Without correct data loading and relationships, no measures or visuals can function. This is the foundational layer.

**Independent Test**: Open `Output/SalesCustomerDashboards/SalesCustomerDashboards.pbip` in Power BI Desktop → all four source tables plus `DimDate` appear in the model view → relationships connect correctly → data preview shows rows with correct types (dates, numbers, text).

**Acceptance Scenarios**:

1. **Given** the PBIP project is opened in Power BI Desktop, **When** the model loads, **Then** all four source tables (Orders, Customers, Location, Products) plus a generated `DimDate` table are visible with data rows.
2. **Given** the CSV files use semicolon delimiters and German locale, **When** M queries execute, **Then** columns parse correctly (decimals as numbers, dates as dates, text as text).
3. **Given** the star-schema relationships are defined, **When** the model diagram is viewed, **Then** Orders connects to Customers (via Customer ID), Orders connects to Location (via Postal Code), Orders connects to Products (via Product ID), and `DimDate` connects to Orders (via Order Date).
4. **Given** the relationships are configured, **When** cross-filtering is tested, **Then** filtering a Customer in Customers table correctly filters Orders rows, and filtering a year in `DimDate` correctly filters Orders rows.

---

### User Story 2 - Calculate Year-Over-Year Measures (Priority: P1)

A report author uses the "Select Year" parameter (slicer) to choose a year (2020–2023). All CY/PY measures, % Diff measures, and KPI indicators calculate correctly relative to the selected year.

**Why this priority**: The 28 calculated fields form the analytical core of the dashboard. Without correct measures, the migration has no business value.

**Independent Test**: Create a card visual bound to `[CY Sales]`, set the year slicer to 2023 → card shows the sum of Sales for 2023. Change slicer to 2022 → card updates to show 2022 total. Place `[% Diff Sales]` in another card → shows correct percentage change between selected year and prior year.

**Acceptance Scenarios**:

1. **Given** "Select Year" is set to 2023, **When** `[CY Sales]` is evaluated, **Then** it returns the total Sales for orders with Order Date in year 2023.
2. **Given** "Select Year" is set to 2023, **When** `[PY Sales]` is evaluated, **Then** it returns the total Sales for orders with Order Date in year 2022.
3. **Given** CY and PY Sales are calculated, **When** `[% Diff Sales]` is evaluated, **Then** it returns `(CY Sales - PY Sales) / PY Sales` formatted as a percentage.
4. **Given** "Select Year" is set to 2021, **When** `[KPI Sales Avg]` is evaluated, **Then** it returns an indicator value comparing CY Sales against the average.
5. **Given** monthly data exists, **When** `[Min/Max Sales]` is evaluated per month, **Then** it correctly identifies the months with minimum and maximum CY Sales values.

---

### User Story 3 - Customer-Level Analytics (Priority: P2)

A report author analyzes customer-level KPIs including CY/PY Customers count, Sales per Customer, and Orders per Customer. These metrics help identify customer behavior trends year-over-year.

**Why this priority**: Customer metrics are a secondary analytical dimension that depends on the core CY/PY framework being correct first.

**Independent Test**: Place `[CY Customers]` in a card with year slicer set to 2023 → shows count of distinct customers who ordered in 2023. Place `[CY Sales per Customer]` → shows `CY Sales / CY Customers`. Place `[% Diff Customers]` → shows year-over-year change in customer count.

**Acceptance Scenarios**:

1. **Given** "Select Year" is set to 2023, **When** `[CY Customers]` is evaluated, **Then** it returns the distinct count of Customer IDs with orders in 2023.
2. **Given** CY Sales and CY Customers are calculated, **When** `[CY Sales per Customer]` is evaluated, **Then** it returns `CY Sales / CY Customers`.
3. **Given** CY and PY Customers are calculated, **When** `[% Diff Customers]` is evaluated, **Then** it returns the percentage change correctly.
4. **Given** a customer placed multiple orders, **When** `[Nr of Orders per Customers]` is evaluated for that customer, **Then** it returns their order count.

---

### User Story 4 - Reproduce Dashboards, Navigation, and Interactivity (Priority: P3)

A report consumer views two report pages — Sales Dashboard and Customer Dashboard (1200×800) — that reproduce the Tableau dashboards: KPI trend visuals, Subcategory Comparison, Weekly Trends, Customer Distribution, and Top Customers, each with the shared Select Year + Category / Sub-Category / Region / State / City filters. They navigate between pages using navigation buttons, and a toggle button shows/hides the filter panel on each page.

**Why this priority**: Reproducing the dashboards and navigation completes the user-facing migration, but it depends on the model and measures (US1–US3) being correct first. The report is analytically functional without the buttons.

**Independent Test**: Open the report → both Sales Dashboard and Customer Dashboard pages render their visuals and the shared filter panel. Click "Sales Dashboard" button on Customer page → navigates to Sales page. Click toggle button → filter panel visibility changes.

**Acceptance Scenarios**:

1. **Given** the report is opened, **When** the Sales Dashboard page renders, **Then** the KPI Sales/Profit/Quantity trend visuals, Subcategory Comparison, Weekly Trends, the Select Year control, and Category/Sub-Category/Region/State/City filters are present.
2. **Given** the report is opened, **When** the Customer Dashboard page renders, **Then** the KPI Customers/Sales Per Customer/Orders visuals, Customer Distribution, and Top Customers visuals are present with the shared filter panel.
3. **Given** the user is on the Customer Dashboard page, **When** they click the "Sales Dashboard" navigation button, **Then** the report navigates to the Sales Dashboard page.
4. **Given** the user is on the Sales Dashboard page, **When** they click the "Customer Dashboard" navigation button, **Then** the report navigates to the Customer Dashboard page.
5. **Given** the filter panel is hidden, **When** the user clicks the toggle button, **Then** the filter panel becomes visible.
6. **Given** the source workbook contains unused worksheets (Test KPI, Test KPI2, Test Max Min), **When** the report is generated, **Then** those worksheets are excluded from both pages.

---

### Edge Cases

- What happens when "Select Year" is set to 2020 and `[PY Sales]` tries to access 2019 data (which may not exist)? → Measures should return BLANK() gracefully.
- What happens when a customer has orders in CY but not PY (prior year has no data)? → `[% Diff]` measures should handle division by zero (return BLANK() when PY = 0 or BLANK).
- What happens when a Postal Code in Orders is null or doesn't match any row in Location? → Unmatched rows should still appear in Orders with blank geography fields (the dimension→fact relationship must not drop fact rows).
- What happens when decimal Sales values use comma separators in the CSV? → M query must handle German locale parsing (semicolon delimiter, comma as decimal separator).
- What happens to the unused Tableau worksheets (Test KPI, Test KPI2, Test Max Min)? → They are excluded from the migrated report (not present on any dashboard).
- What happens to Tableau currency/percent formatting (K-suffix thousands scaling, ▲/▼ percent trend arrows)? → Measure `formatString` values should preserve the intended currency/percent display so KPIs read the same as in Tableau.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load four CSV source files (Orders.csv, Customers.csv, Location.csv, Products.csv) from the `Data/Sales and Customer/` folder using semicolon delimiter and German locale settings.
- **FR-002**: System MUST define a star-schema model with Orders as the fact table and Customers, Location, Products as dimension tables, plus a generated `DimDate` date dimension covering the Order Date range for time intelligence.
- **FR-003**: System MUST create relationships: Orders[Customer ID] → Customers[Customer ID] (many-to-one), Orders[Postal Code] → Location[Postal Code] (many-to-one), Orders[Product ID] → Products[Product ID] (many-to-one), and DimDate[Date] → Orders[Order Date] (one-to-many, single direction).
- **FR-003a**: System MUST generate a `DimDate` table marked as a date table, with at minimum Date, Year, Month Number, Month Name, and Quarter columns spanning the minimum-to-maximum Order Date.
- **FR-004**: System MUST implement a "Select Year" parameter as a disconnected table with values 2020, 2021, 2022, 2023 (default: 2023) as the authoritative source for the current year (CY = `SELECTEDVALUE('Select Year'[Year], 2023)`, PY = CY − 1); the related `DimDate` dimension MUST NOT be used to derive CY/PY and is reserved for trend-axis grouping only.
- **FR-005**: System MUST implement all 28+ DAX measures migrated from Tableau calculated fields: CY/PY pairs for Sales, Profit, Quantity, Customers, Orders; % Diff measures for each; KPI indicators; Min/Max identifiers; Sales per Customer metrics.
- **FR-005a**: System MUST represent the `WINDOW_AVG` / `WINDOW_MAX` / `WINDOW_MIN` table calculations (KPI Avg indicators, Min/Max measures) as DAX measures comparing each displayed point against `AVERAGEX` / `MAXX` / `MINX` over `ALLSELECTED(<axis>)` — i.e., the displayed category set — acknowledging that exact Tableau visual-scope replication may require report-side filter context.
- **FR-005b**: System MUST represent the FIXED LOD fields as CALCULATE patterns: `Nr of Orders per Customers` via `CALCULATE(DISTINCTCOUNT(...), ALLEXCEPT(...))` scoped to CY, and `{SUM([CY Sales])}` via `CALCULATE([CY Sales], REMOVEFILTERS())`.
- **FR-006**: System MUST handle division-by-zero scenarios in % Diff measures by guarding every ratio with `DIVIDE()` (no fallback argument) so a zero or blank prior-year value returns BLANK() rather than an error or infinity.
- **FR-007**: System MUST correctly parse Order Date and Ship Date columns as date types from the CSV source.
- **FR-008**: System MUST reproduce the two dashboards (Sales Dashboard, Customer Dashboard, 1200×800) as report pages with their visuals, the shared Select Year control, the Category/Sub-Category/Region/State/City filters, and navigation buttons (2 page navigation + 1 filter-panel toggle per dashboard).
- **FR-009**: System MUST output all PBIP artifacts to `Output/SalesCustomerDashboards/` following standard PBIP folder structure (.pbip, .SemanticModel/, .Report/).
- **FR-010**: System MUST follow constitution rules from `.specify/memory/constitution.md` for naming conventions, DAX standards, and relationship patterns.
- **FR-011**: System MUST preserve the source field formatting intent — currency measures with thousands ("K") scaling and % Diff measures with ▲/▼ trend-arrow percent formatting — via measure `formatString` values.
- **FR-012**: System MUST exclude the unused Tableau worksheets (Test KPI, Test KPI2, Test Max Min) from the migrated report; only the 12 dashboard-used worksheets are reproduced.

### Key Entities

- **Orders (Fact Table)**: Central transaction table containing sales events. Key attributes: Order ID, Order Date, Ship Date, Ship Mode, Sales, Quantity, Discount, Profit. Foreign keys: Customer ID, Postal Code, Product ID.
- **Customers (Dimension)**: Customer master data. Key attributes: Customer ID, Customer Name. Grain: one row per customer.
- **Location (Dimension)**: Geographic hierarchy. Key attributes: Postal Code, City, State, Region, Country/Region. Grain: one row per postal code.
- **Products (Dimension)**: Product catalog with category hierarchy. Key attributes: Product ID, Category, Sub-Category, Product Name. Grain: one row per product.
- **DimDate (Generated Date Dimension)**: Contiguous date table spanning the Order Date range, marked as the model's date table. Key attributes: Date, Year, Quarter, Month Number, Month Name. Related to Orders via Order Date. Grain: one row per day.
- **Select Year (Disconnected Parameter Table)**: Contains year values (2020–2023, default 2023) for dynamic CY/PY calculation. No relationships to other tables. It is the **authoritative source for the CY value** (CY = `SELECTEDVALUE('Select Year'[Year], 2023)`, PY = CY − 1), mirroring the Tableau `Select Year` parameter. The related `DimDate` dimension is **not** used to choose CY/PY; `DimDate` drives only the monthly/weekly/quarter trend axes on the KPI visuals. (Resolved 2026-06-05 — see Clarifications.)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `.pbip` project opens in Power BI Desktop without any loading or schema errors.
- **SC-002**: All four source tables display data rows matching the source CSV file row counts.
- **SC-003**: All four relationships (three dimensions + DimDate) resolve correctly — filtering a dimension or DimDate table correctly filters the Orders fact table.
- **SC-004**: All 28+ DAX measures calculate without evaluation errors when placed on a visual with the year slicer active.
- **SC-004a**: Currency KPI measures display with thousands ("K") scaling and % Diff measures display with ▲/▼ percent arrows, matching the Tableau source formatting intent.
- **SC-005**: The "Select Year" slicer defaults to 2023 and correctly drives CY/PY measure calculations for any selected year.
- **SC-006**: % Diff measures return BLANK() (not errors) when prior-year values are zero or missing.
- **SC-007**: Navigation buttons successfully switch between Sales Dashboard and Customer Dashboard pages.
- **SC-008**: PBIP validation tools (`tmdl-validate` and `validate_pbip.py`) pass with exit code 0 (no errors).

## Assumptions

- Source CSV files are semicolon-delimited with German locale (comma as decimal separator) — M queries will use `Delimiter = ";"` and `Culture = "de-DE"`.
- All four CSV files are present and well-formed in `Data/Sales and Customer/` at generation time.
- The "Select Year" parameter is implemented as a disconnected DAX table (not a Power Query parameter) to enable dynamic measure switching.
- A `DimDate` date dimension is generated (via DAX `CALENDAR`/`CALENDARAUTO` over the Order Date range) and marked as the model's date table; CY/PY measures continue to compare against the disconnected Select Year value, while DimDate enables month/week/quarter axes used by the KPI trend visuals.
- Unused Tableau worksheets (Test KPI, Test KPI2, Test Max Min) are intentionally excluded from the migrated report.
- Customer ID values in Orders.csv have matching entries in Customers.csv (referential integrity assumed for the primary use case; unmatched rows handled gracefully).
- The PBIP output follows Power BI Projects format compatible with Power BI Desktop (June 2024+).
- Navigation buttons are implemented in the report layer (PBIR format), not the semantic model.
- Constitution rules (when available) take precedence over default patterns for naming and DAX style.
- The `~Sales & Customer Dashboards__26984.twbr` file is a Tableau recovery file and is NOT used as input — only `Sales & Customer Dashboards.twb` is the source.

## Clarifications

### Session 2026-06-04

- Q: Measures vs calculated columns for migrated Tableau calculated fields? → A: Prefer DAX measures for all calculations; calculated columns only for relationship keys or row-level filtering (constitution §3: "Measures over calculated columns").
- Q: How to model multi-table joins (Orders → Customers, Location, Products)? → A: Star schema with Orders as fact, three dimensions joined on natural keys matching Tableau join keys — Customer ID, Postal Code, Product ID (constitution §1: natural keys preferred for single-source star schemas).
- Q: How to migrate Tableau table calculations (WINDOW_AVG, WINDOW_MAX, WINDOW_MIN)? → A: Map to CALCULATE with ALLSELECTED or AVERAGEX/MAXX/MINX patterns within visual context (constitution §3: Table Calc → CALCULATE with date range or ALLSELECTED).
- Q: How to migrate LOD FIXED expressions? → A: CALCULATE with REMOVEFILTERS/ALL to remove all filters except the specified dimension (constitution §3: "LOD Fixed → CALCULATE with ALL/REMOVEFILTERS").
- Q: How to assign data categories for geographic columns? → A: Apply semantic roles from Tableau: City → DataCategory=City, State → DataCategory=StateOrProvince, Country/Region → DataCategory=Country, Postal Code → DataCategory=PostalCode.
- Q: How to implement the "Select Year" parameter (integer list: 2020–2023)? → A: Disconnected DATATABLE with Year values + SELECTEDVALUE measure to consume selected year in CY/PY calculations (constitution §7: Integer list → Disconnected DATATABLE with Label/Value columns + SELECTEDVALUE).
- Q: How to implement navigation buttons between Sales/Customer pages? → A: actionButton visuals with PageNavigation action for cross-page nav and Bookmark action for filter panel toggle.
- Q: How to handle German locale CSV parsing (semicolons, comma decimals)? → A: M query uses `Delimiter = ";"`, `Culture = "de-DE"`, `Encoding = 65001` (UTF-8), `QuoteStyle = QuoteStyle.Csv` per constitution §5.

### Session 2026-06-05

> Automated migration pass — the following underspecified areas were resolved with constitution-aligned default decisions (no interactive input) and encoded as documented defaults rather than open `[NEEDS CLARIFICATION]` blockers.

- Q: Select Year vs DimDate authority for CY/PY? → A: The disconnected `Select Year` table (values 2020–2023, default 2023) is the **authoritative CY selector**, mirroring the Tableau parameter: CY = `SELECTEDVALUE('Select Year'[Year], 2023)`, PY = CY − 1. `DimDate` is used only for the monthly/weekly/quarter **trend axes**, never to choose CY/PY. Rationale: preserves Tableau parameter-driven semantics; avoids ambiguous dual-authority where a DimDate slicer and the year parameter could disagree.
- Q: How to represent `WINDOW_AVG` / `WINDOW_MAX` / `WINDOW_MIN` table calculations (KPI Avg, Min/Max measures)? → A: Visual-level/measure DAX comparing each displayed category point against `AVERAGEX` / `MAXX` / `MINX` evaluated over the displayed category set via `ALLSELECTED` (e.g., `AVERAGEX(ALLSELECTED(<axis>), [CY Sales])`). Rationale: constitution §3 maps Table Calc → CALCULATE/ALLSELECTED with windowing aggregates. Note: exact Tableau visual-scope (partition/addressing) replication may need report-side filter context; documented as a minor report-side configuration point.
- Q: How to represent the FIXED LOD fields `Nr of Orders per Customers` (`{FIXED [CY Customers]: COUNTD([CY Orders])}`) and `{SUM([CY Sales])}`? → A: DAX `CALCULATE` with `ALLEXCEPT` / `VALUES` patterns — `Nr of Orders per Customers` = `CALCULATE(DISTINCTCOUNT(Orders[Order ID]), ALLEXCEPT(Orders, Customers[Customer ID]))` scoped to CY; `{SUM([CY Sales])}` (table-scoped grand total) = `CALCULATE([CY Sales], REMOVEFILTERS())`. Rationale: constitution §3 LOD Fixed → CALCULATE + ALL/REMOVEFILTERS, LOD Exclude → CALCULATE + ALLEXCEPT.
- Q: How should % Diff measures behave when the prior-year (PY) value is 0 or BLANK? → A: Return `BLANK()` by guarding every ratio with `DIVIDE(numerator, denominator)` (no third argument), so divide-by-zero/blank yields BLANK() rather than an error or Infinity. Rationale: constitution §3 "DIVIDE() over `/`"; matches FR-006 / SC-006 / Edge Cases.
- Q: Currency symbol & scaling for KPI measures (source is € / en_DE but Tableau format strings embed `$` with "K" scaling)? → A: Preserve a currency `formatString` with thousands "K" scaling (e.g., `\$#,##0,"K"`) per FR-011; the literal symbol choice (`$` vs `€`) is treated as a **minor downstream config point** and the Tableau-embedded `$` is preserved by default. Rationale: format intent (K-scaling, ▲/▼ percent arrows) matters more than symbol; symbol is trivially adjustable in Desktop.
- Q: Are the unused `Test KPI`, `Test KPI2`, `Test Max Min` worksheets in scope? → A: No — excluded from both report pages (not present on any dashboard). Rationale: confirms FR-012 / SC-007 scope; only the 12 dashboard-used worksheets are reproduced.
