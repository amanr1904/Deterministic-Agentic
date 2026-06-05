# Feature Specification: Q3 Dealer Buying Event — Tableau to Power BI Migration

**Feature Branch**: `004-q3-dealer-buying-event-pbi`  
**Created**: 2026-06-05  
**Status**: Draft  
**Input**: User description: "Migrate '(Active) 2021 Q3 Dealer Buying Event' Tableau workbook to a Power BI semantic model (.pbip) and report. Single flat CSV source, list parameters for Top-N rows and rank sort, rank/percent-of-total calculated fields."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load and Model the Dealer Buying Event Data (Priority: P1)

A Power BI analyst opens the generated `.pbip` project in Power BI Desktop. The dealer pre-season buying-event order data loads from the local CSV file (`Data/Q3 Buyer/Q3LaunchData 1.csv`) into a single table with correct data types, a generated `DimDate` date dimension is present for time-based delivery analysis, and the model opens without errors.

**Why this priority**: Without the source data loading correctly with proper types, no measures, ranking, or visuals can function. This is the foundational layer.

**Independent Test**: Open `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.pbip` in Power BI Desktop → the launch-data table appears with all rows from the CSV → product, geography, delivery-timing, and order-measure columns are visible with correct data types (numbers for order measures, dates for delivery date, text for product/geography attributes) → a `DimDate` table is present and related to the launch-data table.

**Acceptance Scenarios**:

