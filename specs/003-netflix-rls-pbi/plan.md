# Implementation Plan: Netflix RLS — Tableau → Power BI Migration

**Branch**: `003-netflix-rls-pbi` | **Date**: 2026-06-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-netflix-rls-pbi/spec.md`

## Summary

Build a complete Power BI **PBIP** project that reproduces the *Netflix RLS* Tableau workbook with **dynamic row-level security** as its defining feature. The work has two layers:

1. **Semantic model** (TMDL): an Import-mode wide main table `netflix_titles` (all 12 source columns preserved + 1 derived `Year` Date column), the `User_Access` entitlement table (Username, Country), an M-generated `DimDate` (year time-axis), and a **disconnected `Year` date parameter table** (default 2024-03-26). It carries **6 explicit DAX measures**, **two single-direction relationships**, and a **dynamic RLS role** (`Dynamic Country Access`) filtering `User_Access[Username] = USERPRINCIPALNAME()`.
2. **Report** (PBIR enhanced folder format): the nine Tableau worksheets reproduced as Power BI visuals plus one consolidated **Netflix** dashboard page, with chart types fixed by the clarified spec (filled map / line / clustered bar / table / card).

Per **constitution §0 (Single-Table Rule)** the catalog table is kept wide (no genre/country/rating dimension extraction); the only extra relational tables are the security `User_Access` table, the generated `DimDate`, and the disconnected `Year` parameter. The RLS role is generated because the analysis reports **RLS Detected: Yes** (constitution §4a). All artifacts are emitted to `Output/NetflixRLS/` and MUST pass `tmdl-validate` + `validate_pbip.py` with zero errors before delivery (SC-001…SC-006).

## Technical Context

**Language/Version**: TMDL (compatibility level 1567+) for the model; PBIR JSON (`visualContainer/2.4.0`, report schema `3.0.0`) for the report; Power Query M for data load.
**Primary Dependencies**: Power BI Desktop (PBIP project format); Power Query M engine (Import mode); VertiPaq; `USERPRINCIPALNAME()` for dynamic RLS.
**Storage**: 2 local CSV files in `Data/Netflix RLS/` — `netflix_titles.csv` (12 columns, one row per title) and `User_Access.csv` (Username, Country). Loaded **Import** mode, each query independent.
**Testing**: Structural validators — `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` (TMDL lint) and `plugins/pbip/skills/pbip/scripts/validate_pbip.py` (cross-cutting PBIP/PBIR). Functional RLS spot-check (the three sample users must each see only their country).
**Target Platform**: Power BI Desktop (Windows) opening the generated `.pbip`; RLS roles validated via "View as role" in Desktop / enforced in the Service.
**Project Type**: Power BI semantic model + report (PBIP). Not a code project — no `src/tests` trees.
**Performance Goals**: RLS restriction applies to every visual on every page (SC-001); small dataset, so text natural keys on the country relationship are acceptable (constitution §6).
**Constraints**: Import mode; **single-direction** relationships (including the RLS relationship — see §4a note below); RLS filter is a pure row-level boolean predicate (NO measure references); PBIR visual.json root limited to `$schema`/`name`/`position`/`visual` (no `filters`/`filterConfig`); `report.json` minimal template (no forbidden properties).
**Scale/Scope**: 4 model tables (`netflix_titles`, `User_Access`, `DimDate`, `Year`) + 2 active relationships + 1 disconnected parameter; 6 measures + 1 derived Date column; 1 RLS role; 9 worksheet visuals consolidated onto 1 Netflix page.

### Decisions resolved (no NEEDS CLARIFICATION remaining)

| Topic | Decision | Source |
|-------|----------|--------|
| Catalog model shape | **Wide single table** `netflix_titles` (no genre/country/rating extraction) — small size + RLS must land directly on `netflix_titles[country]` | constitution §0; star-schema-output; spec FR-001 |
| Storage mode | Import; each CSV via `Csv.Document(File.Contents(...))`, `QuoteStyle.Csv`, `Encoding=65001`, headers promoted, types cast immediately; queries independent (no cross-query refs) | constitution §5/§6; spec Assumptions |
| `Year` Date column | Parse `date_added` `"MMMM d, yyyy"` string → `type date` in **Power Query** (preferred) named `Year`; DAX SWITCH-parser fallback documented | dax-measures-output (Year column); spec FR-005 |
| `Year` parameter | **Disconnected** date table `Year` from `CALENDAR(DATE(2000,1,1),DATE(2030,12,31))`, default 2024-03-26, **no relationship**; `Year Value = SELECTEDVALUE('Year'[Year], DATE(2024,3,26))` | dax-measures-output; spec FR-006; Clarifications |
| DimDate | M-generated `ADDCOLUMNS(CALENDAR(...))` with Year/Quarter/Month/MonthNumber/Day; relates 1—* to `netflix_titles[Year]`, single direction | star-schema-output; spec FR-005 |
| Distinct title metric | `Total Titles = DISTINCTCOUNT(netflix_titles[show_id])` (matches Tableau `CountD(show_id)`); primary metric on every visual | dax-measures-output; spec FR-004 |
| Type split | `Total Movies` / `Total TV Shows` via `CALCULATE([Total Titles], KEEPFILTERS(netflix_titles[type]=…))` using VAR literals (no measure in CALCULATE filter); `% Movies` / `% TV Shows` via `DIVIDE` | dax-measures-output; spec FR-013 |
| Top 10 Genre | Visual-level Top N filter on `listed_in` by `[Total Titles]` (preferred); `Genre Rank` RANKX DENSE measure as fallback | dax-measures-output; spec FR-013 |
| RLS type | **Dynamic** role `Dynamic Country Access`: `tablePermission 'User_Access' = User_Access[Username] = USERPRINCIPALNAME()`; generalizes hardcoded `user2@maq.com` | constitution §4a; star/dax outputs; spec FR-007…FR-012 |
| RLS relationship | `User_Access[Country]` 1—* `netflix_titles[country]`, **single-direction** (User_Access → netflix_titles); case-insensitive text-key match reproduces Tableau `LOWER()`; multi-country titles matched on full exact string only | star-schema-output; spec FR-003/FR-009; Clarifications |
| `User_Access[Country]` uniqueness | NOT deduplicated (dedup would drop usernames); the role filter on `User_Access` is the restricting mechanism, relationship is single-direction — see Limitations | star-schema-output Limitations §4 |
| `Action (Country)` group | Hidden auto-generated dashboard-action artifact → **NOT** migrated | analysis-output; spec Assumptions |
| `ATTR()` in RLS calc | Tableau LOD construct → no Power BI equivalent needed; restriction achieved via relationship + role filter | analysis-output; spec Assumptions |
| Visual types | filled map (Country, fallback bar), line (Years), clustered bar (Genre/Top 10/Rating/Ratings/Type), donut option (Movie/TV split), table (Duration), table/card (Description) | spec FR-013; Clarifications |
| Pages | 9 worksheets → visuals on **one** consolidated `Netflix` page; page name sanitized to `^[\w-]+$` | spec FR-014; analysis Dashboards |
| Sets / bins / blending | **None** — analysis reports none; no bridge tables | analysis-output; spec |

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md`. Re-checked after design — all gates pass.*

