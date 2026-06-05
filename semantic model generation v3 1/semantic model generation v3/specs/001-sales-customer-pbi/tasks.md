# Tasks: Sales & Customer Dashboards — Tableau → Power BI Migration

**Input**: Design documents from `specs/001-sales-customer-pbi/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅
**Design Artifacts**: `.specify/memory/SalesCustomerDashboards/star-schema-output.md` (6 tables, 4 active + 1 inactive relationships), `.specify/memory/SalesCustomerDashboards/dax-measures-output.md` (36 measures + DimDate + Select Year calculated tables)
**Constitution**: `.specify/memory/constitution.md` (read-only rulebook — NEVER modify)
**Output Target**: `Output/SalesCustomerDashboards/`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[US1]**: Load and Model Source Data (P1)
- **[US2]**: Calculate Year-Over-Year Measures (P1)
- **[US3]**: Customer-Level Analytics (P2)
- **[US4]**: Reproduce Dashboards, Navigation, and Interactivity (P3)

**Model facts** (authoritative for all tasks):

- Tables are **unprefixed**: `Orders` (fact), `Customers`, `Location`, `Products` (dims), `DimDate` (DAX `CALENDAR`), `Select Year` (disconnected DATATABLE).
- CSV encodings: **Orders = 65001**, **Customers = 1252**, **Location = 65001**, **Products = 1252**; all semicolon-delimited; `"de-DE"` culture typing.
- All **36 measures** are authored on `Orders.tmdl`. Pages are **1200×800**.

---

## Phase 1: Setup (Validation & Confirmation)

**Purpose**: Confirm inputs and format rules before generation

- [ ] T001 Read `.specify/memory/constitution.md` and confirm rules §0–§10 apply to this migration
- [ ] T002 [P] Verify `.specify/memory/SalesCustomerDashboards/star-schema-output.md` exists with 6 tables (Orders, Customers, Location, Products, DimDate, Select Year) and 4 active + 1 inactive relationships
- [ ] T003 [P] Verify `.specify/memory/SalesCustomerDashboards/dax-measures-output.md` exists with 36 measures across 7 display folders (Base Metrics, Parameters, Year-over-Year\Current Year, Year-over-Year\Previous Year, Year-over-Year\% Change, KPI Indicators, KPI Indicators\Min Max, LOD Equivalents)
- [ ] T004 [P] Verify source CSV files exist: `Data/Sales and Customer/Orders.csv`, `Customers.csv`, `Location.csv`, `Products.csv`
- [ ] T005 Read `plugins/pbip/skills/tmdl/SKILL.md` for TMDL syntax rules (indentation, quoting, property ordering, `///` descriptions, no measure inside CALCULATE boolean filter)
- [ ] T006 [P] Read `plugins/pbip/skills/pbir-format/SKILL.md` for PBIR JSON schema rules (visual.json root limited to `$schema`/`name`/`position`/`visual`)
- [ ] T007 Create output directory tree: `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/` and `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/`

**Checkpoint**: All inputs validated — generation can proceed

---

## Phase 2: Foundational PBIP Scaffolding (Blocking Prerequisites)

**Purpose**: Generate project scaffolding that ALL table/report files depend on

**⚠️ CRITICAL**: No table TMDL or report JSON can be written until these files exist

- [ ] T008 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.pbip` (root project file referencing the semantic model + report artifacts)
- [ ] T009 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition.pbism` (Import mode model reference)
- [ ] T010 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/.platform` (semantic model metadata config)
- [ ] T011 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/.platform` (report metadata config)
- [ ] T012 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/database.tmdl` (compatibilityLevel, database name)
- [ ] T013 Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/model.tmdl` (culture `en-DE`, `defaultPowerBIDataSourceVersion`, `ref table` for Orders/Customers/Location/Products/DimDate/`Select Year`, model annotations)

**Checkpoint**: PBIP scaffolding complete — table and relationship files can be generated

---

## Phase 3: User Story 1 — Load and Model Source Data (Priority: P1) 🎯 MVP

