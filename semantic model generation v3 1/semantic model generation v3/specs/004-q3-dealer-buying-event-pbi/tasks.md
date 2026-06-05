# Tasks: (Active) 2021 Q3 Dealer Buying Event — Tableau → Power BI Migration

**Input**: Design documents from `specs/004-q3-dealer-buying-event-pbi/`
**Prerequisites**: plan.md ✅, spec.md ✅
**Design Artifacts**: `.specify/memory/Q3DealerBuyingEvent/star-schema-output.md` (4 tables, 1 active relationship, degenerate single-table star), `.specify/memory/Q3DealerBuyingEvent/dax-measures-output.md` (18 measures + 2 calculated columns + 2 disconnected DATATABLE parameter tables)
**Constitution**: `.specify/memory/constitution.md` (read-only rulebook — NEVER modify)
**Output Target**: `Output/Q3DealerBuyingEvent/`

**Tests**: Not requested for this migration — automated TMDL/PBIP validators replace unit tests. No test tasks generated.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[US1]**: Load and Model the Dealer Buying Event Data (P1)
- **[US2]**: Calculate Order, Margin, and Style Measures (P1)
- **[US3]**: Rank and Top-N Filtering Driven by Parameters (P2)
- **[US4]**: Reproduce Dashboards as Report Pages (P3)
- Setup / Foundational / Validation / Polish tasks carry **no** story label
- Every task lists an exact file path

**Model facts** (authoritative for all tasks):

- Tables are **unprefixed** and single-source: `Orders` (single wide flat fact + 18 measures host), `DimDate` (DAX `CALENDAR`, marked date table), `Rows Displayed` + `Rank Sort Measure` (disconnected DAX `DATATABLE` parameters).
- CSV binding: `Csv.Document(File.Contents(...))` over `Data/Q3 Buyer/Q3LaunchData 1.csv` — **never** the absent TWB Excel path; `Delimiter=","`, `Encoding=65001`, `QuoteStyle=QuoteStyle.Csv`, `[PromoteAllScalars = true]`, `"en-US"` typing.
- All **18 measures** and **2 calculated columns** (`Master Style`, `Region`) are authored on `Orders.tmdl` (single-table rule §0).
- `compatibilityLevel: 1567`; culture `en-US`; pages are **1280×720** (16:9).

## Constitution & Skill References

All TMDL/PBIR generation MUST comply with the migration constitution and plugin skills:
- §0 Single-Table Rule: single flat CSV → `Orders` kept intact (Product/Geography/Delivery = logical role dimensions via display folders); only `DimDate` + 2 disconnected parameter tables added
- §2 Naming: PascalCase unprefixed tables/columns, Title Case measures
- §3 DAX: VAR/RETURN, `DIVIDE()` (no fallback → BLANK), `SELECTEDVALUE` for parameters, `RANKX(…, DESC, Skip)` competition ties, `SWITCH(TRUE())`; no measure inside a `CALCULATE` boolean filter
- §4 Relationships: single active 1:many single-direction `Orders[Date] → DimDate[Date]`; both parameter tables disconnected
- §5 M Query: independent partition, `Csv.Document`, comma delimiter, `Encoding=65001`, `QuoteStyle.Csv`, types after header promotion
- §7 Parameter Migration: list parameters → disconnected `DATATABLE` consumed via `SELECTEDVALUE` (never filter the fact directly)
- §8 PBIP Structure: `.pbip` + `.SemanticModel/` (TMDL) + `.Report/` (PBIR)
- TMDL syntax rules: `plugins/pbip/skills/tmdl/SKILL.md`
- PBIR format rules: `plugins/pbip/skills/pbir-format/SKILL.md`

---

## Phase 1: Setup (Validation & Confirmation)

**Purpose**: Confirm inputs and format rules before generation