| Constitution Principle | Status | Notes |
|------------------------|--------|-------|
| §0 Single-table rule | ✅ Pass | Catalog `netflix_titles` kept wide — no genre/country/rating extraction. The only extra tables are the **security** `User_Access` (required for RLS), generated `DimDate`, and disconnected `Year` parameter. |
| §1 Star schema (multi-table) | ✅ Pass | Source is a single federated datasource with two physical CSVs joined on country. `User_Access` is modeled as the entitlement/security dimension (not a fact decomposition); no surrogate keys, no snowflaking. |
| §2 Naming | ✅ Pass | Source-faithful table names `netflix_titles` / `User_Access`; `DimDate` keeps `Dim` prefix; parameter table `Year`. Measures Title Case (`Total Titles`, `% Movies`) with display folders (`Catalog Metrics`, `Catalog Metrics \| Ratios`, `Helper \| Ranking`). Column names preserved from source. |
| §3 DAX standards | ✅ Pass | Measures-first (only 1 derived `Year` Date column, required for the date relationship/axis); `DISTINCTCOUNT` for the count; `DIVIDE()` for both ratios; VAR/literal comparison inside `CALCULATE` filters (no measure references); RANKX DENSE for the Top-N fallback; format strings + display folders on all 6. |
| §4 Relationships | ✅ Pass | Two relationships, both **many-to-one single-direction**: `User_Access[Country]`→`netflix_titles[country]` and `DimDate[Date]`→`netflix_titles[Year]`. The `Year` parameter is disconnected. No bidirectional, no circular dependencies. |
| §4a RLS | ✅ Pass | Detected **Yes** → `roles/` folder created. Dynamic role `Dynamic Country Access`: `modelPermission: read`; table filter `User_Access[Username] = USERPRINCIPALNAME()` (row-level boolean, no measure ref). **Deviation from §4a default**: the RLS relationship is kept **single-direction** (not bidirectional). Justified below — the entitlement is the *one* side already filtering the *many* catalog side, so single-direction correctly propagates the restriction; bidirectional would let the catalog filter the entitlement and break the guarantee (star-schema Relationships rule 1). Logged in Complexity Tracking. |
| §5 M query connectivity | ✅ Pass | Each CSV via `Csv.Document(File.Contents(...))`, `QuoteStyle.Csv`, `Encoding=65001`; queries independent (no cross-query refs, no `Table.NestedJoin`); `Text.Trim` on `country`/`Country` key columns to avoid whitespace mismatch; absolute file paths; `DimDate` generated in M. |
| §6 Performance | ✅ Pass | Import; `Year` date conversion pushed to Power Query (preferred over DAX); minimal calculated columns; text natural keys acceptable (small model); single-direction filtering. |
| §7 Parameter migration | ✅ Pass | Tableau date parameter → **disconnected date table** + `SELECTEDVALUE` (the What-If wizard only emits numeric ranges, so the date table is created manually), default 2024-03-26 preserved. |
| §8 PBIP output structure | ✅ Pass | TMDL `definition/` (database/model/relationships/tables + `roles/`); PBIR `definition/report.json` minimal template (no forbidden props), `pages/` enhanced folder. |
| §9 Report visual layer | ✅ Pass | Titles/borders/alt-text/background per visual; 25px edge / 20px gap layout; professional theme; all table/matrix projections `active: true`. Each visual replicates the Tableau mark type per the clarified defaults. |
| §10 Validation | ✅ Pass | Every in-scope Tableau calc field mapped (`RLS`→role, `Year`→Date column); both parameters covered; validators run at each stage; 9/9 worksheets represented (SC-004). |

