# Tasks: Midnight Census Dashboard — Tableau to Power BI Migration

**Input**: `specs/003-midnight-census-pbi/plan.md`, `specs/003-midnight-census-pbi/spec.md`  
**Feature Branch**: `003-midnight-census-pbi`  
**Output**: `Output/MidnightCensusDashboard/`  
**Model Name**: `MidnightCensusDashboard`

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (independent file, no dependency on an incomplete preceding task)
- **[US#]**: Maps to a user story from spec.md (US1–US7)
- No story label = setup, foundational, or cross-cutting task

---

## Phase 1: Setup & Validation

**Purpose**: Confirm all prerequisite design artifacts and data files exist before any PBIP files are written.

- [ ] T001 Verify all design artifacts exist: `specs/003-midnight-census-pbi/spec.md`, `specs/003-midnight-census-pbi/plan.md`, `.specify/memory/MidnightCensusDashboard/star-schema-output.md`, `.specify/memory/MidnightCensusDashboard/dax-measures-output.md`
- [ ] T002 Verify CSV data source exists at `Data/Midnight Census/Midnight_Census_Template.csv` and has 10 columns (DEPARTMENT_KEY, Encounter CSN, Parent Hospital, Hospital, Unit, Patient Class, Census Date, Census Count, Census Count Adults, Census Count Peds)
- [ ] T003 Create output directory tree `Output/MidnightCensusDashboard/` if not present (folder only — no files yet)

**Checkpoint**: All design artifacts confirmed, CSV verified, output folder ready — model generation can begin.

---

## Phase 2: PBIP Semantic Model Generation

### 2A: Foundational Structure (blocks all user stories)

**Purpose**: PBIP root, SemanticModel folder scaffold, and model-level TMDL files that all table and measure tasks depend on.

**⚠️ CRITICAL**: No user story tasks (T010+) can begin until T004–T009 are complete.

- [ ] T004 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.pbip` — PBIP root project file referencing the SemanticModel and Report artifacts by path
- [ ] T005 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/` folder structure: `definition/` and `definition/tables/` sub-directories
- [ ] T006 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/.platform` — PBIP platform descriptor file (artifact type: SemanticModel, displayName: MidnightCensusDashboard)
- [ ] T007 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/definition.pbism` — version 4.2, `"fromPowerBIServiceLive": false`
- [ ] T008 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/definition/database.tmdl` — `database MidnightCensusDashboard` declaration with `compatibilityLevel: 1567`
- [ ] T009 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/definition/model.tmdl` — model declaration with `ref table` entries for all 7 tables (MidnightCensus, DimDate, FilterAdultsPeds, DateAggLevel, View, StartDate, EndDate) and `ref relationship` entry for relationships.tmdl

**Checkpoint**: Scaffold complete — table TMDL files and relationship file can now be created.

---

### Phase 2B: User Story 1 — Census Data Loads and Displays (Priority: P1) 🎯 MVP

**Goal**: Fact table loads from CSV, all 10 columns typed correctly, DimDate calculated, relationship active — the report can display census data.

**Independent Test**: Open `.pbip` in Power BI Desktop, refresh data, verify row count matches CSV line count minus header, all 10 columns visible with correct types.

- [ ] T010 [US1] Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/definition/tables/MidnightCensus.tmdl` — fact table with M query CSV partition (`Csv.Document(File.Contents(...\Data\Midnight Census\Midnight_Census_Template.csv), [Delimiter=",", Columns=10, Encoding=65001])`) and all 10 typed source columns: DEPARTMENT_KEY (int64, summarizeBy: none), Encounter CSN (string), Parent Hospital (string), Hospital (string), Unit (string), Patient Class (string), Census Date (dateTime, summarizeBy: none), Census Count (int64, summarizeBy: sum), Census Count Adults (int64, summarizeBy: sum), Census Count Peds (int64, summarizeBy: sum)
- [ ] T011 [US1] Add **Parameters** display-folder measures to `definition/tables/MidnightCensus.tmdl`: `Selected Filter Adults/Peds` (SELECTEDVALUE default "(All)"), `Selected Date Agg Level` (SELECTEDVALUE default "Monthly"), `Selected View` (SELECTEDVALUE default "Bar Chart"), `Selected Start Date` (COALESCE + STARTOFYEAR(TODAY()), formatString: Short Date), `Selected End Date` (COALESCE + TODAY()-1, formatString: Short Date)
- [ ] T012 [US1] Add **Census Measures** display-folder base measures to `definition/tables/MidnightCensus.tmdl`: `Total Census Count` (SUM, #,0), `Total Census Count Adults` (SUM, #,0), `Total Census Count Peds` (SUM, #,0), `Last Refresh Date` (MAX(MidnightCensus[Census Date]), Short Date), `Default Start Date` (STARTOFYEAR(TODAY()), Short Date), `Default End Date` (TODAY()-1, Short Date) — all table refs must use `MidnightCensus[...]` not `Midnight_Census_Template[...]`
- [ ] T013 [P] [US1] Create `definition/tables/DimDate.tmdl` — calculated date table with `CALENDAR(DATE(2021,1,1),TODAY())` partition, `Date` column (dateTime, isKey, formatString: Short Date, sourceColumn: Date, summarizeBy: none), 16 computed columns (DateKey int64, Year int64, Quarter int64, QuarterName string, YearQuarter string, Month int64, MonthName string, MonthShort string, YearMonth string, Day int64, DayOfWeek int64, DayOfWeekName string, WeekNumber int64, IsWeekend boolean, StartOfMonth dateTime, EndOfMonth dateTime — all `columnType: calculated`, all `summarizeBy: none`), and annotation `__PBI_MarkAsDateTable_Column = Date`

**Checkpoint**: Fact table and date dimension authored — date range filtering tasks can now begin.

---

### Phase 2C: User Story 2 — Date Range Filtering (Priority: P1)

**Goal**: Start Date and End Date parameter tables exist, relationship to DimDate is active — date slicers can filter census data.

**Independent Test**: Set Start Date slicer to 2023-01-01, End Date to 2023-03-31 — verify all visuals filter to that period only.

- [ ] T014 [P] [US2] Create `definition/tables/StartDate.tmdl` — `GENERATESERIES(DATE(2021,1,1),TODAY(),1)` parameter table; column `Start Date` (dateTime, formatString: Short Date, sourceColumn: Start Date); `isHidden`, `isPrivate`; `annotation PBI_ResultType = Table`
- [ ] T015 [P] [US2] Create `definition/tables/EndDate.tmdl` — `GENERATESERIES(DATE(2021,1,1),TODAY(),1)` parameter table; column `End Date` (dateTime, formatString: Short Date, sourceColumn: End Date); `isHidden`, `isPrivate`; `annotation PBI_ResultType = Table`
- [ ] T016 [US2] Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.SemanticModel/definition/relationships.tmdl` — single active relationship `MidnightCensus_CensusDate_DimDate_Date`: fromTable: MidnightCensus, fromColumn: 'Census Date', toTable: DimDate, toColumn: Date, crossFilteringBehavior: singleCross, isActive: true (many-to-one direction)

**Checkpoint**: Date parameter tables and relationship written — Adults/Peds and aggregation toggle tables can now be added in parallel.

---

### Phase 2D: User Story 3 — Adults/Peds/All Patient Class Filter (Priority: P2)

**Goal**: Filter Adults Peds parameter table and User Defined Census Count measure drive the slicer-responsive census total.

**Independent Test**: Select "Adults" from slicer — verify census totals match `SUM(Census Count Adults)` for the same date range.

- [ ] T017 [P] [US3] Create `definition/tables/FilterAdultsPeds.tmdl` — `DATATABLE("Filter Adults/Peds Value", STRING, {{"(All)"},{"Adults"},{"Peds"}})` parameter table; column `Filter Adults/Peds Value` (string, sourceColumn: Filter Adults/Peds Value); `isHidden`, `isPrivate`; `annotation PBI_ResultType = Table`
- [ ] T018 [US3] Add `User Defined Census Count` measure to `definition/tables/MidnightCensus.tmdl` — `VAR _filter = SELECTEDVALUE('Filter Adults Peds'[Filter Adults/Peds Value], "(All)")`, `RETURN SWITCH(_filter, "(All)", SUM(MidnightCensus[Census Count]), "Adults", SUM(MidnightCensus[Census Count Adults]), "Peds", SUM(MidnightCensus[Census Count Peds]), SUM(MidnightCensus[Census Count]))`, displayFolder: Census Measures, formatString: #,0

**Checkpoint**: Adults/Peds filter operational — aggregation toggle tables can be added next.

---

### Phase 2E: User Story 4 — Monthly vs Daily Aggregation Toggle (Priority: P2)

**Goal**: Date Agg Level parameter table and Is Monthly / Is Daily measures enable the report to show the correct aggregation-level visual.

**Independent Test**: Set Date Agg Level to "Monthly" — bar chart X-axis shows YearMonth. Set to "Daily" — X-axis shows Date.

- [ ] T019 [P] [US4] Create `definition/tables/DateAggLevel.tmdl` — `DATATABLE("Date Agg Level Value", STRING, {{"Monthly"},{"Daily"}})` parameter table; column `Date Agg Level Value` (string, sourceColumn: Date Agg Level Value); `isHidden`, `isPrivate`; `annotation PBI_ResultType = Table`
- [ ] T020 [US4] Add `Is Monthly` and `Is Daily` measures to `definition/tables/MidnightCensus.tmdl` — `Is Monthly = IF(SELECTEDVALUE('Date Agg Level'[Date Agg Level Value],"Monthly")="Monthly",1,0)`, `Is Daily = IF(SELECTEDVALUE('Date Agg Level'[Date Agg Level Value],"Monthly")="Daily",1,0)`; displayFolder: Census Measures, formatString: 0

**Checkpoint**: Aggregation toggle measures in place — View toggle table can be added next.

---

### Phase 2F: User Story 5 — Bar Chart vs Data Table View Toggle (Priority: P2)

**Goal**: View parameter table and Is Bar Chart / Is Data Table measures enable the bookmark-driven visual show/hide.

**Independent Test**: Set View to "Bar Chart" — bar chart is visible, data table is hidden. Set to "Data Table" — reverse.

- [ ] T021 [P] [US5] Create `definition/tables/View.tmdl` — `DATATABLE("View Value", STRING, {{"Bar Chart"},{"Data Table"}})` parameter table; column `View Value` (string, sourceColumn: View Value); `isHidden`, `isPrivate`; `annotation PBI_ResultType = Table`
- [ ] T022 [US5] Add `Is Bar Chart` and `Is Data Table` measures to `definition/tables/MidnightCensus.tmdl` — `Is Bar Chart = IF(SELECTEDVALUE('View'[View Value],"Bar Chart")="Bar Chart",1,0)`, `Is Data Table = IF(SELECTEDVALUE('View'[View Value],"Bar Chart")="Data Table",1,0)`; displayFolder: Census Measures, formatString: 0

**Checkpoint**: All 7 tables and 19 measures complete — partial month warning measures are the final semantic model addition.

---

### Phase 2G: User Story 6 — Partial Month Data Warning (Priority: P3)

**Goal**: Partial-month detection measures correctly identify mid-month date boundaries and surface a warning string.

**Independent Test**: Set Start Date to the 15th of any month — `Partial Months in View?` returns the warning string. Set to the 1st — returns blank.

- [ ] T023 [US6] Add `Start Month Contains Partial Data?` measure to `definition/tables/MidnightCensus.tmdl` — `VAR _startDate = COALESCE(SELECTEDVALUE('Start Date'[Start Date]), STARTOFYEAR(TODAY()))`, `RETURN IF(DAY(_startDate)<>1, 1, 0)`; displayFolder: Census Measures, formatString: 0
- [ ] T024 [US6] Add `End Month Contains Partial Data?` measure to `definition/tables/MidnightCensus.tmdl` — `VAR _endDate = COALESCE(SELECTEDVALUE('End Date'[End Date]), TODAY()-1)`, `VAR _endOfMonth = EOMONTH(_endDate,0)`, `RETURN IF(_endDate<>_endOfMonth, 1, 0)`; displayFolder: Census Measures, formatString: 0
- [ ] T025 [US6] Add `Partial Months in View?` measure to `definition/tables/MidnightCensus.tmdl` — VAR pattern combining _startPartial and _endPartial booleans, `RETURN IF(_startPartial||_endPartial, "**Partial months are displayed in GRAY**", "")`; displayFolder: Census Measures, no format string (text)

**Checkpoint**: All 19 measures authored. Semantic model is complete — report shell generation can begin.

---

## Phase 3: PBIP Report Shell

### 3A: Foundational Report Structure (blocks all visual tasks)

**Purpose**: Report folder scaffold, `.platform`, `definition.pbir`, and `report.json` shell that all visual JSON files depend on.

- [ ] T026 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.Report/` folder structure: `definition/`, `definition/pages/MidnightCensus/visuals/`, `definition/pages/Info/visuals/`
- [ ] T027 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.Report/.platform` — PBIP platform descriptor file (artifact type: Report, displayName: MidnightCensusDashboard)
- [ ] T028 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.Report/definition.pbir` — `$schema`, `version: "4.0"`, `datasetReference: {byPath: {path: "../MidnightCensusDashboard.SemanticModel"}}`
- [ ] T029 Create `Output/MidnightCensusDashboard/MidnightCensusDashboard.Report/definition/report.json` — shell with `$schema`, `themeCollection: {defaultTheme: {type: "SharedResources", name: "CY24SU06"}}`, and empty `bookmarks: []` array (bookmarks will be added in T043)

**Checkpoint**: Report scaffold complete — page and visual JSON files can now be created.

---

### Phase 3B: User Story 1 — Main Page Structure & Info Page (Priority: P1)

**Goal**: Both report pages defined, Info page content rendered, Last Refresh card visible.

**Independent Test**: Report opens in Power BI Desktop with two pages — "Midnight Census" and "Info". Info page displays static text content. Last Refresh card shows a date value.

- [ ] T030 [US1] Create `definition/pages/MidnightCensus/page.json` — `$schema`, `name: "MidnightCensus"` (matches `^[\w-]+$`), `displayName: "Midnight Census"`, `displayOption: 1` (fit to page), canvas width: 1366, height: 768
- [ ] T031 [P] [US1] Create `definition/pages/Info/page.json` — `$schema`, `name: "Info"`, `displayName: "Info"`, `displayOption: 1`
- [ ] T032 [P] [US1] Create `definition/pages/Info/visuals/textbox-info-content/visual.json` — TextBox visual ($schema: visualContainer/2.4.0, name, position spanning full canvas); static text content: Title "Patient Days — Midnight Census", general description of midnight census purpose, Source "CDW-H / custom SQL from ADT, ENCOUNTER, LOCATION, PATIENT masters", Contacts "Austin Gilmore, BI Analyst", Refresh Schedule "Daily 08:30 AM"
- [ ] T033 [P] [US1] Create `definition/pages/MidnightCensus/visuals/card-last-refresh/visual.json` — Card visual bound to `[Last Refresh Date]` measure on MidnightCensus table; title property set to "Refreshes Daily 2:00 AM" (static); positioned bottom-right of canvas

**Checkpoint**: Page scaffolds and Info content complete — all remaining visual creation tasks can run in parallel.

---

### Phase 3C: User Story 2 — Date Range Filtering Slicers (Priority: P1)

**Goal**: Start Date and End Date slicers appear in the control bar and filter all visuals by date.

**Independent Test**: Set Start Date slicer to 2023-01-01, End Date to 2023-03-31 — all bar/table visuals show only that period.

- [ ] T034 [P] [US2] Create `definition/pages/MidnightCensus/visuals/slicer-start-date/visual.json` — date slicer, Between filter type, bound to `'Start Date'[Start Date]`; positioned in control bar zone (top row, left area); title: "Start Date"
- [ ] T035 [P] [US2] Create `definition/pages/MidnightCensus/visuals/slicer-end-date/visual.json` — date slicer, Between filter type, bound to `'End Date'[End Date]`; positioned in control bar zone (top row, right of Start Date); title: "End Date"

---

### Phase 3D: User Story 3 — Adults/Peds/All Slicer (Priority: P2)

**Goal**: Filter Adults/Peds slicer appears in control bar and drives User Defined Census Count across all primary visuals.

**Independent Test**: Select "Adults" — all census totals in bar chart and table reflect Census Count Adults only.

- [ ] T036 [P] [US3] Create `definition/pages/MidnightCensus/visuals/slicer-filter-adults-peds/visual.json` — tile/horizontal slicer bound to `'Filter Adults Peds'[Filter Adults/Peds Value]`; positioned in control bar zone; title: "Filter Adults/Peds"

---

### Phase 3E: User Story 4 — Monthly vs Daily Aggregation Visuals (Priority: P2)

**Goal**: Date Agg Level slicer and 4 primary visuals (2 bar charts, 2 tables) authored — bookmark toggle will control which pair is visible.

**Independent Test**: bookmark Bookmark_Monthly_Bar active — monthly bar chart visible; bookmark Bookmark_Daily_Table active — daily table visible.

- [ ] T037 [P] [US4] Create `definition/pages/MidnightCensus/visuals/slicer-date-agg-level/visual.json` — tile/horizontal slicer bound to `'Date Agg Level'[Date Agg Level Value]`; positioned in control bar zone; title: "Date Agg Level"
- [ ] T038 [P] [US4] Create `definition/pages/MidnightCensus/visuals/bar-monthly/visual.json` — clustered bar chart (`barChart`); category field: `DimDate[YearMonth]`; value field: `MidnightCensus[User Defined Census Count]`; title: "Monthly Census"; positioned in primary visual zone
- [ ] T039 [P] [US4] Create `definition/pages/MidnightCensus/visuals/bar-daily/visual.json` — clustered bar chart (`barChart`); category field: `DimDate[Date]`; value field: `MidnightCensus[User Defined Census Count]`; title: "Daily Census"; positioned in primary visual zone (same position as bar-monthly — visibility controlled by bookmarks)
- [ ] T040 [P] [US4] Create `definition/pages/MidnightCensus/visuals/table-monthly/visual.json` — table visual; row fields: `DimDate[YearMonth]`, `MidnightCensus[Hospital]`, `MidnightCensus[Unit]`; value field: `MidnightCensus[User Defined Census Count]`; title: "Monthly Census Table"; positioned in primary visual zone
- [ ] T041 [P] [US4] Create `definition/pages/MidnightCensus/visuals/table-daily/visual.json` — table visual; row fields: `DimDate[Date]`, `MidnightCensus[Hospital]`, `MidnightCensus[Unit]`; value field: `MidnightCensus[User Defined Census Count]`; title: "Daily Census Table"; positioned in primary visual zone

---

### Phase 3F: User Story 5 — View Toggle Slicer & Bookmarks (Priority: P2)

**Goal**: View slicer and 4 bookmarks implement the Bar Chart ↔ Data Table toggle without page reload.

**Independent Test**: With Bookmark_Monthly_Bar active: bar-monthly visible, bar-daily hidden, table-monthly hidden, table-daily hidden. With Bookmark_Daily_Table: table-daily visible, all others hidden.

- [ ] T042 [P] [US5] Create `definition/pages/MidnightCensus/visuals/slicer-view/visual.json` — tile/horizontal slicer bound to `'View'[View Value]`; positioned in control bar zone; title: "View"
- [ ] T043 [US5] Add 4 bookmarks to `definition/report.json` bookmarks array: `Bookmark_Monthly_Bar` (page MidnightCensus, show bar-monthly, hide bar-daily/table-monthly/table-daily), `Bookmark_Monthly_Table` (show table-monthly, hide others), `Bookmark_Daily_Bar` (show bar-daily, hide others), `Bookmark_Daily_Table` (show table-daily, hide others) — each bookmark stores `visualContainerState` keyed by visual name

---

### Phase 3G: User Story 6 — Partial Month Warning Card (Priority: P3)

**Goal**: Warning card visible when date range cuts across a partial calendar month.

**Independent Test**: Set Start Date to the 15th of a month — card shows warning text. Set to the 1st — card shows blank/empty state.

- [ ] T044 [P] [US6] Create `definition/pages/MidnightCensus/visuals/card-partial-data-warning/visual.json` — Card visual bound to `MidnightCensus[Partial Months in View?]` measure; positioned as warning strip below control bar (25px from top edge, full width minus side padding); no title; no border when blank

---

### Phase 3H: User Story 7 — Dimensional Slicers (Priority: P3)

**Goal**: Parent Hospital, Hospital, Patient Class, and Unit slicers appear on the main page and cross-filter all visuals.

**Independent Test**: Select a single Hospital — all bar/table visuals show only that hospital's census data. Clear selection — all data visible.

- [ ] T045 [P] [US7] Create `definition/pages/MidnightCensus/visuals/slicer-parent-hospital/visual.json` — vertical list slicer bound to `MidnightCensus[Parent Hospital]`; positioned in top filter zone (below control bar); title: "Parent Hospital"
- [ ] T046 [P] [US7] Create `definition/pages/MidnightCensus/visuals/slicer-hospital/visual.json` — vertical list slicer bound to `MidnightCensus[Hospital]`; positioned in top filter zone; title: "Hospital"
- [ ] T047 [P] [US7] Create `definition/pages/MidnightCensus/visuals/slicer-patient-class/visual.json` — vertical list slicer bound to `MidnightCensus[Patient Class]`; positioned in top filter zone; title: "Patient Class"
- [ ] T048 [P] [US7] Create `definition/pages/MidnightCensus/visuals/slicer-unit/visual.json` — vertical list slicer bound to `MidnightCensus[Unit]`; positioned in left sidebar zone; title: "Unit"

**Checkpoint**: All 15 visual containers authored. Report shell is complete — validation phase can begin.

---

## Phase 4: Validation

**Purpose**: Run all three validators in sequence; fix any errors before delivering output. Validation failures MUST block delivery.

**⚠️ CRITICAL**: Do not skip validation. Fix every error before proceeding to the next validator.

- [ ] T049 Run TMDL structural linter on SemanticModel definition folder: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\MidnightCensusDashboard\MidnightCensusDashboard.SemanticModel\definition"` — fix all indentation, property-ordering, quoting, and nesting errors before proceeding to T050
- [ ] T050 Run cross-cutting PBIP validator: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\MidnightCensusDashboard"` — exit code must be 0; fix all `.pbip` root errors, `.platform` errors, `definition.pbir` byPath binding mismatches, page name regex violations, and orphan page errors before proceeding to T051
- [ ] T051 Run semantic validation: `python "scripts\validate_semantics.py" "Output\MidnightCensusDashboard"` — fix any measure DAX syntax errors, broken table references, or relationship validation failures
- [ ] T052 Verify final artifact inventory matches `plan.md` project structure: `MidnightCensusDashboard.pbip`, `.SemanticModel/.platform`, `.SemanticModel/definition.pbism`, `definition/database.tmdl`, `definition/model.tmdl`, `definition/relationships.tmdl`, all 7 table TMDL files, `.Report/.platform`, `.Report/definition.pbir`, `definition/report.json`, `pages/MidnightCensus/page.json`, `pages/Info/page.json`, and all 15 visual JSON files — flag any missing artifacts

**Checkpoint**: All validators return zero errors. Output folder is complete and ready for Power BI Desktop.

---

## Dependencies

```
T001 → T002 → T003
T003 → T004 → T005 → T006, T007, T008, T009
T009 → T010 → T011, T012
T009 → T013 (parallel with T010)
T009 → T014, T015 (parallel)
T010 + T013 → T016
T009 → T017 (parallel)
T017 → T018
T009 → T019 (parallel)
T019 → T020
T009 → T021 (parallel)
T021 → T022
T023 → T024 → T025

T025 → T026 → T027, T028, T029
T030 → T031, T032, T033
T030 → T034, T035, T036, T037, T038, T039, T040, T041, T042, T044, T045, T046, T047, T048
T038 + T039 + T040 + T041 + T042 → T043

T048 → T049 → T050 → T051 → T052
```

## Parallel Execution Opportunities

**Semantic Model (after T009)**:
- T010, T013, T014, T015, T017, T019, T021 can all start simultaneously (separate files)

**Report Visuals (after T030)**:
- T031, T032, T033, T034, T035, T036, T037, T038, T039, T040, T041, T042, T044, T045, T046, T047, T048 can all start simultaneously (separate `visual.json` files)

## Implementation Strategy

| Increment | Scope | Covers |
|-----------|-------|--------|
| MVP | T001–T016 + T026–T033 + T049–T052 | US1 + US2: data loads, date dimension, date range slicers, Info page — functionally openable in Power BI Desktop |
| Increment 2 | T017–T022 + T034–T042 | US3 + US4 + US5: Adults/Peds filter, aggregation toggle, view toggle, all primary visuals + bookmarks |
| Increment 3 | T023–T025 + T043–T048 | US6 + US7: partial month warning, dimensional slicers |

**Suggested MVP scope**: Complete Phase 1 + Phase 2B/2C + Phase 3A/3B + Phase 4 (T001–T016, T026–T033, T049–T052) — this produces a fully openable `.pbip` that loads census data, shows the date dimension, and passes all validators.

---

## Summary

| Phase | Tasks | User Stories |
|-------|-------|-------------|
| Phase 1: Setup | T001–T003 | — |
| Phase 2A: SM Scaffold | T004–T009 | — (foundational) |
| Phase 2B: US1 Data Loads | T010–T013 | US1 (P1) |
| Phase 2C: US2 Date Range | T014–T016 | US2 (P1) |
| Phase 2D: US3 Adults/Peds | T017–T018 | US3 (P2) |
| Phase 2E: US4 Agg Toggle | T019–T020 | US4 (P2) |
| Phase 2F: US5 View Toggle | T021–T022 | US5 (P2) |
| Phase 2G: US6 Partial Month | T023–T025 | US6 (P3) |
| Phase 3A: Report Scaffold | T026–T029 | — (foundational) |
| Phase 3B: US1 Pages | T030–T033 | US1 (P1) |
| Phase 3C: US2 Date Slicers | T034–T035 | US2 (P1) |
| Phase 3D: US3 Adults Slicer | T036 | US3 (P2) |
| Phase 3E: US4 Agg Visuals | T037–T041 | US4 (P2) |
| Phase 3F: US5 View+Bookmarks | T042–T043 | US5 (P2) |
| Phase 3G: US6 Warning Card | T044 | US6 (P3) |
| Phase 3H: US7 Dim Slicers | T045–T048 | US7 (P3) |
| Phase 4: Validation | T049–T052 | — (cross-cutting) |
| **Total** | **52 tasks** | **7 user stories** |
