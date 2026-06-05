# Tasks: Netflix Workbook Power BI Migration

**Input**: Design documents from `specs/006-netflix-pbi/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, `.specify/memory/NetflixAnalysis/dax-measures-output.md`, `.specify/memory/NetflixAnalysis/star-schema-output.md`

**Tests**: Not requested for this migration — automated TMDL/PBIP validators replace unit tests. No test tasks generated.

**Organization**: Tasks are grouped by user story (US1 data load P1, US2 time intelligence P1, US3 DAX measures P2) plus shared setup, validation, and report-authoring phases.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1, US2, US3) — setup/foundational/validation/report/polish tasks carry no story label
- Every task lists an exact file path

## Constitution & Skill References

All TMDL/PBIR generation MUST comply with the migration constitution and plugin skills:
- §0 Single-Table Rule: single CSV → `NetflixTitles` kept intact; only `DimDate` added
- §2 Naming: PascalCase tables/columns, Title Case measures
- §3 DAX: VAR/RETURN, `KEEPFILTERS` with literal boolean filters (no measure refs), display folders, format strings
- §4 Relationships: single many-to-one, single-direction, active
- §5 M Query: independent load, `QuoteStyle.Csv`, Encoding 65001, types after header promotion
- §8 PBIP Structure: `.pbip` + `.SemanticModel/` (TMDL) + `.Report/` (PBIR)
- TMDL syntax rules: `plugins/pbip/skills/tmdl/SKILL.md`
- PBIR format rules: `plugins/pbip/skills/pbir-format/SKILL.md`

---

## Phase 1: Setup (Scaffold PBIP Structure)

**Purpose**: Read format rules and create the `Output/NetflixAnalysis/` container files (.pbip, .platform, .pbism, .pbir, diagramLayout)

- [ ] T001 Read TMDL syntax rules from `plugins/pbip/skills/tmdl/SKILL.md` before generating any `.tmdl` files
- [ ] T002 Read PBIR format rules from `plugins/pbip/skills/pbir-format/SKILL.md` before generating any report JSON
- [ ] T003 [P] Create project manifest `Output/NetflixAnalysis/NetflixAnalysis.pbip` with `$schema` and `byPath` artifact reference to `NetflixAnalysis.Report`
- [ ] T004 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/.platform` with `$schema`, `metadata` (type `SemanticModel`, displayName `NetflixAnalysis`), and `config`
- [ ] T005 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.Report/.platform` with `$schema`, `metadata` (type `Report`, displayName `NetflixAnalysis`), and `config`
- [ ] T006 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition.pbism` with the semantic model `$schema` and version
- [ ] T007 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/diagramLayout.json` with NetflixTitles and DimDate node placeholders
- [ ] T008 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.Report/definition.pbir` with `$schema`, `version`, and `datasetReference.byPath` pointing to `../NetflixAnalysis.SemanticModel`

**Checkpoint**: Project scaffold complete — all container files exist and bind to each other

---

## Phase 2: Foundational (Model Definition — Blocking)

**Purpose**: Author the model-level TMDL that every table and relationship depends on

**⚠️ CRITICAL**: No table or relationship TMDL can be authored until this phase completes

- [ ] T009 Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/database.tmdl` with `compatibilityLevel: 1601`
- [ ] T010 Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/model.tmdl` with culture `en-US`, `defaultPowerBIDataSourceVersion: powerBI_V3`, discourageImplicitMeasures annotation, and `ref table NetflixTitles` + `ref table DimDate`

**Checkpoint**: Model shell ready — table TMDL authoring can begin

---

## Phase 3: User Story 1 — Load Netflix Data into Power BI (Priority: P1) 🎯 MVP

**Goal**: Generate the `NetflixTitles` table loading all 12 columns from `netflix_titles.csv` with correct data types

