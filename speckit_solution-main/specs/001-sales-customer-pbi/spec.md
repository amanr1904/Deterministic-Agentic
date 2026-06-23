# Feature Specification: Sales & Customer Dashboards — Tableau → Power BI Migration

**Feature Branch**: `001-sales-customer-pbi`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "Migrate Sales and Customer Dashboards Tableau workbook to Power BI semantic model"

## Clarifications

### Session 2026-06-09

Resolved non-interactively for the automated pipeline using defaults grounded in the Tableau analysis and the migration constitution. Each decision is integrated into the relevant Requirements/Assumptions below.

- Q: Storage mode for the four CSV sources? → A: **Import** mode (constitution §6 default); per-file M encodings — Orders/Location `Encoding=65001` (UTF-8), Customers/Products `Encoding=1252` (windows-1252); delimiter `;`, `QuoteStyle.Csv`.
- Q: How to implement the **Select Year** parameter (Tableau integer list 2020–2023, default 2023)? → A: A **disconnected single-column table** `Select Year` built with `GENERATESERIES(2020, 2023, 1)` (values are contiguous), rendered as a single-select slicer; measures read it via `SELECTEDVALUE('Select Year'[Year], 2023)`. No relationship to any table.
- Q: Migrate the conditional "dimension" fields (CY/PY Customers, CY/PY Orders) as columns or measures? → A: As **explicit measures** (constitution §3 "measures over calculated columns") using `CALCULATE(DISTINCTCOUNT(...), <year filter>)`. The ONLY non-measure logic is M-side typing/trimming; no DAX calculated columns are created for CY/PY logic.
- Q: How do CY/PY measures derive their year without a year relationship? → A: A `VAR _Year = SELECTEDVALUE('Select Year'[Year], 2023)` (PY = `_Year - 1`) wrapped in `CALCULATE(<agg>, FILTER(ALL('DimDate'), 'DimDate'[Year] = _Year))`. Year context is parameter-driven, not via a physical filter relationship.
- Q: How to support the month-level sparkline axis and weekly-trend axis (constitution §1 "always create DimDate")? → A: Add an **M-generated `DimDate`** (Year, Month Number, Month Name, Week of Year, Date) related **many-to-one, single-direction** to `Orders[Order Date]`. This is a **fourth** relationship in addition to the three dimension joins, used only as the trend axes (month for sparklines, week for Weekly Trends). Year comparison stays parameter-driven.
- Q: Min/Max sparkline highlight implementation? → A: DAX `MAXX`/`MINX` over `VALUES('DimDate'[Month Number])` of the CY measure, plus a **marker measure** returning the value only at the max/min month to drive the highlight circle (replaces Tableau `WINDOW_MAX`/`WINDOW_MIN`).
- Q: INDEX rank and the Top-10 customers limit? → A: `RANKX(ALLSELECTED(Customers[Customer Name]), [CY Profit], , DESC, Dense)`; Top-10 enforced via a **filter measure** `IF([Rank] <= 10, 1, 0)` (no `filters`/`filterConfig` at the visual.json root per PBIR rules); a native Top N visual filter may also be added in Desktop.
- Q: LOD FIXED fields → DAX pattern? → A: `{SUM([CY Sales])}` → `CALCULATE([CY Sales], REMOVEFILTERS())`; `Nr of Orders per Customer` → `CALCULATE(DISTINCTCOUNT(Orders[Order ID]), ALLEXCEPT(Customers, Customers[Customer ID]))` scoped to the selected year (constitution LOD-Fixed mapping).
- Q: Divide-by-zero handling for %Diff and per-customer ratios? → A: All ratios use **`DIVIDE()`** returning **BLANK** (constitution §3); for year 2020 the missing PY denominator yields blank, not an error, and the %Diff format renders blank gracefully.
- Q: %Diff arrow and currency formatting in DAX format strings? → A: Positive/negative custom format `"▲ "0.0%;"▼ "0.0%`; K-currency `$#,##0,"K"`; per-customer currency `$#,##0`; rank `"#"0` — no separate text measures needed.
- Q: KPI sparkline card reproduction (no 1:1 Tableau equivalent)? → A: A **composite of native visuals per card**: a large Card value (CY), a line chart of the CY measure by `DimDate[Month]` styled as a sparkline with a min/max highlight marker, and a %Diff value with directional arrow. Pixel-level Tableau styling is approximated.
- Q: Collapsible filter-panel reproduction? → A: **Bookmark-based** Open/Close pattern: the slicer panel group is hidden by default; Show/Hide buttons swap two bookmarks that toggle the panel group's visibility in the Selection pane (matches the Tableau hidden zone toggle).
- Q: Page-navigation buttons? → A: **Native buttons** using the built-in **Page Navigation** action; the active page's button is styled as selected.
- Q: Postal Code join key (integer in source, format `*00000`)? → A: Cast to **zero-padded 5-character text** and `Text.Trim` in **both** Orders and Location during M load so the relationship joins reliably (avoids integer/whitespace mismatch).
- Q: Color legends (KPI CY-less-PY dot, Above/Below, Subcategory profit/loss)? → A: Reproduced as **static text boxes / shape markers** with the source palette colors (not data-bound legend visuals).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faithful KPI & Trend Analysis Across Two Dashboards (Priority: P1)

