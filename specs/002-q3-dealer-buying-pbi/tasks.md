---
description: "Dependency-ordered task list for the (Active) 2021 Q3 Dealer Buying Event Tableau → Power BI migration"
---

# Tasks: (Active) 2021 Q3 Dealer Buying Event — Tableau → Power BI Migration

**Input**: Design documents from `specs/002-q3-dealer-buying-pbi/`
**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required), `.specify/memory/Q3DealerBuyingEvent/star-schema-output.md`, `.specify/memory/Q3DealerBuyingEvent/dax-measures-output.md`, `.specify/memory/Q3DealerBuyingEvent/tableau-analysis-output.md`

**Tests**: No automated unit/integration test suite is requested. Validation is performed by the structural validators (`tmdl-validate`, `validate_pbip.py`) plus PBIR JSON parse checks and functional DAX spot-checks — these appear as explicit validation tasks, not test-code tasks.

**Build target**: `Output/Q3DealerBuyingEvent/`
**Model shape**: Single flat Import table `LaunchData` (53 source cols + 2 derived) + generated `DimDate` + 2 disconnected parameter tables (`Rows Displayed`, `Rank Sort Measure`) — per constitution §0 Single-Table Rule (FR-002).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story the task serves — [US1] five-dashboard report, [US2] model/measures/parameters, [US3] slicing & Top-N control
- Setup, Foundational, and Polish tasks carry no story label
- Every task lists an exact file path

## Path Conventions

All paths are relative to the workspace root. Generated artifacts live under:
- Model: `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/`
- Report: `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/`

---

## Phase 1: Setup (Project Scaffolding)

**Purpose**: Create the PBIP folder tree and project-entry/manifest files so the model and report skeletons resolve.