- [ ] T001 Read `.specify/memory/constitution.md` and confirm rules §0–§10 apply to this single-table migration
- [ ] T002 [P] Verify `.specify/memory/Q3DealerBuyingEvent/star-schema-output.md` exists with 4 tables (Orders, DimDate, Rows Displayed, Rank Sort Measure), 1 active relationship, and the M query / collapse-rules manifest
- [ ] T003 [P] Verify `.specify/memory/Q3DealerBuyingEvent/dax-measures-output.md` exists with 18 measures across 3 display folders (Order Metrics, Style Analysis, Ranking & Top-N) + 2 calculated columns (Master Style, Region) + 2 disconnected DATATABLE parameters
- [ ] T004 [P] Verify source CSV exists: `Data/Q3 Buyer/Q3LaunchData 1.csv` (52 source columns, 1000 data rows)
- [ ] T005 Read `plugins/pbip/skills/tmdl/SKILL.md` for TMDL syntax rules (tab indentation, `///` descriptions, selective quoting, property ordering, no measure inside CALCULATE boolean filter)
- [ ] T006 [P] Read `plugins/pbip/skills/pbir-format/SKILL.md` for PBIR JSON schema rules (visual.json root limited to `$schema`/`name`/`position`/`visual`; no root `filters`/`filterConfig`)
- [ ] T007 Create output directory tree: `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/` and `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/pages/`

**Checkpoint**: All inputs validated — generation can proceed

---

## Phase 2: Foundational PBIP Scaffolding (Blocking Prerequisites)

**Purpose**: Generate project scaffolding that ALL table/report files depend on

**⚠️ CRITICAL**: No table TMDL or report JSON can be written until these files exist

- [ ] T008 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.pbip` (root project file with `$schema` + `byPath` artifact reference to `Q3DealerBuyingEvent.Report`)
- [ ] T009 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/.platform` (`$schema`, `metadata` type `SemanticModel` displayName `Q3DealerBuyingEvent`, `config`)
- [ ] T010 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/.platform` (`$schema`, `metadata` type `Report` displayName `Q3DealerBuyingEvent`, `config`)
- [ ] T011 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition.pbism` (Import mode model `$schema` + version; empty `settings`)
- [ ] T012 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/diagramLayout.json` (node placeholders: Orders center; DimDate adjacent; Rows Displayed + Rank Sort Measure offset/disconnected)
- [ ] T013 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/database.tmdl` (`compatibilityLevel: 1567`, database name)
- [ ] T014 Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/model.tmdl` (culture `en-US`, `defaultPowerBIDataSourceVersion: powerBI_V3`, `ref table` for Orders / DimDate / `Rows Displayed` / `Rank Sort Measure`, model annotations)

**Checkpoint**: PBIP scaffolding complete — table and relationship files can be generated

---

## Phase 3: User Story 1 — Load and Model the Dealer Buying Event Data (Priority: P1) 🎯 MVP

**Goal**: The flat CSV loads into a single wide `Orders` table with correct `en-US` types (trailing-space aliases collapsed, pre-materialized columns dropped); `DimDate` is generated and marked as the date table; the active `Orders[Date] → DimDate[Date]` relationship resolves; both disconnected parameter tables exist

**Independent Test**: Open `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.pbip` in Power BI Desktop → `Orders` shows all 1000 CSV rows with correct types and no duplicate trailing-space columns → `DimDate` is populated and related to `Orders[Date]` → `Rows Displayed` and `Rank Sort Measure` appear with no relationships

### Source Table (M partition + columns) — structure only

- [ ] T015 [US1] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/Orders.tmdl` (structure only) — M partition: `Csv.Document(File.Contents("…/Data/Q3 Buyer/Q3LaunchData 1.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])` → `Table.PromoteHeaders([PromoteAllScalars = true])` → `Table.RemoveColumns` (the 6 trailing-space aliases `Delivery Month `/`Delivery Season `/`Region `/`Sales Area `/`Style Code `/`Style Description ` + pre-materialized `Measure for Rank` + `Style Count` + source `Region` + source `Master Style`) → `Table.TransformColumnTypes(…, "en-US")`. **Never** reference the absent TWB Excel path; keep the partition independent. Measures + calc columns added in Phase 4
- [ ] T016 [US1] Add the **11 order-measure columns** to `Orders.tmdl` with correct types and `summarizeBy: sum`: `Order $ (USD)`, `Order $ (U.S. Cost)`, `Order $ (U.S. Dealer Net)`, `Order $ (U.S. MSRP)`, `Cost`, `Dnet`, `MSRP`, `Margin $` (double); `Order Quantity`, `Sum of Quantity (Units)`, `Sum of Extra Quantity (Units)` (int64); quote names containing spaces/`$`/`(`/`)`; unique `lineageTag` GUID per column
- [ ] T017 [US1] Add the **Delivery Timing** columns to `Orders.tmdl` (display folder `Delivery Timing`, `summarizeBy: none`): `Date` (date, FK → `DimDate[Date]`), `Delivery Date` / `Delivery Month` / `Delivery Season` (string), `Year` / `Month` (int64); unique `lineageTag` per column
- [ ] T018 [US1] Add the **Product** columns to `Orders.tmdl` (display folder `Product`, `summarizeBy: none`): `Item Code`, `Base Part`, `Base Part Number`, `Base Style`, `Base Style Name`, `Style`, `Style Code`, `Style Description`, `Category`, `Product Category`, `Family`, `Product Family`, `Sub-Family`, `Product Sub-Family`, `Gender`, `Product Gender`, `Gender/Stature/Type`, `Garment Type`, `Color`, `Collection`, `Reorder Type` (string); `Global` (string, **isHidden**); quote `Sub-Family` / `Gender/Stature/Type`; unique `lineageTag` per column
- [ ] T019 [US1] Add the **Geography** columns to `Orders.tmdl` (display folder `Geography`, `summarizeBy: none`, **no** data category): `Macro Area`, `Micro Area`, `Sales Area` (string); unique `lineageTag` per column