A sales/customer analyst opens the migrated Power BI report and finds the exact same two dashboards they used in Tableau — a **Customer Dashboard** and a **Sales Dashboard**, each 1200×800 — with all six KPI sparkline cards, the distribution histogram, the subcategory comparison, the weekly trend lines, and the Top‑10 customers table rendering the same numbers and layout as the source. Switching the **Select Year** control updates every current‑year (CY) and previous‑year (PY) comparison consistently across both pages.

**Why this priority**: This is the core reason for the migration — the report must reproduce the analytical value of the original workbook. Without faithful KPIs and trends, the migration delivers no business value.

**Independent Test**: Open the generated `.pbip` in Power BI Desktop, select each year (2020–2023) in the Select Year control, and confirm every KPI card, the %Diff arrows, the histogram, the diverging bar, the weekly dual‑line chart, and the Top‑10 table update correctly and match the Tableau output for the same year.

**Acceptance Scenarios**:

1. **Given** the report is open on the Customer Dashboard with Select Year = 2023, **When** the analyst reads the KPI Customers / KPI Sales Per Customers / KPI Orders cards, **Then** each card shows the CY value, a sparkline trend over months, a min/max highlight point, and a %Diff vs. prior year with an up/down arrow.
2. **Given** the analyst changes Select Year from 2023 to 2021, **When** the value changes, **Then** all CY measures recompute for 2021, all PY measures recompute for 2020, and every visual on both pages reflects the new comparison.
3. **Given** the Sales Dashboard, **When** the analyst views the Subcategory Comparison and Weekly Trends visuals, **Then** sales and profit are shown by sub‑category (PY vs CY) and over weekly time respectively, matching the Tableau encodings.

---

### User Story 2 - Star‑Schema Semantic Model with Complete Measure Coverage (Priority: P1)

A BI developer inherits the migrated semantic model and finds a clean star schema — an **Orders** fact joined many‑to‑one to **Customers**, **Location**, and **Products** dimensions — plus a complete set of explicit DAX measures covering every Tableau calculated field (CY/PY metrics, %Diff YoY, min/max highlights, INDEX rank, and the two LOD FIXED fields). They can build new visuals or audit existing ones using well‑named, well‑formatted measures grouped into display folders.

**Why this priority**: A correct model and complete measures are the foundation everything else depends on; visuals and parameters are meaningless if the underlying calculations are missing or wrong.

**Independent Test**: Inspect the model relationships (3 many‑to‑one), enumerate measures against the Tableau calculated‑field list, and validate each measure returns the expected value via DAX query for a sample year.

**Acceptance Scenarios**:

1. **Given** the semantic model, **When** the developer reviews relationships, **Then** Orders→Customers (Customer ID), Orders→Location (Postal Code), and Orders→Products (Product ID) are all single‑direction, many‑to‑one.
2. **Given** the measure list, **When** compared to the Tableau calculated fields, **Then** every CY measure, PY measure, %Diff measure, min/max highlight, rank, and LOD FIXED field has a corresponding DAX measure with an appropriate format string and display folder.
3. **Given** any CY/PY measure, **When** evaluated, **Then** it respects the Select Year parameter for its year context exactly as the Tableau `[Parameters].[Parameter 1]` logic did.