- [ ] T001 Create the output folder tree `Output/Q3DealerBuyingEvent/` with `Q3DealerBuyingEvent.SemanticModel/definition/tables/` and `Q3DealerBuyingEvent.Report/definition/pages/` subfolders
- [ ] T002 Create the project entry file `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.pbip` (artifact reference to the `.Report` definition)
- [ ] T003 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/.platform` and `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition.pbism`
- [ ] T004 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/diagramLayout.json` (default layout)
- [ ] T005 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/.platform` and `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition.pbir` with `datasetReference` byPath → `../Q3DealerBuyingEvent.SemanticModel`
- [ ] T006 [P] Create `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/version.json` (report schema 3.0.0)

**Checkpoint**: PBIP skeleton exists and `definition.pbir` points at the semantic model folder.

---

## Phase 2: Foundational — Data Layer (Blocking Prerequisites)

**Purpose**: Author the model header plus every table's Power Query M partition (CSV load, key trimming, generated calendar, parameter DATATABLEs). The model, all measures, and every report visual depend on these tables existing with correct columns, types, and keys.

**⚠️ CRITICAL**: No measure, relationship, derived column, or report-visual task may begin until this phase is complete. Read `plugins/pbip/skills/tmdl/SKILL.md` for TMDL syntax rules before authoring any `.tmdl` file.

- [ ] T007 Author `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/database.tmdl` (compatibilityLevel 1567+, model id)
- [ ] T008 Author `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/model.tmdl` (culture `en-US`, `ref table` entries for all 4 tables — LaunchData, DimDate, 'Rows Displayed', 'Rank Sort Measure' — default annotations)
- [ ] T009 [P] Author the `LaunchData` M partition in `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/LaunchData.tmdl` — `Csv.Document(File.Contents("…\\Data\\Q3 Buyer\\Q3LaunchData 1.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])`; `Table.PromoteHeaders([PromoteAllScalars=true])`; cast types immediately (`Date`→date; `Month`, `Year`, `Order Quantity`, `Sum of Extra Quantity (Units)`, `Sum of Quantity (Units)`→Int64; `Cost`, `Dnet`, `Margin $`, `Measure for Rank`, `MSRP`, `Order $ (U.S. Cost)`, `Order $ (U.S. Dealer Net)`, `Order $ (U.S. MSRP)`, `Order $ (USD)`→number; all remaining→text); apply `Text.Trim` to canonical `Style Code` and `Sales Area`; preserve ALL 53 source columns including the 6 "(trailing space)" duplicate variants (FR-001, FR-003)
- [ ] T010 [P] Author the `DimDate` table in `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/DimDate.tmdl` — M-generated contiguous daily calendar over `LaunchData[Date]` range (`Date.StartOfYear(List.Min(...))` … `Date.EndOfYear(List.Max(...))`); columns Date, Year, Quarter, Quarter Name ("Q3"), Month, Month Name; set Month Name `sortByColumn` = Month and Quarter Name `sortByColumn` = Quarter; Calendar hierarchy Year > Quarter Name > Month Name; mark as date table on `Date` (FR-004, FR-026)
- [ ] T011 [P] Author the `Rows Displayed` parameter table in `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/Rows Displayed.tmdl` — `DATATABLE("Label",STRING,"Value",INTEGER,{{"5",5},{"10",10},{"20",20},{"50",50},{"All",10000}})`; `Value` column hidden; sort `Label` by `Value`; disconnected (no relationship); default selection 10 (FR-006)
- [ ] T012 [P] Author the `Rank Sort Measure` parameter table in `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/Rank Sort Measure.tmdl` — `DATATABLE("Label",STRING,"SortOrder",INTEGER,{{"Order $ (Decending)",1},{"Order Units (Decending)",2},{"Order $ (Accending)",3},{"Order Units (Accending)",4}})`; `SortOrder` hidden; sort `Label` by `SortOrder`; disconnected; default "Order $ (Decending)" — spellings preserved verbatim so SWITCH matches (FR-007)

**Checkpoint**: All 4 tables load with trimmed keys; the calendar is marked as a date table; both parameter DATATABLEs exist with exact domains/defaults. Model layer can begin.

---

## Phase 3: User Story 2 — Single-Table Model with Complete Measure & Parameter Coverage (Priority: P1) 🎯 MVP foundation

**Goal**: Add the 2 derived calculated columns, all 7 explicit DAX measures (grouped into display folders with format strings), and the single DimDate relationship — so every in-scope Tableau calculated field is covered and the model is independently auditable.

**Independent Test**: Inspect the model (one flat `LaunchData`, generated `DimDate`, two disconnected parameter tables, one relationship); enumerate measures/columns against the dax-measures index (expect 7 measures + 2 columns, zero "(copy)" duplicates); evaluate sample measures via DAX query for a sample part/parameter selection and confirm rank/percent results are sensible and divide-by-zero safe.

> Calculated columns and measures are added into the existing `LaunchData.tmdl` from Phase 2 (sequential — same file). DAX is copied verbatim from `dax-measures-output.md`. `Measure for Rank` and `Rank Filter` reference the disconnected parameter tables via `SELECTEDVALUE`.

- [ ] T013 [US2] Add the 2 derived calculated columns to `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/LaunchData.tmdl` — `Master Style = LEFT(LaunchData[Style Code],8)` and `Region = SWITCH(TRUE(), LaunchData[Sales Area]="Canada","Canada", LaunchData[Sales Area]="United States of America","USA", LaunchData[Macro Area])` (FR-014, FR-015)
- [ ] T014 [US2] Add the 4 **Core Metrics** measures to `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/LaunchData.tmdl` — `Order $` (`SUM(LaunchData[Order $ (USD)])`, format `\$#,##0`), `Order Quantity` (`SUM(LaunchData[Order Quantity])`, format `#,##0`), `Style Count` (`DISTINCTCOUNT(LaunchData[Master Style])`, format `#,##0`), `Order $ (Percent of Total)` (`DIVIDE([Order $], CALCULATE([Order $], ALLSELECTED(LaunchData)))`, format `0.00%`); display folder "Core Metrics" (FR-008, FR-012, FR-013, FR-016)
- [ ] T015 [US2] Add the 3 **Ranking** measures to `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/tables/LaunchData.tmdl` — `Measure for Rank` (VAR/RETURN SWITCH over `SELECTEDVALUE('Rank Sort Measure'[Label],"Order $ (Decending)")` returning ±[Order $]/±[Order Quantity], format `#,##0`), `Rank` (`RANKX(ALLSELECTED(LaunchData[Base Part Number]),[Measure for Rank],,DESC,DENSE)`, format `#,##0`), `Rank Filter` (`IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value],10),1,0)`, format `0`); display folder "Ranking" (FR-009, FR-010, FR-011)
- [ ] T016 [US2] Author `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.SemanticModel/definition/relationships.tmdl` — one active many-to-one single-direction relationship `DimDate[Date]` 1—* `LaunchData[Date]`; confirm neither parameter table participates in any relationship (FR-004)

### TMDL Validation (User Story 2)

- [ ] T017 [US2] Run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.SemanticModel\definition"`; fix any indentation, property-order, quoting, or referential-integrity errors before proceeding
- [ ] T018 [US2] Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"` and confirm the semantic model section reports zero errors (exit code 0/1); fix any exit-code-2 errors
- [ ] T019 [US2] Functional spot-check: run DAX queries for `Rank`, `Measure for Rank`, `Rank Filter`, and `Order $ (Percent of Total)` across a sample of `Base Part Number` values with each `Rank Sort Measure` option and `Rows Displayed` = 5/10/All — confirm re-rank/re-trim, dense-rank ties retained, and percent-of-total returns BLANK (not error) on zero context total (SC-005, SC-006)

**Checkpoint**: Model is complete — one flat table, generated date table, two disconnected parameters, one relationship, 7 measures + 2 derived columns, TMDL validation passes. The semantic model is independently usable (SC-001, SC-002).

---

## Phase 4: User Story 1 — Faithful Five-Dashboard Launch Report (Priority: P1)

**Goal**: Build the five report pages reproducing each Tableau dashboard's visual composition — Data Detail (large table + ~13 slicers), Delivery Season Summary (small-multiple bar grid + Top Parts tables), Launch Report Dashboard (bar charts + Top Parts table + KPI cards + Sales-by-Date), Slide View 1, and Slide View 2 — each visual replicating the source mark type with descriptive title, 1px `#E0E0E0` border, alt text, and all table/matrix projections `active: true`.

**Independent Test**: Open the generated `.pbip` in Power BI Desktop, navigate all five pages, and confirm each visual renders the correct mark type (table→table/matrix, bar→bar, line→line, KPI→card) with the same fields and numbers as the Tableau source.

> Read `plugins/pbip/skills/pbir-format/SKILL.md` before authoring any visual.json. visual.json root must contain ONLY `$schema`, `name`, `position`, `visual` — never `filters`/`filterConfig`. `report.json` uses the minimal template (no forbidden properties).

### Report scaffolding (US1)

- [ ] T020 [US1] Author `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/report.json` (minimal: `$schema` + `themeCollection` + settings; no forbidden properties) (FR-030)
- [ ] T021 [US1] Author `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.Report/definition/pages/pages.json` (page order `[DataDetail, DeliverySeasonSummary, LaunchReportDashboard, SlideView1, SlideView2]`, active page `LaunchReportDashboard`) (FR-019)
- [ ] T022 [P] [US1] Author `…/pages/DataDetail/page.json` (name `DataDetail` matching `^[\w-]+$`, displayName "Data Detail")
- [ ] T023 [P] [US1] Author `…/pages/DeliverySeasonSummary/page.json` (name `DeliverySeasonSummary`, displayName "Delivery Season Summary")
- [ ] T024 [P] [US1] Author `…/pages/LaunchReportDashboard/page.json` (name `LaunchReportDashboard`, displayName "Launch Report Dashboard")
- [ ] T025 [P] [US1] Author `…/pages/SlideView1/page.json` (name `SlideView1`, displayName "Slide View 1")
- [ ] T026 [P] [US1] Author `…/pages/SlideView2/page.json` (name `SlideView2`, displayName "Slide View 2")

### Data Detail page visuals (US1)

- [ ] T027 [P] [US1] Detail Table/Matrix of launch records (the `Data` worksheet) — all projections `active: true` — in `…/pages/DataDetail/visuals/detailTable/visual.json` (FR-020, FR-029)
- [ ] T028 [P] [US1] The ~13 dimension slicers (Region, Sales Area, Delivery Season, Delivery Month, Garment Type, Product Gender, Product Category, Product Family, Product Sub-Family, Base Style Name, Style Code, Base Part Number, Style Description) in `…/pages/DataDetail/visuals/{slicer}/visual.json` (one visual.json per slicer) (FR-020)

### Delivery Season Summary page visuals (US1)

- [ ] T029 [P] [US1] The 4-column small-multiple bar grid — MacroArea (1–4), Garment Type (1–4), Gender (1–4), Category (1–4) — as bar charts in `…/pages/DeliverySeasonSummary/visuals/{barChart}/visual.json` (FR-021, FR-027)
- [ ] T030 [P] [US1] The Top Parts US / Int / All summaries as Table/Matrix visuals (ranked, columns Base Part Number, Order $, Order $ (Percent of Total); projections `active: true`) in `…/pages/DeliverySeasonSummary/visuals/{topPartsTable}/visual.json` (FR-021)

### Launch Report Dashboard page visuals (US1)

- [ ] T031 [P] [US1] The 6 category bar charts (MacroArea, Gender, Category, Family, Delivery Season, Garment Type) in `…/pages/LaunchReportDashboard/visuals/{barChart}/visual.json` (FR-022, FR-027)
- [ ] T032 [P] [US1] The Top Parts Table/Matrix (ranked, columns Base Part Number, Order $, Order $ (Percent of Total); projections `active: true`) in `…/pages/LaunchReportDashboard/visuals/topParts/visual.json` (FR-022)
- [ ] T033 [P] [US1] The Launch Summary KPI cards in `…/pages/LaunchReportDashboard/visuals/{kpiCard}/visual.json` (FR-022, FR-027)
- [ ] T034 [P] [US1] The Sales-by-Date line/column chart over `DimDate[Date]` colored by `Reorder Type` (New vs Reorder) with legend in `…/pages/LaunchReportDashboard/visuals/salesByDate/visual.json` (FR-022, FR-026)

### Slide View 1 page visuals (US1)

- [ ] T035 [P] [US1] Slide layout visuals — Sales by Date (chart over DimDate colored by Reorder Type), MacroArea (bar), Category (bar), Delivery Season (bar), Launch Summary (Card), Style Count (Card) — in `…/pages/SlideView1/visuals/{visual}/visual.json` (FR-023, FR-027)

### Slide View 2 page visuals (US1)

- [ ] T036 [P] [US1] Slide layout visuals — Sales by Date (chart), MacroArea (bar), Delivery Season (bar), Family (bar), Launch Summary (Card), Style Count (Card), and a Reorder Type color legend — in `…/pages/SlideView2/visuals/{visual}/visual.json` (FR-024, FR-026)

### PBIR Validation (User Story 1)

- [ ] T037 [US1] Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"` and confirm the report section reports zero errors (page-name regex, definition.pbir binding, orphan pages, theme resolution); fix any exit-code-2 errors
- [ ] T038 [US1] Parse-check every `*.json`/`*.pbir` in `Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.Report` (each must `ConvertFrom-Json` without error); confirm no visual.json carries `filters`/`filterConfig` at root and `visualContainerObjects.title` only uses `show`/`text` (FR-030)

**Checkpoint**: All five pages render with faithful mark types and correct data bindings; report-side validation passes (SC-004).

---

## Phase 5: User Story 3 — Interactive Slicing & Top-N Control Matching Tableau UX (Priority: P2)

**Goal**: Place the two parameter slicers on the pages hosting Top Parts visuals, wire each Top Parts visual to the `Rank Filter = 1` visual-level filter, and confirm the dimension slicers drive every dependent visual — reproducing the Tableau parameter-driven Top-N experience in a single interaction.

**Independent Test**: Apply each dimension slicer on the relevant pages and toggle the two parameter slicers; confirm visuals respond and every Top Parts visual re-trims (Rows Displayed) and re-ranks (Rank Sort Measure) consistently, including the "All" (10000) and tie cases.

- [ ] T039 [US3] Add the `Rows Displayed` single-select slicer (`'Rows Displayed'[Label]`, sorted by Value, default "10") to `…/pages/DeliverySeasonSummary/visuals/rowsDisplayedSlicer/visual.json`, `…/pages/LaunchReportDashboard/visuals/rowsDisplayedSlicer/visual.json`, and any other Top-Parts-hosting page (FR-006, FR-025)
- [ ] T040 [US3] Add the `Rank Sort Measure` single-select slicer (`'Rank Sort Measure'[Label]`, sorted by SortOrder, default "Order $ (Decending)") to the same Top-Parts-hosting pages in `…/pages/{page}/visuals/rankSortMeasureSlicer/visual.json` (FR-007, FR-025)
- [ ] T041 [US3] Wire each Top Parts visual (T030, T032) to the visual-level filter `Rank Filter = 1` (applied via the Desktop filter pane, NOT at the visual.json root) so only the top `Rows Displayed` ranked parts show; document the binding in each Top Parts visual's notes (FR-011, FR-025)
- [ ] T042 [US3] Confirm the Sales-by-Date `Reorder Type` color legend and the Data Detail dimension slicers cross-filter their dependent visuals on each page (FR-026, US3 acceptance)

### Top-N Validation (User Story 3)

- [ ] T043 [US3] Functional spot-check via DAX query: with `Rows Displayed` = 5/10/20/50/All and each `Rank Sort Measure` option, confirm the set of parts where `Rank Filter = 1` re-trims and re-ranks correctly, "All" (10000) shows every part without truncation, and tied parts (same `Measure for Rank`) stay in the Top-N set under DENSE rank (SC-003, SC-005)

**Checkpoint**: Slicing and Top-N control reproduce the Tableau interactive UX; both parameter slicers drive every Top Parts visual in a single interaction (SC-003).

---

## Phase 6: Polish & End-to-End Validation (Cross-Cutting)

**Purpose**: Final fidelity pass and full-project validation before delivery.

- [ ] T044 Fidelity pass — confirm every visual carries its Tableau worksheet-name title, 1px `#E0E0E0` border, alt text, light-gray background, and 25px edge / 20px gap layout; confirm currency `$#,##0` and percent `0.00%` formats are preserved in all visuals (FR-028, FR-029)
- [ ] T045 [P] Confirm no redundant objects were created — pure aliases / "(copy)" duplicates (`Base Style Name`, `Delivery Season (copy)`, `Delivery Month (copy)`, `Category (copy)`, `Base Part (copy)`, the `(copy)` measure variants, `Global="Global"`) reuse original source columns/measures and are NOT new objects; confirm no RLS roles, sets, groups, or bins exist (FR-005, FR-017, SC-002)
- [ ] T046 Run the full end-to-end validation in order: (1) `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.SemanticModel\definition"`, (2) `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"`, (3) PBIR JSON parse check over `.Report/`; fix every exit-code-2 error and re-run until all three are clean (SC-007)
- [ ] T047 Open `Output/Q3DealerBuyingEvent/Q3DealerBuyingEvent.pbip` in Power BI Desktop and confirm it loads with no model/refresh errors and all five pages render (SC-007)

**Checkpoint**: All artifacts pass structural validation with zero errors and open cleanly in Power BI Desktop.

---

## Dependencies & Story Completion Order

```
Phase 1 (Setup: T001–T006)
        ↓
Phase 2 (Foundational data layer: T007–T012)  ← BLOCKS everything below
        ↓
Phase 3 (US2 model/measures: T013–T019)  ← P1, MVP foundation; model usable standalone
        ↓
Phase 4 (US1 five-dashboard report: T020–T038)  ← P1; depends on the model (measures/columns/relationship)
        ↓
Phase 5 (US3 slicing & Top-N: T039–T043)  ← P2; depends on report pages + parameter tables
        ↓
Phase 6 (Polish & E2E validation: T044–T047)
```

- **US2 (Phase 3)** depends only on the foundational data layer (Phase 2) — it is the MVP foundation and is independently testable.
- **US1 (Phase 4)** depends on US2 (visuals bind to the measures, derived columns, and DimDate relationship).
- **US3 (Phase 5)** depends on US1 (slicers/Top-N filters attach to existing report pages and visuals) and the Phase 2 parameter tables.
- Within a phase, `[P]` tasks touch different files and may run in parallel; tasks editing the **same** file (e.g., all measure/column tasks on `LaunchData.tmdl`) run sequentially.

## Parallel Execution Examples

- **Phase 1**: T003, T004, T005, T006 in parallel (distinct files) after T001/T002.
- **Phase 2**: T009, T010, T011, T012 in parallel — each authors a separate table `.tmdl` after the model header (T007/T008).
- **Phase 4**: T022–T026 (page.json files) in parallel; then each page's visual tasks (T027/T028, T029/T030, T031–T034, T035, T036) in parallel across pages since they write to distinct `visuals/{visual}/visual.json` paths.

## Implementation Strategy (MVP First)

1. **MVP = Phase 1 → Phase 2 → Phase 3 (US2)**: delivers a complete, validated single-table semantic model with all 7 measures, 2 derived columns, the DimDate relationship, and both parameter tables — independently auditable and DAX-testable.
2. **Increment 2 = Phase 4 (US1)**: adds the five faithful dashboard pages on top of the model.
3. **Increment 3 = Phase 5 (US3)**: layers the parameter slicers and Top-N filtering for full interactive parity.
4. **Finalize = Phase 6**: fidelity polish + zero-error structural validation + Desktop load check before delivery.
