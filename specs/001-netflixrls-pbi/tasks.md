---
description: "Dependency-ordered implementation tasks for the Netflix RLS Tableau → Power BI migration"
---

# Tasks: Netflix RLS Dashboard Migration (Tableau → Power BI)

**Input**: Design documents from `specs/001-netflixrls-pbi/`
**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (user stories), [data-model.md](data-model.md), [research.md](research.md), [dax-measures-output.md](../../.specify/memory/NetflixRLS/dax-measures-output.md), [star-schema-output.md](../../.specify/memory/NetflixRLS/star-schema-output.md)

**Tests**: This is a PBIP migration — there is no executable test suite. "Tests" are the plugin validators (`tmdl-validate`, `validate_pbip.py`, JSON syntax) and the manual "View as role" RLS verification in Power BI Desktop. These are captured as explicit validation tasks per phase and in the final Polish phase.

**Output root**: `Output/NetflixRLS/`
**Source CSVs** (absolute-path referenced in M partitions): `Data/Netflix RLS/netflix_titles.csv`, `Data/Netflix RLS/User_Access.csv`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task serves — `[US1]` RLS, `[US2]` Dashboard, `[US3]` Year Trend, `[US4]` Genres/Ratings. Setup, Foundational, and Polish tasks carry no story label.
- Each task includes the exact file path it creates or edits.

## Skills to read BEFORE authoring (read once, reuse)

- TMDL syntax → `plugins/pbip/skills/tmdl/SKILL.md`
- PBIR JSON format → `plugins/pbip/skills/pbir-format/SKILL.md`
- PBIP project structure → `plugins/pbip/skills/pbip/SKILL.md`

---

## Phase 1: Setup (PBIP Scaffold — Plan Phase A.1)

**Purpose**: Create the empty PBIP project skeleton so every downstream artifact has a home.

- [ ] T001 Create the `Output/NetflixRLS/` folder tree: `NetflixRLS.SemanticModel/definition/tables/`, `NetflixRLS.SemanticModel/definition/roles/`, `NetflixRLS.Report/definition/pages/`.
- [ ] T002 Create `Output/NetflixRLS/NetflixRLS.pbip` (project pointer: `version`, `artifacts` → semantic model + report relative paths).
- [ ] T003 [P] Create `Output/NetflixRLS/NetflixRLS.SemanticModel/definition.pbism` (semantic model descriptor).
- [ ] T004 [P] Create `Output/NetflixRLS/NetflixRLS.SemanticModel/diagramLayout.json` (empty/default layout).
- [ ] T005 [P] Create `Output/NetflixRLS/NetflixRLS.Report/definition.pbir` (`$schema`, `version`, `datasetReference` byPath → `../NetflixRLS.SemanticModel`).
- [ ] T006 [P] Create `Output/NetflixRLS/NetflixRLS.Report/definition/version.json` (report version stamp).
- [ ] T007 [P] Create `.platform` files for `NetflixRLS.SemanticModel/` and `NetflixRLS.Report/` (logical type + metadata).

**Checkpoint**: Empty PBIP project opens its folder structure cleanly; `validate_pbip.py` recognizes the project root (warnings about missing tables expected at this stage).

---

## Phase 2: Foundational (Model Skeleton, Tables, Relationships, Core Measure — Plan Phases A.2, B, C.1, D)

**Purpose**: Build the complete semantic model that ALL user stories depend on. No user story (RLS or visuals) can be implemented until the tables, relationships, and the primary `Total Titles` measure exist.

**⚠️ CRITICAL**: User-story phases (3–6) MUST NOT start until this phase is complete and TMDL-valid.

### Model headers

- [ ] T008 Author `Output/NetflixRLS/NetflixRLS.SemanticModel/definition/database.tmdl` (compatibility level).
- [ ] T009 Author `Output/NetflixRLS/NetflixRLS.SemanticModel/definition/model.tmdl` (default culture `en-US`, `discourageImplicitMeasures` on, table refs).

### Tables with Power Query (M) partitions — each reads its CSV independently (constitution §5: `QuoteStyle.Csv`, `Text.Trim`, null-safe parse, no cross-query refs, no `Table.NestedJoin`)