---

### User Story 3 - Interactive Filtering & Navigation Matching Tableau UX (Priority: P2)

An end user navigates between the Customer and Sales dashboards using on‑page navigation buttons, and opens a collapsible filter panel to slice by Year, Category, Sub‑Category, Region, State, and City — reproducing the hidden‑by‑default filter drawer and the three‑button toolbar from the Tableau dashboards.

**Why this priority**: Navigation and filtering reproduce the interactive UX; important for usability but secondary to the data and visuals being correct.

**Independent Test**: Click the navigation buttons to move between pages, toggle the filter panel open/closed, and apply each slicer to confirm visuals respond.

**Acceptance Scenarios**:

1. **Given** the Customer Dashboard, **When** the user clicks "Go to Sales Dashboard", **Then** the report navigates to the Sales Dashboard page; the reverse button returns to Customer Dashboard.
2. **Given** either dashboard with the filter panel collapsed, **When** the user clicks the filter toggle button, **Then** the slicer panel (Year, Category, Sub‑Category, Region, State, City) becomes visible and can be collapsed again.
3. **Given** the filter panel open, **When** the user selects a Region/State/City or Category/Sub‑Category, **Then** all visuals on the page filter accordingly.

---

### Edge Cases

- **No prior‑year data**: When Select Year = 2020 (the earliest year), PY measures have no 2019 data; %Diff measures MUST avoid divide‑by‑zero (return blank/zero gracefully) rather than error.
- **Top‑10 fewer than 10 customers**: When a filter context yields fewer than 10 customers, the Top Customers table MUST show all available customers without padding or error.
- **Empty filter selection**: Selecting a Region/State/City combination with no Orders MUST render empty visuals cleanly (no error), with KPI cards showing blank/zero.
- **Whitespace/encoding in keys**: Customer/Product/Postal keys originate from CSVs with mixed encodings (UTF‑8 and windows‑1252); key columns MUST be trimmed so relationships do not break on whitespace.
- **Unused worksheets**: The three Tableau "Test" worksheets (Test KPI, Test KPI2, Test Max Min) are out of scope and MUST NOT be reproduced in the report.

## Requirements *(mandatory)*

### Functional Requirements

#### Data Source & Model Structure

- **FR-001**: System MUST load four source CSV tables — Orders, Customers, Location, Products — from the `Sales DataSource` as independent queries (semicolon delimiter, appropriate encodings preserved per file).
- **FR-002**: System MUST model **Orders** as the fact table (Sales, Quantity, Discount, Profit measures; Order Date, Ship Date, keys) and **Customers**, **Location**, **Products** as dimension tables.
- **FR-003**: System MUST create three single‑direction, many‑to‑one relationships: Orders→Customers on Customer ID, Orders→Location on Postal Code, Orders→Products on Product ID.
- **FR-004**: System MUST provide an M‑generated **DimDate** table (Year, Month Number, Month Name, Week of Year, Date) related many‑to‑one, single‑direction to Orders[Order Date]; it supplies the month axis for KPI sparklines and the week axis for Weekly Trends. Year‑based CY/PY logic is driven by the Select Year parameter (not by filtering this relationship).
- **FR-005**: System MUST trim/normalize key columns (Customer ID, Product ID, Postal Code) to prevent relationship mismatches caused by whitespace or encoding differences.

#### Parameter Migration

- **FR-006**: System MUST migrate the Tableau **Select Year** integer‑list parameter (values 2020, 2021, 2022, 2023; default 2023) into a disconnected single‑column `Select Year` table (`GENERATESERIES(2020, 2023, 1)`) rendered as a single‑select slicer, consumed via `SELECTEDVALUE('Select Year'[Year], 2023)`.
- **FR-007**: All current‑year and previous‑year measures MUST derive their year context from the Select Year parameter value (CY = selected year; PY = selected year − 1).

#### Measure Migration (Complete Coverage)

