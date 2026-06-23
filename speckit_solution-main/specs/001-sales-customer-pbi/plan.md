# Implementation Plan: Sales & Customer Dashboards — Tableau → Power BI Migration

**Branch**: `001-sales-customer-pbi` | **Date**: 2026-06-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-sales-customer-pbi/spec.md`

## Summary

Build a complete Power BI **PBIP** project that faithfully reproduces the two-dashboard Tableau workbook *Sales & Customer Dashboards*. The work has two layers:

1. **Semantic model** (TMDL): an Import-mode star schema — `Orders` fact joined many-to-one to `Customers`, `Location`, `Products`, plus an M-generated `DimDate` (trend axes) and a disconnected `Select Year` What-If table — carrying all **45 explicit DAX measures** organized into display folders, with key trimming and Postal Code zero-padding pushed into Power Query.
2. **Report** (PBIR enhanced folder format): two pages — **Customer Dashboard** and **Sales Dashboard** — at **1280×720 (16:9 PBI standard)**, reproducing the Tableau zone layout (KPI legend strip, three KPI sparkline cards per page, Customer Distribution histogram, Top Customers Top-10 table, Subcategory Comparison diverging bar, Weekly Trends dual-line), page-navigation buttons, a bookmark-toggled collapsible filter panel, and static color legends.

All artifacts are emitted to `Output/SalesCustomerDashboards/` and must pass `tmdl-validate` + `validate_pbip.py` with zero errors before delivery (SC-008).

## Technical Context

**Language/Version**: TMDL (Tabular Model Definition Language, compatibility level 1567+) for the model; PBIR JSON (`visualContainer/2.4.0`, report schema `3.0.0`) for the report; Power Query M for data load.
**Primary Dependencies**: Power BI Desktop (PBIP project format); Power Query M engine (Import mode); VertiPaq.
**Storage**: 4 local CSV files in `Data/Sales and Customer/` — `Orders.csv`, `Customers.csv`, `Location.csv`, `Products.csv` (semicolon delimiter, mixed UTF-8 / windows-1252 encodings). Loaded **Import** mode.
**Testing**: Structural validators — `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` (TMDL lint) and `plugins/pbip/skills/pbip/scripts/validate_pbip.py` (cross-cutting PBIP/PBIR). Functional spot-check via DAX queries per year (2020–2023).
**Target Platform**: Power BI Desktop (Windows) opening the generated `.pbip`.
**Project Type**: Power BI semantic model + report (PBIP). Not a code project — no `src/tests` trees.
**Performance Goals**: Single-interaction recompute when `Select Year` changes (SC-004); model well under 1M rows so text natural keys are acceptable (constitution §6).
**Constraints**: Import mode; single-direction relationships; measures-only (no DAX calculated columns); PBIR visual.json must contain **only** `$schema`/`name`/`position`/`visual` at root (no `filters`/`filterConfig`); `report.json` minimal template (no forbidden properties).
**Scale/Scope**: 4 source tables + DimDate + Select Year = 6 model tables; 4 active relationships (+1 optional inactive Ship Date); 45 measures; 2 report pages; ~12 in-scope visuals (3 Test worksheets excluded).

### Decisions resolved (no NEEDS CLARIFICATION remaining)

| Topic | Decision | Source |
|-------|----------|--------|
| Canvas size | **1280×720** (16:9 PBI standard). Tableau zones (native 1200×800, units 0–100000) are mapped proportionally: `px = unit/100000 × {1280 \| 720}`. Layout order/positions preserved. | User request (overrides spec's 1200×800 reference) |
| Storage mode | Import; per-file encodings (Orders/Location 65001, Customers/Products 1252); delimiter `;`, `QuoteStyle.Csv` | Spec clarifications |
| Year parameter | Disconnected `Select Year` table via `GENERATESERIES(2020,2023,1)`; consumed by `SELECTEDVALUE(...,2023)` | star-schema + dax-measures |
| Year context | Parameter-driven `FILTER(ALL(DimDate[Year]), …)` override (single-column, keeps month axis intact) | dax-measures |
| Trend axes | M-generated `DimDate` (Year, Quarter, Month Number, Month Name, Week of Year, Day, Date), many-to-one to `Orders[Order Date]` | star-schema |
| Key joins | Postal Code → zero-padded 5-char text + `Text.Trim` (both sides); Customer ID / Product ID `Text.Trim` | star-schema Key Handling |
| Collapsible filter panel | Bookmark Open/Close toggling a slicer group's visibility | Spec clarification |
| Navigation | Native buttons with Page Navigation action; active page styled selected | Spec clarification |
| Top 10 | `Customer Rank` (RANKX DENSE) + `Top 10 Customer Filter = IF(Rank<=10,1,0)` applied as visual-level filter `=1` | dax-measures |
| RLS | None — no `roles/` folder | Analysis RLS Detected: No |

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md`. Re-checked after design — all gates pass.*