- [ ] T010 [P] Author `definition/tables/FactTitle.tmdl` — partition loads `netflix_titles.csv`; promote headers; cast types; columns `show_id, type, title, director, cast, country, release_year, rating, duration, description`; parse `date_added` (text "MMMM d, yyyy", en-US, `try…otherwise null`) → `Date Added` (nullable date); derive `Year Added = Date.Year([Date Added])` (Int64, null-safe). Set `DataCategory` where relevant. (Plan B.1, C.3)
- [ ] T011 [P] Author `definition/tables/BridgeCountry.tmdl` — partition loads `netflix_titles.csv`; keep `show_id` + `country`; `Text.Split` country by `,`; `Text.Trim`; expand to one row per (`show_id`, `Country`); drop blank `Country`. (Plan B.2)
- [ ] T012 [P] Author `definition/tables/BridgeGenre.tmdl` — partition loads `netflix_titles.csv`; keep `show_id` + `listed_in`; split by `,`; `Text.Trim`; one row per (`show_id`, `Genre`); drop blanks. (Plan B.3)
- [ ] T013 [P] Author `definition/tables/DimCountry.tmdl` — partition unions split `netflix_titles.country` values AND `User_Access.Country` (both files read directly in one query), `Text.Trim`, `Distinct`; set `Country` column `Data Category = Country` for the filled map. (Plan B.4, data-model DimCountry)
- [ ] T014 [P] Author `definition/tables/DimGenre.tmdl` — partition reads `netflix_titles.csv`, split `listed_in` by `,`, `Text.Trim`, `Distinct` → `Genre`. (Plan B.5)
- [ ] T015 [P] Author `definition/tables/User_Access.tmdl` — partition loads `User_Access.csv`; columns `Username`, `Country`; `Text.Trim`; mark columns `isHidden` (security-only, kept out of report). (Plan B.6, data-model D7)

### Core measure (needed by every visual across all stories)

- [ ] T016 Add measure `Total Titles = DISTINCTCOUNT(FactTitle[show_id])` to `definition/tables/FactTitle.tmdl` — display folder `Core Metrics`, format `#,##0`. (Plan C.1, FR-008)

### Relationships (Plan Phase D — `relationships.tmdl`)

- [ ] T017 Author `Output/NetflixRLS/NetflixRLS.SemanticModel/definition/relationships.tmdl` with all 5 relationships and exact cross-filter flags: R1 `FactTitle[show_id]→BridgeCountry[show_id]` (Both), R2 `DimCountry[Country]→BridgeCountry[Country]` (Single), R3 `DimCountry[Country]→User_Access[Country]` (Both — RLS), R4 `FactTitle[show_id]→BridgeGenre[show_id]` (Both), R5 `DimGenre[Genre]→BridgeGenre[Genre]` (Single). All many-to-one, active; bidirectional ONLY on R1/R3/R4. (data-model Relationships, FR-006)

### Foundational validation

- [ ] T018 Run TMDL structural lint and fix all errors: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"`. Confirm indentation, property order, quoting, and referential integrity pass.

**Checkpoint**: All 6 tables, 5 relationships, and `Total Titles` parse cleanly. The model loads (author view, no role) and `Total Titles` returns the full distinct `show_id` count (SC-006). Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 — Dynamic Row-Level Security by Country (Priority: P1) 🎯 MVP

**Goal**: Each signed-in user sees only the Netflix titles for their entitled country, driven by `USERPRINCIPALNAME()` matched against `User_Access` — replacing the Tableau hardcoded `"user2@maq.com"` predicate.

**Independent Test**: Open the model in Power BI Desktop → "View as role" with `Dynamic Country Access` and a sample mapped username → every visual/measure filters to only that user's entitled country; switching to a different entitled user changes the visible titles; an unmapped user sees zero.

### Implementation for User Story 1 (Plan Phase E)

