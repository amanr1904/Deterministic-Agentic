---
description: "Dependency-ordered task list for the Sales & Customer Dashboards Tableau → Power BI migration"
---

# Tasks: Sales & Customer Dashboards — Tableau → Power BI Migration

**Input**: Design documents from `specs/001-sales-customer-pbi/`
**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required), `.specify/memory/SalesCustomerDashboards/star-schema-output.md`, `.specify/memory/SalesCustomerDashboards/dax-measures-output.md`

**Tests**: No automated unit/integration test suite is requested. Validation is performed by the structural validators (`tmdl-validate`, `validate_pbip.py`) and functional DAX spot-checks per year — these appear as explicit validation tasks, not test-code tasks.

**Build target**: `Output/SalesCustomerDashboards/`
**Canvas**: 1280×720 (16:9 PBI standard — per plan, overrides spec's 1200×800 reference)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story the task serves — [US1] visuals/trends, [US2] model/measures, [US3] navigation/filtering
- Setup, Foundational, and Polish tasks carry no story label
- Every task lists an exact file path

## Path Conventions

All paths are relative to the workspace root. Generated artifacts live under:
- Model: `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/`
- Report: `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/`

---

## Phase 1: Setup (Project Scaffolding)

**Purpose**: Create the PBIP folder tree and project-entry/manifest files so the model and report skeletons resolve.

- [ ] T001 Create the output folder tree `Output/SalesCustomerDashboards/` with `SalesCustomerDashboards.SemanticModel/definition/tables/` and `SalesCustomerDashboards.Report/definition/pages/` subfolders
- [ ] T002 Create the project entry file `Output/SalesCustomerDashboards/SalesCustomerDashboards.pbip` (artifact references to the `.Report` definition)
- [ ] T003 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/.platform` and `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition.pbism`
- [ ] T004 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/diagramLayout.json` (empty/default layout)
- [ ] T005 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/.platform` and `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition.pbir` with `datasetReference` byPath → `../SalesCustomerDashboards.SemanticModel`
- [ ] T006 [P] Create `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/version.json` (report schema 3.0.0)

**Checkpoint**: PBIP skeleton exists and `definition.pbir` points at the semantic model folder.

---

## Phase 2: Foundational — Data Layer (Blocking Prerequisites)

**Purpose**: Author the model header plus every table's Power Query M partition (CSV load, key prep, generated calendar, What-If table). The model and all measures depend on these tables existing with correct columns and keys.

**⚠️ CRITICAL**: No measure, relationship, or report-visual task may begin until this phase is complete. Read `plugins/pbip/skills/tmdl/SKILL.md` for TMDL syntax rules before authoring any `.tmdl` file.

- [ ] T007 Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/database.tmdl` (compatibilityLevel 1567+, model id)
- [ ] T008 Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/model.tmdl` (culture `en-US`, `ref table` entries for all 6 tables, default annotations)
- [ ] T009 [P] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl` — M partition `Csv.Document(File.Contents("…\\Data\\Sales and Customer\\Orders.csv"), [Delimiter=";", Encoding=65001, QuoteStyle=QuoteStyle.Csv])`; promote headers; `Text.Trim` Customer ID & Product ID; Postal Code → `Text.Trim(Text.PadStart(Text.From([Postal Code]),5,"0"))` text; Order Date / Ship Date typed `date`; columns Row ID, Order ID, Order Date, Ship Date, Ship Mode, Customer ID, Segment, Postal Code, Product ID, Sales, Quantity, Discount, Profit with data types per star-schema
- [ ] T010 [P] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Customers.tmdl` — M partition (Customers.csv, Encoding=1252, `;`, QuoteStyle.Csv); `Text.Trim` Customer ID; columns Customer ID (text), Customer Name (text)
- [ ] T011 [P] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Location.tmdl` — M partition (Location.csv, Encoding=65001, `;`, QuoteStyle.Csv); Postal Code → zero-padded 5-char `Text.Trim`; columns Postal Code (text), City, State, Region, Country/Region; Geography hierarchy Region > State > City
- [ ] T012 [P] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Products.tmdl` — M partition (Products.csv, Encoding=1252, `;`, QuoteStyle.Csv); `Text.Trim` Product ID; columns Product ID (text), Category, Sub-Category, Product Name; Product hierarchy Category > Sub-Category > Product Name
- [ ] T013 [P] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/DimDate.tmdl` — M-generated daily calendar 2020-01-01 → 2023-12-31; columns Date, Year, Quarter, Quarter Name, Month Number, Month Name, Week of Year, Day; set Month Name `sortByColumn` = Month Number and Quarter Name `sortByColumn` = Quarter; Calendar hierarchy Year > Quarter Name > Month Name > Day; mark as date table on `Date`
- [ ] T014 [P] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Select Year.tmdl` — DAX calculated table `SELECTCOLUMNS(GENERATESERIES(2020,2023,1),"Year",[Value])`, column `Year` (Int64), disconnected (no relationship)

**Checkpoint**: All 6 tables load with trimmed keys, the calendar is marked as a date table, and the What-If table exists. Model layer can begin.

---

## Phase 3: User Story 2 — Star-Schema Model with Complete Measure Coverage (Priority: P1) 🎯 MVP foundation

**Goal**: Wire the four many-to-one relationships and add all 45 explicit DAX measures (grouped into display folders with format strings) so every Tableau calculated field is covered.

**Independent Test**: Inspect relationships (4 active many-to-one, single-direction); enumerate measures against the dax-measures index (expect 45/45); evaluate sample measures via DAX query for years 2020–2023 and confirm CY/PY/%Diff results are sensible and divide-by-zero safe.

> Measures are added into existing table files from Phase 2 — measure tasks on the **same** table run sequentially; measure tasks on **different** tables may run in parallel. DAX is copied verbatim from `dax-measures-output.md` (preserve the two `-- REVIEW` notes).

- [ ] T015 [US2] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/relationships.tmdl` — 4 active many-to-one single-direction: Customers[Customer ID]→Orders[Customer ID], Location[Postal Code]→Orders[Postal Code], Products[Product ID]→Orders[Product ID], DimDate[Date]→Orders[Order Date]; optional inactive DimDate[Date]→Orders[Ship Date]
- [ ] T016 [P] [US2] Add the 2 **Parameters** measures (Selected Year, Previous Year, format `0`) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Select Year.tmdl`, display folder "Parameters"
- [ ] T017 [P] [US2] Add the 2 **Ranking** measures (Customer Rank `"#"0`, Top 10 Customer Filter `0`) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Customers.tmdl`, display folder "Ranking"
- [ ] T018 [US2] Add the 6 **Current Year** measures (CY Sales, CY Profit, CY Quantity, CY Customers, CY Orders, CY Sales per Customer) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl`, display folder "Current Year", with format strings per index
- [ ] T019 [US2] Add the 6 **Previous Year** measures (PY Sales, PY Profit, PY Quantity, PY Customers, PY Orders, PY Sales per Customer) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl`, display folder "Previous Year"
- [ ] T020 [US2] Add the 6 **Year-over-Year** measures (% Diff Sales/Profit/Quantity/Orders/Customers/Sales per Customer, format `"▲ "0.0%;"▼ "0.0%`, DIVIDE-safe) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl`, display folder "Year-over-Year"
- [ ] T021 [US2] Add the 18 **Highlights** measures (Max/Min/Marker × Sales, Profit, Quantity, Orders, Customers, Sales per Customer) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl`, display folder "Highlights"
- [ ] T022 [US2] Add the 2 **LOD** measures (Total CY Sales (Fixed), Nr of Orders per Customer (Fixed)) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl`, display folder "LOD"
- [ ] T023 [US2] Add the 3 **KPI Helpers** measures (KPI CY Less PY, KPI Sales Avg, KPI Profit Avg, text) into `Output/SalesCustomerDashboards/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl`, display folder "KPI Helpers"

### TMDL Validation (User Story 2)

- [ ] T024 [US2] Run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\SalesCustomerDashboards\SalesCustomerDashboards.SemanticModel\definition"`; fix any indentation, property-order, quoting, or referential-integrity errors before proceeding
- [ ] T025 [US2] Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"` and confirm the semantic model section reports zero errors (exit code 0/1); fix any exit-code-2 errors
- [ ] T026 [US2] Functional spot-check: run DAX queries for CY/PY/%Diff measures with Select Year = 2020, 2021, 2022, 2023 (via the DAX query tooling) and confirm results match Tableau within rounding tolerance and return BLANK (not error) for PY 2019

**Checkpoint**: Model is complete, relationships resolve, all 45 measures evaluate correctly, and TMDL validation passes. The semantic model is independently usable (SC-001, SC-002, SC-008 model portion).

---

## Phase 4: User Story 1 — Faithful KPI & Trend Analysis Across Two Dashboards (Priority: P1)

**Goal**: Build the two report pages at 1280×720 with all in-scope visuals in Tableau order/position — KPI legend strip, three KPI sparkline cards per page, Customer Distribution histogram, Top Customers Top-10 table, Subcategory Comparison diverging bar, Weekly Trends dual-line — plus static color legends.

**Independent Test**: Open the `.pbip` in Power BI Desktop; on each page confirm all visuals render with correct data bindings; switch Select Year 2020–2023 and confirm every KPI card, %Diff arrow, histogram, diverging bar, weekly line, and Top-10 table update consistently.

> Read `plugins/pbip/skills/pbir-format/SKILL.md` before authoring any visual.json. visual.json root must contain ONLY `$schema`, `name`, `position`, `visual` — never `filters`/`filterConfig`.

### Report scaffolding (US1)

- [ ] T027 [US1] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/report.json` (minimal: `$schema` + `themeCollection` + settings; no forbidden properties)
- [ ] T028 [US1] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/pages.json` (page order `[CustomerDashboard, SalesDashboard]`, active page CustomerDashboard)
- [ ] T029 [P] [US1] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/CustomerDashboard/page.json` (name `CustomerDashboard` matching `^[\w-]+$`, displayName "Customer Dashboard", 1280×720)
- [ ] T030 [P] [US1] Author `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/pages/SalesDashboard/page.json` (name `SalesDashboard`, displayName "Sales Dashboard", 1280×720)

### Customer Dashboard visuals (US1)

- [ ] T031 [P] [US1] KPI legend strip text/shape markers at px (0,53,1280,26) in `…/pages/CustomerDashboard/visuals/legendStrip/visual.json`
- [ ] T032 [P] [US1] KPI Customers sparkline card (Card CY Customers + line of CY Customers by DimDate[Month Name] sorted by Month Number + Customers Min/Max Marker highlight + % Diff Customers arrow) at px (0,79,427,256) in `…/pages/CustomerDashboard/visuals/kpiCustomers/visual.json`
- [ ] T033 [P] [US1] KPI Sales per Customer sparkline card (CY Sales per Customer + sparkline + Sales per Customer Min/Max Marker + % Diff Sales per Customer) at px (427,79,427,256) in `…/pages/CustomerDashboard/visuals/kpiSalesPerCustomer/visual.json`
- [ ] T034 [P] [US1] KPI Orders sparkline card (CY Orders + sparkline + Orders Min/Max Marker + % Diff Orders) at px (853,79,427,256) in `…/pages/CustomerDashboard/visuals/kpiOrders/visual.json`
- [ ] T035 [P] [US1] Customer Distribution column histogram — axis `Nr of Orders per Customer (Fixed)`, value `CY Customers` — at px (0,335,640,385) in `…/pages/CustomerDashboard/visuals/customerDistribution/visual.json`
- [ ] T036 [P] [US1] Top Customers table — columns Customer Rank, Customers[Customer Name], MAX(Orders[Order Date]) (Last Order), CY Profit, CY Sales, CY Orders; all projections `active: true`; visual-level filter `Top 10 Customer Filter = 1` (applied via filter pane in Desktop, not visual.json root) — at px (640,335,640,385) in `…/pages/CustomerDashboard/visuals/topCustomers/visual.json`

### Sales Dashboard visuals (US1)

- [ ] T037 [P] [US1] KPI legend strip at px (0,53,1280,26) in `…/pages/SalesDashboard/visuals/legendStrip/visual.json`
- [ ] T038 [P] [US1] KPI Sales sparkline card (CY Sales + sparkline by Month + Sales Min/Max Marker + % Diff Sales) at px (0,79,427,256) in `…/pages/SalesDashboard/visuals/kpiSales/visual.json`
- [ ] T039 [P] [US1] KPI Profit sparkline card (CY Profit + sparkline + Profit Min/Max Marker + % Diff Profit) at px (427,79,427,256) in `…/pages/SalesDashboard/visuals/kpiProfit/visual.json`
- [ ] T040 [P] [US1] KPI Quantity sparkline card (CY Quantity + sparkline + Quantity Min/Max Marker + % Diff Quantity) at px (853,79,427,256) in `…/pages/SalesDashboard/visuals/kpiQuantity/visual.json`
- [ ] T041 [P] [US1] Subcategory Comparison diverging/clustered bar — axis Products[Sub-Category], values PY Sales, CY Sales, CY Profit (profit/loss coloring) — at px (18,410,604,295) in `…/pages/SalesDashboard/visuals/subcategoryComparison/visual.json`
- [ ] T042 [P] [US1] Weekly Trends multi-line — axis DimDate[Week of Year], lines CY Sales & CY Profit (above/below coloring) — at px (658,403,604,302) in `…/pages/SalesDashboard/visuals/weeklyTrends/visual.json`

### Static legends (US1)

- [ ] T043 [P] [US1] Subcategory profit/loss static legend (text box / shape markers, source palette colors) in `…/pages/SalesDashboard/visuals/subcategoryLegend/visual.json`
- [ ] T044 [P] [US1] Weekly Trends Above/Below static legend in `…/pages/SalesDashboard/visuals/weeklyLegend/visual.json`

**Checkpoint**: Both pages render every in-scope visual in matching order/position; the three Test worksheets are excluded (FR-022); Select Year drives all CY/PY visuals (SC-003, SC-004, SC-005).

---

## Phase 5: User Story 3 — Interactive Filtering & Navigation Matching Tableau UX (Priority: P2)

**Goal**: Add page-navigation buttons (active page styled selected) and a bookmark-toggled collapsible filter panel (Select Year, Category, Sub-Category, Region, State, City slicers) to each page.

**Independent Test**: Click nav buttons to move between pages; toggle the filter panel open/closed; apply each of the six slicers and confirm all visuals on the active page respond.

### Filter-panel slicers (US3)

- [ ] T045 [P] [US3] Customer Dashboard filter-panel slicer group (Select Year[Year], Products[Category], Products[Sub-Category], Location[Region], Location[State], Location[City]), hidden by default, in `…/pages/CustomerDashboard/visuals/` (one visual.json per slicer)
- [ ] T046 [P] [US3] Sales Dashboard filter-panel slicer group (same six slicers), hidden by default, in `…/pages/SalesDashboard/visuals/` (one visual.json per slicer)

### Navigation buttons (US3)

- [ ] T047 [P] [US3] Customer Dashboard nav buttons (native Page Navigation action → Sales Dashboard; active page styled selected) + filter-toggle button at px (~1003–1197,5,97,63) in `…/pages/CustomerDashboard/visuals/navButtons/visual.json`
- [ ] T048 [P] [US3] Sales Dashboard nav buttons (native Page Navigation action → Customer Dashboard; active styled) + filter-toggle button in `…/pages/SalesDashboard/visuals/navButtons/visual.json`

### Bookmarks (US3)

- [ ] T049 [US3] Author the Open/Close bookmark pair toggling the slicer-group visibility in `Output/SalesCustomerDashboards/SalesCustomerDashboards.Report/definition/bookmarks/bookmarks.json` plus per-bookmark `{id}.bookmark.json` files; wire the filter-toggle buttons to them

**Checkpoint**: Navigation moves between both pages, the filter panel toggles, and all six slicers filter the active page (SC-006).

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Validate the report layer and run final end-to-end validation across the whole PBIP project.

- [ ] T050 Report JSON parse check: run the PowerShell `ConvertFrom-Json` loop over all `*.json`/`*.pbir` under `Output\SalesCustomerDashboards\SalesCustomerDashboards.Report`; fix any malformed file
- [ ] T051 PBIR validation: run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"`; confirm `definition.pbir` byPath target resolves, page names match `^[\w-]+$`, no orphan pages, theme resources resolve; fix any exit-code-2 errors
- [ ] T052 Final end-to-end validation: re-run `tmdl-validate` on the SemanticModel `definition` folder AND `validate_pbip.py` on the project root `Output\SalesCustomerDashboards`; confirm zero errors across model + report (SC-008)
- [ ] T053 Log all validation findings under `validation_results` in pipeline state and confirm SC-001 … SC-008 are satisfied before delivery

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational / Data Layer (Phase 2)**: Depends on Setup. **BLOCKS** all model and report work.
- **US2 Model (Phase 3)**: Depends on Phase 2 (tables/columns must exist before relationships and measures). This is the foundation the report binds to.
- **US1 Report Visuals (Phase 4)**: Depends on Phase 3 (visuals bind to measures and relationships).
- **US3 Navigation/Filtering (Phase 5)**: Depends on Phase 4 page scaffolding (pages.json + page.json must exist before adding slicers/buttons/bookmarks).
- **Polish (Phase 6)**: Depends on Phases 3–5 being complete.

### Story Dependency Note

Although US1 and US2 are both Priority P1, **US2 (model) must complete before US1 (visuals)** because every report visual binds to the measures and relationships defined in US2. US3 (P2) layers navigation/filtering onto the US1 pages.

### Within Each Phase

- Foundational: T007–T008 (model header) before T009–T014 (tables); the four CSV table files (T009–T012), DimDate (T013), and Select Year (T014) are independent `[P]`.
- US2: relationships (T015) and measures on different tables (T016, T017) are `[P]`; measures on Orders (T018–T023) are sequential (same file); validation (T024–T026) after all measures.
- US1: page scaffolding (T027–T030) before visuals; visuals on different files (T031–T044) are `[P]`.
- US3: slicers/buttons (T045–T048) `[P]`; bookmarks (T049) after slicers exist.

### Parallel Opportunities

- Phase 1: T003, T004, T005, T006 in parallel.
- Phase 2: T009, T010, T011, T012, T013, T014 in parallel (after T007–T008).
- Phase 3: T016 + T017 in parallel (different table files) alongside T015.
- Phase 4: all visual tasks T031–T044 in parallel (after T027–T030).
- Phase 5: T045–T048 in parallel (after Phase 4).

---

## Implementation Strategy

### MVP scope

The minimum deliverable that proves the migration is **Phase 1 → Phase 2 → Phase 3 (US2)**: a validated star-schema semantic model with all 45 measures. This alone satisfies SC-001, SC-002, and the model portion of SC-008, and is independently testable via DAX queries.

### Incremental delivery

1. **Increment 1 (MVP)**: Setup + Data Layer + Model (US2) → validated `.SemanticModel`.
2. **Increment 2**: Report visuals (US1) → both dashboards render with faithful KPIs/trends.
3. **Increment 3**: Navigation & filtering (US3) → full interactive UX.
4. **Increment 4**: Polish → end-to-end validation, zero-error delivery.

### Format validation

All 53 tasks follow the checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`. Setup/Foundational/Polish tasks carry no story label; Phase 3–5 tasks carry [US2]/[US1]/[US3].
