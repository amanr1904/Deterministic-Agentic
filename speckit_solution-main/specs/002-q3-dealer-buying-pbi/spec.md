# Feature Specification: (Active) 2021 Q3 Dealer Buying Event — Tableau → Power BI Migration

**Feature Branch**: `002-q3-dealer-buying-pbi`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "Migrate (Active) 2021 Q3 Dealer Buying Event Tableau workbook to Power BI semantic model + report"

## Clarifications

### Session 2026-06-09

Resolved non-interactively for the automated pipeline using defaults grounded in the Tableau analysis (`.specify/memory/Q3DealerBuyingEvent/tableau-analysis-output.md`) and the migration constitution. Each decision is integrated into the relevant Requirements/Assumptions below.

- Q: Model shape — single flat table or star schema? → A: **Single flat table** (constitution §0). The Tableau workbook has one denormalized `excel-direct` datasource (Sheet1, 53 columns, no joins, no blending). Load it as a single primary table `LaunchData`; do NOT decompose into fact/dimensions. Add only a generated `DimDate` for the date axis and the two disconnected parameter tables.
- Q: Storage mode and CSV load pattern? → A: **Import** mode (constitution §6). Migration source is the flat CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` (not the original Excel) loaded via `Csv.Document(File.Contents(...))` with `QuoteStyle.Csv`, `Encoding=65001` (UTF‑8), comma delimiter, headers promoted, types cast, and `Text.Trim` on `Style Code` (source of `Master Style`) and `Sales Area` (source of `Region`).
- Q: How to implement the **Rows Displayed** parameter (Tableau integer list 5/10/20/50/10000-as-"All", default 10)? → A: A **disconnected DATATABLE** `Rows Displayed` with `Label`/`Value` columns (rows: "5"=5, "10"=10, "20"=20, "50"=50, "All"=10000), default 10, rendered as a single‑select slicer; the Top‑N filter measure reads it via `SELECTEDVALUE('Rows Displayed'[Value], 10)`.
- Q: How to implement the **Rank Sort Measure** parameter (Tableau string list, 4 options, default "Order $ (Decending)")? → A: A **disconnected DATATABLE** `Rank Sort Measure` with `Label`/`SortOrder` columns (the four options: "Order $ (Decending)", "Order Units (Decending)", "Order $ (Accending)", "Order Units (Accending)"), default "Order $ (Decending)", rendered as a single‑select slicer; consumed via `SELECTEDVALUE('Rank Sort Measure'[Label], "Order $ (Decending)")`.
- Q: How to migrate the parameter‑driven **Measure for Rank** Tableau `CASE` calc? → A: As a DAX measure using `SWITCH(SELECTEDVALUE('Rank Sort Measure'[Label]), ...)` returning `[Order $]`, `[Order Quantity]`, or their negatives for the ascending options, exactly mirroring the Tableau `CASE`. (The CSV also carries a precomputed `Measure for Rank` column; the measure version is authoritative for ranking because it must respond to the parameter.)
- Q: How to migrate the **Rank** table calculation (`RANK(SUM([Measure for Rank]))`)? → A: A DAX measure `Rank = RANKX(ALLSELECTED(LaunchData[Base Part Number]), [Measure for Rank], , DESC, Dense)`, ranking parts within the current visual context (replicates the Tableau ordering-Columns table calc).
- Q: How to migrate the **Rank Filter** Top‑N table calc (`IF [Rank] <= [Rows Displayed] THEN "Yes" ELSE "No"`)? → A: A DAX filter measure `Rank Filter = IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value], 10), 1, 0)`; Top‑Parts visuals keep parts where this returns 1. No `filters`/`filterConfig` at the `visual.json` root (PBIR rule); the measure drives Top‑N and a native Top N visual filter may be added in Desktop.
- Q: How to migrate the **Order $ (Percent of Total)** table calc (`SUM([Order $]) / TOTAL(SUM([Order $]))`)? → A: A DAX measure using `DIVIDE([Order $], CALCULATE([Order $], ALLSELECTED(LaunchData)))` formatted `0.00%` (matches Tableau `p0.00%`, divide‑by‑zero safe).
- Q: How to migrate **Master Style** (`LEFT([Style Code],8)`) and **Style Count** (`COUNTD([Master Style])`)? → A: `Master Style` as an **M query / calculated column** = first 8 characters of trimmed `Style Code` (constitution §6 prefers M for text ops); `Style Count` as a DAX **measure** `DISTINCTCOUNT(LaunchData[Master Style])`.
- Q: How to migrate **Region** (`IF [Sales Area]="Canada" … ELSEIF "United States of America" THEN "USA" ELSE [Macro Area]`)? → A: A **calculated column** `Region` on `LaunchData` using `SWITCH(TRUE(), ...)` over `Sales Area`, falling back to `Macro Area` (used as a slicer/axis, so a column, not a measure).
- Q: How to migrate the redundant Tableau "(copy)" helper calcs and `Global="Global"`? → A: Migrate the **distinct logical fields once** — `Order $` (primary value measure), `Region`, `Master Style`, `Style Count`, `Rank`, `Rank Filter`, `Order $ (Percent of Total)`, `Measure for Rank`. The pure aliases (`Base Style Name`=`[Base Style]`, `Delivery Season (copy)`, `Delivery Month (copy)`, `Category (copy)`=`[Product Category]`, `Base Part (copy)`=`[Base Part Number]`, the `(copy)` measure duplicates) are NOT recreated as new objects — the original source columns/measures are used directly. `Global="Global"` is added as a single‑value calculated column only if a visual needs the "Global" grouping label.
- Q: Date axis for **Sales by Date**? → A: Add an **M‑generated `DimDate`** (Date, Year, Month Number, Month Name) related many‑to‑one, single‑direction to `LaunchData[Date]`, supplying the time axis for the Sales by Date line/column chart. (The flat table also has `Year`/`Month` integer columns usable directly; DimDate provides a clean continuous axis.)
- Q: Reproduction of the 49 Tableau worksheets vs. 5 dashboards? → A: The report reproduces the **5 dashboards as 5 report pages**. The many per‑category worksheet variants ("- 1/- 2/- 3/- 4", "(Slide)") are the building blocks of those dashboards and are reproduced as the visuals composing each page — not as 49 separate pages.
- Q: RLS, sets, groups, bins? → A: **None.** Analysis reports RLS Detected: No, no user sets/groups (the 8 `<group>` elements are auto‑generated hidden dashboard‑action helpers), and no bins. No `roles/` folder, no bridge tables.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faithful Five-Dashboard Launch Report (Priority: P1)

A dealer-buying-event analyst opens the migrated Power BI report and finds the same five dashboards they used in Tableau — **Data Detail**, **Delivery Season Summary**, **Launch Report Dashboard**, **Slide View 1**, and **Slide View 2** — each reproduced as its own page with the same visual composition: the large detail table with its ~13 slicers, the small-multiple summary grid, the main launch dashboard with bar charts / Top Parts table / KPI cards / Sales-by-Date trend, and the two slide layouts. Adjusting **Rows Displayed** and **Rank Sort Measure** re-ranks and re-trims every Top Parts visual consistently.

**Why this priority**: Reproducing the five dashboards with faithful visual types is the core reason for the migration; without them the migration delivers no business value.

**Independent Test**: Open the generated `.pbip` in Power BI Desktop, navigate all five pages, and confirm each visual renders the correct mark type (table→table/matrix, bar→bar, line→line, KPI→card) with the same fields and the same numbers as the Tableau source.

**Acceptance Scenarios**:

1. **Given** the report is open on **Data Detail**, **When** the analyst views the page, **Then** a single large Table/Matrix of launch records is shown alongside the ~13 slicers (Region, Sales Area, Delivery Season, Delivery Month, Garment Type, Product Gender, Product Category, Product Family, Product Sub‑Family, Base Style Name, Style Code, Base Part Number, Style Description).
2. **Given** the **Launch Report Dashboard** page, **When** the analyst views it, **Then** bar charts (MacroArea, Gender, Category, Family, Delivery Season, Garment Type), a Top Parts table/matrix, KPI cards (Launch Summary), and a Sales‑by‑Date line/column chart colored by Reorder Type are all present.
3. **Given** any page containing a **Top Parts** visual, **When** the analyst changes **Rows Displayed** from 10 to 20 (or "All"), **Then** the Top Parts visual shows the new number of top‑ranked parts; **When** the analyst changes **Rank Sort Measure**, **Then** the ranking re‑sorts by the chosen measure/direction.

---

### User Story 2 - Single-Table Semantic Model with Complete Measure & Parameter Coverage (Priority: P1)

A BI developer inherits the migrated semantic model and finds a clean single flat table **LaunchData** (all 53 source columns preserved) plus a generated **DimDate** and two disconnected parameter tables, with a complete set of explicit DAX measures and migrated calculated columns covering every Tableau calculated field: Rank, Order $ (Percent of Total), Master Style, Style Count, Region, Measure for Rank, and Rank Filter. They can audit or extend the model using well-named, well-formatted measures grouped into display folders.

**Why this priority**: A correct model with complete measures and parameters is the foundation the report depends on; visuals are meaningless if the underlying calculations are missing or wrong.

**Independent Test**: Inspect the model (one primary table, DimDate, two parameter tables, one DimDate relationship), enumerate measures/columns against the Tableau calculated-field list, and validate each via a DAX query for a sample selection.

**Acceptance Scenarios**:

1. **Given** the semantic model, **When** the developer reviews the structure, **Then** `LaunchData` is a single flat table (no fact/dimension decomposition), `DimDate` is related many‑to‑one single‑direction to `LaunchData[Date]`, and `Rows Displayed` and `Rank Sort Measure` are disconnected parameter tables.
2. **Given** the measure/column list, **When** compared to the Tableau calculated fields, **Then** every one (Rank, Order $ (Percent of Total), Master Style, Style Count, Region, Measure for Rank, Rank Filter) has a corresponding DAX measure or calculated column with an appropriate format string and display folder.
3. **Given** the **Measure for Rank** and **Rank** measures, **When** the **Rank Sort Measure** parameter changes, **Then** the ranking responds exactly as the Tableau parameter‑driven `CASE` logic did (descending/ascending by Order $ or Order Units).

---

### User Story 3 - Interactive Slicing & Top-N Control Matching Tableau UX (Priority: P2)

An end user slices the Data Detail and Launch dashboards by the available dimension slicers and uses the **Rows Displayed** and **Rank Sort Measure** controls to govern how many top parts appear and how they are ranked — reproducing the Tableau parameter-driven Top‑N experience.

**Why this priority**: Slicing and Top‑N control reproduce the interactive UX; important for usability but secondary to the data and visuals being correct.

**Independent Test**: Apply each slicer on the relevant pages and toggle the two parameter slicers; confirm visuals respond and Top Parts visuals re‑trim/re‑rank.

**Acceptance Scenarios**:

1. **Given** the Data Detail page, **When** the user selects a Region/Garment Type/Product Category in the slicers, **Then** the detail table and all summary visuals filter accordingly.
2. **Given** any page with the **Rows Displayed** slicer, **When** the user selects "5", **Then** Top Parts visuals show only the top 5 ranked parts; selecting "All" shows all parts.
3. **Given** any page with the **Rank Sort Measure** slicer, **When** the user picks "Order Units (Decending)", **Then** Top Parts rank by Order Quantity descending instead of Order $.

---

### Edge Cases

- **"All" rows selection**: When **Rows Displayed** = "All" (value 10000), the Top‑N filter MUST effectively show every ranked part without truncation or error.
- **Ranking ties**: When two parts share the same `Measure for Rank` value, dense ranking MUST assign equal ranks without dropping rows from the Top‑N set.
- **Percent-of-total with zero context total**: The Order $ (Percent of Total) measure MUST use `DIVIDE()` to return blank (not an error) when the visual-context total is zero/blank.
- **Short Style Code**: When `Style Code` is shorter than 8 characters, `Master Style` (LEFT 8) MUST return the full available string without error, and Style Count MUST still count distinct values correctly.
- **Region fallback**: When `Sales Area` is neither "Canada" nor "United States of America", `Region` MUST fall back to `Macro Area`; null `Sales Area`/`Macro Area` MUST not raise an error.
- **Trailing-space duplicate columns**: The source contains several "(trailing space)" duplicate columns (e.g., `Delivery Month`, `Sales Area`, `Style Code`); these MUST be retained as-is on load but the trimmed canonical columns are used for `Master Style`/`Region` derivation.
- **Excluded constructs**: No RLS roles, sets, groups, or bins are generated.

## Requirements *(mandatory)*

### Functional Requirements

#### Data Source & Model Structure

- **FR-001**: System MUST load the single flat source CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` (53 columns) as one Import-mode table named **LaunchData** via `Csv.Document(File.Contents(...))` with `QuoteStyle.Csv`, UTF‑8 encoding, headers promoted, and types cast.
- **FR-002**: System MUST keep **LaunchData** as a single denormalized table (constitution §0 Single‑Table Rule) — it MUST NOT be decomposed into fact/dimension tables and MUST NOT introduce surrogate keys or bridge tables.
- **FR-003**: System MUST preserve all 53 source columns, including the duplicate "(trailing space)" variants, while applying `Text.Trim` to the canonical `Style Code` and `Sales Area` columns used to derive `Master Style` and `Region`.
- **FR-004**: System MUST add an M‑generated **DimDate** table (Date, Year, Month Number, Month Name) related many‑to‑one, single‑direction to `LaunchData[Date]`, supplying the Sales‑by‑Date time axis.
- **FR-005**: System MUST NOT create any row‑level security roles, sets, groups, or bins (analysis reports none).