**Goal**: All four CSV sources load with correct en_DE types; `DimDate` + `Select Year` generated; star-schema relationships resolve without errors

**Independent Test**: Open `Output/SalesCustomerDashboards/SalesCustomerDashboards.pbip` in Power BI Desktop → Orders, Customers, Location, Products, DimDate, Select Year appear → relationships connect → data preview shows correctly typed rows

### Source Tables (M partitions)

- [ ] T014 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Customers.tmdl` — `Csv.Document` over `Data/Sales and Customer/Customers.csv` (`Delimiter=";"`, `Columns=2`, `Encoding=1252`, `QuoteStyle=QuoteStyle.Csv`, `"de-DE"` typing); 2 columns (Customer ID text **hidden PK**, Customer Name text)
- [ ] T015 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Location.tmdl` — `Csv.Document` over `Data/Sales and Customer/Location.csv` (`Delimiter=";"`, `Columns=5`, `Encoding=65001`, `QuoteStyle=QuoteStyle.Csv`, `"de-DE"` typing); 5 columns (Postal Code Int64 **hidden PK** dataCategory=PostalCode, City text dataCategory=City, State text dataCategory=StateOrProvince, Region text **no geo category**, Country/Region text dataCategory=Country); Geography hierarchy Country/Region > Region > State > City
- [ ] T016 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Products.tmdl` — `Csv.Document` over `Data/Sales and Customer/Products.csv` (`Delimiter=";"`, `Columns=4`, `Encoding=1252`, `QuoteStyle=QuoteStyle.Csv`, `"de-DE"` typing); 4 columns (Product ID text **hidden PK**, Category text, Sub-Category text, Product Name text); Product hierarchy Category > Sub-Category > Product Name
- [ ] T017 [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl` (structure only) — `Csv.Document` over `Data/Sales and Customer/Orders.csv` (`Delimiter=";"`, `Columns=13`, `Encoding=65001`, `QuoteStyle=QuoteStyle.Csv`, `"de-DE"` typing); **13 columns** (Row ID Int64 hidden, Order ID text, Order Date date, Ship Date date, Ship Mode text, Customer ID text **hidden FK**, Segment text, Postal Code Int64 **hidden FK**, Product ID text **hidden FK**, Sales number, Quantity Int64, Discount number, Profit number). Measures added in Phase 4.

### Generated Tables (DAX calculated)

