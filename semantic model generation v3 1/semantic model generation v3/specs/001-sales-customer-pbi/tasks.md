# Tasks: Sales & Customer Dashboards — Tableau → Power BI Migration

**Input**: Design documents from `specs/001-sales-customer-pbi/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅
**Design Artifacts**: `.specify/memory/star-schema-output.md` (6 tables, 5 relationships), `.specify/memory/dax-measures-output.md` (39 measures + 1 calculated table)
**Constitution**: `.specify/memory/constitution.md` (NEVER modify — read-only rulebook)
**Output Target**: `Output/SalesCustomerDashboards/`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US1]**: Load and Model Source Data (P1)
- **[US2]**: Calculate Year-Over-Year Measures (P1)
- **[US3]**: Customer-Level Analytics (P2)
- **[US4]**: Navigation and Interactivity (P3)

---

## Phase 1: Setup (Validation & Confirmation)

**Purpose**: Validate constitution compliance and confirm all design artifacts exist before generation

- [ ] T001 Read `.specify/memory/constitution.md` and verify all rules (§0–§10) are documented and applicable
- [ ] T002 [P] Verify `.specify/memory/star-schema-output.md` exists with 6 tables (FactOrders, DimCustomer, DimLocation, DimProduct, DimDate, SelectYear) and 5 relationships
- [ ] T003 [P] Verify `.specify/memory/dax-measures-output.md` exists with 39 measures across 8 display folders + SelectYear DATATABLE definition
- [ ] T004 [P] Verify source CSV files exist: `Data/Sales and Customer/Orders.csv`, `Customers.csv`, `Location.csv`, `Products.csv`
- [ ] T005 Read `plugins/pbip/skills/tmdl/SKILL.md` for TMDL syntax rules (indentation, quoting, property ordering)
- [ ] T006 [P] Read `plugins/pbip/skills/pbir-format/SKILL.md` for report JSON schema rules
- [ ] T007 Create output directory structure: `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/` and `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/`

**Checkpoint**: All inputs validated — generation can proceed

---

## Phase 2: Foundational PBIP Structure (Blocking Prerequisites)

**Purpose**: Generate project scaffolding files that ALL table/report files depend on

**⚠️ CRITICAL**: No table TMDL or report JSON can be written until these files exist

- [ ] T008 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.pbip` (root project file with version, semantic model + report references)
- [ ] T009 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition.pbism` (version 4.2, Import mode)
- [ ] T010 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/.platform` (metadata config)
- [ ] T011 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/.platform` (metadata config)
- [ ] T012 Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/database.tmdl` (compatibilityLevel 1604, model name)
- [ ] T013 Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/model.tmdl` (culture en-US, defaultPowerBIDataSourceVersion, ref tables for FactOrders/DimCustomer/DimLocation/DimProduct/DimDate/SelectYear, annotations)

**Checkpoint**: PBIP scaffolding complete — table and relationship files can be generated

---

## Phase 3: User Story 1 — Load and Model Source Data (Priority: P1) 🎯 MVP

**Goal**: All four CSV sources load correctly with proper data types; star-schema relationships resolve without errors

**Independent Test**: Open `.pbip` in Power BI Desktop → all tables appear in model view → relationships connect correctly → data preview shows rows with correct types

### Implementation for User Story 1

- [ ] T014 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/FactOrders.tmdl` — M query loading `Data/Sales and Customer/Orders.csv` with `Delimiter=";"`, `QuoteStyle=QuoteStyle.Csv`, `Encoding=65001`, `Culture="de-DE"`; 13 columns (Row ID int, Order ID text, Order Date date, Ship Date date, Ship Mode text, Segment text, Customer ID text, Postal Code text, Product ID text, Sales decimal, Quantity int, Discount decimal, Profit decimal)
- [ ] T015 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/DimCustomer.tmdl` — M query loading `Data/Sales and Customer/Customers.csv` with semicolon delimiter; 2 columns (Customer ID text key, Customer Name text)
- [ ] T016 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/DimLocation.tmdl` — M query loading `Data/Sales and Customer/Location.csv` with semicolon delimiter; 5 columns (Postal Code text key, City text, State text, Region text, Country/Region text); data categories (City, StateOrProvince, PostalCode, Country); Geography hierarchy
- [ ] T017 [P] [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/DimProduct.tmdl` — M query loading `Data/Sales and Customer/Products.csv` with semicolon delimiter; 4 columns (Product ID text key, Category text, Sub-Category text, Product Name text); Product Category hierarchy
- [ ] T018 [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/DimDate.tmdl` — M query generated date table (List.Dates, range 2020-01-01 to 2023-12-31); 12 columns (Date date key, Year int, Quarter int, QuarterLabel text, Month int, MonthName text, MonthShort text, Day int, WeekNum int, DayOfWeek int, DayName text, YearMonth text); markAsDateTable on Date column; Date hierarchy
- [ ] T019 [US1] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/relationships.tmdl` — 5 relationships: DimCustomer[Customer ID] → FactOrders[Customer ID] (active, single), DimLocation[Postal Code] → FactOrders[Postal Code] (active, single), DimProduct[Product ID] → FactOrders[Product ID] (active, single), DimDate[Date] → FactOrders[Order Date] (active, single), DimDate[Date] → FactOrders[Ship Date] (inactive, single)

**Checkpoint**: All tables and relationships defined — measures can be added; model loads in Desktop with correct schema

---

## Phase 4: User Story 2 + User Story 3 — Year-Over-Year & Customer Measures (Priority: P1/P2)

**Goal**: All 39 DAX measures calculate correctly; SelectYear parameter drives CY/PY logic; customer-level KPIs available

**Independent Test**: Place `[CY Sales]` on card with year slicer → shows correct year total; `[% Diff Sales]` → shows YoY change; `[CY Customers]` → distinct customer count for selected year

### Implementation for User Stories 2 & 3

- [ ] T020 [US2] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/SelectYear.tmdl` — DAX DATATABLE calculated table with Year column (2020, 2021, 2022, 2023); include `Current Year` and `Previous Year` measures in Parameters display folder
- [ ] T021 [US2] Add 8 Core Metrics measures to FactOrders.tmdl — Total Sales, Total Profit, Total Quantity, Total Discount, Order Count, Customer Count, Average Sales, Average Profit (display folder: `Core Metrics`)
- [ ] T022 [US2] Add 6 Current Year measures to FactOrders.tmdl — CY Sales, CY Profit, CY Quantity, CY Customers, CY Orders, CY Sales per Customer (display folder: `Year-over-Year\Current Year`); uses CALCULATE with DimDate[Year] = SELECTEDVALUE(SelectYear[Year])
- [ ] T023 [US2] Add 6 Previous Year measures to FactOrders.tmdl — PY Sales, PY Profit, PY Quantity, PY Customers, PY Orders, PY Sales per Customer (display folder: `Year-over-Year\Previous Year`); uses SELECTEDVALUE(SelectYear[Year]) - 1
- [ ] T024 [US2] Add 6 % Diff measures to FactOrders.tmdl — % Diff Sales, % Diff Profit, % Diff Quantity, % Diff Customers, % Diff Orders, % Diff Sales per Customers (display folder: `Year-over-Year\% Change`); uses DIVIDE(CY - PY, PY) returning BLANK() on zero
- [ ] T025 [US2] Add 3 KPI Indicator measures to FactOrders.tmdl — KPI Sales Avg, KPI Profit Avg, KPI CY Less PY (display folder: `KPI Indicators`)
- [ ] T026 [US2] Add 6 Min/Max measures to FactOrders.tmdl — Min/Max Sales, Min/Max Profit, Min/Max Quantity, Min/Max Customers, Min/Max Orders, Min/Max Sales Per Customers (display folder: `KPI Indicators\Min Max`)
- [ ] T027 [US3] Add 2 LOD Equivalent measures to FactOrders.tmdl — Nr of Orders per Customer, Grand Total CY Sales (display folder: `LOD Equivalents`)
- [ ] T028 Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/diagramLayout.json` (visual layout for model diagram view — position 6 tables in star arrangement)

**Checkpoint**: Complete semantic model — all 39 measures + SelectYear table; ready for TMDL validation

---

## Phase 5: Semantic Model Validation (Gate)

**Purpose**: Validate semantic model before proceeding to report layer

**⚠️ CRITICAL**: Report generation CANNOT begin until this phase passes with exit code 0

- [ ] T029 Run `tmdl-validate` on `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition` — fix any indentation, property ordering, or quoting errors
- [ ] T030 Run `validate_pbip.py` on `Output/SalesCustomerDashboards/` — fix any structural or schema errors (must exit code 0)
- [ ] T031 Verify all JSON files parse correctly: `.pbip`, `definition.pbism`, `diagramLayout.json`
- [ ] T032 Verify M query safety: no cross-query references, no hardcoded absolute paths beyond data folder, QuoteStyle.Csv present in all CSV loads

**Checkpoint**: Semantic model validated — report layer generation can begin

---

## Phase 6: User Story 4 — Report Layer & Navigation (Priority: P3)

**Goal**: Two report pages (Sales Dashboard, Customer Dashboard) with KPI visuals, charts, tables, slicers, and navigation buttons

**Independent Test**: Open report in Desktop → Sales page shows KPI line charts, subcategory bar, slicers → click navigation button → navigates to Customer page → Customer page shows distribution chart, top customers table

### Report Scaffolding

- [ ] T033 Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition.pbir` — byPath reference to `../SalesCustomerDashboards.SemanticModel` with correct schema version
- [ ] T034 [P] [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/version.json` (report format version)
- [ ] T035 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/report.json` — minimal report config with themeCollection per constitution §8

### Sales Dashboard Page

- [ ] T036 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/SalesDashboard/page.json` — displayName "Sales Dashboard", 1280×720 canvas
- [ ] T037 [P] [US4] Create visual: KPI Sales line chart in `pages/SalesDashboard/visuals/kpiSales/visual.json` — lineChart with CY Sales, PY Sales by Month; markers; KPI Sales Avg reference line
- [ ] T038 [P] [US4] Create visual: KPI Profit line chart in `pages/SalesDashboard/visuals/kpiProfit/visual.json` — lineChart with CY Profit, PY Profit by Month; markers
- [ ] T039 [P] [US4] Create visual: KPI Quantity line chart in `pages/SalesDashboard/visuals/kpiQuantity/visual.json` — lineChart with CY Quantity, PY Quantity by Month; markers
- [ ] T040 [P] [US4] Create visual: Subcategory Comparison bar chart in `pages/SalesDashboard/visuals/subcategoryBar/visual.json` — barChart with CY Sales by Sub-Category (horizontal)
- [ ] T041 [P] [US4] Create visual: Weekly Trends in `pages/SalesDashboard/visuals/weeklyTrends/visual.json` — lineChart with CY Sales by Week
- [ ] T042 [P] [US4] Create visual: Year slicer in `pages/SalesDashboard/visuals/yearSlicer/visual.json` — slicer bound to SelectYear[Year], single-select
- [ ] T043 [P] [US4] Create visual: Category slicer in `pages/SalesDashboard/visuals/categorySlicer/visual.json` — dropdown slicer bound to DimProduct[Category]
- [ ] T044 [P] [US4] Create visual: Navigation button (→ Customer Dashboard) in `pages/SalesDashboard/visuals/navCustomer/visual.json` — actionButton with PageNavigation action
- [ ] T045 [P] [US4] Create visual: KPI legend card in `pages/SalesDashboard/visuals/kpiLegend/visual.json` — multi-row card showing % Diff Sales, % Diff Profit, % Diff Quantity

### Customer Dashboard Page

- [ ] T046 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/CustomerDashboard/page.json` — displayName "Customer Dashboard", 1280×720 canvas
- [ ] T047 [P] [US4] Create visual: KPI Customers line chart in `pages/CustomerDashboard/visuals/kpiCustomers/visual.json` — lineChart with CY Customers, PY Customers by Month
- [ ] T048 [P] [US4] Create visual: KPI Sales Per Customer line chart in `pages/CustomerDashboard/visuals/kpiSalesPerCust/visual.json` — lineChart with CY Sales per Customer, PY Sales per Customer by Month
- [ ] T049 [P] [US4] Create visual: KPI Orders line chart in `pages/CustomerDashboard/visuals/kpiOrders/visual.json` — lineChart with CY Orders, PY Orders by Month
- [ ] T050 [P] [US4] Create visual: Customer Distribution column chart in `pages/CustomerDashboard/visuals/custDistribution/visual.json` — columnChart with Customer Count by Region
- [ ] T051 [P] [US4] Create visual: Top Customers table in `pages/CustomerDashboard/visuals/topCustomers/visual.json` — table with Customer Name, CY Sales, CY Orders, CY Sales per Customer
- [ ] T052 [P] [US4] Create visual: Year slicer in `pages/CustomerDashboard/visuals/yearSlicer/visual.json` — slicer bound to SelectYear[Year], single-select
- [ ] T053 [P] [US4] Create visual: Region slicer in `pages/CustomerDashboard/visuals/regionSlicer/visual.json` — dropdown slicer bound to DimLocation[Region]
- [ ] T054 [P] [US4] Create visual: Navigation button (→ Sales Dashboard) in `pages/CustomerDashboard/visuals/navSales/visual.json` — actionButton with PageNavigation action
- [ ] T055 [P] [US4] Create visual: KPI legend card in `pages/CustomerDashboard/visuals/kpiLegend/visual.json` — multi-row card showing % Diff Customers, % Diff Orders, % Diff Sales per Customers

### Page Registry

- [ ] T056 [US4] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/pages.json` — ordered page list: SalesDashboard, CustomerDashboard

**Checkpoint**: Report layer complete — all visuals, slicers, navigation buttons generated

---

## Phase 7: Final Validation & Polish

**Purpose**: End-to-end validation of complete PBIP project (semantic model + report)

- [ ] T057 Run `tmdl-validate` on `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition` — confirm exit code 0
- [ ] T058 Run `validate_pbip.py` on `Output/SalesCustomerDashboards/` — confirm exit code 0 for full project (model + report)
- [ ] T059 Validate all report JSON files parse without errors: `definition.pbir`, `report.json`, `version.json`, all `page.json`, all `visual.json`
- [ ] T060 Verify `definition.pbir` byPath target resolves to existing semantic model folder
- [ ] T061 Verify page names match regex `^[\w-]+$` (no spaces, dots, special punctuation)
- [ ] T062 Verify visual.json files contain only allowed top-level properties: `$schema`, `name`, `position` + (`visual` | `visualGroup`) — NO `filters`, `filterConfig`, or extra properties
- [ ] T063 Verify M query relationship integrity: all FK columns (Customer ID, Postal Code, Product ID, Order Date, Ship Date) referenced in relationships exist in table definitions
- [ ] T064 Cross-check measure references: all 39 measures in dax-measures-output.md are present in TMDL files with correct display folders and format strings
- [ ] T065 Run quickstart.md validation steps (documented in `specs/001-sales-customer-pbi/quickstart.md`)

**Checkpoint**: Full PBIP project validated — ready for Power BI Desktop

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational PBIP)**: Depends on Phase 1 completion — BLOCKS all table/report files
- **Phase 3 (US1 - Tables + Relationships)**: Depends on Phase 2 (scaffolding must exist)
- **Phase 4 (US2/US3 - Measures)**: Depends on Phase 3 (table files must exist to add measures)
- **Phase 5 (Semantic Model Validation)**: Depends on Phase 4 — BLOCKS report generation
- **Phase 6 (US4 - Report)**: Depends on Phase 5 passing (semantic model must validate before report binding)
- **Phase 7 (Final Validation)**: Depends on Phase 6 completion

### User Story Dependencies

- **US1 (Load & Model)**: Foundation for all other stories — tables + relationships must exist first
- **US2 (YoY Measures)**: Depends on US1 — measures go INTO table TMDL files
- **US3 (Customer Analytics)**: Depends on US1 — additional measures in same files; can parallel with US2
- **US4 (Navigation & Report)**: Depends on US1+US2+US3 complete + validated — report binds to semantic model

### Within Phase 3 (Tables)

- T014–T017 (CSV tables) can run in parallel [P] — independent files
- T018 (DimDate) should follow CSV tables (may reference date range)
- T019 (relationships) depends on ALL table files existing

### Within Phase 4 (Measures)

- T020 (SelectYear) first — other measures reference it via SELECTEDVALUE
- T021–T027 can run sequentially within FactOrders.tmdl (same file, cumulative)
- T028 (diagramLayout) can parallel with any measure task [P]

### Within Phase 6 (Report)

- T033–T035 (scaffolding) first
- T036 + T046 (page.json) before their visuals
- All visuals within a page can run in parallel [P]
- T056 (pages.json) after both pages exist

---

## Parallel Opportunities

### Phase 2 — All scaffolding files in parallel:
```
T008 (.pbip) | T009 (.pbism) | T010 (.platform SM) | T011 (.platform Report)
```

### Phase 3 — CSV table files in parallel:
```
T014 (FactOrders) | T015 (DimCustomer) | T016 (DimLocation) | T017 (DimProduct)
```

### Phase 6 — Visuals per page in parallel:
```
Sales page: T037 | T038 | T039 | T040 | T041 | T042 | T043 | T044 | T045
Customer page: T047 | T048 | T049 | T050 | T051 | T052 | T053 | T054 | T055
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup ✓
2. Complete Phase 2: PBIP scaffolding ✓
3. Complete Phase 3: Tables + relationships (US1)
4. Complete Phase 4: DAX measures (US2/US3)
5. **STOP and VALIDATE** (Phase 5): Run tmdl-validate + validate_pbip.py
6. At this point: semantic model opens in Power BI Desktop with all measures working

### Full Delivery (Add Report)

7. Complete Phase 6: Report visuals + navigation (US4)
8. Complete Phase 7: Final end-to-end validation
9. Result: Complete .pbip project with 2 dashboard pages

### Key Rules

- **Constitution** (`.specify/memory/constitution.md`) is the SINGLE SOURCE OF TRUTH — never modify it
- **TMDL syntax** must follow `plugins/pbip/skills/tmdl/SKILL.md` rules exactly
- **PBIR JSON** must follow `plugins/pbip/skills/pbir-format/SKILL.md` schema
- **Validation** must pass (exit code 0) before presenting output to user
- All measures use `DIVIDE()` for division, `VAR/RETURN` pattern, proper display folders
- M queries: independent loads, no cross-references, `QuoteStyle.Csv`, `"de-DE"` culture

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 65 |
| Phase 1 (Setup) | 7 |
| Phase 2 (Foundational) | 6 |
| Phase 3 (US1 - Tables) | 6 |
| Phase 4 (US2/US3 - Measures) | 9 |
| Phase 5 (SM Validation) | 4 |
| Phase 6 (US4 - Report) | 24 |
| Phase 7 (Final Validation) | 9 |
| Parallelizable tasks | 34 |
| MVP scope | Phases 1–5 (32 tasks) |