**Gate result: PASS** — one documented, justified deviation (single-direction RLS relationship) recorded in Complexity Tracking; no unjustified violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-netflix-rls-pbi/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── checklists/
│   └── requirements.md  # Requirements checklist (speckit.specify output)
└── tasks.md             # Phase 2 output (speckit.tasks — NOT created here)
```

> Phase-0 research and Phase-1 data-model artifacts already exist as pipeline memory and are the authoritative design inputs for this plan (no duplicate research.md/data-model.md generated):
> - `.specify/memory/NetflixRLS/tableau-analysis-output.md` (research / source facts — 1 date parameter, 12+2 columns, 2 calc fields, 9 worksheets, 1 dashboard, RLS Detected: Yes)
> - `.specify/memory/NetflixRLS/star-schema-output.md` (data model — wide catalog + User_Access + DimDate + disconnected Year; 2 relationships; RLS propagation)
> - `.specify/memory/NetflixRLS/dax-measures-output.md` (measure contracts — 6 measures + Year Date column + Year parameter + RLS role)

### Generated PBIP output (repository — build target)

```text
Output/NetflixRLS/
├── NetflixRLS.pbip                               # Project entry (opens in PBI Desktop)
├── NetflixRLS.SemanticModel/
│   ├── definition.pbism
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl                         # compatibilityLevel + model id
│       ├── model.tmdl                            # culture, ref table entries, annotations
│       ├── relationships.tmdl                    # 2 active single-direction relationships
│       ├── roles/
│       │   └── Dynamic Country Access.tmdl       # dynamic RLS role (Username = USERPRINCIPALNAME())
│       └── tables/
│           ├── netflix_titles.tmdl               # wide catalog: 12 source cols + Year + 6 measures
│           ├── User_Access.tmdl                  # entitlement: Username, Country (security)
│           ├── DimDate.tmdl                      # generated calendar, marked as date table
│           └── Year.tmdl                         # disconnected date parameter (default 2024-03-26)
└── NetflixRLS.Report/
    ├── definition.pbir                           # datasetReference byPath → ../.SemanticModel
    ├── .platform
    └── definition/
        ├── version.json
        ├── report.json                           # minimal: $schema + themeCollection + settings
        └── pages/
            ├── pages.json                        # page order + active page
            └── Netflix/
                ├── page.json                      # name ^[\w-]+$, displayName "Netflix"
                └── visuals/{visual}/visual.json   # 9 worksheet visuals (map/line/bar/table/card)
