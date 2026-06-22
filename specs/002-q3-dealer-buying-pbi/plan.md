# Implementation Plan: (Active) 2021 Q3 Dealer Buying Event — Tableau → Power BI Migration

**Branch**: `002-q3-dealer-buying-pbi` | **Date**: 2026-06-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-q3-dealer-buying-pbi/spec.md`

## Summary

Build a complete Power BI **PBIP** project that faithfully reproduces the five-dashboard Tableau workbook *(Active) 2021 Q3 Dealer Buying Event*. The work has two layers:

1. **Semantic model** (TMDL): an Import-mode **single flat table** `LaunchData` (all 53 source CSV columns preserved + 2 derived columns), an M-generated `DimDate` (Sales-by-Date time axis), and **two disconnected DATATABLE parameter tables** (`Rows Displayed`, `Rank Sort Measure`). Carries the complete set of **7 explicit DAX measures** plus **2 derived columns** organized into display folders, with text trimming pushed into Power Query.
2. **Report** (PBIR enhanced folder format): **five pages** — **DataDetail**, **DeliverySeasonSummary**, **LaunchReportDashboard**, **SlideView1**, **SlideView2** — reproducing the Tableau dashboard composition (large detail table with ~13 slicers; small-multiple bar-chart grid; main dashboard with category bar charts, Top Parts ranked table, Launch Summary KPI cards, Sales-by-Date trend colored by Reorder Type; and two slide layouts). The two parameter slicers drive every Top Parts visual.

Per **constitution §0 (Single-Table Rule)**, the single denormalized `excel-direct` source is loaded as ONE table — it is NOT decomposed into fact/dimension tables. All artifacts are emitted to `Output/Q3DealerBuyingEvent/` and must pass `tmdl-validate` + `validate_pbip.py` with zero errors before delivery (SC-007).

## Technical Context

**Language/Version**: TMDL (Tabular Model Definition Language, compatibility level 1567+) for the model; PBIR JSON (`visualContainer/2.4.0`, report schema `3.0.0`) for the report; Power Query M for data load.
**Primary Dependencies**: Power BI Desktop (PBIP project format); Power Query M engine (Import mode); VertiPaq.
**Storage**: 1 local CSV file `Data/Q3 Buyer/Q3LaunchData 1.csv` (53 columns, ~13k rows, comma-delimited, UTF-8). Loaded **Import** mode.
**Testing**: Structural validators — `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` (TMDL lint) and `plugins/pbip/skills/pbip/scripts/validate_pbip.py` (cross-cutting PBIP/PBIR). Functional spot-check via DAX queries over sample part/parameter selections.
**Target Platform**: Power BI Desktop (Windows) opening the generated `.pbip`.
**Project Type**: Power BI semantic model + report (PBIP). Not a code project — no `src/tests` trees.
**Performance Goals**: Single-interaction re-rank/re-trim when `Rows Displayed` or `Rank Sort Measure` changes (SC-005); model ~13k rows so text natural keys are acceptable (constitution §6).
**Constraints**: Import mode; single-direction relationship; measures-first (only 2 row-level derived columns: `Master Style`, `Region`); PBIR visual.json root limited to `$schema`/`name`/`position`/`visual` (no `filters`/`filterConfig`); `report.json` minimal template (no forbidden properties).
**Scale/Scope**: 1 flat table + DimDate + 2 parameter tables = 4 model tables; 1 active relationship; 7 measures + 2 derived columns; 5 report pages; ~13 slicers on Data Detail plus the dashboard/slide visual sets.

### Decisions resolved (no NEEDS CLARIFICATION remaining)

| Topic | Decision | Source |
|-------|----------|--------|
| Model shape | **Single flat table** `LaunchData` (no fact/dim decomposition) + DimDate + 2 disconnected parameter tables | constitution §0; spec FR-002; star-schema-output |
| Storage mode | Import; CSV via `Csv.Document(File.Contents(...))`, `QuoteStyle.Csv`, `Encoding=65001` (UTF-8), comma delimiter, headers promoted, types cast | spec clarifications; constitution §5/§6 |
| Key trimming | `Text.Trim` on canonical `Style Code` (source of `Master Style`) and `Sales Area` (source of `Region`); "(trailing space)" duplicate columns retained as-is for fidelity | spec FR-003; star-schema Key Handling |
| `Rows Displayed` parameter | Disconnected DATATABLE (`Label` text / `Value` int hidden): 5,10,20,50,All=10000; default 10; consumed by `SELECTEDVALUE('Rows Displayed'[Value],10)` | dax-measures; spec FR-006 |
| `Rank Sort Measure` parameter | Disconnected DATATABLE (`Label` text / `SortOrder` int hidden): 4 sort options; default "Order $ (Decending)"; consumed by `SELECTEDVALUE('Rank Sort Measure'[Label],"Order $ (Decending)")` | dax-measures; spec FR-007 |
| Top-N pattern | `Rank = RANKX(ALLSELECTED(LaunchData[Base Part Number]),[Measure for Rank],,DESC,DENSE)` + `Rank Filter = IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value],10),1,0)` applied as visual-level filter `=1` | dax-measures; spec FR-010/FR-011 |
| Parameter-driven sort | `Measure for Rank = SWITCH(SELECTEDVALUE('Rank Sort Measure'[Label],…), ±[Order $]/±[Order Quantity])` mirroring Tableau `CASE` | dax-measures; spec FR-009 |
| Percent-of-total | `Order $ (Percent of Total) = DIVIDE([Order $], CALCULATE([Order $], ALLSELECTED(LaunchData)))` format `0.00%` | dax-measures; spec FR-012 |
| Derived columns | `Master Style = LEFT(LaunchData[Style Code],8)`; `Region = SWITCH(TRUE(), Sales Area="Canada"→"Canada", ="United States of America"→"USA", Macro Area)` | dax-measures; spec FR-014/FR-015 |
| Date axis | M-generated `DimDate` (Date, Year, Quarter, Month, Month Name) many-to-one single-direction to `LaunchData[Date]`; supplies Sales-by-Date continuous axis | star-schema; spec FR-004/FR-026 |
| Pages | 5 dashboards → 5 pages; the 49 worksheets are the visuals composing those pages (not 49 pages); page names sanitized to `^[\w-]+$` | spec FR-019; analysis Dashboards table |
| Redundant calcs | "(copy)" aliases & `Global="Global"` NOT recreated — original source columns/measures reused | dax-measures; spec FR-017 |
| RLS / sets / groups / bins | **None** — analysis reports none; no `roles/` folder, no bridge tables | analysis; spec FR-005 |

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md`. Re-checked after design — all gates pass.*