1. **Given** the PBIP project is opened in Power BI Desktop, **When** the model loads, **Then** the single launch-data table contains all rows from `Q3LaunchData 1.csv` with correct data types.
2. **Given** the TWB declared an Excel source that is absent from the workspace, **When** the M query executes, **Then** it binds to the local CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` (not the missing Excel path) and loads successfully.
3. **Given** the model loads, **When** the user inspects the Fields pane, **Then** product attributes (Style, Style Code, Base Part, Category, Family, Sub-Family, Gender, Garment Type, Color, Collection), geography attributes (Macro Area, Micro Area, Sales Area), and delivery-timing attributes (Delivery Season, Delivery Month, Delivery Date, Year, Month, Date) are present.
4. **Given** the `DimDate` table exists, **When** the user examines relationships, **Then** an active relationship connects the launch-data delivery date to `DimDate[Date]`.

---

### User Story 2 - Calculate Order, Margin, and Style Measures (Priority: P1)

A report author places order-value, quantity, margin, and style-count measures on visuals and breaks them down by product, geography, and delivery-timing attributes. The measures calculate correctly and match the source order data.

**Why this priority**: The order measures and derived calculated fields form the analytical core of the buying-event report. Without correct measures, the migration delivers no business value.

**Independent Test**: Place an Order $ measure on a card and break it down by Category → values aggregate correctly per category. Place the Style Count measure on a card → it returns the distinct count of master styles. Place a Margin $ measure alongside Order $ → both reconcile against the source CSV totals.

**Acceptance Scenarios**:

1. **Given** the model is loaded, **When** the user places an Order $ measure on a card, **Then** it returns the total order value across the filtered rows.
2. **Given** the model is loaded, **When** the user places the Style Count measure on a card, **Then** it returns the distinct count of Master Style (migrating Tableau `CountD([Master Style])`, where Master Style = `LEFT([Style Code], 8)`).
3. **Given** the model is loaded, **When** the user breaks an order measure down by Category, Family, Gender, Garment Type, Color, or Collection, **Then** the value is correctly split across those product attributes.
4. **Given** the model is loaded, **When** the user breaks an order measure down by Region, **Then** the Region grouping reflects the Tableau rule (Sales Area "Canada" → "Canada", "United States of America" → "USA", otherwise Macro Area).
5. **Given** the model is loaded, **When** the user places a Margin $ measure and the order-cost/dealer-net/MSRP order measures on a visual, **Then** each returns its respective aggregated source value.

---

### User Story 3 - Rank and Top-N Filtering Driven by Parameters (Priority: P2)

A report author uses two parameter controls — "Rows Displayed" (5 / 10 / 20 / 50 / All) and "Rank Sort Measure" (Order $ or Order Units, ascending or descending) — to rank items and limit the report to the top-N rows. The ranking and percent-of-total behave like the Tableau source.

**Why this priority**: The parameter-driven ranking and Top-N filtering is the distinctive interactive feature of the source workbook, but it depends on the core measures (US2) being correct first.

**Independent Test**: Place a ranked table of items with an Order $ measure → set "Rank Sort Measure" to "Order $ (Descending)" → items rank from highest to lowest order value. Set "Rows Displayed" to 10 → only the top 10 ranked items remain. Add a percent-of-total measure → each item shows its share of the visible total.

**Acceptance Scenarios**:

1. **Given** the "Rank Sort Measure" parameter is set to "Order $ (Descending)" (default), **When** items are ranked, **Then** the rank orders items from highest to lowest Order $.
2. **Given** the "Rank Sort Measure" parameter is set to "Order Units (Ascending)", **When** items are ranked, **Then** the rank orders items from lowest to highest order quantity.
3. **Given** the "Rows Displayed" parameter is set to 10 (default), **When** the Top-N flag is evaluated, **Then** only items with rank ≤ 10 are flagged as visible.
4. **Given** the "Rows Displayed" parameter is set to "All" (value 10000), **When** the Top-N flag is evaluated, **Then** all items are flagged as visible.
5. **Given** a percent-of-total measure is on the visual, **When** it is evaluated for each item, **Then** it returns that item's Order $ divided by the total Order $ across the currently selected items.

---

### User Story 4 - Reproduce Dashboards as Report Pages (Priority: P3)

A report consumer views a small set of Power BI report pages that reproduce the five Tableau dashboards (Launch Report Dashboard, Delivery Season Summary, Data Detail, and the slide views) — including launch-summary breakdowns by category/family/gender/macro-area, top-parts ranking tables, sales-by-date trends, and the parameter controls.

**Why this priority**: Reproducing the dashboards completes the user-facing migration, but it depends on the model, measures, and ranking (US1–US3) being correct first. The model is analytically functional without the report pages.

**Independent Test**: Open the report → the launch-summary, top-parts ranking, and sales-by-date pages render their visuals with the "Rows Displayed" and "Rank Sort Measure" parameter controls present and functional.

**Acceptance Scenarios**:

1. **Given** the report is opened, **When** the launch-report page renders, **Then** launch-summary breakdowns (by Category, Family, Gender, Macro Area, Color) and the order/style measures are present.
2. **Given** the report is opened, **When** the top-parts page renders, **Then** a ranked table of items is present with the "Rows Displayed" and "Rank Sort Measure" parameter controls.
3. **Given** the report is opened, **When** the delivery-season page renders, **Then** order measures broken down by Delivery Season (and Delivery Month) are present.
4. **Given** the report is opened, **When** the data-detail page renders, **Then** a detailed item-level table of the launch data is present.
5. **Given** the 49 Tableau worksheets include many near-duplicate "Slide" and numbered variant sheets, **When** the report is generated, **Then** these are consolidated into three non-redundant pages — **(1) Launch Report Dashboard** (overview KPIs, top-parts rank table, key category/region breakdowns), **(2) Delivery Season Summary** (order measures by Delivery Season and Delivery Month), and **(3) Data Detail** (full item-level order table) — rather than reproduced one-to-one. The two "Slide View" dashboards are presentation variants folded into pages (1) and (2). Final exact visuals are decided at the report-visual stage.

---

### Edge Cases

- What happens when the TWB-declared Excel source path (`C:/Users/jagerb/Desktop/Q3 Launch Data.xlsx`) is absent? → The M query MUST bind to the local CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` instead; the missing Excel path is never referenced.
- What happens with the trailing-space alias columns (`Region `, `Sales Area `, `Style Code `, `Style Description `, `Delivery Season `, `Delivery Month `) that duplicate their base fields? → They are collapsed to the single base field; the duplicate trailing-space columns are not exposed in the model.
- What happens when "Rows Displayed" = "All"? → The underlying parameter value is 10000, large enough to include every row, so no rows are filtered out.
- What happens to ranking ties (two items with equal Order $)? → Standard competition ranking via `RANKX` (default `Skip` ties, NOT dense): tied items deterministically share the same rank value, and the next rank is skipped accordingly. Top-N uses `Rank <= SELECTEDVALUE('Rows Displayed'[Value], 10)`.
- What happens when the percent-of-total denominator is zero (no selected rows)? → The percent-of-total measure returns BLANK() rather than an error or infinity.
- What happens to the pre-materialized `Measure for Rank` and `Style Count` columns already present in the CSV? → They are recreated as DAX (measure/parameter-driven) rather than imported as static columns, so they respond to parameter and filter context.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load the dealer buying-event order data from the local CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` (52 columns, 1000 data rows) using a Power Query `Csv.Document(File.Contents(...))` pattern, NOT the absent Excel source declared in the TWB.
- **FR-002**: System MUST model the source as a single flat table (no fact/dimension decomposition), preserving the product, geography, delivery-timing, and order-measure columns, per the Single-Table Rule (constitution §0).
- **FR-003**: System MUST generate a `DimDate` date dimension covering the source delivery-date range, marked as the model's date table, with at minimum Date, Year, Quarter, Month, and MonthName columns, and create an active many-to-one relationship from the launch-data delivery date to `DimDate[Date]`.
- **FR-004**: System MUST assign correct data types: numeric for order measures (Order $, Order Quantity, Cost, Dnet, MSRP, Margin $, Order $ USD/US Cost/US Dealer Net/US MSRP, Sum of Quantity Units, Sum of Extra Quantity Units), date for the delivery Date column, integer for Year/Month, and text for all product and geography attributes.
- **FR-005**: System MUST collapse the trailing-space alias columns (`Region `, `Sales Area `, `Style Code `, `Style Description `, `Delivery Season `, `Delivery Month `) to their single base field, and MUST NOT import the pre-materialized `Measure for Rank` / `Style Count` columns as static data (these are recreated as DAX).
- **FR-006**: System MUST migrate the dimension-style calculated fields as model fields: `Region` (IF Sales Area = "Canada" → "Canada", = "United States of America" → "USA", ELSE Macro Area), `Master Style` (`LEFT([Style Code], 8)`), `Base Part` (alias of Base Part Number), and the Category/Family/Gender/Sub-Family aliases mapping to their base product columns.
- **FR-007**: System MUST migrate the order/style aggregations as DAX measures, including order-value totals (Order $ USD, US Cost, US Dealer Net, US MSRP), Order Quantity, Sum of Quantity (Units), Sum of Extra Quantity (Units), Margin $, and Style Count (`DISTINCTCOUNT` of Master Style, migrating Tableau `CountD([Master Style])`).
- **FR-008**: System MUST implement the "Rows Displayed" parameter as a **disconnected** single-column table (no relationships to the launch-data table) with values 5, 10, 20, 50, 10000 (10000 = "All"; default 10), consumed via `SELECTEDVALUE` to drive Top-N row filtering through measures — it MUST NOT filter the fact table directly.
- **FR-009**: System MUST implement the "Rank Sort Measure" parameter as a **disconnected** single-column table (no relationships to the launch-data table) with the four values "Order $ (Descending)", "Order Units (Descending)", "Order $ (Ascending)", "Order Units (Ascending)" (default "Order $ (Descending)"), consumed via `SELECTEDVALUE` to drive the rank ordering through measures — it MUST NOT filter the fact table directly.
- **FR-010**: System MUST migrate the ranking and percent-of-total table calculations as DAX measures: a "Measure for Rank" that switches sign/metric based on the Rank Sort Measure parameter, a Rank using `RANKX` over the displayed item set with **standard competition ranking (default `Skip` ties, NOT dense — tied items deterministically share a rank and the next rank is skipped)**, a Rank (Order $) variant, an Order $ percent-of-total (`DIVIDE` of item Order $ against the `ALLSELECTED` total), and a Top-N flag (`Rank <= SELECTEDVALUE('Rows Displayed'[Value], 10)`).
- **FR-011**: System MUST guard percent-of-total and any ratio measures with `DIVIDE()` (no fallback argument) so a zero or blank denominator returns BLANK() rather than an error or infinity.
- **FR-012**: System MUST preserve the source field-formatting intent via measure `formatString` values: all monetary amounts are **USD** — currency (`$#,##0`) for order-value and margin measures, whole number (`#,##0`) for quantity and style-count measures, and percentage (`0.00%`) for the percent-of-total measure.
- **FR-013**: System MUST reproduce the five Tableau dashboards (Launch Report Dashboard, Delivery Season Summary, Data Detail, Slide View 1, Slide View 2) as a consolidated set of **three** Power BI report pages — **(1) Launch Report Dashboard** (overview KPIs, top-parts ranking table, key category/region breakdowns), **(2) Delivery Season Summary** (order measures by Delivery Season and Delivery Month), and **(3) Data Detail** (full item-level order table) — with the two "Slide View" presentation variants folded into pages (1) and (2), without one-to-one reproduction of all 49 worksheets. (Report-layer visual detail is a downstream stage.)
- **FR-014**: System MUST output all PBIP artifacts to `Output/Q3DealerBuyingEvent/` following the standard PBIP folder structure (`.pbip`, `.SemanticModel/`, `.Report/`).
- **FR-015**: System MUST follow constitution rules from `.specify/memory/constitution.md` for naming conventions, DAX standards, parameter modeling, and relationship patterns.