#### Parameter Migration

- **FR-006**: System MUST migrate the Tableau **Rows Displayed** integer‑list parameter (5, 10, 20, 50, "All"=10000; default 10) into a disconnected `Rows Displayed` DATATABLE (`Label`/`Value` columns) rendered as a single‑select slicer, consumed via `SELECTEDVALUE('Rows Displayed'[Value], 10)`.
- **FR-007**: System MUST migrate the Tableau **Rank Sort Measure** string‑list parameter (the four sort options; default "Order $ (Decending)") into a disconnected `Rank Sort Measure` DATATABLE (`Label`/`SortOrder` columns) rendered as a single‑select slicer, consumed via `SELECTEDVALUE('Rank Sort Measure'[Label], "Order $ (Decending)")`.

#### Measure & Calculated-Column Migration (Complete Coverage)

- **FR-008**: System MUST provide a primary value measure **Order $** = `SUM(LaunchData[Order $ (USD)])`, formatted as currency (`$#,##0`), used as the base for ranking and percent‑of‑total.
- **FR-009**: System MUST provide a **Measure for Rank** DAX measure using `SWITCH(SELECTEDVALUE('Rank Sort Measure'[Label]), …)` returning `[Order $]`, `[Order Quantity]`, or their negatives for the ascending options — mirroring the Tableau parameter‑driven `CASE`.
- **FR-010**: System MUST provide a **Rank** measure `RANKX(ALLSELECTED(LaunchData[Base Part Number]), [Measure for Rank], , DESC, Dense)` replicating the Tableau `RANK(SUM([Measure for Rank]))` table calculation.
- **FR-011**: System MUST provide a **Rank Filter** measure `IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value], 10), 1, 0)` to enforce the parameter‑driven Top‑N selection on Top Parts visuals (no `filters`/`filterConfig` at the `visual.json` root).
- **FR-012**: System MUST provide an **Order $ (Percent of Total)** measure `DIVIDE([Order $], CALCULATE([Order $], ALLSELECTED(LaunchData)))` formatted `0.00%` (matching Tableau `p0.00%`), divide‑by‑zero safe.
- **FR-013**: System MUST provide a **Style Count** measure `DISTINCTCOUNT(LaunchData[Master Style])` (Tableau `COUNTD([Master Style])`).
- **FR-014**: System MUST migrate **Master Style** as a calculated column (or M column) = first 8 characters of trimmed `Style Code` (Tableau `LEFT([Style Code],8)`).
- **FR-015**: System MUST migrate **Region** as a calculated column using `SWITCH(TRUE(), 'LaunchData'[Sales Area]="Canada","Canada", 'LaunchData'[Sales Area]="United States of America","USA", 'LaunchData'[Macro Area])` — the Tableau Canada/USA/Macro Area consolidation.
- **FR-016**: System MUST provide supporting aggregate measures used by the dashboards — Order Quantity (`SUM`), and any KPI/card aggregates needed by the Launch Summary and Style Count cards — each with an appropriate format string.
- **FR-017**: System MUST migrate the distinct logical Tableau calculated fields exactly once; pure aliases and "(copy)" duplicates (`Base Style Name`, `Delivery Season (copy)`, `Delivery Month (copy)`, `Category (copy)`, `Base Part (copy)`, and the `(copy)` measure variants) MUST reuse the original source columns/measures rather than create redundant new objects.
- **FR-018**: Every migrated measure MUST carry an appropriate format string (currency `$#,##0`, percent `0.00%`, integer `#,##0`, rank) matching the Tableau field formatting, and be grouped into logical display folders (e.g., Core Metrics, Ranking, Parameters).

