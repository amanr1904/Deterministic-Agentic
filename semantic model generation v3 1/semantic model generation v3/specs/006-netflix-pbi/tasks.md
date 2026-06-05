# Tasks: Netflix Workbook Power BI Migration

**Input**: Design documents from `specs/006-netflix-pbi/`
**Prerequisites**: plan.md (required), spec.md (required), `.specify/memory/dax-measures-output.md`, `.specify/memory/constitution.md`

**Tests**: Not explicitly requested — test tasks omitted.

**Organization**: Tasks are grouped by user story (P1 data loading, P1 time intelligence, P2 DAX measures) with a setup phase and validation phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Constitution Reference

All tasks MUST comply with `.specify/memory/constitution.md` (never modify it). Key rules:
- §0 Single-Table Rule: No decomposition of the single CSV source
- §2 Naming: PascalCase tables/columns, Title Case measures
- §3 DAX: VAR/RETURN, DIVIDE(), display folders, format strings
- §5 M Query: Independent loads, QuoteStyle.Csv, promote headers immediately
- §8 PBIP Structure: Standard folder layout with .pbip, .SemanticModel/, .Report/

---

## Phase 1: Setup (Validation & Scaffold)

**Purpose**: Validate constitution compliance, confirm design artifacts exist, create project scaffold

- [ ] T001 Verify constitution compliance by reading `.specify/memory/constitution.md` and confirming all rules §0–§10 are satisfied per plan.md gate evaluation
- [ ] T002 Confirm design artifacts exist: `.specify/memory/dax-measures-output.md` (8 measures defined), `specs/006-netflix-pbi/plan.md` (star schema inline)
- [ ] T003 Read TMDL syntax rules from `plugins/pbip/skills/tmdl/SKILL.md` before generating any .tmdl files
- [ ] T004 Read PBIR format rules from `plugins/pbip/skills/pbir-format/SKILL.md` before generating report files
- [ ] T005 [P] Create project file at `Output/NetflixAnalysis/NetflixAnalysis.pbip` with `$schema` and `byPath` reference to `.SemanticModel`
- [ ] T006 [P] Create semantic model platform file at `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/.platform` with `"$schema"`, `"config"`, `"settings"` structure
- [ ] T007 [P] Create report platform file at `Output/NetflixAnalysis/NetflixAnalysis.Report/.platform` with `"$schema"`, `"config"`, `"settings"` structure
- [ ] T008 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition.pbism` with version 4.2 and byConnection binding
- [ ] T009 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/diagramLayout.json` with empty layout structure
- [ ] T010 [P] Create `Output/NetflixAnalysis/NetflixAnalysis.Report/definition.pbir` with version 4.0 and byPath datasetReference pointing to `../NetflixAnalysis.SemanticModel`

**Checkpoint**: Project scaffold complete — all container files exist

---

## Phase 2: User Story 1 — Load Netflix Data into Power BI (Priority: P1) 🎯 MVP

**Goal**: Generate the NetflixTitles table with M query loading all 12 columns from netflix_titles.csv with correct data types

**Independent Test**: Open .pbip in Power BI Desktop → NetflixTitles table loads all rows with correct data types for all 12 columns

### Implementation for User Story 1

- [ ] T011 [US1] Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/database.tmdl` with compatibilityLevel 1601 and model ID annotation (GUID)
- [ ] T012 [US1] Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/model.tmdl` with ref table entries for NetflixTitles and DimDate, culture en-US, defaultPowerBIDataSourceVersion powerBI_V3
- [ ] T013 [US1] Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/tables/NetflixTitles.tmdl` with M partition loading `Data/Netflix/netflix_titles.csv` via `Csv.Document(File.Contents(...))`, 12 source columns (show_id Int64, type text, title text, director text, cast text, country text with dataCategory Country, date_added dateTime, release_year Int64, rating text, duration text, listed_in text, description text), all non-additive columns with summarizeBy none
- [ ] T014 [US1] Add 8 DAX measures to `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/tables/NetflixTitles.tmdl` organized by display folders: Core Metrics (Total Titles, Total Movies, Total TV Shows, % Movies, % TV Shows), Ranking (Genre Rank, Is Top 10 Genre), Year-over-Year (Titles Added This Year) — each with formatString per `.specify/memory/dax-measures-output.md`

**Checkpoint**: NetflixTitles table with M query + 8 measures complete

---

## Phase 3: User Story 2 — Analyze Netflix Content by Time Period (Priority: P1)

**Goal**: Generate DimDate table and relationship enabling time intelligence slicing by year/month/quarter

**Independent Test**: Drag DimDate[Year] to a visual → titles correctly grouped by year of date_added; date slicer filters related visuals

### Implementation for User Story 2

- [ ] T015 [US2] Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/tables/DimDate.tmdl` with M partition using `List.Dates(#date(2008,1,1), ...)` generating dates 2008-01-01 to 2026-12-31, columns: Date (isKey true, type dateTime), Year (Int64), Month (Int64), MonthName (text), Quarter (text), DayOfWeek (text) — all with summarizeBy none
- [ ] T016 [US2] Generate `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/relationships.tmdl` with single relationship: NetflixTitles[date_added] many-to-one DimDate[Date], singleDirection crossFilteringBehavior