- [ ] T019 [US1] Author `Output/NetflixRLS/NetflixRLS.SemanticModel/definition/roles/Dynamic Country Access.tmdl` — `modelPermission: read`; `tablePermission User_Access = User_Access[Username] = USERPRINCIPALNAME()` (row-level boolean, NO measure references per constitution §4a). (FR-011, FR-012)
- [ ] T020 [US1] Verify the RLS propagation path in `relationships.tmdl`: `User_Access →(R3 Both)→ DimCountry →(R2 Single)→ BridgeCountry →(R1 Both)→ FactTitle`. Confirm R3 and R1 are bidirectional so the entitlement reaches the fact; confirm no circular path. (data-model RLS Propagation, FR-014)
- [ ] T021 [US1] Confirm `User_Access` columns are hidden from report use (set in T015) and deny-by-default holds (unmapped user → zero rows → zero titles). (FR-013, D7)

### Validation for User Story 1

- [ ] T022 [US1] Re-run `tmdl-validate` on `.SemanticModel\definition` after adding the role; fix any role syntax/reference errors.
- [ ] T023 [US1] Manual "View as role" check in Power BI Desktop: (a) mapped single-country user sees only that country's titles (SC-002); (b) unmapped user sees zero (SC-003); (c) author/no-role sees full count (SC-006, acceptance scenario 4).