| Constitution Principle | Status | Notes |
|------------------------|--------|-------|
| §0 Single-table rule | ✅ N/A | Source has **4** physical CSV tables → star schema decomposition is correct, not forced. |
| §1 Star schema (multi-table) | ✅ Pass | Orders fact + 3 dims on natural text keys + generated DimDate. No snowflaking, no bridge (no many-to-many). |
| §2 Naming | ⚠️ Justified deviation | Single-source descriptive names retained (`Orders`, `Customers`, `Location`, `Products`) instead of `Fact*/Dim*` prefixes, to preserve Tableau field provenance and the report's column references. `DimDate` keeps the `Dim` prefix. Measures Title Case; display folders logical. Documented in Complexity Tracking. |
| §3 DAX standards | ✅ Pass | Measures over columns (zero calc columns); VAR/RETURN; `DIVIDE()`; RANKX for Top N; SELECTEDVALUE for What-If; explicit measures only; format strings + display folders on all 45. No CALCULATE boolean filter references a measure (VAR pattern). |
| §4 Relationships | ✅ Pass | All many-to-one, single cross-filter direction, active. No bidirectional. Optional Ship Date join left **inactive**. `Select Year` participates in no relationship. |
| §4a RLS | ✅ Pass | Detected No → no roles created. |
| §5 M query connectivity | ✅ Pass | CSV `Csv.Document(File.Contents(...))`, `QuoteStyle.Csv`, per-file `Encoding`; each query independent (no cross-query refs); `Text.Trim` on all join keys; absolute file paths. |
| §6 Performance | ✅ Pass | Import; transformations in M; no DAX calc columns; text natural keys acceptable (<1M rows); single-direction filtering. |
| §7 Parameter migration | ✅ Pass | Integer list → `GENERATESERIES` What-If + SELECTEDVALUE (complete coverage). |
| §8 PBIP output structure | ✅ Pass | TMDL `definition/` (database/model/relationships/tables); PBIR `definition/report.json` minimal template (no forbidden props), `pages/` enhanced folder. |
| §9 Report visual layer | ✅ Pass | Titles/borders/alt-text/background per visual; 25px edge / 20px gap layout; professional theme; all table projections `active: true`. |
| §10 Validation | ✅ Pass | Every Tableau calc field has DAX (SC-002, coverage table confirms 45/45); validators run at each stage. |

**Gate result: PASS** (one justified naming deviation — see Complexity Tracking).

## Project Structure

### Documentation (this feature)

```text
specs/001-sales-customer-pbi/
├── plan.md              # This file
├── spec.md              # Feature specification (input)
├── checklists/
│   └── requirements.md  # Requirements checklist (speckit.specify output)
└── tasks.md             # Phase 2 output (speckit.tasks — NOT created here)
```

> Phase-0 research and Phase-1 data-model artifacts already exist as pipeline memory and are the authoritative design inputs for this plan (no duplicate research.md/data-model.md generated):
> - `.specify/memory/SalesCustomerDashboards/tableau-analysis-output.md` (research / source facts)
> - `.specify/memory/SalesCustomerDashboards/star-schema-output.md` (data model — tables, columns, relationships, key handling)
> - `.specify/memory/SalesCustomerDashboards/dax-measures-output.md` (measure contracts — 45 measures + What-If table)

### Generated PBIP output (repository — build target)

```text
Output/SalesCustomerDashboards/
├── SalesCustomerDashboards.pbip                 # Project entry (opens in PBI Desktop)
├── SalesCustomerDashboards.SemanticModel/
│   ├── definition.pbism
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl                        # compatibilityLevel + model id
│       ├── model.tmdl                           # culture, ref table entries, annotations
│       ├── relationships.tmdl                   # 4 active (+1 optional inactive)
│       ├── expressions.tmdl                     # shared M params (folder path) — optional
│       └── tables/
│           ├── Orders.tmdl                      # fact: cols + degenerate dims + 38 measures
│           ├── Customers.tmdl                   # dim + Customer Rank / Top 10 Filter measures
│           ├── Location.tmdl                    # dim (Region>State>City hierarchy)
│           ├── Products.tmdl                    # dim (Category>Sub-Category>Product hierarchy)
│           ├── DimDate.tmdl                     # generated calendar, marked as date table
│           └── Select Year.tmdl                 # disconnected GENERATESERIES + Selected/Previous Year
└── SalesCustomerDashboards.Report/
    ├── definition.pbir                          # datasetReference byPath → ../.SemanticModel
    ├── .platform
    └── definition/
        ├── version.json
        ├── report.json                          # minimal: $schema + themeCollection + settings
        ├── pages/
        │   ├── pages.json                       # page order + active page
        │   ├── CustomerDashboard/
        │   │   ├── page.json                     # 1280×720, name ^[\w-]+$
        │   │   └── visuals/{visual}/visual.json
        │   └── SalesDashboard/
        │       ├── page.json
        │       └── visuals/{visual}/visual.json
        ├── bookmarks/                            # filter-panel Open/Close pair
        │   ├── bookmarks.json
        │   └── {id}.bookmark.json
        └── StaticResources/RegisteredResources/  # theme + button/legend assets (optional)
```