**Independent Test**: Open the `.pbip` in Power BI Desktop → `NetflixTitles` loads all rows; show_id/release_year = Whole Number, date_added = Date, all others = Text; all 12 columns visible in the Fields pane

### Implementation for User Story 1

- [ ] T011 [US1] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/tables/NetflixTitles.tmdl` with an M partition loading `Data\Netflix\netflix_titles.csv` via `Csv.Document(File.Contents(...))` using `[Delimiter = ",", Columns = 12, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]`, `Table.PromoteHeaders([PromoteAllScalars = true])`, then `Table.TransformColumnTypes` for all 12 columns
- [ ] T012 [US1] Add the 12 column declarations to `NetflixTitles.tmdl` with correct types and `summarizeBy: none`: show_id (int64), type (string), title (string), director (string), cast (string), country (string), date_added (dateTime), release_year (int64), rating (string), duration (string), listed_in (string), description (string); generate a unique `lineageTag` GUID per column
- [ ] T013 [US1] Apply `dataCategory: Country` to the `country` column in `NetflixTitles.tmdl` (FR-011) to enable geographic map visuals
- [ ] T014 [US1] Set `show_id` and `release_year` to Do Not Summarize (`summarizeBy: none`) in `NetflixTitles.tmdl` so they are treated as keys/attributes, not sums

**Checkpoint**: `NetflixTitles` table loads correctly with all 12 typed columns and the Country data category

---

## Phase 4: User Story 2 — Analyze Netflix Content by Time Period (Priority: P1)

**Goal**: Generate the `DimDate` calculated table and the active date relationship for time intelligence

**Independent Test**: Drag `DimDate[Year]` to a visual axis → titles group by the year of `date_added`; a date slicer filters related visuals; the relationship is active

**Depends on**: US1 (DimDate's `CALENDAR` range derives from `NetflixTitles[date_added]`)

### Implementation for User Story 2

- [ ] T015 [US2] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/tables/DimDate.tmdl` as a calculated table whose partition source is the DAX `CALENDAR(DATE(YEAR(MIN(NetflixTitles[date_added])),1,1), DATE(YEAR(MAX(NetflixTitles[date_added])),12,31))` wrapped in `ADDCOLUMNS`, with 7 columns: Date (dateTime, key), Year, Quarter, Month, MonthName, Day, DayOfWeek; unique `lineageTag` per column
- [ ] T016 [US2] Mark `DimDate` as a date table in `DimDate.tmdl` (set the date-table annotation / `dataCategory: Time`) and set `Date` as `isKey`
- [ ] T017 [US2] Set `MonthName` sort-by-column to `Month` in `DimDate.tmdl` for chronological ordering
- [ ] T018 [US2] Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/relationships.tmdl` with a single active many-to-one relationship `NetflixTitles[date_added]` → `DimDate[Date]`, single cross-filter direction, unique `lineageTag` GUID

**Checkpoint**: `DimDate` populated and the active date relationship filters `NetflixTitles` correctly

---

## Phase 5: User Story 3 — Use DAX Measures for Content Analysis (Priority: P2)

**Goal**: Add the 5 DAX measures (host: `NetflixTitles`) per `.specify/memory/NetflixAnalysis/dax-measures-output.md`

**Independent Test**: Place Total Titles + Distinct Titles on cards → Total Titles = source row count, Distinct Titles = unique show_id count; both respond to type/rating/genre/country and DimDate[Year] filters

**Depends on**: US1 (measures host) and US2 (Titles Added by Year uses the date relationship)

### Implementation for User Story 3

- [ ] T019 [US3] Add `Total Titles` (`COUNTROWS(NetflixTitles)`) and `Distinct Titles` (`DISTINCTCOUNT(NetflixTitles[show_id])`) measures to `NetflixTitles.tmdl`, display folder `Core Metrics`, formatString `#,##0`, unique lineageTag each
- [ ] T020 [US3] Add `Movies Count` and `TV Shows Count` measures to `NetflixTitles.tmdl` using the VAR + `CALCULATE(DISTINCTCOUNT(NetflixTitles[show_id]), KEEPFILTERS(NetflixTitles[type] = ...))` literal-boolean pattern, display folder `Category Counts`, formatString `#,##0`
- [ ] T021 [US3] Add `Titles Added by Year` measure to `NetflixTitles.tmdl` using `CALCULATE(DISTINCTCOUNT(NetflixTitles[show_id]), KEEPFILTERS(NOT ISBLANK(NetflixTitles[date_added])))`, display folder `Time Intelligence`, formatString `#,##0`