- **FR-008**: System MUST provide current‑year measures for Sales, Profit, Quantity, distinct Customers, distinct Orders, and Sales‑per‑Customer, each scoped to the selected year.
- **FR-009**: System MUST provide the corresponding previous‑year measures for Sales, Profit, Quantity, distinct Customers, distinct Orders, and Sales‑per‑Customer, scoped to the selected year − 1.
- **FR-010**: System MUST provide %Diff (YoY) measures for Sales, Profit, Quantity, Orders, Customers, and Sales‑per‑Customer, formatted with up/down (▲/▼) directional indicators, and divide‑by‑zero safe.
- **FR-011**: System MUST provide min/max highlight measures (WINDOW_MAX / WINDOW_MIN equivalents) for Sales, Profit, Quantity, Orders, Customers, and Sales‑per‑Customer to drive the sparkline highlight points.
- **FR-012**: System MUST provide an INDEX‑based rank measure used to rank and number customers in the Top Customers table.
- **FR-013**: System MUST migrate both LOD FIXED fields — total CY Sales (fixed) and Number of Orders per Customer (fixed) — as DAX measures using the appropriate filter‑removal pattern.
- **FR-014**: System MUST migrate the KPI helper fields (CY‑less‑PY profit/loss indicator, above/below‑average flags) needed by the legends and KPI highlighting.
- **FR-015**: Every migrated measure MUST carry an appropriate format string (currency with "K" suffix, percent with arrows, rank with "#", integer) matching the Tableau field formatting, and be grouped into logical display folders (e.g., Current Year, Previous Year, Year‑over‑Year, Highlights, Ranking).

#### Report — Pages & Visuals

- **FR-016**: System MUST produce exactly two report pages — **Customer Dashboard** and **Sales Dashboard** — each sized 1200×800 px.
- **FR-017**: The Customer Dashboard MUST reproduce, in matching positions/order: the KPI legend strip, three KPI sparkline cards (KPI Customers, KPI Sales Per Customers, KPI Orders), the **Customer Distribution** histogram (customers by number of orders), and the **Top Customers** Top‑10 table (Rank, Customer Name, Last Order, Profit, Sales, Orders).
- **FR-018**: The Sales Dashboard MUST reproduce, in matching positions/order: the KPI legend strip, three KPI sparkline cards (KPI Sales, KPI Profit, KPI Quantity), the **Subcategory Comparison** diverging/grouped bar (PY Sales, CY Sales, CY Profit by Sub‑Category with profit/loss coloring + its legend), and the **Weekly Trends** dual‑line chart (CY Sales & CY Profit by week with above/below coloring + its legend).
- **FR-019**: Each KPI sparkline card MUST show the CY value, a month‑level trend line, a min/max highlight point, and the %Diff vs. prior year with a directional arrow.
- **FR-020**: The Top Customers table MUST be limited to the top 10 customers ordered by CY Profit descending, and MUST gracefully show fewer rows when fewer than 10 exist in context.
- **FR-021**: Visual positions and stacking order on both pages MUST match the Tableau dashboard zone layout (title bar, KPI row, charts row, and the right‑side filter drawer position).
- **FR-022**: The three "Test" worksheets MUST be excluded from the report.

#### Report — Navigation & Filtering

- **FR-023**: Each page MUST include page‑navigation buttons to move between the Customer Dashboard and Sales Dashboard, with the active page's button visually indicated.
- **FR-024**: Each page MUST include a collapsible filter panel, hidden by default, toggled by a filter button, containing slicers for Year (Select Year), Category, Sub‑Category, Region, State, and City.
- **FR-025**: Applying any slicer in the filter panel MUST filter all visuals on the active page consistently.
- **FR-026**: System MUST reproduce the color legends (KPI legend and Subcategory profit/loss legend) as on the source dashboards.

#### Fidelity & Formatting

- **FR-027**: Numeric, currency, percent, and rank formats in all visuals MUST preserve the source Tableau formatting (e.g., "$#,##0K", "▲ 0.0% / ▼ ‑0.0%", "#N").
- **FR-028**: System MUST NOT generate row‑level security artifacts (analysis reports RLS Detected: No).

### Key Entities *(include if feature involves data)*