**Structure Decision**: PBIP project (semantic model + report) emitted to `Output/SalesCustomerDashboards/`. The model uses the **TMDL `definition/` folder** form; the report uses the **PBIR enhanced `definition/pages/` folder** form. This matches constitution §8 and the `pbir-format` skill, and is what `validate_pbip.py` expects.

## Technical Approach

### 1. Data layer (Power Query M, Import mode)

- **Four independent CSV queries** (`Csv.Document(File.Contents("C:\...\Data\Sales and Customer\<file>.csv"), [Delimiter=";", Encoding=<per-file>, QuoteStyle=QuoteStyle.Csv])`), headers promoted, types cast immediately. No query references another query (constitution §5 rule 1).
- **Key prep in M** (star-schema Key Handling):
  - `Postal Code` (Orders **and** Location): `Text.Trim(Text.PadStart(Text.From([Postal Code]),5,"0"))` → `type text`.
  - `Customer ID`, `Product ID` (fact + matching dim): `Text.Trim(...)` → `type text`.
  - `Order Date` / `Ship Date`: `type date` (en_DE parse).
- **DimDate** generated in M (no CSV): daily range `Date.StartOfYear(List.Min(Orders[Order Date]))` → `Date.EndOfYear(List.Max(Orders[Order Date]))` extended to 2020-01-01…2023-12-31; derive `Year, Quarter, Quarter Name, Month Number, Month Name, Week of Year, Day`. `Month Name` Sort-By `Month Number`; `Quarter Name` Sort-By `Quarter`. Marked as date table on `Date`.
- **Select Year** is a **DAX calculated table** (not M): `SELECTCOLUMNS(GENERATESERIES(2020,2023,1),"Year",[Value])`.

### 2. Model layer (TMDL)

- **Tables**: `Orders` (fact — measure columns Sales/Quantity/Discount/Profit + degenerate dims Row ID/Order ID/Ship Mode/Segment/Ship Date + FKs), `Customers`, `Location` (Geography hierarchy Region>State>City), `Products` (Product hierarchy Category>Sub-Category>Product Name), `DimDate` (Calendar hierarchy), `Select Year`.
- **Relationships** (`relationships.tmdl`): 4 active many-to-one single-direction — Customers→Orders (Customer ID), Location→Orders (Postal Code), Products→Orders (Product ID), DimDate→Orders (Order Date). Optional inactive DimDate→Orders (Ship Date) only if downstream ship-date analysis is added.
- **45 measures** placed on home tables per the dax-measures index, grouped into display folders: **Parameters** (2, on Select Year), **Current Year** (6), **Previous Year** (6), **Year-over-Year** (6), **Highlights** (18), **Ranking** (2, on Customers), **LOD** (2), **KPI Helpers** (3). Each carries its format string (`$#,##0,"K"`, `"▲ "0.0%;"▼ "0.0%`, `"#"0`, `#,##0`, `0`). DAX copied verbatim from dax-measures-output.md (VAR/RETURN, DIVIDE, ALL(DimDate[Year]) override). The two `-- REVIEW` notes (% Diff Profit CY denominator; Total CY Sales scoped REMOVEFILTERS) are preserved as authored.
- **No calculated columns** — all derivations live in M (DimDate) or as measures.

### 3. Report layer (PBIR)