#### Report — Pages & Visuals (5 Dashboards → 5 Pages)

- **FR-019**: System MUST produce exactly five report pages, one per Tableau dashboard: **Data Detail**, **Delivery Season Summary**, **Launch Report Dashboard**, **Slide View 1**, and **Slide View 2** (page names sanitized to match `^[\w-]+$`).
- **FR-020**: The **Data Detail** page MUST reproduce the large `Data` worksheet as a **Table/Matrix** of launch records, accompanied by the ~13 slicers (Region, Sales Area, Delivery Season, Delivery Month, Garment Type, Product Gender, Product Category, Product Family, Product Sub‑Family, Base Style Name, Style Code, Base Part Number, Style Description).
- **FR-021**: The **Delivery Season Summary** page MUST reproduce the 4‑column small‑multiple grid of summaries (MacroArea 1‑4, Garment Type 1‑4, Gender 1‑4, Category 1‑4) as **bar charts**, plus the Top Parts (US / Int / All) summaries as **tables/matrices**.
- **FR-022**: The **Launch Report Dashboard** page (main) MUST reproduce: **bar charts** for MacroArea, Gender, Category, Family, Delivery Season, and Garment Type; a **Top Parts table/matrix** (ranked, with Order $ and Order $ Percent of Total); **KPI cards** for Launch Summary; and a **Sales by Date** line/column chart over Date colored by **Reorder Type** (New vs Reorder) with a legend.
- **FR-023**: The **Slide View 1** page MUST reproduce the slide layout containing: Sales by Date (chart), MacroArea (chart), Launch Summary (**KPI card**), Category (chart), Delivery Season (chart), and Style Count (**KPI card**).
- **FR-024**: The **Slide View 2** page MUST reproduce the slide layout containing: Sales by Date (chart), MacroArea (chart), Delivery Season (chart), Family (chart), Launch Summary (KPI), Style Count (KPI), the slicers (Product Category, Product Gender, Garment Type), and a **Reorder Type color legend**.
- **FR-025**: Each **Top Parts** visual MUST honor the **Rank Filter** measure so only the top `Rows Displayed` parts (ranked by **Measure for Rank**) are shown, re‑ranking when **Rank Sort Measure** changes.
- **FR-026**: The **Sales by Date** visual MUST use `DimDate` (or `LaunchData[Date]`) as the time axis and encode **Reorder Type** as the series color, reproducing the Tableau New/Reorder color encoding.