### Generated Tables (DAX calculated)

- [ ] T020 [US1] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/DimDate.tmdl` — calculated-table partition `CALENDAR(DATE(YEAR(MIN(Orders[Date])),1,1), DATE(YEAR(MAX(Orders[Date])),12,31))` wrapped in `ADDCOLUMNS`; 6 columns: `Date` (date, key), `Year`, `Quarter`, `Month` (int64), `MonthName` (string, **Sort By = `Month`**), `Day` (int64); **mark as date table** on `Date` (set date-table annotation, `isKey` on Date); Calendar hierarchy Year > Quarter > MonthName > Day; unique `lineageTag` per column
- [ ] T021 [P] [US1] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/Rows Displayed.tmdl` — disconnected DAX `DATATABLE("Value", INTEGER, {{5},{10},{20},{50},{10000}})`; single int64 column `Value`; no relationships; unique `lineageTag`
- [ ] T022 [P] [US1] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/Rank Sort Measure.tmdl` — disconnected DAX `DATATABLE("Selection", STRING, {{"Order $ (Decending)"},{"Order Units (Decending)"},{"Order $ (Accending)"},{"Order Units (Accending)"}})`; single string column `Selection` (source spellings preserved verbatim); no relationships; unique `lineageTag`

### Relationship

- [ ] T023 [US1] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/relationships.tmdl` — single **active** many-to-one single-direction relationship `Orders[Date]` → `DimDate[Date]`; unique `lineageTag` GUID; confirm `Rows Displayed` and `Rank Sort Measure` have **no** relationships

**Checkpoint**: All tables + the single relationship defined — model loads in Desktop with correct schema, no duplicate columns, populated DimDate, disconnected parameters (US1 independently testable)

---

## Phase 4: User Story 2 — Order, Margin, and Style Measures (Priority: P1)

**Goal**: The 2 calculated columns and the 13 order/margin/style measures calculate correctly and reconcile to source totals; Region rollup and Master Style grain behave like the Tableau source

**Independent Test**: Card bound to `[Total Order $]` broken down by Category aggregates per category; `[Style Count]` returns the distinct master-style count; `[Margin %]` returns Margin $ ÷ Order $; a Region breakdown shows Canada / USA / Macro-Area rollups

> All measures + calc columns are authored on `Orders.tmdl` (created in Phase 3). Add measures in display-folder groups. Preserve format strings (`\$#,##0`, `#,##0`, `0.00%`, `0`) and `///` descriptions verbatim from `dax-measures-output.md`. Generate a unique `lineageTag` per measure/column.

**Depends on**: US1 (Orders columns + the `Style Code` / `Sales Area` / `Macro Area` source columns the calc columns reference)

### Calculated Columns (host: Orders)

- [ ] T024 [US2] Add the `Master Style` calculated column to `Orders.tmdl` — `LEFT(Orders[Style Code], 8)` (string, `summarizeBy: none`); row-level grouping grain required by `Style Count`
- [ ] T025 [US2] Add the `Region` calculated column to `Orders.tmdl` — `IF(Orders[Sales Area]="Canada","Canada", IF(Orders[Sales Area]="United States of America","USA", Orders[Macro Area]))` (string, `summarizeBy: none`, display folder `Geography`, **no** data category); preserves the Tableau IF/ELSEIF rule