- **Two pages** at 1280×720; page `name` matches `^[\w-]+$` (`CustomerDashboard`, `SalesDashboard`); `displayName` shows the friendly title.
- **Zone → pixel mapping** (Tableau unit/100000 × canvas; preserves order & relative position):

  | Page / Visual | Tableau (x,y,w,h units) | Mapped px (x,y,w,h) @1280×720 |
  |---|---|---|
  | Customer · Legend KPI strip | 0, 7375, 100000, 3625 | 0, 53, 1280, 26 |
  | Customer · KPI Customers | 0, 11000, 33333, 35500 | 0, 79, 427, 256 |
  | Customer · KPI Sales/Customer | 33333, 11000, 33333, 35500 | 427, 79, 427, 256 |
  | Customer · KPI Orders | 66667, 11000, 33333, 35500 | 853, 79, 427, 256 |
  | Customer · Customer Distribution | 0, 46500, 50000, 53500 | 0, 335, 640, 385 |
  | Customer · Top Customers | 50000, 46500, 50000, 53500 | 640, 335, 640, 385 |
  | Sales · KPI Sales/Profit/Quantity | 0/33333/66667, 11000, ~33333, 35500 | 0/427/853, 79, 427, 256 |
  | Sales · Subcategory Comparison | 1416, 56875, 47168, 40987 | 18, 410, 604, 295 |
  | Sales · Weekly Trends | 51416, 56000, 47168, 41875 | 658, 403, 604, 302 |
  | Both · Nav + Filter buttons | 78333–93500, 750, 7583, 8750 | ~1003–1197, 5, 97, 63 |

  Final pixel values are normalized by the generator to honor the 25px edge / 20px gap layout rule (constitution §9) while keeping the Tableau order.
- **KPI sparkline cards** = composite per card: a Card (CY value) + a line chart of the CY measure by `DimDate[Month Name]` (sort by Month Number) styled as sparkline with the `… Min/Max Marker` measure as a highlight scatter point + a Card showing the matching `% Diff` measure (arrow format string).
- **Customer Distribution**: column histogram — axis = `Nr of Orders per Customer (Fixed)`, value = `CY Customers`.
- **Top Customers**: table with `Customer Rank`, `Customers[Customer Name]`, `MAX(Orders[Order Date])` (Last Order), `CY Profit`, `CY Sales`, `CY Orders`; visual-level filter `Top 10 Customer Filter = 1`; all projections `active: true`.
- **Subcategory Comparison**: clustered/diverging bar by `Products[Sub-Category]` of `PY Sales`, `CY Sales`, `CY Profit` (profit/loss color) + static legend.
- **Weekly Trends**: multi-line by `DimDate[Week of Year]` of `CY Sales` & `CY Profit` + Above/Below static legend.
- **Navigation**: native buttons (Page Navigation action) per page; active page button styled selected.
- **Collapsible filter panel**: slicer group (Select Year, Category, Sub-Category, Region, State, City) hidden by default; two bookmarks (Open/Close) toggle group visibility via the filter button.
- **Legends**: static text boxes / shape markers with source palette colors (not data-bound legend visuals).
- **PBIR safety**: visual.json root limited to `$schema`,`name`,`position`,`visual`; no `filters`/`filterConfig` at root; `visualContainerObjects.title` only `show`/`text`; colors via `{"solid":{"color":{"expr":{"Literal":{"Value":"'#RRGGBB'"}}}}}`. `report.json` uses the minimal template (no `modelExtensions`/`publicCustomVisuals`/`sections`/`baseTheme`).
- **Excluded**: the three Test worksheets (Test KPI, Test KPI2, Test Max Min) are not reproduced (FR-022).

### 4. Validation (run before delivery — MANDATORY)

1. TMDL lint: `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\SalesCustomerDashboards\SalesCustomerDashboards.SemanticModel\definition"`
2. Cross-cutting: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"`
3. Report JSON parse check over `*.json`/`*.pbir` in `.Report/`.
Errors (exit code 2 / lint failures) are fixed before the artifact is presented; findings logged in pipeline state.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| §2 naming: descriptive table names (`Orders`/`Customers`/`Location`/`Products`) instead of `Fact*/Dim*` prefixes | Preserves 1:1 provenance with the Tableau `Sales DataSource` field names so DAX measures and report column bindings reference the same identifiers the analyst already knows; reduces rename churn across 45 measures and ~12 visuals. | Renaming to `FactOrder`/`DimCustomer` would force every measure reference, relationship, and visual binding to use synthetic names with no business value and a higher chance of broken references — cosmetic gain only. `DimDate` keeps the prefix since it is a generated, non-source table. |
| Canvas 1280×720 vs. Tableau 1200×800 | User-mandated 16:9 PBI standard; better fit for the Power BI viewport and web/projector rendering. | Keeping 1200×800 wastes the Power BI canvas and is non-standard; proportional zone mapping preserves the exact visual order/position so fidelity is retained. |

## Phase Outputs

- **Phase 0 (research)**: satisfied by `tableau-analysis-output.md` — all unknowns resolved (source type, encodings, parameter, RLS, visual inventory).
- **Phase 1 (design & contracts)**: satisfied by `star-schema-output.md` (data model) + `dax-measures-output.md` (measure contracts). Agent context marker updated in `.github/copilot-instructions.md` to point at this plan.
- **Phase 2 (tasks)**: produced by `speckit.tasks` (next stage) → `tasks.md`.
- **Build**: `pbip-generator` (model) + `report-visual-migration` (report) consume this plan to emit `Output/SalesCustomerDashboards/`.