| Constitution Principle | Status | Notes |
|------------------------|--------|-------|
| §0 Single-table rule | ✅ Pass | Source has **one** `excel-direct` datasource (Sheet1, 53 cols, no joins, no blending) → loaded as a single flat `LaunchData` table. NO fact/dimension decomposition (the decisive rule here). |
| §1 Star schema (multi-table) | ✅ N/A | Not applicable — single source, no joins. The only added relational table is the generated `DimDate`. No bridges, no surrogate keys. |
| §2 Naming | ✅ Pass | Single-source descriptive table name `LaunchData`; `DimDate` keeps the `Dim` prefix; parameter tables named `Rows Displayed` / `Rank Sort Measure`. Measures Title Case; display folders (`Core Metrics`, `Ranking`). Source column names preserved verbatim. |
| §3 DAX standards | ✅ Pass | Measures-first (only 2 row-level derived columns, required for slicing/feeding distinct count); VAR/RETURN; `DIVIDE()`; RANKX DENSE for Top N; SELECTEDVALUE for parameter consumption; explicit measures only; format strings + display folders on all 7. No CALCULATE boolean filter references a measure. |
| §4 Relationships | ✅ Pass | One relationship: `DimDate[Date]` 1—* `LaunchData[Date]`, single cross-filter direction, active. No bidirectional. Both parameter tables participate in NO relationship (disconnected). No circular dependencies. |
| §4a RLS | ✅ Pass | Detected No → no `roles/` folder created. |
| §5 M query connectivity | ✅ Pass | CSV `Csv.Document(File.Contents(...))`, `QuoteStyle.Csv`, `Encoding=65001`; each query independent (no cross-query refs); `Text.Trim` on the `Style Code`/`Sales Area` key-derivation columns; absolute file path; `DimDate` generated in M without `Table.NestedJoin`. |
| §6 Performance | ✅ Pass | Import; text transformations in M where preferred (`Master Style` documented M-equivalent `Text.Start(Text.Trim([Style Code]),8)`); minimal calculated columns; text natural keys acceptable (~13k rows ≪ 1M); single-direction filtering. |
| §7 Parameter migration | ✅ Pass | Integer list → disconnected DATATABLE + SELECTEDVALUE; string list → disconnected DATATABLE + SELECTEDVALUE. Complete coverage of both Tableau parameters with exact domains/defaults; "All"→10000 Top-N pattern. |
| §8 PBIP output structure | ✅ Pass | TMDL `definition/` (database/model/relationships/tables); PBIR `definition/report.json` minimal template (no forbidden props), `pages/` enhanced folder. |
| §9 Report visual layer | ✅ Pass | Titles/borders/alt-text/background per visual; 25px edge / 20px gap layout; professional theme; all table/matrix projections `active: true`. Each visual replicates the Tableau mark type. |
| §10 Validation | ✅ Pass | Every in-scope Tableau calc field has a DAX equivalent (SC-002: 7/7 + 2 supporting aggregates); validators run at each stage. |