### Order Metrics Measures (display folder `Order Metrics`)

- [ ] T026 [US2] Add the 11 additive **Order Metrics** SUM measures to `Orders.tmdl` — Total Order $ (`SUM(Orders[Order $ (USD)])`, `\$#,##0`), Total Order Quantity (`#,##0`), Total Cost (`\$#,##0`), Total Dnet (`\$#,##0`), Total MSRP (`\$#,##0`), Total Margin $ (`\$#,##0`), Total Extra Quantity (`SUM(Orders[Sum of Extra Quantity (Units)])`, `#,##0`), Total Quantity Units (`SUM(Orders[Sum of Quantity (Units)])`, `#,##0`), Total Order $ (U.S. Cost) (`\$#,##0`), Total Order $ (U.S. Dealer Net) (`\$#,##0`), Total Order $ (U.S. MSRP) (`\$#,##0`)
- [ ] T027 [US2] Add the `Margin %` measure to `Orders.tmdl` — `DIVIDE([Total Margin $], [Total Order $])`, format `0.00%`, display folder `Order Metrics` (DIVIDE → BLANK on zero/blank denominator)

### Style Analysis Measure (display folder `Style Analysis`)

- [ ] T028 [US2] Add the `Style Count` measure to `Orders.tmdl` — `DISTINCTCOUNT(Orders[Master Style])`, format `#,##0`, display folder `Style Analysis` (depends on the `Master Style` calc column from T024)

**Checkpoint**: 2 calc columns + 13 measures evaluate without error and reconcile to source; Region/Master Style behave per Tableau (US2 independently testable)

---

## Phase 5: User Story 3 — Rank and Top-N Filtering Driven by Parameters (Priority: P2)

**Goal**: The 5 ranking/Top-N measures drive parameter-controlled ordering and Top-N row limiting via `SELECTEDVALUE` over the two disconnected tables; percent-of-total returns BLANK() on a zero denominator

**Independent Test**: Set `Rank Sort Measure` = "Order $ (Decending)" → `[Rank]` orders Base Parts high→low Order $; set `Rows Displayed` = 10 → `[Rank Filter Flag]` = 1 only for rank ≤ 10; `[Order $ (Percent of Total)]` returns each item's share of the ALLSELECTED total

**Depends on**: US1 (parameter tables) and US2 (`[Total Order $]` / `[Total Order Quantity]` base measures)

### Ranking & Top-N Measures (display folder `Ranking & Top-N`)

- [ ] T029 [US3] Add the `Measure for Rank` measure to `Orders.tmdl` — VAR `SortBy = SELECTEDVALUE('Rank Sort Measure'[Selection], "Order $ (Decending)")` + `SWITCH(TRUE(), …)` negating for the two "Accending" cases over `[Total Order $]` / `[Total Order Quantity]`; format `#,##0`; **isHidden** (internal sort helper); no measure inside a CALCULATE boolean filter
- [ ] T030 [US3] Add the `Rank` measure to `Orders.tmdl` — `RANKX(ALLSELECTED(Orders[Base Part]), [Measure for Rank], , DESC, Skip)` (competition ties — Skip, NOT dense), format `#,##0`
- [ ] T031 [US3] Add the `Rank (Order $)` measure to `Orders.tmdl` — `RANKX(ALLSELECTED(Orders[Base Part]), [Total Order $], , DESC, Skip)` (fixed Order $ rank, ignores the parameter), format `#,##0`
- [ ] T032 [US3] Add the `Order $ (Percent of Total)` measure to `Orders.tmdl` — `DIVIDE([Total Order $], CALCULATE([Total Order $], ALLSELECTED()))`, format `0.00%` (BLANK on zero/blank denominator — FR-011/SC-007)
- [ ] T033 [US3] Add the `Rank Filter Flag` measure to `Orders.tmdl` — `IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value], 10), 1, 0)`, format `0` (applied as a visual-level filter `= 1` in Desktop for Top-N row limiting; 10000 = "All")