### Key Entities

- **Launch Data (Single Source Table)**: The flat dealer buying-event order table loaded from `Q3LaunchData 1.csv`. Grain: one row per item/order line. Attribute groups: **Product** (Style, Style Code, Base Part, Master Style, Style Description, Category, Family, Sub-Family, Gender, Garment Type, Color, Collection, Reorder Type), **Geography** (Macro Area, Micro Area, Sales Area, derived Region), **Delivery Timing** (Delivery Season, Delivery Month, Delivery Date, Year, Month, Date). Order **measures**: Order $ (USD / US Cost / US Dealer Net / US MSRP), Order Quantity, Cost, Dnet, MSRP, Margin $, Sum of Quantity (Units), Sum of Extra Quantity (Units).
- **DimDate (Generated Date Dimension)**: A contiguous date table spanning the source delivery-date range, marked as the model's date table and related to the launch-data delivery date. Key attributes: Date, Year, Quarter, Month, MonthName. Grain: one row per day.
- **Rows Displayed (Disconnected Parameter Table)**: Values 5, 10, 20, 50, 10000 (10000 displayed as "All"; default 10). No relationships. Consumed via `SELECTEDVALUE` to drive Top-N row filtering, mirroring the Tableau "Rows Displayed" list parameter.
- **Rank Sort Measure (Disconnected Parameter Table)**: The four string values controlling rank metric (Order $ vs Order Units) and direction (Ascending vs Descending); default "Order $ (Descending)". No relationships. Consumed via `SELECTEDVALUE` to drive the rank ordering, mirroring the Tableau "Rank Sort Measure" list parameter.
- **Measures (Logical Group)**: The migrated DAX measures — order-value/margin/quantity aggregations, Style Count, Measure for Rank, Rank, Rank (Order $), Order $ percent-of-total, and the Top-N flag — that respond to product/geography/delivery filtering and to the two disconnected parameters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `.pbip` project opens in Power BI Desktop without any loading or schema errors.
- **SC-002**: The launch-data table loads all rows from `Q3LaunchData 1.csv` (row count matches the source CSV).
- **SC-003**: All product, geography, and delivery-timing attributes plus order measures are accessible in the Fields pane with correct data types, and the trailing-space alias columns are not exposed as duplicates.
- **SC-004**: The `DimDate` relationship filters the launch-data table correctly when a date, year, or month is selected.
- **SC-005**: The order, margin, quantity, and Style Count measures calculate without evaluation errors and reconcile against the source totals when broken down by product/geography/delivery attributes.
- **SC-006**: Setting the "Rank Sort Measure" parameter changes the rank ordering (metric and direction) as specified, and setting "Rows Displayed" limits the visible items to the selected Top-N (with "All" showing every item).
- **SC-007**: The percent-of-total measure returns each item's share of the selected total and returns BLANK() (not an error) when the denominator is zero or blank.
- **SC-008**: Currency measures display with a `$#,##0` currency format, quantity/style measures with a `#,##0` whole-number format, and the percent-of-total with a percentage format, matching the Tableau source formatting intent.
- **SC-009**: PBIP validation tools (`tmdl-validate` and `validate_pbip.py`) pass with no errors (exit code 0/1, no code 2).