**Checkpoint**: All 5 measures present with display folders and format strings; semantic model is content-complete

---

## Phase 6: Semantic Model Validation

**Purpose**: Validate TMDL syntax and PBIP structure before authoring the report (per plan Stage B)

- [ ] T022 Run `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixAnalysis\NetflixAnalysis.SemanticModel\definition"` and fix any indentation/property-order/quoting errors until it exits 0 (SC-006)
- [ ] T023 Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixAnalysis"` and fix any exit-code-2 errors (SC-007)

**Checkpoint**: Semantic model passes both validators — safe to author the report

---

## Phase 7: Report Authoring (PBIR Pages — 9 Worksheets + Netflix Dashboard)

**Purpose**: Generate the PBIR report mapping the Tableau worksheets and the `Netflix` dashboard to Power BI visuals (25px edge padding, 20px gaps, titles shown, 1px `#E0E0E0` borders, `active: true` projections)

**Depends on**: Phase 6 (validated semantic model providing fields/measures)

- [ ] T024 Create `Output/NetflixAnalysis/NetflixAnalysis.Report/definition/report.json` with the minimal enhanced PBIR schema (`$schema`, `themeCollection`, `settings`) — no root `filters`/`filterConfig`
- [ ] T025 Create the `Netflix` dashboard report page at `Output/NetflixAnalysis/NetflixAnalysis.Report/definition/pages/Netflix/page.json` with `$schema`, `name` matching `^[\w-]+$`, `displayName` `Netflix`, and `displayOption`; register it in `pages.json`
- [ ] T026 [P] Add the **Country wise distribution** visual (filled map on `NetflixTitles[country]` using the Country data category, value = `Distinct Titles`) under `pages/Netflix/visuals/`
- [ ] T027 [P] Add the **Movies and TV Shows distribution** visual (donut/pie split by `NetflixTitles[type]` with `Movies Count` / `TV Shows Count` or `Distinct Titles` by type) under `pages/Netflix/visuals/`
- [ ] T028 [P] Add the **Total Movies and TV Shows by Years** visual (line/column chart, axis `DimDate[Year]`, value `Titles Added by Year`, legend `NetflixTitles[type]`) under `pages/Netflix/visuals/`
- [ ] T029 [P] Add the **Rating** / **Ratings** visual(s) (bar chart of `Distinct Titles` by `NetflixTitles[rating]`) under `pages/Netflix/visuals/`
- [ ] T030 [P] Add the **Genre** visual (bar chart of `Distinct Titles` by `NetflixTitles[listed_in]`) under `pages/Netflix/visuals/`
- [ ] T031 [P] Add the **Top 10 Genre** visual (bar chart of `Distinct Titles` by `NetflixTitles[listed_in]`; Top-N to be applied in Desktop UI — no root `filters` in JSON) under `pages/Netflix/visuals/`
- [ ] T032 [P] Add the **Duration** visual (table/bar of `NetflixTitles[title]` filtered to `type = "TV Show"`, showing `NetflixTitles[duration]`) under `pages/Netflix/visuals/`
- [ ] T033 [P] Add the **Description** visual (table of `NetflixTitles[title]` + `NetflixTitles[description]`) under `pages/Netflix/visuals/`
- [ ] T034 [P] Add a `DimDate[Year]` date slicer (migrating the Tableau `Year` parameter) under `pages/Netflix/visuals/`
- [ ] T035 Verify each visual.json contains only `$schema`, `name`, `position`, and `visual` at the root; title shown, 1px `#E0E0E0` border, alt text, and `active: true` projections; honor 25px edge padding and 20px inter-visual gaps