**Checkpoint**: All 18 measures present with correct display folders + format strings; parameter-driven rank/Top-N and percent-of-total behave per spec — semantic model is content-complete

---

## Phase 6: Semantic Model Validation (Gate)

**Purpose**: Validate the semantic model before proceeding to the report layer (plan Stage B)

**⚠️ CRITICAL**: Report generation CANNOT begin until this phase passes (no exit-code-2 errors)

- [ ] T034 Run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.SemanticModel\definition"` — fix any indentation, property-order, or quoting errors until it exits 0 (SC-009)
- [ ] T035 Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"` — fix any exit-code-2 structural/schema errors (SC-009)
- [ ] T036 [P] Verify `.pbip`, `definition.pbism`, `diagramLayout.json` parse as valid JSON
- [ ] T037 [P] Verify M-query safety in `Orders.tmdl`: `Csv.Document` over the local CSV (not the Excel path), `QuoteStyle.Csv`, `Encoding=65001`, comma delimiter, `[PromoteAllScalars = true]`, `"en-US"` typing; 6 trailing-space aliases + `Measure for Rank` + `Style Count` + source `Region`/`Master Style` removed; independent partition (no cross-query references)
- [ ] T038 [P] Confirm no measure is referenced inside a `CALCULATE` boolean filter; `Measure for Rank` uses `SWITCH(TRUE())` over `SELECTEDVALUE`; both parameter tables remain disconnected
- [ ] T039 [P] Cross-check all 18 measures + 2 calc columns from `dax-measures-output.md` are present in `Orders.tmdl` with correct display folders + format strings; `Measure for Rank` is hidden

**Checkpoint**: Semantic model validated — report layer generation can begin

---

## Phase 7: User Story 4 — Report Layer (3 Pages — Priority: P3)

**Goal**: Three 1280×720 PBIR pages (Launch Report Dashboard, Delivery Season Summary, Data Detail) consolidating the 49 worksheets / 5 dashboards, with the two parameter slicers, a rank/Top-N table, and category/region/season breakdowns; 25px edge padding, 20px gaps, titles shown, 1px `#E0E0E0` borders, alt text, `active: true` projections

**Independent Test**: Open the report → all three pages render their visuals + the `Rows Displayed` / `Rank Sort Measure` slicers → the top-parts rank table responds to both parameters → the Delivery Season page breaks order measures by season/month

**Depends on**: Phase 6 (validated semantic model providing fields/measures)

### Report Scaffolding