- **Orders (Fact)**: One row per order line. Key attributes: Row ID, Order ID, Order Date, Ship Date, Ship Mode, Customer ID (FK), Segment, Postal Code (FK), Product ID (FK), and measures Sales, Quantity, Discount, Profit. Central table of the star schema.
- **Customers (Dimension)**: Descriptive customer attributes. Key: Customer ID. Attributes: Customer Name. Joined many‑to‑one from Orders.
- **Location (Dimension)**: Geographic attributes. Key: Postal Code. Attributes: City, State, Region, Country/Region. Joined many‑to‑one from Orders.
- **Products (Dimension)**: Product attributes. Key: Product ID. Attributes: Category, Sub‑Category, Product Name. Joined many‑to‑one from Orders.
- **Select Year (Parameter)**: Disconnected single‑column table (`GENERATESERIES(2020, 2023, 1)`, default 2023 via `SELECTEDVALUE`) driving CY/PY year context for all comparison measures.
- **DimDate (Dimension)**: M‑generated calendar (Year, Month Number, Month Name, Week of Year, Date) joined many‑to‑one to Orders[Order Date]; provides the month/week trend axes only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four source tables, the M‑generated DimDate, and the four many‑to‑one relationships (Orders→Customers, Orders→Location, Orders→Products, Orders→DimDate) are present and resolve correctly, with 100% of Orders rows matching to Customers, Location, and Products dimension keys after trimming.
- **SC-002**: 100% of the Tableau calculated fields in scope (all CY, PY, %Diff, min/max, INDEX rank, and both LOD FIXED fields) have corresponding DAX measures — zero omissions.
- **SC-003**: For each of the four selectable years (2020–2023), every KPI card, %Diff value, histogram, diverging bar, weekly trend, and Top‑10 table matches the Tableau output for the same year within rounding tolerance.
- **SC-004**: Changing the Select Year control updates every CY/PY‑dependent visual on both pages in a single interaction, with no stale or inconsistent values.
- **SC-005**: The report contains exactly two pages at 1200×800, each reproducing all in‑scope visuals in positions/order matching the Tableau dashboards, and excluding the three Test worksheets.
- **SC-006**: Navigation buttons move correctly between the two pages, and the filter panel toggles open/closed and applies all six slicers (Year, Category, Sub‑Category, Region, State, City) to the page's visuals.
- **SC-007**: %Diff and Sales‑per‑Customer measures return a graceful blank/zero (no error) when the prior‑year denominator is zero or missing (e.g., year 2020).
- **SC-008**: The generated `.pbip` passes structural validation (TMDL + PBIP/PBIR validators) with zero errors before delivery.

## Assumptions

- The four CSVs reside together in the `Sales DataSource` location and are loaded in Import mode (default per migration constitution); a developer will repoint file paths if running outside the original environment.
- The **Select Year** parameter is implemented as a disconnected `GENERATESERIES` table (contiguous integers 2020–2023); year filtering on visuals is driven by measures consuming `SELECTEDVALUE` rather than a relationship to a date dimension.
- A dedicated **DimDate** (related to Orders[Order Date]) supplies the month and week trend axes; it is intentionally NOT used to drive the CY/PY year comparison, which remains parameter-driven.
- KPI sparkline cards are reproduced using the closest native Power BI equivalent (card + line/area sparkline with a highlighted min/max point); exact pixel‑level sparkline styling may approximate Tableau where a 1:1 visual is unavailable.
- The Subcategory Comparison and Weekly Trends visuals are reproduced with the nearest native Power BI chart types (grouped/diverging bar and multi‑line) matching the Tableau encodings.
- Logo/icon bitmaps and exact custom button artwork from Tableau are represented with equivalent Power BI buttons/images; brand imagery may be substituted if original assets are unavailable.
- The collapsible filter drawer is reproduced using a bookmark/selection‑pane toggle pattern (or equivalent) since Tableau's hidden‑zone toggle has no direct 1:1 in Power BI.
- Cross‑highlight action artifacts (auto‑generated Tableau dashboard actions) are treated as standard slicer/cross‑filter interactions, not reproduced as bespoke set actions.
- No row‑level security is implemented, consistent with the analysis (RLS Detected: No).