#### Fidelity & Formatting

- **FR-027**: Each visual MUST replicate the corresponding Tableau mark type: table → Table/Matrix, bar → bar chart, line → line/column chart, KPI/text → Card. No mark type may be substituted with an incompatible visual.
- **FR-028**: Numeric, currency, and percent formats in all visuals MUST preserve the source Tableau formatting (currency `$#,##0`, percent‑of‑total `0.00%`).
- **FR-029**: Every visual MUST carry a descriptive title (from the Tableau worksheet name), a 1px `#E0E0E0` border, and alt text; all table/matrix projections MUST be `active: true` (constitution §9).
- **FR-030**: The generated `report.json` MUST use the minimal PBIR enhanced template (no forbidden properties), and `visual.json` files MUST NOT carry any disallowed top‑level properties (no `filters`/`filterConfig` at root) per the PBIR format rules.

### Key Entities *(include if feature involves data)*

- **LaunchData (Single Flat Table)**: One row per launch/order record. Retains all 53 source columns — dimensions (Base Part/Number, Base Style/Name, Category, Collection, Color, Date, Delivery Date/Month/Season and their trailing-space variants, Family, Garment Type, Gender, Global, Item Code, Macro Area, Master Style, Micro Area, Month, Product Category/Family/Gender/Sub‑Family, Region, Reorder Type, Sales Area, Style/Code/Description and variants, Sub‑Family, Year) and measures (Cost, Dnet, Margin $, Measure for Rank, MSRP, Order $ (U.S. Cost/Dealer Net/MSRP), Order $ (USD), Order Quantity, Style Count, Sum of Extra/Quantity Units). Derived columns added: `Master Style`, `Region`.
- **DimDate (Dimension)**: M‑generated calendar (Date, Year, Month Number, Month Name) joined many‑to‑one, single‑direction to `LaunchData[Date]`; supplies the Sales‑by‑Date time axis only.
- **Rows Displayed (Parameter)**: Disconnected DATATABLE (`Label`/`Value`: 5, 10, 20, 50, All=10000; default 10) driving the Top‑N row count via `SELECTEDVALUE`.
- **Rank Sort Measure (Parameter)**: Disconnected DATATABLE (`Label`/`SortOrder`: four sort options; default "Order $ (Decending)") driving the ranking measure/direction via `SELECTEDVALUE`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The semantic model contains exactly one primary flat table `LaunchData` (53 source columns + `Master Style` + `Region`), an M‑generated `DimDate` related many‑to‑one to `LaunchData[Date]`, and the two disconnected parameter tables — with no fact/dimension decomposition, sets, groups, bins, or RLS roles.
- **SC-002**: 100% of the Tableau calculated fields in scope (Rank, Order $ (Percent of Total), Master Style, Style Count, Region, Measure for Rank, Rank Filter) have corresponding DAX measures or calculated columns — zero omissions, no redundant "(copy)" duplicates.
- **SC-003**: Both parameters (Rows Displayed, Rank Sort Measure) are present as disconnected slicer tables with the exact Tableau domains and defaults, and every Top Parts visual responds to both in a single interaction.
- **SC-004**: The report contains exactly five pages, one per Tableau dashboard, and each visual replicates the source mark type (table→table/matrix, bar→bar, line→line, KPI→card) with the same fields.
- **SC-005**: Changing **Rows Displayed** or **Rank Sort Measure** re‑trims/re‑ranks every Top Parts visual consistently, including the "All" (10000) and tie cases, with no error or truncation.
- **SC-006**: The Order $ (Percent of Total) and any ratio measures return a graceful blank (no error) when the context total is zero/blank, and `Master Style` handles Style Codes shorter than 8 characters without error.
- **SC-007**: The generated `.pbip` passes structural validation (TMDL `tmdl-validate` + `validate_pbip.py` + PBIR JSON checks) with zero errors, and opens in Power BI Desktop with no load errors.