**Checkpoint**: Netflix dashboard page renders all 9 worksheet-derived visuals plus the year slicer

---

## Phase 8: Final End-to-End Validation (Model + Report)

**Purpose**: Re-validate the full project per plan Stage D

- [ ] T036 Run report JSON validity check: `Get-ChildItem "Output\NetflixAnalysis\NetflixAnalysis.Report" -Recurse -Include "*.json","*.pbir" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }` and fix any malformed JSON
- [ ] T037 Re-run `tmdl-validate-windows-x64.exe` on the semantic model `definition` folder and confirm exit code 0
- [ ] T038 Run `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixAnalysis"` on the project root and fix any exit-code-2 errors (model + report)
- [ ] T039 Confirm Success Gate: `.pbip` opens cleanly (SC-001), NetflixTitles row count matches source (SC-002), 12 columns with correct types (SC-003), DimDate relationship filters (SC-004), all 5 measures respond to date/category filters (SC-005)

**Checkpoint**: Full PBIP project passes all validators and meets every success criterion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all table/relationship work
- **US1 (Phase 3)**: Depends on Foundational — the MVP (data loads)
- **US2 (Phase 4)**: Depends on US1 (DimDate range derives from `NetflixTitles[date_added]`)
- **US3 (Phase 5)**: Depends on US1 (measures host) and US2 (date-aware measure)
- **Model Validation (Phase 6)**: Depends on US1–US3
- **Report (Phase 7)**: Depends on Phase 6 (validated model)
- **Final Validation (Phase 8)**: Depends on Phase 7

### User Story Dependencies

- **US1 (P1)**: Foundational base table — no story dependencies
- **US2 (P1)**: Builds on US1 (date relationship)
- **US3 (P2)**: Builds on US1 + US2 (measures, including the date-aware trend)

### Parallel Opportunities

- Setup container files T003–T008 run in parallel (different files)
- US1 column work (T012–T014) edits the same `NetflixTitles.tmdl` — keep sequential after T011
- Report visuals T026–T034 run in parallel (separate visual.json files) once the page (T025) exists

---

## Implementation Strategy

- **MVP scope**: Phases 1–3 (US1) deliver a loadable single-table model — the minimum viable migration.
- **Incremental delivery**: Add US2 (time intelligence) → US3 (measures) → validate → author report → final validation.
- **Validate early**: Run Phase 6 before report authoring so schema/structure errors surface before visuals are built on top.

---

## Task Summary

- **Total tasks**: 39 (T001–T039)
- **Setup (Phase 1)**: 8 — scaffold .pbip / .platform / .pbism / .pbir / diagramLayout
- **Foundational (Phase 2)**: 2 — database.tmdl + model.tmdl
- **US1 data load (Phase 3)**: 4 — NetflixTitles M partition + 12 columns + Country data category
- **US2 time intelligence (Phase 4)**: 4 — DimDate CALENDAR + mark-as-date + sort + relationship
- **US3 measures (Phase 5)**: 3 — 5 measures across Core Metrics / Category Counts / Time Intelligence
- **Model validation (Phase 6)**: 2 — tmdl-validate + validate_pbip.py
- **Report authoring (Phase 7)**: 12 — report.json, Netflix page + 9 worksheet visuals + year slicer
- **Final validation (Phase 8)**: 4 — JSON check, tmdl-validate, validate_pbip.py, success gate
- **Parallelizable [P] tasks**: 14 (T003–T008, T026–T034)
- **Suggested MVP**: User Story 1 (Phases 1–3) → a Power BI model that loads the Netflix CSV