## Assumptions

- The source CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` is present and well-formed at generation time (52 columns, 1000 data rows), and is the authoritative data source despite the TWB declaring an absent Excel file.
- The CSV uses comma delimiter and UTF-8 encoding with a standard header row.
- The single-table rule (constitution §0) applies — the flat Tableau source is kept as one table, with only a generated `DimDate` and the two disconnected parameter tables added; no star-schema decomposition.
- The two Tableau list parameters are implemented as disconnected DAX/parameter tables (not Power Query parameters) so the rank and Top-N logic respond dynamically to user selection.
- Tableau RANK table calculations map to DAX `RANKX` over `ALLSELECTED`, and the `TOTAL`/percent-of-total table calculation maps to `DIVIDE` against the `ALLSELECTED` total; exact Tableau visual-scope (partition/addressing) replication may require minor report-side filter-context configuration.
- The internal parameter aliases `Total Orders Parameter` and `Rank Sort Measure (copy)` referenced in the TWB are treated as the same two user-facing parameters (Rows Displayed / Rank Sort Measure).
- Sets, groups, bins, and data blending are not used in the source workbook, so no bridge tables or blend logic are required.
- Auto-generated Tableau dashboard-action highlight groups (`Action (...)`) are interactivity artifacts, not user-defined groups, and are not migrated as model objects.
- The 49 Tableau worksheets (with many "Slide" and numbered variants) consolidate into a small set of report pages; the report layer is generated in a downstream stage and only described functionally here.
- The PBIP output follows the Power BI Projects format compatible with Power BI Desktop (June 2024+).
- Output artifacts are written to `Output/Q3DealerBuyingEvent/`.
- Mobile layout and row-level security are out of scope for this migration.

## Clarifications

### Session 2026-06-05

- Q: How should the 49 worksheets / 5 dashboards consolidate into report pages? → A: Three pages — (1) Launch Report Dashboard (overview KPIs + rank table + key category/region breakdowns), (2) Delivery Season Summary, (3) Data Detail (full order detail table). The two "Slide View" dashboards are presentation variants folded into the above; final exact visuals decided at the report-visual stage.
- Q: How should ranking ties be handled? → A: Standard competition ranking via `RANKX` with default `Skip` ties (NOT dense) — deterministic, tied items share a rank and the next rank is skipped. Top-N uses `Rank <= SELECTEDVALUE('Rows Displayed'[Value], 10)`.
- Q: What currency and number formats apply to the monetary measures? → A: Amounts are USD; keep the Tableau currency format `$#,##0` for order-value/margin measures and `0.00%` for the percent-of-total measure.
- Q: Do the two list parameters filter the fact table directly? → A: No. The "Rows Displayed" and "Rank Sort Measure" parameters are disconnected single-column tables driving measures via `SELECTEDVALUE`; they do NOT have relationships to or directly filter the launch-data fact table.