**Checkpoint**: DimDate + relationship complete — time intelligence enabled

---

## Phase 4: User Story 3 — Use DAX Measures for Content Analysis (Priority: P2)

**Goal**: Verify all 8 DAX measures are correctly defined with proper format strings, display folders, and lineage tags

**Independent Test**: Place Total Titles on a card visual → shows correct count; filter by DimDate[Year] → measure responds to filter context

### Implementation for User Story 3

- [ ] T017 [US3] Verify all 8 measures in `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition/tables/NetflixTitles.tmdl` have: unique lineageTag GUIDs, correct formatString (#,##0 or 0.0%), correct displayFolder assignment, VAR/RETURN pattern for Genre Rank/Is Top 10 Genre/Titles Added This Year
- [ ] T018 [US3] Verify measure column references resolve: `NetflixTitles[type]` for Total Movies/Total TV Shows, `NetflixTitles[listed_in]` for Genre Rank, `NetflixTitles[date_added]` for Titles Added This Year — all columns must exist in the same .tmdl file

**Checkpoint**: All DAX measures validated — content analysis ready

---

## Phase 5: Validation & Compliance

**Purpose**: Run automated validators, fix errors, confirm PBIP schema compliance

- [ ] T019 Run TMDL structural validation: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixAnalysis\NetflixAnalysis.SemanticModel\definition"` — fix any syntax/indentation/property-order errors
- [ ] T020 Run PBIP cross-cutting validation: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixAnalysis"` — must exit with code 0 or 1 (no code-2 errors)
- [ ] T021 Validate all JSON files parse correctly: `NetflixAnalysis.pbip`, `definition.pbism`, `definition.pbir`, `diagramLayout.json`, `.platform` files
- [ ] T022 Verify M query safety: no cross-query references between NetflixTitles and DimDate partitions, QuoteStyle.Csv present, headers promoted
- [ ] T023 Verify relationship integrity: NetflixTitles[date_added] exists as dateTime, DimDate[Date] exists with isKey true, relationship direction is singleDirection
- [ ] T024 Confirm constitution compliance: re-check all rules §0–§10 against generated artifacts — no modifications to `.specify/memory/constitution.md`

**Checkpoint**: All validation passes — output ready for Power BI Desktop

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **US1 (Phase 2)**: Depends on T003, T004 (skill files read), T005–T010 (scaffold created)
- **US2 (Phase 3)**: Depends on T012 (model.tmdl must reference DimDate)
- **US3 (Phase 4)**: Depends on T013, T014 (measures must exist to verify)
- **Validation (Phase 5)**: Depends on ALL previous phases complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundation — NetflixTitles table is prerequisite for everything
- **User Story 2 (P1)**: Depends on US1 (model.tmdl references both tables)
- **User Story 3 (P2)**: Depends on US1 (measures defined in NetflixTitles.tmdl)

### Within Each User Story

- Read skill files → scaffold → TMDL generation → validation
- model.tmdl before table .tmdl files (ref declarations needed)
- Table files before relationships (columns must exist for relationship keys)

### Parallel Opportunities

- T005–T010 (all scaffold files) can run in parallel
- T011, T012 can run in parallel (database.tmdl and model.tmdl are independent)
- T019–T024 (validation tasks) are sequential (fix errors before proceeding)

---

## Parallel Example: Phase 1 Scaffold

```
# All scaffold files can be created simultaneously:
Task T005: Create NetflixAnalysis.pbip
Task T006: Create .SemanticModel/.platform
Task T007: Create .Report/.platform
Task T008: Create definition.pbism
Task T009: Create diagramLayout.json
Task T010: Create definition.pbir
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup & Scaffold
2. Complete Phase 2: NetflixTitles table with M query + DAX measures
3. **STOP and VALIDATE**: Run tmdl-validate on partial output
4. Proceed to Phase 3: DimDate + relationship

### Incremental Delivery

1. Setup + Scaffold → Foundation ready
2. Add NetflixTitles table → Verify M query loads CSV → MVP (single table works)
3. Add DimDate + relationship → Verify time slicing works
4. Verify all measures → Full model ready
5. Run validators → Fix issues → Output complete

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Constitution at `.specify/memory/constitution.md` is READ-ONLY — never modify
- All .tmdl files use tab indentation (semantic), one tab per depth level
- Generate unique lineageTag GUIDs for every table, column, measure, and relationship
- M query uses absolute path: `C:\Users\AmanRajMAQSoftware\Downloads\semantic model generation v2\semantic model generation v2\Data\Netflix\netflix_titles.csv`
- DimDate range: 2008-01-01 to 2026-12-31 (covers all Netflix data + future buffer)
- Commit after each phase checkpoint