```

**Structure Decision**: PBIP project (semantic model + report) emitted to `Output/NetflixRLS/`. The model uses the **TMDL `definition/` folder** form with a `roles/` subfolder for the dynamic RLS role; the report uses the **PBIR enhanced `definition/pages/` folder** form. This matches constitution §8 and the `pbir-format` skill, and is what `validate_pbip.py` expects.

## Technical Approach

### 1. Data layer (Power Query M, Import mode)

- **CSV query `netflix_titles`**:
  ```m
  Source = Csv.Document(
      File.Contents("C:\Users\AmanRajMAQSoftware\Downloads\New folder\speckit_solution\Data\Netflix RLS\netflix_titles.csv"),
      [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
  )
  ```
  Headers promoted (`Table.PromoteHeaders(Source, [PromoteAllScalars = true])`); types cast immediately — `show_id`, `release_year` → `Int64.Type`; all other source columns → `type text`. Apply **`Text.Trim` to `country`** (the RLS key column) to prevent whitespace mismatch with the entitlement key.
- **`Year` Date column (preferred — Power Query)**: transform `date_added` (`"MMMM d, yyyy"`) to a Date column named `Year`:
  ```m
  = Table.TransformColumns(
      #"Trimmed",
      {{"date_added", each Date.From(DateTime.FromText(Text.Trim(_), [Format="MMMM d, yyyy", Culture="en-US"])), type date}}
  )
  ```
  Blank/unparseable strings yield `null` → those rows are excluded from year grouping but still counted elsewhere (spec edge case). The DAX SWITCH-parser in dax-measures-output is the documented fallback if the column must remain in the model as DAX.
- **CSV query `User_Access`** (independent query — constitution §5 rule 1):
  ```m
  Source = Csv.Document(
      File.Contents("C:\Users\AmanRajMAQSoftware\Downloads\New folder\speckit_solution\Data\Netflix RLS\User_Access.csv"),
      [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
  )
  ```
  Headers promoted; `Username`, `Country` → `type text`; apply **`Text.Trim` to `Country`** (the RLS join key). NOT deduplicated — multiple usernames may map to the same country.
- **`DimDate`** generated in M (no CSV): `ADDCOLUMNS(CALENDAR(DATE(2008,1,1), DATE(2025,12,31)), "Year", YEAR([Date]), "Quarter", "Q"&FORMAT([Date],"Q"), "Month", FORMAT([Date],"MMMM"), "MonthNumber", MONTH([Date]), "Day", DAY([Date]))`; marked as date table on `Date`. Generated independently (no cross-query join).
- **`Year` parameter table** generated via `CALENDAR(DATE(2000,1,1), DATE(2030,12,31))` exposing a single `Year` Date column. **No relationship** to any table.

### 2. Model layer (TMDL)

- **Tables**:
  - `netflix_titles` (wide catalog, secured) — all 12 source columns + the derived `Year` Date column + the 6 measures. `show_id` is the distinct-count grain; `country` is the RLS FK (many side); `Year` is the date FK (many side).
  - `User_Access` (security/entitlement) — `Username` (UPN), `Country` (entitled country, the one side of the RLS relationship). The RLS-filtered table.
  - `DimDate` — generated calendar with a `Calendar` hierarchy (`Year > Quarter > Month > Date`), marked as date table.
  - `Year` — disconnected date parameter table (no relationship).
- **Derived column** (1, on `netflix_titles`): `Year` (Date), produced in Power Query (above). `formatString` `"General Date"` (or `m/d/yyyy`). Optionally add `Year Number = YEAR(netflix_titles[Year])` for a year-only axis.
- **Measures** (6, on `netflix_titles`) — DAX copied verbatim from dax-measures-output.md, each with format string + display folder:

  | Measure | Display Folder | Format | DAX (summary) |
  |---|---|---|---|
  | Total Titles | Catalog Metrics | `#,##0` | `DISTINCTCOUNT(netflix_titles[show_id])` |
  | Total Movies | Catalog Metrics | `#,##0` | `VAR _movie="Movie" RETURN CALCULATE([Total Titles], KEEPFILTERS(netflix_titles[type]=_movie))` |
  | Total TV Shows | Catalog Metrics | `#,##0` | `VAR _tv="TV Show" RETURN CALCULATE([Total Titles], KEEPFILTERS(netflix_titles[type]=_tv))` |
  | % Movies | Catalog Metrics \| Ratios | `0.0%` | `DIVIDE([Total Movies], [Total Titles])` |
  | % TV Shows | Catalog Metrics \| Ratios | `0.0%` | `DIVIDE([Total TV Shows], [Total Titles])` |
  | Genre Rank | Helper \| Ranking | `#,##0` | `RANKX(ALL(netflix_titles[listed_in]), [Total Titles], , DESC, DENSE)` |

  > The nine "count by dimension" worksheets are `[Total Titles]` sliced on a visual axis — no extra measures required (dax-measures-output). `Genre Rank` is only used if a visual-level Top N filter is not applied for "Top 10 Genre".

- **`Year` parameter measure**: `Year Value = SELECTEDVALUE('Year'[Year], DATE(2024,3,26))`, format `"General Date"`.
- **Relationships** (`relationships.tmdl`), both active, single cross-filter direction:

  | # | From (one) | To (many) | Keys | Cardinality | Cross-filter | Active |
  |---|---|---|---|---|---|---|
  | 1 | `User_Access[Country]` | `netflix_titles[country]` | Country ↔ country (text) | One-to-many | **Single** (User_Access → netflix_titles) | Yes |
  | 2 | `DimDate[Date]` | `netflix_titles[Year]` | Date ↔ Year (date) | One-to-many | **Single** (DimDate → netflix_titles) | Yes |

  The `Year` parameter table participates in **no** relationship. Relationship 1 is the RLS propagation path and MUST stay single-direction (see §4a / Complexity Tracking).

- **RLS role** (`roles/Dynamic Country Access.tmdl`):
  ```tmdl
  role 'Dynamic Country Access'
      modelPermission: read

      tablePermission User_Access = User_Access[Username] = USERPRINCIPALNAME()
  ```
  The filter restricts `User_Access` to the current viewer's rows; the surviving `Country` value(s) flow through relationship 1 to restrict `netflix_titles`. A viewer with no row → empty `User_Access` → zero titles (FR-011 / SC-003). No measure reference appears in the filter (pure row-level boolean — constitution §4a).

### 3. Report layer (PBIR)

- **One page** `Netflix` (name `^[\w-]+$`, `displayName` "Netflix") consolidating all nine worksheet visuals, mirroring the single Tableau "Netflix" dashboard (FR-014).
- **Visual composition** (Tableau worksheet → Power BI visual; FR-013), every visual using `[Total Titles]` as the value and the listed field as axis/category:

  | Worksheet | Power BI visual | Axis / Category | Notes |
  |---|---|---|---|
  | Country wise distribution | **Filled map** (fallback clustered bar) | `netflix_titles[country]` | Map data category Country; bar fallback if map unavailable |
  | Total Movies and TV Shows by Years | **Line chart** | `netflix_titles[Year]` (or `DimDate[Year]`) + `type` legend | Continuous year axis |
  | Genre | **Clustered bar** | `netflix_titles[listed_in]` | |
  | Top 10 Genre | **Clustered bar** | `netflix_titles[listed_in]` | Visual-level Top N filter (10) by `[Total Titles]` |
  | Rating | **Clustered bar** | `netflix_titles[rating]` | |
  | Ratings | **Clustered bar** | `netflix_titles[rating]` | |
  | Movies and TV Shows distribution | **Clustered bar** (donut option) | `netflix_titles[type]` | Two-category Movie/TV split |
  | Duration | **Table** | `netflix_titles[duration]` (+ `[Total Titles]`) | All projections `active: true` |
  | Description | **Table** (or card) | `netflix_titles[description]` (+ `[Total Titles]`) | All projections `active: true` |

- **RLS-aware counts**: every visual uses `[Total Titles]` (distinct `show_id`), so all counts automatically reflect the active country restriction (FR-015 / SC-005). No per-visual filter is needed for RLS — it flows from the role + relationship 1.
- **Formatting & fidelity**: every visual has a descriptive title (from the Tableau worksheet name), 1px `#E0E0E0` border, alt text, and a light-gray background; 25px edge / 20px gap layout; professional theme (constitution §9).
- **PBIR safety**: visual.json root limited to `$schema`, `name`, `position`, `visual` — **no** `filters`/`filterConfig` at root (Top N for genre is enforced via the visual-level filter UI / `Genre Rank` measure, not a root property); `visualContainerObjects.title` only `show`/`text`; colors via `{"solid":{"color":{"expr":{"Literal":{"Value":"'#RRGGBB'"}}}}}`. `report.json` uses the minimal template (no `modelExtensions`/`publicCustomVisuals`/`sections`/`baseTheme`).
- **Excluded**: `Action (Country)` group (hidden dashboard-action artifact); no sets/bins; the nine worksheets are visuals on the single Netflix page (not nine pages).

### 4. Validation (run before delivery — MANDATORY)

1. TMDL lint: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"`
2. Cross-cutting: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"`
3. Report JSON parse check over `*.json`/`*.pbir` in `.Report/` (each must `ConvertFrom-Json` without error).

Errors (exit code 2 / lint failures) are fixed before the artifact is presented; findings logged in pipeline state. Checks specific to this model: the RLS role parses, has `modelPermission: read`, and its filter references only `User_Access[Username]` / `USERPRINCIPALNAME()` (no measure); both relationships are many-to-one/single-direction/active and the RLS relationship is **not** bidirectional; `Year` parameter table has **zero** relationships; `DimDate[Date]` contiguous/unique and marked as date table; the single `Netflix` page has a sanitized name; all table/matrix projections `active: true`. Functional RLS reasoning: `shashank@maq.com`→India, `user2@maq.com`→United States, `user3@maq.com`→United Kingdom, unknown user → zero rows (SC-002/SC-003).

### Plugin skills to read before generation

| Task | Skill to load |
|------|---------------|
| Writing/editing `.tmdl` files (tables, relationships, RLS role) | `plugins/pbip/skills/tmdl/SKILL.md` |
| Writing/editing PBIR JSON (visual.json, page.json, report.json) | `plugins/pbip/skills/pbir-format/SKILL.md` |

## Complexity Tracking

> One justified deviation from constitution §4a's "set bothDirections on the RLS relationship" default. All other choices align with the constitution.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| RLS relationship `User_Access[Country] → netflix_titles[country]` kept **single-direction** instead of §4a's bidirectional default | `User_Access` is the **one** side and already filters the **many** catalog side; single-direction correctly propagates the entitlement restriction to `netflix_titles` and matches the spec/star-schema design (Clarifications, FR-003/FR-009) | Bidirectional would let `netflix_titles` filter back into `User_Access`, breaking the security guarantee and introducing ambiguous/circular filtering. §4a's bidirectional guidance applies when the mapping table is on the *many* side and must reach the fact — not this topology, where the entitlement is already the one side. |

## Phase Outputs

- **Phase 0 (research)**: satisfied by `tableau-analysis-output.md` — all unknowns resolved (source type CSV/UTF-8 federated 2-table, 1 date parameter, 2 calc fields, 9 worksheets → 1 dashboard, **RLS Detected: Yes** dynamic mapping, no sets/bins/blending).
- **Phase 1 (design & contracts)**: satisfied by `star-schema-output.md` (model: wide `netflix_titles` + `User_Access` + `DimDate` + disconnected `Year`, 2 single-direction relationships, dynamic RLS role) + `dax-measures-output.md` (measure contracts — 6 measures, `Year` Date column, `Year` parameter, RLS role filter). Agent context marker updated in `.github/copilot-instructions.md` to point at this plan.
- **Phase 2 (tasks)**: produced by `speckit.tasks` (next stage) → `tasks.md`.
- **Build**: `pbip-generator` (model + RLS role) + `report-visual-migration` (report) consume this plan to emit `Output/NetflixRLS/`.