**Gate result: PASS** (no violations — Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/002-q3-dealer-buying-pbi/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── checklists/
│   └── requirements.md  # Requirements checklist (speckit.specify output)
└── tasks.md             # Phase 2 output (speckit.tasks — NOT created here)
```

> Phase-0 research and Phase-1 data-model artifacts already exist as pipeline memory and are the authoritative design inputs for this plan (no duplicate research.md/data-model.md generated):
> - `.specify/memory/Q3DealerBuyingEvent/tableau-analysis-output.md` (research / source facts — parameters, columns, calc fields, worksheets, 5 dashboards)
> - `.specify/memory/Q3DealerBuyingEvent/star-schema-output.md` (data model — single-table shape, DimDate, parameter tables, the one relationship)
> - `.specify/memory/Q3DealerBuyingEvent/dax-measures-output.md` (measure contracts — 7 measures + 2 derived columns + 2 parameter DATATABLEs)

### Generated PBIP output (repository — build target)

```text
Output/Q3DealerBuyingEvent/
├── Q3DealerBuyingEvent.pbip                      # Project entry (opens in PBI Desktop)
├── Q3DealerBuyingEvent.SemanticModel/
│   ├── definition.pbism
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl                         # compatibilityLevel + model id
│       ├── model.tmdl                            # culture, ref table entries, annotations
│       ├── relationships.tmdl                    # 1 active (DimDate → LaunchData on Date)
│       └── tables/
│           ├── LaunchData.tmdl                   # single flat table: 53 source cols + Master Style + Region + 7 measures
│           ├── DimDate.tmdl                      # generated calendar, marked as date table
│           ├── Rows Displayed.tmdl               # disconnected DATATABLE (Label / Value hidden)
│           └── Rank Sort Measure.tmdl            # disconnected DATATABLE (Label / SortOrder hidden)
└── Q3DealerBuyingEvent.Report/
    ├── definition.pbir                           # datasetReference byPath → ../.SemanticModel
    ├── .platform
    └── definition/
        ├── version.json
        ├── report.json                           # minimal: $schema + themeCollection + settings
        └── pages/
            ├── pages.json                        # page order + active page
            ├── DataDetail/
            │   ├── page.json                      # name ^[\w-]+$, displayName "Data Detail"
            │   └── visuals/{visual}/visual.json   # detail Table/Matrix + ~13 slicers
            ├── DeliverySeasonSummary/
            │   ├── page.json
            │   └── visuals/{visual}/visual.json   # MacroArea/Garment/Gender/Category bar grid + Top Parts tables
            ├── LaunchReportDashboard/
            │   ├── page.json
            │   └── visuals/{visual}/visual.json   # category bars + Top Parts table + KPI cards + Sales by Date
            ├── SlideView1/
            │   ├── page.json
            │   └── visuals/{visual}/visual.json   # Sales by Date / MacroArea / Category / Delivery Season + 2 KPI cards
            └── SlideView2/
                ├── page.json
                └── visuals/{visual}/visual.json   # Sales by Date / MacroArea / Delivery Season / Family + KPIs + slicers + legend
```

**Structure Decision**: PBIP project (semantic model + report) emitted to `Output/Q3DealerBuyingEvent/`. The model uses the **TMDL `definition/` folder** form; the report uses the **PBIR enhanced `definition/pages/` folder** form. This matches constitution §8 and the `pbir-format` skill, and is what `validate_pbip.py` expects.

## Technical Approach

### 1. Data layer (Power Query M, Import mode)

- **One CSV query** `LaunchData`:
  ```
  Source = Csv.Document(
      File.Contents("C:\Users\AmanRajMAQSoftware\Downloads\New folder\speckit_solution\Data\Q3 Buyer\Q3LaunchData 1.csv"),
      [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
  )
  ```
  Headers promoted via `Table.PromoteHeaders(Source, [PromoteAllScalars = true])`, then **types cast immediately** after promotion (`Table.TransformColumnTypes`): `Date` → `type date`; `Month`, `Year`, `Order Quantity`, `Sum of Extra Quantity (Units)`, `Sum of Quantity (Units)` → `Int64.Type`; `Cost`, `Dnet`, `Margin $`, `Measure for Rank`, `MSRP`, `Order $ (U.S. Cost)`, `Order $ (U.S. Dealer Net)`, `Order $ (U.S. MSRP)`, `Order $ (USD)` → `type number`; all remaining columns → `type text`.
- **Key trimming in M** (constitution §5 rule 3 / star-schema Key Handling): apply `Text.Trim` to the canonical `Style Code` and `Sales Area` columns (the sources of derived `Master Style` and `Region`) to prevent whitespace mismatches. The "(trailing space)" duplicate variants (`Delivery Month (trailing space)`, `Delivery Season (trailing space)`, `Region (trailing space)`, `Sales Area (trailing space)`, `Style Code (trailing space)`, `Style Description (trailing space)`) are **retained as-is** for fidelity (FR-003) and are NOT used for key derivation.
- **All 53 source columns preserved** — no column dropped; the query is the single denormalized table (no `Table.NestedJoin`, no reference to any other query — constitution §5 rules 1 & 8).
- **`Master Style` (optional M form)**: constitution §6 prefers text ops in M — may be materialized in M as `Text.Start(Text.Trim([Style Code]), 8)`. The authoritative contract is the DAX column `LEFT(LaunchData[Style Code],8)`; either form is acceptable provided the result is identical and safe for codes shorter than 8 chars.
- **DimDate** generated in M (no CSV): daily contiguous range `Date.StartOfYear(List.Min(LaunchData[Date]))` … `Date.EndOfYear(List.Max(LaunchData[Date]))`; derive `Year`, `Quarter`, `Quarter Name` ("Q3"), `Month` (number), `Month Name`. `Month Name` Sort-By `Month`; `Quarter Name` Sort-By `Quarter`. Marked as the model date table on `Date`. Generated independently (the inline min/max bootstrap over `LaunchData[Date]` is resolved by the generator without a cross-query join).

### 2. Model layer (TMDL)

- **Tables**:
  - `LaunchData` (single flat table) — all 53 source columns + 2 derived columns (`Master Style`, `Region`) + the 7 measures. `Base Part Number` is the degenerate ranking grain (stays in the table). `Date` is the lone FK.
  - `DimDate` — generated calendar (Calendar hierarchy `Year > Quarter > Month Name`), marked as date table.
  - `Rows Displayed` — disconnected DATATABLE parameter.
  - `Rank Sort Measure` — disconnected DATATABLE parameter.
- **Derived columns** (2, on `LaunchData`):
  - `Master Style = LEFT ( LaunchData[Style Code], 8 )`
  - `Region = SWITCH ( TRUE(), LaunchData[Sales Area] = "Canada", "Canada", LaunchData[Sales Area] = "United States of America", "USA", LaunchData[Macro Area] )`
- **Measures** (7, on `LaunchData`) — DAX copied verbatim from dax-measures-output.md, each with its format string and display folder:

  | Measure | Display Folder | Format | DAX (summary) |
  |---|---|---|---|
  | Order $ | Core Metrics | `\$#,##0` | `SUM(LaunchData[Order $ (USD)])` |
  | Order Quantity | Core Metrics | `#,##0` | `SUM(LaunchData[Order Quantity])` |
  | Style Count | Core Metrics | `#,##0` | `DISTINCTCOUNT(LaunchData[Master Style])` |
  | Order $ (Percent of Total) | Core Metrics | `0.00%` | `DIVIDE([Order $], CALCULATE([Order $], ALLSELECTED(LaunchData)))` |
  | Measure for Rank | Ranking | `#,##0` | `SWITCH(SELECTEDVALUE('Rank Sort Measure'[Label],"Order $ (Decending)"), …, ±[Order $]/±[Order Quantity])` (VAR/RETURN) |
  | Rank | Ranking | `#,##0` | `RANKX(ALLSELECTED(LaunchData[Base Part Number]), [Measure for Rank], , DESC, DENSE)` |
  | Rank Filter | Ranking | `0` | `IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value],10), 1, 0)` |

- **Parameter tables** (DAX DATATABLE definitions, both disconnected):
  - `Rows Displayed` — `DATATABLE("Label",STRING,"Value",INTEGER,{{"5",5},{"10",10},{"20",20},{"50",50},{"All",10000}})`; `Value` hidden; sort `Label` by `Value`; default selection 10.
  - `Rank Sort Measure` — `DATATABLE("Label",STRING,"SortOrder",INTEGER,{{"Order $ (Decending)",1},{"Order Units (Decending)",2},{"Order $ (Accending)",3},{"Order Units (Accending)",4}})`; `SortOrder` hidden; sort `Label` by `SortOrder`; default "Order $ (Decending)". Spellings preserved verbatim so `SWITCH` matches.
- **Relationships** (`relationships.tmdl`): one — `DimDate[Date]` 1—* `LaunchData[Date]`, single cross-filter direction, active. Neither parameter table participates in any relationship.
- **No redundant objects**: pure aliases / "(copy)" duplicates (`Base Style Name`, `Delivery Season (copy)`, `Delivery Month (copy)`, `Category (copy)`, `Base Part (copy)`, `Order $ (U.S. Dealer Net) (copy)`, `Order $ (Percent of Total) (copy)`, `Global="Global"`) are NOT recreated — original source columns/measures are reused (FR-017).

### 3. Report layer (PBIR)

- **Five pages**; each page `name` matches `^[\w-]+$`; `displayName` shows the friendly title:

  | Page `name` | `displayName` | Source dashboard |
  |---|---|---|
  | `DataDetail` | Data Detail | Dashboard 1 |
  | `DeliverySeasonSummary` | Delivery Season Summary | Dashboard 2 |
  | `LaunchReportDashboard` | Launch Report Dashboard | Dashboard 3 (main) |
  | `SlideView1` | Slide View 1 | Dashboard 4 |
  | `SlideView2` | Slide View 2 | Dashboard 5 |

- **Visual composition per page** (Tableau mark type → Power BI visual; FR-027):

  - **DataDetail** — one large **Table/Matrix** of launch records (the `Data` worksheet) + **~13 slicers**: Region, Sales Area, Delivery Season, Delivery Month, Garment Type, Product Gender, Product Category, Product Family, Product Sub-Family, Base Style Name, Style Code, Base Part Number, Style Description. All table/matrix projections `active: true`.
  - **DeliverySeasonSummary** — 4-column small-multiple grid as **bar charts**: MacroArea (1–4), Garment Type (1–4), Gender (1–4), Category (1–4); plus **Top Parts** US / Int / All summaries as **Table/Matrix** (ranked, honoring `Rank Filter`).
  - **LaunchReportDashboard** (main) — **bar charts** for MacroArea, Gender, Category, Family, Delivery Season, Garment Type; a **Top Parts Table/Matrix** (ranked, columns `Base Part Number`, `Order $`, `Order $ (Percent of Total)`, honoring `Rank Filter`); **KPI cards** for Launch Summary; and a **Sales by Date** line/column chart over `DimDate[Date]` colored by `Reorder Type` (New vs Reorder) with a legend.
  - **SlideView1** — slide layout: **Sales by Date** (chart), **MacroArea** (bar), **Launch Summary** (**Card**), **Category** (bar), **Delivery Season** (bar), **Style Count** (**Card**).
  - **SlideView2** — slide layout: **Sales by Date** (chart), **MacroArea** (bar), **Delivery Season** (bar), **Family** (bar), **Launch Summary** (Card), **Style Count** (Card), slicers (Product Category, Product Gender, Garment Type), and a **Reorder Type color legend**.

- **Top-N enforcement**: each **Top Parts** visual carries a visual-level filter `Rank Filter = 1` so only the top `Rows Displayed` parts (ranked by `Measure for Rank`) are shown; changing `Rank Sort Measure` re-ranks and changing `Rows Displayed` re-trims. The `Rows Displayed` and `Rank Sort Measure` slicers are placed on the pages hosting Top Parts visuals (FR-025).
- **Sales by Date**: uses `DimDate[Date]` (continuous time axis) with `Reorder Type` as series color, reproducing the Tableau New/Reorder encoding (FR-026).
- **Formatting & fidelity**: currency `$#,##0`, percent-of-total `0.00%` preserved (FR-028); every visual has a descriptive title (from the Tableau worksheet name), 1px `#E0E0E0` border, and alt text; light-gray visual background; 25px edge / 20px gap layout (constitution §9).
- **PBIR safety**: visual.json root limited to `$schema`, `name`, `position`, `visual` — **no** `filters`/`filterConfig` at root (Top-N is enforced via the `Rank Filter` measure + visual-level filter UI, not a root property); `visualContainerObjects.title` only `show`/`text`; colors via `{"solid":{"color":{"expr":{"Literal":{"Value":"'#RRGGBB'"}}}}}`. `report.json` uses the minimal template (no `modelExtensions`/`publicCustomVisuals`/`sections`/`baseTheme`).
- **Excluded**: no RLS roles, sets, groups, or bins; the 49 worksheets are reproduced as the visuals composing the 5 pages (not 49 separate pages); the per-category "- 1/- 2/- 3/- 4" and "(Slide)" variants are layout building blocks.

### 4. Validation (run before delivery — MANDATORY)

1. TMDL lint: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.SemanticModel\definition"`
2. Cross-cutting: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"`
3. Report JSON parse check over `*.json`/`*.pbir` in `.Report/` (each must `ConvertFrom-Json` without error).

Errors (exit code 2 / lint failures) are fixed before the artifact is presented; findings logged in pipeline state. Checks specific to this model: `DimDate[Date]` contiguous/unique and marked as date table; the single relationship is many-to-one/single-direction/active; both parameter tables have **zero** relationships with exact domains/defaults; no surrogate keys, bridges, RLS roles, sets, groups, or bins; no bidirectional cross-filtering; all 5 pages present with sanitized names; all table/matrix projections `active: true`.

## Complexity Tracking

> No constitution violations — single-table shape, single-direction relationship, measures-first, and parameter DATATABLEs all align with the constitution. Table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| — | — | — |

## Phase Outputs

- **Phase 0 (research)**: satisfied by `tableau-analysis-output.md` — all unknowns resolved (source type CSV/UTF-8, single flat datasource, 2 parameters, 7 calc fields, 49 worksheets → 5 dashboards, RLS=No, no sets/groups/bins).
- **Phase 1 (design & contracts)**: satisfied by `star-schema-output.md` (model: single `LaunchData` + DimDate + 2 disconnected parameters, 1 relationship) + `dax-measures-output.md` (measure contracts — 7 measures, 2 derived columns, 2 DATATABLEs). Agent context marker updated in `.github/copilot-instructions.md` to point at this plan.
- **Phase 2 (tasks)**: produced by `speckit.tasks` (next stage) → `tasks.md`.
- **Build**: `pbip-generator` (model) + `report-visual-migration` (report) consume this plan to emit `Output/Q3DealerBuyingEvent/`.