## Assumptions

- The migration source is the flat CSV `Data/Q3 Buyer/Q3LaunchData 1.csv` (not the original Excel `Q3 Launch Data.xlsx`); a developer will repoint the file path if running outside the original environment. Import mode is used per constitution §6.
- The single denormalized datasource is kept as one table `LaunchData` (constitution §0); no star‑schema decomposition is applied because there are no joins or multiple datasources.
- The precomputed CSV columns `Measure for Rank` and `Style Count` are retained, but the **parameter‑driven measure versions** are authoritative for ranking and distinct counting because they must respond to slicer/parameter context.
- Both Tableau parameters are reproduced as disconnected DATATABLE slicers consumed via `SELECTEDVALUE`; the "All" option maps to value 10000 as in the source.
- A generated `DimDate` provides the Sales‑by‑Date continuous time axis; the flat table's own `Year`/`Month` integer columns remain available for non‑continuous axes.
- The 49 Tableau worksheets are reproduced as the visuals composing the 5 dashboard pages, not as 49 separate report pages; the per‑category "- 1/- 2/- 3/- 4" and "(Slide)" variants are layout building blocks.
- KPI/Launch Summary and Style Count tiles are reproduced with native **Card** visuals; bar/line charts use the nearest native Power BI chart types matching the Tableau encodings (Reorder Type as series color on Sales by Date).
- Trailing‑space duplicate source columns are loaded as-is for fidelity but are not used for key derivation; the trimmed canonical columns drive `Master Style` and `Region`.
- The 8 Tableau `<group>` elements are auto‑generated hidden dashboard‑action helpers, not user groups, and are not reproduced. No sets, groups, bins, or RLS are implemented, consistent with the analysis.