**Checkpoint**: RLS is fully functional and independently verifiable via "View as role" before any visual exists — the security boundary (the workbook's defining feature) is the MVP.

---

## Phase 4: User Story 2 — Netflix Content Distribution Dashboard (Priority: P1)

**Goal**: Reproduce the core distribution/detail views on a single dark-themed Netflix dashboard page: filled map, Movies/TV donut, and the genre/description/duration/rating detail views.

**Independent Test**: Open the report page in Power BI Desktop → the map, donut, and detail tables render with correct bindings and the dark theme (black bg, red accents); the Movie/TV type encoding is preserved; all bindings use `[Total Titles]` so RLS still filters them.

### Report shell & theme (Plan Phase F setup)

- [ ] T024 [US2] Create `Output/NetflixRLS/NetflixRLS.Report/definition/report.json` — `$schema` (report 3.0.0), `themeCollection` referencing a dark Netflix theme (`#000000` background, white text, red accents `#aa0000`/`#ff0000`). (FR-019, SC-005)
- [ ] T025 [US2] Create `Output/NetflixRLS/NetflixRLS.Report/definition/pages/pages.json` (active page = `NetflixDashboard`) and `pages/NetflixDashboard/page.json` (`displayName "Netflix"`, `displayOption`, page size). Page name matches `^[\w-]+$`. (FR-020)

### Donut-supporting measure (Plan Phase C.2)

- [ ] T026 [US2] Add measure `% of Total Titles = DIVIDE([Total Titles], CALCULATE([Total Titles], REMOVEFILTERS(FactTitle[type])))` to `FactTitle.tmdl` using the VAR/RETURN form — folder `Core Metrics`, format `0.0%`; re-run `tmdl-validate`. (FR-009)

### Visuals (each its own `pages/NetflixDashboard/visuals/{name}/visual.json`; schema visualContainer 2.4.0 — NO `filters`/`filterConfig` at root; 25px edges, 20px gaps, no overlap, borders + titles + alt text)

- [ ] T027 [P] [US2] Filled map visual — Location = `DimCountry[Country]` (Data Category = Country), color saturation = `[Total Titles]`. (FR-015 country map, FR-016)
- [ ] T028 [P] [US2] Donut visual — Legend = `FactTitle[type]`, Value = `[Total Titles]`, detail label = `[% of Total Titles]`. (FR-015 distribution, acceptance scenario 3 type encoding)
- [ ] T029 [P] [US2] Genre table/list visual — `DimGenre[Genre]`, projection `active: true`. (FR-015 genre)
- [ ] T030 [P] [US2] Description table visual — `FactTitle[description]`, filtered to `type = "TV Show"` (use a visual-level filter authored in Desktop or a DAX-driven flag — NOT a forbidden root property). (FR-015 description)
- [ ] T031 [P] [US2] Duration table visual — `FactTitle[duration]`. (FR-015 duration)
- [ ] T032 [P] [US2] Rating card/list visual — `FactTitle[rating]`. (FR-015 rating)

### Validation for User Story 2

- [ ] T033 [US2] Validate report JSON syntax for all created `visual.json`/`page.json`/`report.json` (every file parses); verify no overlapping coordinates and all visuals carry title + alt text + border. (constitution §9)

**Checkpoint**: The dashboard shell, theme, map, donut, and detail views render correctly under the active role; US1 + US2 together form a usable secured MVP.

---

## Phase 5: User Story 3 — Titles Added Over Years Trend (Priority: P2)

**Goal**: An area/trend chart of distinct title count by `Year Added`, split by `type`, ordered chronologically.

**Independent Test**: The trend visual plots `[Total Titles]` by added-year, the year axis is sorted chronologically, the Movie/TV split shows, and it respects the active RLS filter.

### Implementation for User Story 3 (Plan Phase F)

- [ ] T034 [US3] Area/line trend visual — `pages/NetflixDashboard/visuals/titles-by-years/visual.json`: Axis = `FactTitle[Year Added]` (chronological sort), Value = `[Total Titles]`, Legend = `FactTitle[type]`. (FR-015 by-Years, FR-017, depends on `Year Added` from T010)

### Validation for User Story 3

- [ ] T035 [US3] Validate the trend `visual.json` parses; confirm year axis sorts chronologically and the type split renders under a test role. (SC-007 chronological)

**Checkpoint**: Catalog-growth trend works on top of US1/US2 without modifying them.

---

## Phase 6: User Story 4 — Top Genres and Ratings Breakdowns (Priority: P3)

**Goal**: Top 10 Genre horizontal bar (descending) and a ratings bar chart, both on the distinct-count measure and respecting RLS.

**Independent Test**: Top 10 Genre shows exactly ten genres in descending count order; the ratings bar breaks counts down by `rating`; both honor the active role.

### Implementation for User Story 4 (Plan Phase F)

- [ ] T036 [P] [US4] Top 10 Genre horizontal bar — `pages/NetflixDashboard/visuals/top-10-genre/visual.json`: Axis = `DimGenre[Genre]`, Value = `[Total Titles]`, Top-N = 10 descending (rely on visual Top-N / DAX rank logic, NOT a forbidden visual.json root property). (FR-015 Top 10, FR-018)
- [ ] T037 [P] [US4] Ratings bar chart — `pages/NetflixDashboard/visuals/ratings/visual.json`: Axis = `FactTitle[rating]`, Value = `[Total Titles]`. (FR-015 ratings)

### Validation for User Story 4

- [ ] T038 [US4] Validate both `visual.json` files parse; confirm Top 10 Genre shows exactly ten descending genres. (SC-007 top-10)

**Checkpoint**: All nine source worksheets are now represented (map, donut, area, ratings bar, Top 10 Genre, genre, description, duration, rating) on one page.

---

## Phase 7: Polish & Cross-Cutting Validation (Plan Phase G)

**Purpose**: End-to-end validation of the complete model + report before handoff.

- [ ] T039 Run full TMDL lint on the finished model: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"` — fix any remaining errors.
- [ ] T040 Run the cross-cutting PBIP validator on the project root: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"` — resolve all exit-code-2 errors (binding target exists, page name regex, no orphan pages, theme resolves) before handoff.
- [ ] T041 [P] Report JSON syntax sweep — every `*.json`/`*.pbir` under `Output\NetflixRLS\NetflixRLS.Report` parses (PowerShell `ConvertFrom-Json` loop from plan Phase G.3).
- [ ] T042 Final manual acceptance in Power BI Desktop: opens with zero structural/model/report errors (SC-001); "View as role" confirms entitled-only (SC-002) and deny-by-default (SC-003); author full count (SC-006); dark theme applied (SC-005); all nine visuals present with correct bindings (SC-004); chronological years + exactly 10 genres (SC-007).
- [ ] T043 [P] Record validation results (tmdl-validate, validate_pbip.py exit codes, JSON sweep, View-as-role outcomes) for traceability.

---

## Dependencies & Execution Order

```text
Phase 1 (Setup T001–T007)
        ↓ (T001 first; T002–T007 then, T003–T007 parallel)
Phase 2 (Foundational T008–T018)  ← BLOCKS all user stories
   T008,T009 → T010–T015 (parallel tables) → T016 (measure) → T017 (relationships) → T018 (validate)
        ↓
Phase 3 US1 RLS (T019–T023)   ← MVP; depends on User_Access + relationships
        ↓ (US2 may begin once Foundation done; US1 recommended first as MVP)
Phase 4 US2 Dashboard (T024–T033)   T024,T025 → T026 → T027–T032 (parallel visuals) → T033
        ↓
Phase 5 US3 Trend (T034–T035)   depends on Year Added (T010) + page shell (T025)
        ↓
Phase 6 US4 Genres/Ratings (T036–T038)   depends on DimGenre/BridgeGenre + page shell
        ↓
Phase 7 Polish/Validation (T039–T043)
```

**Hard dependencies**
- All visuals depend on `Total Titles` (T016) and the relationships (T017).
- T026 (`% of Total Titles`) blocks the donut T028.
- RLS (T019) depends on `User_Access` (T015) + R3/R1 in `relationships.tmdl` (T017).
- The filled map (T027) depends on `DimCountry` Data Category = Country (T013).
- The trend (T034) depends on `Year Added` (T010).
- Top 10 Genre (T036) depends on `DimGenre`/`BridgeGenre` (T012, T014).

**Story independence**: After Phase 2, US1 is fully testable alone (security boundary, no visuals needed). US2/US3/US4 each add visuals to the shared page without altering prior stories — each is an independently verifiable increment.

---

## Parallel Execution Examples

- **Setup**: T003, T004, T005, T006, T007 (distinct descriptor/platform files) run together after T001/T002.
- **Foundational tables**: T010, T011, T012, T013, T014, T015 (six independent per-table `.tmdl` files) run in parallel; converge at T016/T017.
- **US2 visuals**: T027, T028, T029, T030, T031, T032 (six independent `visual.json` files) run in parallel after the page shell (T025) and measures (T016, T026).
- **US4 visuals**: T036, T037 run in parallel.
- **Polish**: T041 and T043 run alongside T039/T040.

---

## Implementation Strategy

- **MVP = Phase 1 + Phase 2 + Phase 3 (US1)**: a secured semantic model whose RLS is provable via "View as role" — the workbook's defining feature — even before a single visual exists.
- **Incremental delivery**: add US2 (the visible dashboard, second P1) for a usable secured report; then US3 (P2 trend) and US4 (P3 breakdowns) layer on without touching earlier stories.
- **Validate continuously**: run `tmdl-validate` after T016/T017/T019/T026 and `validate_pbip.py` after each report milestone; never advance a phase with open exit-code-2 errors.

---

## Task Summary

- **Total tasks**: 43 (T001–T043)
- **By phase**: Setup 7 (T001–T007) · Foundational 11 (T008–T018) · US1 RLS 5 (T019–T023) · US2 Dashboard 10 (T024–T033) · US3 Trend 2 (T034–T035) · US4 Genres/Ratings 3 (T036–T038) · Polish/Validation 5 (T039–T043)
- **By user story**: US1 = 5 · US2 = 10 · US3 = 2 · US4 = 3 (20 story tasks); 23 setup/foundational/polish
- **Parallelizable [P]**: 21 tasks (scaffold files, 6 table tmdl, 6 US2 visuals, 2 US4 visuals, polish JSON/record)
- **Validation tasks**: 8 (T018, T022, T023, T033, T035, T038, T039–T043) covering `tmdl-validate`, `validate_pbip.py`, JSON syntax, and "View as role" RLS checks
- **Suggested MVP scope**: User Story 1 (Dynamic RLS) on top of Setup + Foundational
- **Coverage**: Plan Phases A (T001–T009), B (T010–T015), C (T016, T026), D (T017), E (T019–T021), F (T024–T037), G (T018, T022, T033, T035, T038, T039–T043) — all mapped.
