# Implementation Plan: Netflix RLS Dashboard Migration (Tableau → Power BI)

**Branch**: `001-netflixrls-pbi` | **Date**: 2026-06-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-netflixrls-pbi/spec.md`

## Summary

Migrate the Tableau "Netflix RLS" workbook into a Power BI Project (PBIP) containing a semantic model (TMDL) and a report (PBIR). The defining capability is **dynamic row-level security**: each signed-in user sees only the Netflix titles for the country/countries they are entitled to, driven by `USERPRINCIPALNAME()` matched against the `User_Access` mapping table — replacing the Tableau hardcoded `"user2@maq.com"` predicate.

The technical approach is a **star-schema decomposition** (two source CSVs + two multi-valued fields require bridges): `FactTitle` (grain = one `show_id`), `DimCountry`, `DimGenre`, `User_Access` (security-only dimension), plus `BridgeCountry` and `BridgeGenre`. Two measures (`Total Titles`, `% of Total Titles`) drive nine visuals reproduced on a single dark Netflix-themed dashboard page. Power Query parses the text `date_added` to a Date and splits the multi-valued `country`/`listed_in` fields into bridges. RLS propagates `User_Access → DimCountry → BridgeCountry → FactTitle` via two sanctioned bidirectional relationships. Output is validated with `tmdl-validate` and `validate_pbip.py` from `plugins/pbip/`.

## Technical Context

**Language/Version**: TMDL (Tabular Model Definition Language) for the semantic model; PBIR JSON (report schema 3.0.0 / visualContainer 2.4.0) for the report; Power Query M for data load/transform; DAX for measures, the calculated column, and the RLS predicate.
**Primary Dependencies**: Power BI Desktop (PBIP author/open target); `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` (TMDL structural linter); `plugins/pbip/skills/pbip/scripts/validate_pbip.py` (cross-cutting PBIP validator, Python 3).
**Storage**: Two local CSV source files loaded in Import mode via Power Query — `netflix_titles.csv` (title catalog) and `User_Access.csv` (user→country entitlement). Absolute paths under `Data/Netflix RLS/`.
**Testing**: `tmdl-validate-windows-x64.exe` on `.SemanticModel/definition`; `validate_pbip.py` on the project root and on `.SemanticModel/` / `.Report/`; manual "View as role" verification of RLS in Power BI Desktop (acceptance scenarios in spec US1).
**Target Platform**: Power BI Desktop (PBIP format) → Power BI Service for RLS enforcement with authenticated UPN identity.
**Project Type**: Power BI Project (PBIP) migration — semantic model (`.SemanticModel/` TMDL) + report (`.Report/` PBIR). Not a traditional code project.
**Performance Goals**: Import mode; `DISTINCTCOUNT(show_id)` aggregation; small dataset (single Netflix catalog CSV, <1M rows) → text natural keys acceptable; single-direction filtering everywhere except the three justified bidirectional relationships (R1/R3/R4).
**Constraints**: TMDL syntax rules (`plugins/pbip/skills/tmdl/SKILL.md`); PBIR schema rules (`plugins/pbip/skills/pbir-format/SKILL.md`) — no extra top-level visual.json properties, no `filters`/`filterConfig` at visual root; constitution naming, DAX, relationship, and RLS standards; deny-by-default RLS; dark theme (#000000 bg, white text, red accents #aa0000/#ff0000).
**Scale/Scope**: 6 model tables, 5 relationships, 1 RLS role, 2 measures, 1 calculated column (M-derived), 9 visuals on 1 report page.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Constitution Principle | Status | How this plan complies |
|---|---|---|
| §0 Single-Table Rule | ✅ PASS | Source has **two** tables (`netflix_titles` + `User_Access`) and **two** multi-valued fields → §0 does NOT apply; decomposition is mandated by §1. |
| §1 Star Schema (multi-table) | ✅ PASS | `FactTitle` (grain = 1 `show_id`); conformed `DimCountry`/`DimGenre`; `BridgeCountry`/`BridgeGenre` for multi-valued `country`/`listed_in`; no snowflaking; natural text keys (single-source, small model). |
| §2 Naming Conventions | ✅ PASS | `Fact`/`Dim`/`Bridge` PascalCase singular; measures Title Case (`Total Titles`, `% of Total Titles`); display folder `Core Metrics`; source column names preserved. |
| §3 DAX Standards | ✅ PASS | Explicit measures (no implicit); `DISTINCTCOUNT`; `DIVIDE` over `/`; `CALCULATE + REMOVEFILTERS([type])` for percent-of-total; `VAR/RETURN`; format strings (`#,##0`, `0.0%`); display folder. |
| §4 Relationships | ✅ PASS | All many-to-one; single-direction by default. Bidirectional ONLY on R1/R4 (bridge many-to-many) and R3 (RLS — sole sanctioned exception). No circular paths. |
| §4a Row-Level Security | ✅ PASS | RLS `Detected: Yes` → role `Dynamic Country Access`, `modelPermission: read`, `tablePermission User_Access = [Username] = USERPRINCIPALNAME()` (boolean, no measure refs); bidirectional only on the security relationship R3; entitlement reaches fact via R3→R2→R1. |
| §5 M Query Rules | ✅ PASS | `Csv.Document(File.Contents(...))` + `QuoteStyle.Csv`; each table loads independently (no cross-query refs, no `Table.NestedJoin`); `Text.Trim` on split key columns; null-safe `date_added` parse; types cast after header promotion; absolute paths. |
| §6 Performance | ✅ PASS | Import mode; transformations pushed to M (date parse, splits); text natural keys (model <1M rows); single-direction filtering except justified exceptions. |
| §7 Parameter Migration | ✅ PASS | Tableau `Year` parameter has no detected binding (spec FR-022 / Assumptions) → not migrated (documented), no orphan What-If table. |
| §8 PBIP Output Structure | ✅ PASS | Standard `.pbip` + `.Report/` + `.SemanticModel/` TMDL layout; `report.json` uses minimal PBIR schema (no forbidden properties); `roles/` folder created (RLS detected). |
| §9 Report Visual Layer | ✅ PASS | 25px edge padding, 20px gaps, no overlap (coordinate math verified), borders + titles + alt text on every visual, all table projections `active: true`. Dark Netflix theme overrides the default professional theme (spec FR-019 — domain-justified). |
| §10 Validation Checklist | ✅ PASS | TMDL parses; QuoteStyle.Csv; Text.Trim; no implicit measures; bidirectional only where justified; visuals validated; every dashboard → a page. |