- [ ] T040 [US4] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition.pbir` — `$schema`, `version`, `datasetReference.byPath` → `../Q3DealerBuyingEvent.SemanticModel`
- [ ] T041 [P] [US4] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/version.json` (PBIR format version)
- [ ] T042 [US4] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/report.json` — minimal enhanced template (`$schema`, `themeCollection`, `settings`); no root `filters`/`filterConfig`

### Launch Report Dashboard Page (1280×720)

- [ ] T043 [US4] Create `pages/LaunchReportDashboard/page.json` — `$schema`, `name` matching `^[\w-]+$`, displayName "Launch Report Dashboard", 1280×720 canvas, `displayOption`
- [ ] T044 [P] [US4] Create `pages/LaunchReportDashboard/visuals/kpiCards/visual.json` — multi-row card / KPI cards: `Total Order $`, `Total Order Quantity`, `Style Count`, `Margin %`
- [ ] T045 [P] [US4] Create `pages/LaunchReportDashboard/visuals/topPartsRankTable/visual.json` — table: `Base Part` × (`Total Order $`, `Rank`, `Order $ (Percent of Total)`); `Rank Filter Flag = 1` visual-level filter applied in Desktop (no root `filters` in JSON)
- [ ] T046 [P] [US4] Create `pages/LaunchReportDashboard/visuals/orderByCategory/visual.json` — bar chart `Total Order $` by `Category`
- [ ] T047 [P] [US4] Create `pages/LaunchReportDashboard/visuals/orderByFamily/visual.json` — bar chart `Total Order $` by `Family`
- [ ] T048 [P] [US4] Create `pages/LaunchReportDashboard/visuals/orderByGender/visual.json` — bar/donut `Total Order $` by `Gender`
- [ ] T049 [P] [US4] Create `pages/LaunchReportDashboard/visuals/orderByRegion/visual.json` — bar chart `Total Order $` by `Region` (Macro Area rollup)
- [ ] T050 [P] [US4] Create `pages/LaunchReportDashboard/visuals/orderByColor/visual.json` — bar chart `Total Order $` by `Color`
- [ ] T051 [P] [US4] Create `pages/LaunchReportDashboard/visuals/rowsDisplayedSlicer/visual.json` — single-select slicer bound to `'Rows Displayed'[Value]`, default 10
- [ ] T052 [P] [US4] Create `pages/LaunchReportDashboard/visuals/rankSortMeasureSlicer/visual.json` — single-select slicer bound to `'Rank Sort Measure'[Selection]`, default "Order $ (Decending)"
- [ ] T053 [P] [US4] Create `pages/LaunchReportDashboard/visuals/categoryFilter/visual.json` — Category slicer (`Orders[Category]`)
- [ ] T054 [P] [US4] Create `pages/LaunchReportDashboard/visuals/familyGenderFilter/visual.json` — Family + Gender slicers (`Orders[Family]`, `Orders[Gender]`)

### Delivery Season Summary Page (1280×720)

- [ ] T055 [US4] Create `pages/DeliverySeasonSummary/page.json` — displayName "Delivery Season Summary", 1280×720 canvas
- [ ] T056 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/orderBySeason/visual.json` — bar/column `Total Order $` (+ `Total Order Quantity`) by `Delivery Season`
- [ ] T057 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/orderByMonth/visual.json` — column chart `Total Order $` by `Delivery Month`
- [ ] T058 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/orderTrend/visual.json` — line chart `Total Order $` over `DimDate[Date]` (date axis), legend `Delivery Season`
- [ ] T059 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/seasonMeasuresTable/visual.json` — matrix: `Delivery Season` × (`Total Order $`, `Total Margin $`, `Margin %`, `Total Order Quantity`)
- [ ] T060 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/rowsDisplayedSlicer/visual.json` — single-select slicer bound to `'Rows Displayed'[Value]`, default 10
- [ ] T061 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/rankSortMeasureSlicer/visual.json` — single-select slicer bound to `'Rank Sort Measure'[Selection]`, default "Order $ (Decending)"
- [ ] T062 [P] [US4] Create `pages/DeliverySeasonSummary/visuals/regionColorFilter/visual.json` — Region + Color slicers (`Orders[Region]`, `Orders[Color]`)

### Data Detail Page (1280×720)

- [ ] T063 [US4] Create `pages/DataDetail/page.json` — displayName "Data Detail", 1280×720 canvas
- [ ] T064 [P] [US4] Create `pages/DataDetail/visuals/itemDetailTable/visual.json` — full item-level table: `Item Code`, `Style`, `Category`, `Region`, `Delivery Season` + (`Total Order $`, `Total Margin $`, `Margin %`, `Total Order Quantity`)
- [ ] T065 [P] [US4] Create `pages/DataDetail/visuals/categoryFilter/visual.json` — Category slicer (`Orders[Category]`)
- [ ] T066 [P] [US4] Create `pages/DataDetail/visuals/regionFilter/visual.json` — Region slicer (`Orders[Region]`)
- [ ] T067 [P] [US4] Create `pages/DataDetail/visuals/seasonFilter/visual.json` — Delivery Season slicer (`Orders[Delivery Season]`)
- [ ] T068 [P] [US4] Create `pages/DataDetail/visuals/rowsDisplayedSlicer/visual.json` — single-select slicer bound to `'Rows Displayed'[Value]`, default 10
- [ ] T069 [P] [US4] Create `pages/DataDetail/visuals/rankSortMeasureSlicer/visual.json` — single-select slicer bound to `'Rank Sort Measure'[Selection]`, default "Order $ (Decending)"

### Page Registry

- [ ] T070 [US4] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/pages/pages.json` — ordered list (LaunchReportDashboard, DeliverySeasonSummary, DataDetail) with the active page set to LaunchReportDashboard
- [ ] T071 [US4] Verify every `visual.json` root has only `$schema`, `name`, `position` + `visual`; title shown, 1px `#E0E0E0` border, alt text, `active: true` projections; honor 25px edge padding / 20px inter-visual gaps

**Checkpoint**: Report layer complete — all three pages, visuals, both parameter slicers, the rank/Top-N table, and breakdown filters generated