- [ ] T018 [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/DimDate.tmdl` — DAX `CALENDAR` calculated table spanning Jan 1 of `MIN(Orders[Order Date])` year → Dec 31 of `MAX(Orders[Order Date])` year; columns Date (key), Year, Quarter, Month, MonthName (**Sort By = Month**), Day, DayOfWeek, WeekNum; **mark as date table** on Date; Date hierarchy Year > Quarter > MonthName > Day
- [ ] T019 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Select Year.tmdl` — disconnected DAX `DATATABLE` with single Int64 column `Year` (2020, 2021, 2022, 2023); no relationships

### Relationships

- [ ] T020 [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/relationships.tmdl` — 4 active 1:many single-direction (Customers[Customer ID]→Orders[Customer ID], Location[Postal Code]→Orders[Postal Code], Products[Product ID]→Orders[Product ID], DimDate[Date]→Orders[Order Date]) + 1 optional **inactive** DimDate[Date]→Orders[Ship Date]
- [ ] T021 [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/diagramLayout.json` — position the 6 tables in a star arrangement (Orders center; dims + DimDate around; Select Year offset/disconnected)

**Checkpoint**: All tables + relationships defined — model loads in Desktop with correct schema (US1 independently testable)

---

## Phase 4: User Story 2 + User Story 3 — Year-Over-Year & Customer Measures (Priority: P1/P2)

**Goal**: All 36 DAX measures calculate correctly; `Select Year` drives CY/PY; customer-level KPIs available

**Independent Test**: Card bound to `[CY Sales]` with year slicer = 2023 shows the 2023 total; `[% Diff Sales]` shows YoY change; `[CY Customers]` shows distinct customers for the selected year

> All measures are authored on `Orders.tmdl` (created in T017). Add them in display-folder groups. Preserve format strings (`\$#,##0,"K";-\$#,##0,"K"`, `▲ 0.0%;▼ -0.0%`, `#,##0`) and `///` descriptions verbatim from `dax-measures-output.md`.

### Implementation for User Story 2

- [ ] T022 [US2] Add 5 **Base Metrics** measures to `Orders.tmdl` — Total Sales, Total Profit, Total Quantity, Total Orders, Total Customers (display folder `Base Metrics`)
- [ ] T023 [US2] Add 2 **Parameters** measures to `Orders.tmdl` — Current Year = `SELECTEDVALUE('Select Year'[Year], 2023)`, Previous Year = `… - 1` (display folder `Parameters`)
- [ ] T024 [US2] Add 6 **Current Year** measures to `Orders.tmdl` — CY Sales, CY Profit, CY Quantity, CY Orders, CY Customers, CY Sales per Customer; CY = VAR + `CALCULATE(…, FILTER(ALL(Orders[Order Date]), YEAR(...) = _CY))` (display folder `Year-over-Year\Current Year`)
- [ ] T025 [US2] Add 6 **Previous Year** measures to `Orders.tmdl` — PY Sales, PY Profit, PY Quantity, PY Orders, PY Customers, PY Sales per Customer; PY = CY − 1 boundary (display folder `Year-over-Year\Previous Year`)
- [ ] T026 [US2] Add 6 **% Change** measures to `Orders.tmdl` — % Diff Sales/Quantity/Customers/Orders/Sales per Customers divide by **PY**, % Diff Profit divides by **CY** (source-faithful); every ratio uses `DIVIDE()` (no fallback → BLANK) (display folder `Year-over-Year\% Change`, format `▲ 0.0%;▼ -0.0%`)
- [ ] T027 [US2] Add 3 **KPI Indicators** measures to `Orders.tmdl` — KPI Sales Avg + KPI Profit Avg (`AVERAGEX(ALLSELECTED(DimDate[WeekNum]), …)`), KPI CY Less PY (`IF([CY Sales] < [PY Sales], "⬤", "")`) (display folder `KPI Indicators`)
- [ ] T028 [US2] Add 6 **Min/Max** measures to `Orders.tmdl` — Min/Max Sales/Profit/Quantity/Customers/Orders/Sales per Customers via `MAXX`/`MINX` over `ALLSELECTED(DimDate[MonthName])` returning the CY value at extremes else BLANK (display folder `KPI Indicators\Min Max`)

### Implementation for User Story 3

- [ ] T029 [US3] Add 2 **LOD Equivalents** measures to `Orders.tmdl` — Nr of Orders per Customers (`CALCULATE(DISTINCTCOUNT(Orders[Order ID]), FILTER(ALL(Orders[Order Date]), YEAR=…_CY), ALLEXCEPT(Customers, Customers[Customer ID]))`), Grand Total CY Sales (`CALCULATE([CY Sales], REMOVEFILTERS())`) (display folder `LOD Equivalents`)

**Checkpoint**: Complete semantic model — 36 measures + DimDate + Select Year; ready for validation

---

## Phase 5: Semantic Model Validation (Gate)

**Purpose**: Validate semantic model before proceeding to the report layer

**⚠️ CRITICAL**: Report generation CANNOT begin until this phase passes with exit code 0

- [ ] T030 Run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\SalesCustomerDashboards\SalesCustomerDashboards.SemanticModel\definition"` — fix any indentation, property-order, or quoting errors
- [ ] T031 Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"` — fix structural/schema errors (must exit code 0)
- [ ] T032 [P] Verify `.pbip`, `definition.pbism`, `diagramLayout.json` parse as valid JSON
- [ ] T033 [P] Verify M-query safety: `QuoteStyle.Csv` + `"de-DE"` typing present in all 4 CSV loads; correct encodings (Orders/Location 65001, Customers/Products 1252); no cross-query references
- [ ] T034 [P] Confirm no measure is referenced inside a `CALCULATE` boolean filter; all CY/PY filter `Orders[Order Date]` via `FILTER(ALL(...))`

**Checkpoint**: Semantic model validated — report layer generation can begin

---

## Phase 6: User Story 4 — Report Layer & Navigation (Priority: P3)

**Goal**: Two 1200×800 report pages (Sales Dashboard, Customer Dashboard) reproducing the Tableau dashboards with KPI line charts, Subcategory Comparison, Weekly Trends, Customer Distribution, Top Customers, legends, the Select Year slicer, Category/Sub-Category/Region/State/City filters, and navigation; `Test KPI`/`Test KPI2`/`Test Max Min` excluded

**Independent Test**: Open report → both pages render their visuals + shared filter panel → navigation button switches pages → filter-toggle button shows/hides the filter panel

### Report Scaffolding

- [ ] T035 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition.pbir` — `byPath` dataset reference to `../SalesCustomerDashboards.SemanticModel`
- [ ] T036 [P] [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/version.json` (PBIR format version)
- [ ] T037 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/report.json` — minimal enhanced template with `themeCollection` (no `sections`/`modelExtensions`/`publicCustomVisuals`)

### Sales Dashboard Page (1200×800)

- [ ] T038 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/SalesDashboard/page.json` — displayName "Sales Dashboard", 1200×800 canvas
- [ ] T039 [P] [US4] Create `pages/SalesDashboard/visuals/legendKpi/visual.json` — KPI legend card (CY/PY swatches for the KPI trend charts)
- [ ] T040 [P] [US4] Create `pages/SalesDashboard/visuals/kpiSales/visual.json` — lineChart, Month axis, CY Sales + PY Sales, circle markers, Min/Max Sales markers
- [ ] T041 [P] [US4] Create `pages/SalesDashboard/visuals/kpiProfit/visual.json` — lineChart, Month axis, CY Profit + PY Profit, circle markers, Min/Max Profit markers
- [ ] T042 [P] [US4] Create `pages/SalesDashboard/visuals/kpiQuantity/visual.json` — lineChart, Month axis, CY Quantity + PY Quantity, circle markers, Min/Max Quantity markers
- [ ] T043 [P] [US4] Create `pages/SalesDashboard/visuals/legendSubcategory/visual.json` — Subcategory legend (CY/PY + KPI CY Less PY ⬤)
- [ ] T044 [P] [US4] Create `pages/SalesDashboard/visuals/subcategoryComparison/visual.json` — clustered bar, Sub-Category × (CY Sales + PY Sales), KPI CY Less PY ⬤ marker
- [ ] T045 [P] [US4] Create `pages/SalesDashboard/visuals/weeklyTrends/visual.json` — lineChart, Week (DimDate[WeekNum]) axis, CY Sales + PY Sales + KPI Sales Avg flag
- [ ] T046 [P] [US4] Create `pages/SalesDashboard/visuals/selectYearSlicer/visual.json` — single-select slicer bound to `'Select Year'[Year]`, default 2023
- [ ] T047 [P] [US4] Create `pages/SalesDashboard/visuals/categoryFilter/visual.json` — Category slicer (Products[Category])
- [ ] T048 [P] [US4] Create `pages/SalesDashboard/visuals/subCategoryFilter/visual.json` — Sub-Category slicer (Products[Sub-Category])
- [ ] T049 [P] [US4] Create `pages/SalesDashboard/visuals/regionFilter/visual.json` — Region slicer (Location[Region])
- [ ] T050 [P] [US4] Create `pages/SalesDashboard/visuals/stateFilter/visual.json` — State slicer (Location[State])
- [ ] T051 [P] [US4] Create `pages/SalesDashboard/visuals/cityFilter/visual.json` — City slicer (Location[City])
- [ ] T052 [P] [US4] Create `pages/SalesDashboard/visuals/navCustomer/visual.json` — actionButton, PageNavigation → Customer Dashboard
- [ ] T053 [P] [US4] Create `pages/SalesDashboard/visuals/navSales/visual.json` — actionButton, PageNavigation → Sales Dashboard (current)
- [ ] T054 [P] [US4] Create `pages/SalesDashboard/visuals/filterToggle/visual.json` — actionButton, Bookmark action to show/hide the filter panel

### Customer Dashboard Page (1200×800)

- [ ] T055 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/CustomerDashboard/page.json` — displayName "Customer Dashboard", 1200×800 canvas
- [ ] T056 [P] [US4] Create `pages/CustomerDashboard/visuals/legendKpi/visual.json` — KPI legend card (CY/PY swatches)
- [ ] T057 [P] [US4] Create `pages/CustomerDashboard/visuals/kpiCustomers/visual.json` — lineChart, Month axis, CY Customers + PY Customers, circle markers
- [ ] T058 [P] [US4] Create `pages/CustomerDashboard/visuals/kpiSalesPerCustomer/visual.json` — lineChart, Month axis, CY Sales per Customer + PY Sales per Customer, circle markers
- [ ] T059 [P] [US4] Create `pages/CustomerDashboard/visuals/kpiOrders/visual.json` — lineChart, Month axis, CY Orders + PY Orders, circle markers
- [ ] T060 [P] [US4] Create `pages/CustomerDashboard/visuals/customerDistribution/visual.json` — clustered column, Nr of Orders per Customers × distinct customer count
- [ ] T061 [P] [US4] Create `pages/CustomerDashboard/visuals/topCustomers/visual.json` — table: Customer Name, CY Sales, CY Orders, last Order Date
- [ ] T062 [P] [US4] Create `pages/CustomerDashboard/visuals/selectYearSlicer/visual.json` — single-select slicer bound to `'Select Year'[Year]`, default 2023
- [ ] T063 [P] [US4] Create `pages/CustomerDashboard/visuals/categoryFilter/visual.json` — Category slicer (Products[Category])
- [ ] T064 [P] [US4] Create `pages/CustomerDashboard/visuals/subCategoryFilter/visual.json` — Sub-Category slicer (Products[Sub-Category])
- [ ] T065 [P] [US4] Create `pages/CustomerDashboard/visuals/regionFilter/visual.json` — Region slicer (Location[Region])
- [ ] T066 [P] [US4] Create `pages/CustomerDashboard/visuals/stateFilter/visual.json` — State slicer (Location[State])
- [ ] T067 [P] [US4] Create `pages/CustomerDashboard/visuals/cityFilter/visual.json` — City slicer (Location[City])
- [ ] T068 [P] [US4] Create `pages/CustomerDashboard/visuals/navSales/visual.json` — actionButton, PageNavigation → Sales Dashboard
- [ ] T069 [P] [US4] Create `pages/CustomerDashboard/visuals/navCustomer/visual.json` — actionButton, PageNavigation → Customer Dashboard (current)
- [ ] T070 [P] [US4] Create `pages/CustomerDashboard/visuals/filterToggle/visual.json` — actionButton, Bookmark action to show/hide the filter panel

### Page Registry

- [ ] T071 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/pages.json` — ordered list (SalesDashboard, CustomerDashboard) with active page; confirm `Test KPI`/`Test KPI2`/`Test Max Min` are absent

**Checkpoint**: Report layer complete — both pages, visuals, slicers, filters, and navigation generated

---

## Phase 7: Final End-to-End Validation & Polish

**Purpose**: End-to-end validation of the complete PBIP project (semantic model + report)

- [ ] T072 Run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\SalesCustomerDashboards\SalesCustomerDashboards.SemanticModel\definition"` — confirm exit code 0
- [ ] T073 Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"` — confirm exit code 0 for the full project (model + report)
- [ ] T074 [P] JSON-parse check on `.Report/`: `definition.pbir`, `report.json`, `version.json`, all `page.json`, all `visual.json`, `pages.json`
- [ ] T075 [P] Verify `definition.pbir` `byPath` target resolves to the existing `.SemanticModel` folder
- [ ] T076 [P] Verify page folder names match `^[\w-]+$` (SalesDashboard, CustomerDashboard — no spaces/dots)
- [ ] T077 [P] Verify every `visual.json` root has only `$schema`, `name`, `position` + (`visual` | `visualGroup`) — NO `filters`/`filterConfig`/extra properties
- [ ] T078 [P] Cross-check all 36 measures from `dax-measures-output.md` are present in `Orders.tmdl` with correct display folders + format strings
- [ ] T079 [P] Verify relationship integrity: FK columns (Customer ID, Postal Code, Product ID, Order Date, Ship Date) exist in their table definitions and match `relationships.tmdl`
- [ ] T080 Run quickstart.md smoke-test steps from `specs/001-sales-customer-pbi/quickstart.md` (open in Desktop, default year 2023, navigation, filter toggle)

**Checkpoint**: Full PBIP project validated — ready for Power BI Desktop

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** → no dependencies; start immediately
- **Phase 2 (Scaffolding)** → depends on Phase 1; BLOCKS all table/report files
- **Phase 3 (US1 — tables + relationships)** → depends on Phase 2
- **Phase 4 (US2/US3 — measures)** → depends on Phase 3 (measures go INTO `Orders.tmdl`)
- **Phase 5 (Model validation GATE)** → depends on Phase 4; BLOCKS report generation
- **Phase 6 (US4 — report)** → depends on Phase 5 passing
- **Phase 7 (Final validation)** → depends on Phase 6

### User Story Dependencies

- **US1** (Load & Model) — foundation; tables + relationships must exist first
- **US2** (YoY Measures) — depends on US1; measures authored on `Orders.tmdl`
- **US3** (Customer Analytics) — depends on US1; LOD measures in `Orders.tmdl`; can follow US2
- **US4** (Report & Navigation) — depends on US1+US2+US3 validated; report binds to the model

### Parallel Opportunities

- **Phase 1**: T002, T003, T004, T006 in parallel
- **Phase 2**: T008–T012 in parallel (distinct scaffolding files); T013 after
- **Phase 3**: T014, T015, T016 (dim tables) in parallel; T017 (Orders structure) independent; T019 (Select Year) parallel; T018 (DimDate) after Orders exists (references Order Date); T020 + T021 after all tables exist
- **Phase 4**: T022–T029 are sequential (same file `Orders.tmdl`, cumulative edits)
- **Phase 5**: T030 → T031 sequential; T032, T033, T034 in parallel after
- **Phase 6**: all `visual.json` tasks within a page are [P] (distinct files); `page.json` before its visuals; `pages.json` (T071) after both pages
- **Phase 7**: T074–T079 in parallel after the two validators (T072, T073)

### Parallel Execution Example (Phase 6 — Sales Dashboard visuals)

```text
# After T038 (page.json) completes, launch in parallel:
T039 legendKpi · T040 kpiSales · T041 kpiProfit · T042 kpiQuantity ·
T043 legendSubcategory · T044 subcategoryComparison · T045 weeklyTrends ·
T046 selectYearSlicer · T047 categoryFilter · T048 subCategoryFilter ·
T049 regionFilter · T050 stateFilter · T051 cityFilter ·
T052 navCustomer · T053 navSales · T054 filterToggle
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) → Phase 2 (Scaffolding) → Phase 3 (US1).
2. **STOP and validate**: open in Power BI Desktop → all 6 tables load with correct types, relationships resolve. This is the independently shippable MVP.

### Incremental Delivery

1. **Setup + Scaffolding + US1** → model loads → validate → MVP.
2. **US2 + US3** (measures) → validate (Phase 5 gate) → analytical model complete.
3. **US4** (report) → validate (Phase 7) → full dashboards.

Each story checkpoint is independently testable and adds a working increment without breaking earlier stories.

### Suggested MVP Scope

**User Story 1 (Phases 1–3)** — a loadable, correctly-related star-schema model — is the minimum viable, independently testable deliverable.