**Result**: No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-netflixrls-pbi/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions & rationale
├── data-model.md        # Phase 1 output — tables, columns, relationships, RLS, measures
├── quickstart.md        # Phase 1 output — build & validate walkthrough
├── spec.md              # Feature specification (input)
└── checklists/
    └── requirements.md  # (existing)
```

### Source Code (repository root) — PBIP Output

```text
Output/NetflixRLS/
├── NetflixRLS.pbip
├── NetflixRLS.SemanticModel/
│   ├── definition.pbism
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl
│       ├── model.tmdl
│       ├── relationships.tmdl
│       ├── tables/
│       │   ├── FactTitle.tmdl
│       │   ├── DimCountry.tmdl
│       │   ├── DimGenre.tmdl
│       │   ├── User_Access.tmdl
│       │   ├── BridgeCountry.tmdl
│       │   └── BridgeGenre.tmdl
│       └── roles/
│           └── Dynamic Country Access.tmdl
└── NetflixRLS.Report/
    ├── definition.pbir
    └── definition/
        ├── report.json
        ├── version.json
        └── pages/
            ├── pages.json
            └── NetflixDashboard/
                ├── page.json
                └── visuals/
                    └── {visual_name}/visual.json   # 9 visuals
```

**Structure Decision**: PBIP migration layout per constitution §8. The semantic model lives in `Output/NetflixRLS/NetflixRLS.SemanticModel/` (TMDL) and the report in `Output/NetflixRLS/NetflixRLS.Report/` (PBIR enhanced folder format). A `roles/` folder is included because RLS is detected. Source CSVs remain in `Data/Netflix RLS/` and are referenced by absolute path in each table's M partition.

## Phases

### Phase A — Model Skeleton & Connectivity

1. Generate PBIP scaffold: `NetflixRLS.pbip`, `.SemanticModel/definition.pbism`, `diagramLayout.json`, `.Report/definition.pbir`, `version.json`, `.platform` files.
2. Author `database.tmdl` (compatibility level) and `model.tmdl` (model properties, default culture `en-US`, `discourageImplicitMeasures` on).
3. Define M partitions per table (Phase B detail) — each reads its CSV independently via `Csv.Document(File.Contents("...Data\Netflix RLS\...csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])`.

### Phase B — Power Query (M) Transforms

1. **FactTitle**: load `netflix_titles.csv`; promote headers; cast types; parse `date_added` (text "MMMM d, yyyy", en-US) → `Date Added` (nullable date, `try…otherwise null`); derive `Year Added = Date.Year([Date Added])` (Int64, null-safe); retain original `country` string for display.
2. **BridgeCountry**: load `netflix_titles.csv`; keep `show_id` + `country`; `Text.Split` country by `,`; `Text.Trim`; expand to one row per (`show_id`, `Country`); drop blanks.
3. **BridgeGenre**: load `netflix_titles.csv`; keep `show_id` + `listed_in`; split by `,`; `Text.Trim`; one row per (`show_id`, `Genre`).
4. **DimCountry**: union of split `netflix_titles.country` values AND `User_Access.Country` (read both files directly in one query, `Text.Trim`, `Distinct`) → guarantees every entitlement key exists.
5. **DimGenre**: distinct trimmed `listed_in` split values from `netflix_titles.csv`.
6. **User_Access**: load `User_Access.csv`; columns `Username`, `Country`; `Text.Trim`.

*Constitution §5 enforced: no query references another query; no `Table.NestedJoin`; `QuoteStyle.Csv`; types after headers; null-safe parse.*

### Phase C — Measures & Calculated Columns

1. `Total Titles = DISTINCTCOUNT(FactTitle[show_id])` — folder `Core Metrics`, format `#,##0`.
2. `% of Total Titles = DIVIDE([Total Titles], CALCULATE([Total Titles], REMOVEFILTERS(FactTitle[type])))` — folder `Core Metrics`, format `0.0%`.
3. `Year Added` produced in M (Phase B). DAX fallback column `YEAR(FactTitle[Date Added])` only if the M parse is skipped.

### Phase D — Relationships

Author `relationships.tmdl` with 5 relationships (see [data-model.md](data-model.md)):

| # | From (one) | To (many) | Key | Cross-filter |
|---|---|---|---|---|
| R1 | FactTitle[show_id] | BridgeCountry[show_id] | show_id | **Both** (bridge) |
| R2 | DimCountry[Country] | BridgeCountry[Country] | Country | Single |
| R3 | DimCountry[Country] | User_Access[Country] | Country | **Both** (RLS) |
| R4 | FactTitle[show_id] | BridgeGenre[show_id] | show_id | **Both** (bridge) |
| R5 | DimGenre[Genre] | BridgeGenre[Genre] | Genre | Single |

### Phase E — Row-Level Security

1. Create `roles/Dynamic Country Access.tmdl`: `modelPermission: read`; `tablePermission User_Access = User_Access[Username] = USERPRINCIPALNAME()`.
2. Confirm propagation path `User_Access →(R3)→ DimCountry →(R2)→ BridgeCountry →(R1)→ FactTitle`; bidirectional set on R3 (RLS) and R1 (bridge) so the filter reaches the fact.
3. Mark `User_Access` columns hidden from report use (security-only); deny-by-default verified (unmapped user → zero rows).

### Phase F — Report Visuals (9 on a single page)

Single page `NetflixDashboard` (`displayName "Netflix"`), dark theme via report theme JSON in `themeCollection`. Visuals (constitution §9 layout: 25px edges, 20px gaps, borders/titles/alt text):

| Visual (Tableau worksheet) | Power BI type | Bindings |
|---|---|---|
| Country wise distribution | Filled map | Location = `DimCountry[Country]` (Data Category = Country), color = `[Total Titles]` |
| Movies and TV Shows distribution | Donut | Legend = `FactTitle[type]`, value = `[Total Titles]`, label = `[% of Total Titles]` |
| Total Movies and TV Shows by Years | Area/line | Axis = `FactTitle[Year Added]` (chronological), value = `[Total Titles]`, legend = `FactTitle[type]` |
| Ratings | Bar chart | Axis = `FactTitle[rating]`, value = `[Total Titles]` |
| Top 10 Genre | Horizontal bar (Top 10) | Axis = `DimGenre[Genre]`, value = `[Total Titles]`, top-10 descending |
| Genre | Table/list | `DimGenre[Genre]` |
| Description | Table | `FactTitle[description]`, filtered `type = "TV Show"` |
| Duration | Table | `FactTitle[duration]` |
| Rating | Table/card | `FactTitle[rating]` |

*RLS-sensitive: every visual uses `[Total Titles]` so the active role filters all of them. `User_Access` is not surfaced in any visual or slicer.*

### Phase G — Validation

1. TMDL structural lint:
   `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"`
2. Cross-cutting PBIP validator (exit 0=clean, 2=errors → fix before proceeding):
   `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"`
3. Report JSON syntax check (every `*.json`/`*.pbir` parses).
4. Manual: open in Power BI Desktop, "View as role" → confirm SC-002/SC-003 (entitled-only / deny-by-default), SC-006 (author full count), SC-007 (chronological years, exactly 10 genres).

## Phase 0: Research

See [research.md](research.md) — all NEEDS CLARIFICATION resolved (none remain; spec clarifications already fixed RLS identity, country normalization, measure definition, date parsing, theme, and donut chart choice).

## Phase 1: Design & Contracts

- [data-model.md](data-model.md) — full table/column definitions, 5 relationships with cross-filter flags, RLS propagation path, measures, calculated column.
- [quickstart.md](quickstart.md) — step-by-step build + validation walkthrough.
- Contracts: N/A for a PBIP migration (no external API/CLI surface); the "contract" is PBIR/TMDL schema conformance enforced by the plugin validators.
- Agent context: plan reference in `.github/copilot-instructions.md` updated to point to this plan.

## Complexity Tracking

> No constitution violations — section intentionally empty.