---

## Phase 8: Final End-to-End Validation & Polish

**Purpose**: End-to-end validation of the complete PBIP project (semantic model + report) (plan Stage D)

- [ ] T072 Run report JSON validity check: `Get-ChildItem "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.Report" -Recurse -Include "*.json","*.pbir" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }` and fix any malformed JSON
- [ ] T073 Re-run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.SemanticModel\definition"` — confirm exit code 0
- [ ] T074 Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"` — confirm no exit-code-2 errors for the full project (model + report)
- [ ] T075 [P] Verify `definition.pbir` `byPath` target resolves to the existing `.SemanticModel` folder
- [ ] T076 [P] Verify page folder names match `^[\w-]+$` (LaunchReportDashboard, DeliverySeasonSummary, DataDetail — no spaces/dots)
- [ ] T077 [P] Verify the active relationship `Orders[Date] → DimDate[Date]` is present in `relationships.tmdl` and both parameter tables are disconnected
- [ ] T078 Confirm Success Gate: `.pbip` opens cleanly (SC-001), `Orders` row count matches the source CSV (SC-002), all attributes/measures typed with no trailing-space duplicates (SC-003), DimDate relationship filters (SC-004), 18 measures + 2 calc columns reconcile (SC-005), parameters drive rank ordering + Top-N (SC-006), percent-of-total BLANK on zero denominator (SC-007), currency/whole-number/percentage formats applied (SC-008)

**Checkpoint**: Full PBIP project passes all validators and meets every success criterion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all table/relationship work
- **US1 (Phase 3)**: Depends on Foundational — the MVP (data loads, DimDate, parameters, relationship)
- **US2 (Phase 4)**: Depends on US1 (Orders columns hosting the calc columns + measures)
- **US3 (Phase 5)**: Depends on US1 (parameter tables) + US2 (base measures)
- **Model Validation (Phase 6)**: Depends on US1–US3
- **US4 / Report (Phase 7)**: Depends on Phase 6 (validated model)
- **Final Validation (Phase 8)**: Depends on Phase 7

### User Story Dependencies

- **US1 (P1)**: Foundational single-table model — no story dependencies
- **US2 (P1)**: Builds on US1 (calc columns + order/margin/style measures)
- **US3 (P2)**: Builds on US1 (disconnected parameters) + US2 (base measures)
- **US4 (P3)**: Builds on US1–US3 (model + measures + parameters)

### Parallel Opportunities

- Setup container files T008–T013 run in parallel (different files)
- US1 generated tables T021–T022 run in parallel (separate table files); Orders column tasks T016–T019 edit the same `Orders.tmdl` — keep sequential after T015
- US2/US3 measures edit the same `Orders.tmdl` — keep sequential within each phase
- Report visuals within each page run in parallel (separate visual.json files) once that page's `page.json` exists

---

## Implementation Strategy

- **MVP scope**: Phases 1–3 (US1) deliver a loadable single-table model with DimDate + disconnected parameters — the minimum viable migration.
- **Incremental delivery**: Add US2 (order/margin/style measures) → US3 (rank/Top-N parameters) → validate → author the 3 report pages → final validation.
- **Validate early**: Run Phase 6 before report authoring so TMDL/structure errors surface before visuals are built on top.

---

## Task Summary

- **Total tasks**: 78 (T001–T078)
- **Setup (Phase 1)**: 7 — confirm inputs, read TMDL/PBIR skills, create output tree
- **Foundational (Phase 2)**: 7 — scaffold .pbip / .platform / .pbism / diagramLayout / database.tmdl / model.tmdl
- **US1 (Phase 3)**: 9 — Orders M partition + columns, DimDate, 2 disconnected parameter tables, relationship
- **US2 (Phase 4)**: 5 — 2 calc columns + 13 order/margin/style measures
- **US3 (Phase 5)**: 5 — 5 ranking/Top-N measures
- **Model Validation (Phase 6)**: 6 — tmdl-validate + validate_pbip.py + safety cross-checks
- **US4 / Report (Phase 7)**: 32 — scaffolding + 3 pages (29 visuals/slicers) + page registry
- **Final Validation (Phase 8)**: 7 — JSON/TMDL/PBIP gates + success-criteria confirmation
- **Parallelizable tasks [P]**: 45
