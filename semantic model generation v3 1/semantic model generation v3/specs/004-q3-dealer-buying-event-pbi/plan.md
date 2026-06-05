# Implementation Plan: (Active) 2021 Q3 Dealer Buying Event — Tableau to Power BI Migration

**Feature Branch**: `004-q3-dealer-buying-event-pbi`
**Date**: 2026-06-05
**Spec**: [spec.md](spec.md)
**Output**: `Output/Q3DealerBuyingEvent/`
**Status**: Ready for Implementation

---

## Summary

Migrate the Tableau **"(Active) 2021 Q3 Dealer Buying Event"** workbook into a complete Power BI Project (`.pbip`) — semantic model (TMDL) plus report (PBIR enhanced folder format). The source is a **single denormalized flat CSV** (`Data/Q3 Buyer/Q3LaunchData 1.csv`, 52 source columns, 1000 data rows) for a seasonal dealer pre-season buying event. Per the Single-Table Rule (constitution §0) the flat source is kept as **one wide `Orders` table** — Product, Geography, and Delivery-Timing attribute groups become **logical role dimensions** (display folders) inside `Orders`, not physical dimension tables. The model adds a DAX-generated **`DimDate`** (marked as the date table) and **two disconnected parameter tables** (`Rows Displayed`, `Rank Sort Measure`) consumed via `SELECTEDVALUE`. It implements **18 explicit DAX measures** (11 order/quantity aggregates, Margin %, Style Count, and the 4 ranking/Top-N/percent-of-total measures + the Measure-for-Rank sort helper) and **2 DAX calculated columns** (`Master Style`, `Region`). One active relationship `DimDate[Date] → Orders[Date]` provides time intelligence. The 49 Tableau worksheets / 5 dashboards consolidate into **three** PBIR report pages — Launch Report Dashboard, Delivery Season Summary, Data Detail. All artifacts land in `Output/Q3DealerBuyingEvent/` and are gated by the PBIP/TMDL validators.

> **Source binding note**: the TWB *declares* an absent Excel file (`C:/Users/jagerb/Desktop/Q3 Launch Data.xlsx`). The M partition MUST bind to the local CSV via `Csv.Document(File.Contents(...))`, never the missing Excel path (FR-001).

---

## Technical Context

| Aspect | Decision |
|--------|----------|
| Format | Power BI PBIP (TMDL semantic model + PBIR enhanced report) |
| Data Source | Single local CSV via `Csv.Document(File.Contents(...))` Power Query M |
| Model Type | **Single-table degenerate star** (one flat CSV → constitution §0, no fact/dimension decomposition) |
| Storage Mode | Import (in-memory VertiPaq) |
| Date Dimension | `DimDate` generated via **DAX `CALENDAR`** over full calendar years of `Orders[Date]`; self-deriving range, no extra M query |
| Key Strategy | Natural keys; `DimDate[Date]` is the only relationship key; `Item Code` is the degenerate grain identifier; no surrogate keys |
| Parameters | Two **disconnected** `DATATABLE`s (`Rows Displayed`, `Rank Sort Measure`) consumed via `SELECTEDVALUE` — never related to / never filter `Orders` directly (FR-008/FR-009) |
| DAX Patterns | `SUM`, `DISTINCTCOUNT`, `DIVIDE`, `SWITCH(TRUE())`, `RANKX(ALLSELECTED(...), …, DESC, Skip)`, `SELECTEDVALUE`, VAR/RETURN |
| Multi-value / blending | None present (no Sets, Groups, Bins, LOD, blending) — no bridge tables required |
| TMDL Authoring | `plugins/pbip/skills/tmdl/SKILL.md` — tab indentation, `///` descriptions, selective quoting, property order |
| PBIR Authoring | `plugins/pbip/skills/pbir-format/SKILL.md` — `visual.json` root limited to `$schema`/`name`/`position`/`visual`; minimal `report.json` |
| Validation | `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` + `plugins/pbip/skills/pbip/scripts/validate_pbip.py` |
| Language/Version | TMDL (compatibilityLevel 1567), Power Query M, DAX |
| Target Platform | Power BI Desktop (June 2024+ with PBIP/TMDL/PBIR preview enabled) |
| Output Path | `Output/Q3DealerBuyingEvent/` |

**CSV absolute path** (for the M partition):
`c:/Users/ShashankDwivediMAQSo/Desktop/New folder (2)/speckit_solution/semantic model generation v3 1/semantic model generation v3/Data/Q3 Buyer/Q3LaunchData 1.csv`

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md`:

| Constitution Rule | Plan Compliance | Status |
|---|---|---|
| §0 Single-Table Rule | Source is **one flat CSV** → kept as a single wide `Orders` table; only `DimDate` + 2 disconnected parameter tables added. NO fact/dim decomposition | ✅ PASS |
| §1 Star Schema (multi-table) | N/A — deliberately NOT applied (single source); Product/Geography/Delivery are logical role dimensions (display folders), not physical tables | ✅ PASS |
| §2 Naming Conventions | Single-source table `Orders` (PascalCase, unprefixed so the 18 measures resolve); `DimDate`, `Rows Displayed`, `Rank Sort Measure` descriptive; source column names preserved; measures Title Case | ✅ PASS |
| §3 DAX Standards | Explicit measures only; VAR/RETURN; `DIVIDE()` (no fallback → BLANK); `SELECTEDVALUE` for parameters; `RANKX` for Top-N; `SWITCH(TRUE())` for the sort switch; display folders + format strings; no measure inside a `CALCULATE` boolean filter | ✅ PASS |
| §4 Relationships | One active 1:many single-direction `DimDate[Date] → Orders[Date]`; no bidirectional; both parameter tables disconnected | ✅ PASS |
| §5 M Query | `Csv.Document` + `QuoteStyle.Csv` + `Delimiter = ","` + `Encoding = 65001` + absolute path; header promotion then `"en-US"` typing; single independent partition (no cross-query references) | ✅ PASS |
| §6 Performance | Import mode; 44-col × 1000-row table — VertiPaq trivial; 2 calc columns only (`Master Style`, `Region`, both row-level grouping grains); single-direction filtering | ✅ PASS |
| §7 Parameter Migration | Integer list → disconnected `DATATABLE` (`Rows Displayed` 5/10/20/50/10000); string list → disconnected `DATATABLE` (`Rank Sort Measure` 4 values); both + `SELECTEDVALUE` | ✅ PASS |
| §8 PBIP Output Structure | Standard `.pbip` + `.SemanticModel/` (TMDL) + `.Report/` (PBIR); minimal `report.json` enhanced template | ✅ PASS |
| §9 Report Visual Layer | 25px edge / 20px gap, borders, titles, alt text, professional theme; 3 consolidated pages | ✅ PASS |
| §10 Validation Checklist | tmdl-validate + validate_pbip.py gates at model, report, and end-to-end stages | ⏳ Pending (run after generation) |

**Gate result**: PASS — no violations; Complexity Tracking not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/004-q3-dealer-buying-event-pbi/
├── plan.md              # This file
├── research.md          # Phase 0 — M / TMDL / DimDate / parameter / PBIR decisions
├── data-model.md        # Phase 1 — tables, columns, relationship, 18 measures, 2 calc columns
├── quickstart.md        # Phase 1 — build & validation walkthrough
├── contracts/           # Phase 1 — PBIP/TMDL/PBIR structural contracts (file-based; no external API)
├── spec.md              # Clarified specification (input)
├── tasks.md             # Phase 2 (generated by /speckit.tasks)
└── checklists/          # Quality checklists
```

### Source Code (generated output)

```text
Output/Q3DealerBuyingEvent/
├── Q3DealerBuyingEvent.pbip
├── Q3DealerBuyingEvent.SemanticModel/
│   ├── definition.pbism
│   ├── .platform
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl              # compatibilityLevel 1567
│       ├── model.tmdl                 # culture, default data source version, ref tables
│       ├── relationships.tmdl         # 1 active relationship
│       └── tables/
│           ├── Orders.tmdl            # single wide source table (M partition, 42 typed cols + 2 DAX calc cols + 18 measures)
│           ├── DimDate.tmdl           # DAX CALENDAR calculated table, marked as date table
│           ├── Rows Displayed.tmdl    # disconnected DATATABLE parameter (Top-N)
│           └── Rank Sort Measure.tmdl # disconnected DATATABLE parameter (rank metric/direction)
└── Q3DealerBuyingEvent.Report/
    ├── definition.pbir                # byPath dataset reference
    ├── .platform
    └── definition/
        ├── report.json                # minimal PBIR enhanced template
        ├── version.json
        └── pages/
            ├── pages.json             # active page + page order
            ├── LaunchReportDashboard/ # page name matches ^[\w-]+$
            │   ├── page.json
            │   └── visuals/{visual}/visual.json
            ├── DeliverySeasonSummary/
            │   ├── page.json
            │   └── visuals/{visual}/visual.json
            └── DataDetail/
                ├── page.json
                └── visuals/{visual}/visual.json
```

**Structure Decision**: Single PBIP deliverable with a **4-table** model (`Orders` + `DimDate` + 2 disconnected parameter tables). All 18 measures and both calculated columns are authored on the `Orders` table (single-table rule). `DimDate` and the two parameter tables are model-generated (DAX `CALENDAR` / `DATATABLE`). Report pages are PBIR enhanced-format folders, one per consolidated page, with `pages.json` naming the active page. The input CSV stays in `Data/Q3 Buyer/`; nothing is copied into `Output/`.

---

## Phase 0: Research

All open questions were resolved in the 2026-06-05 clarification pass and captured in [research.md](research.md). Key decisions:

### CSV Loading via Power Query M

**Decision**: `Csv.Document(File.Contents(absolute_path), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv])`, then `Table.PromoteHeaders([PromoteAllScalars = true])`, then `Table.RemoveColumns(...)` to collapse aliases / drop pre-materialized columns, then `Table.TransformColumnTypes(..., "en-US")`.

**Rationale**: `QuoteStyle.Csv` (constitution §5) keeps quoted fields containing embedded commas intact. `Encoding = 65001` preserves UTF-8 product/geography text. The CSV is US-formatted (decimal point, ISO `yyyy-mm-dd` dates) so the `"en-US"` culture argument types `27.99` and `2021-01-26` correctly. The partition is independent (no references to other queries) per §5.

**Alternatives rejected**: binding to the TWB-declared Excel path (absent → load failure); M-generated DimDate via `List.Dates` (rejected in favor of DAX `CALENDAR` — no second query, self-deriving range, no load-order dependency).

### Data-Handling Rules (CSV → Orders)

- **Collapse 6 trailing-space alias columns** to their single base field (FR-005): `Delivery Month `, `Delivery Season `, `Region `, `Sales Area `, `Style Code `, `Style Description ` are removed in the `Table.RemoveColumns` step so the base columns (`Delivery Month`, `Delivery Season`, …) remain without duplicate display names.
- **Drop the 2 pre-materialized aggregate columns** `Measure for Rank` and `Style Count` (FR-005) — these are recreated as parameter-driven DAX so they respond to filter/parameter context, not imported as static data.
- **Drop the source `Region` and `Master Style` columns and recreate as DAX calculated columns** (FR-006): the CSV's pre-materialized `Region` value (e.g. "Europe") does **not** match the Tableau `Region` rule (which yields the Macro Area, e.g. "EMEA"), so the authored business logic is preserved in DAX. `Master Style` is recreated as `LEFT([Style Code], 8)` for consistency with the measure dependency.
- **`Date`** typed as `date` and used as the FK to `DimDate`. `Delivery Date` is a month-abbreviation **text** attribute (e.g. "Jan"), not a real date — it is NOT related to `DimDate`.

### DimDate via DAX CALENDAR

**Decision**: Generate `DimDate` as a calculated table — `CALENDAR(DATE(YEAR(MIN(Orders[Date])),1,1), DATE(YEAR(MAX(Orders[Date])),12,31))` wrapped in `ADDCOLUMNS` for Year/Quarter/Month/MonthName/Day. Mark as the model's date table on `Date`; `MonthName` Sort-By `Month`.

**Rationale**: Auto-derives the range from the data (2021-centric), needs no separate M query/CSV, and avoids load-order risk. Full Jan 1 → Dec 31 coverage keeps time intelligence contiguous.

### Disconnected Parameter Tables

**Decision**: Two `DATATABLE` calculated tables with NO relationships — `Rows Displayed[Value]` (5, 10, 20, 50, 10000; default 10, 10000 = "All") and `Rank Sort Measure[Selection]` (the 4 string values, default "Order $ (Decending)"). Bound to single-select slicers; consumed only via `SELECTEDVALUE`.

**Rationale**: The two Tableau list parameters are list selections (not numeric ranges) so they map to disconnected `DATATABLE`s, not What-If GENERATESERIES tables. They drive the rank/Top-N measures via `SELECTEDVALUE` and MUST NOT filter the fact directly (FR-008/FR-009). Source spellings ("Decending"/"Accending") are preserved verbatim so `SELECTEDVALUE` matches slicer values exactly.

### Ranking, Top-N, and Percent-of-Total

**Decision**: `Measure for Rank` switches sign/metric via `SWITCH(TRUE())` on `SELECTEDVALUE('Rank Sort Measure'[Selection])`; `Rank` = `RANKX(ALLSELECTED(Orders[Base Part]), [Measure for Rank], , DESC, Skip)` (standard **competition** ties — `Skip`, NOT dense, per Clarification); `Order $ (Percent of Total)` = `DIVIDE([Total Order $], CALCULATE([Total Order $], ALLSELECTED()))`; `Rank Filter Flag` = `IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value], 10), 1, 0)` applied as a visual-level filter for Top-N row limiting.

**Rationale**: `RANKX` over `ALLSELECTED` respects visual filters while ignoring the rank scope; `Skip` ties are deterministic (Clarification 2026-06-05). `DIVIDE` with no fallback returns BLANK() on a zero/blank denominator (FR-011/SC-007). No measure is referenced inside a `CALCULATE` boolean filter (constitution §3).

### TMDL Syntax (from `plugins/pbip/skills/tmdl/SKILL.md`)

Tab-based semantic indentation (one tab per level); `///` descriptions immediately precede the declaration; only quote names with spaces/special chars/leading digits (so `Order $ (USD)`, `Rows Displayed`, `Rank Sort Measure`, `Sub-Family`, `Gender/Stature/Type` ARE quoted); measure DAX bodies indented under the declaration with `formatString` following; `summarizeBy: none` on text/key attributes; `DimDate` marked as date table; `MonthName` Sort-By `Month`; unique `lineageTag` GUIDs for every object.

### PBIR Report Format (from `plugins/pbip/skills/pbir-format/SKILL.md`)

Minimal `report.json` (`$schema` + `themeCollection` + `settings`). Each `visualContainer/2.4.0` carries only `$schema`, `name`, `position`, `visual` — **no** `filters`/`filterConfig` at the visual root (PBI Desktop rejects undefined root properties). Top-N filtering is realized via the `Rank Filter Flag` measure as a visual-level filter configured in Desktop, not in JSON. Page folder names match `^[\w-]+$` (`LaunchReportDashboard`, `DeliverySeasonSummary`, `DataDetail`).

**Output**: research.md (all NEEDS CLARIFICATION resolved — none remain; spec is fully clarified).

---

## Phase 1: Design & Contracts

### Tables (data-model.md)

| Table | Source | Role | Grain |
|-------|--------|------|-------|
| `Orders` | `Q3LaunchData 1.csv` (M query) | Single wide source table + measures host | One row per item / order line |
| `DimDate` | DAX `CALENDAR` | Date dimension (Mark as Date Table) | One row per day |
| `Rows Displayed` | DAX `DATATABLE` | Disconnected Top-N parameter | One row per choice (5) |
| `Rank Sort Measure` | DAX `DATATABLE` | Disconnected rank metric/direction parameter | One row per choice (4) |

### Orders Columns (logical role dimensions via Display Folders)

- **Order measure columns (numeric, aggregated by measures)**: `Order $ (USD)`, `Order $ (U.S. Cost)`, `Order $ (U.S. Dealer Net)`, `Order $ (U.S. MSRP)`, `Cost`, `Dnet`, `MSRP`, `Margin $` (Decimal); `Order Quantity`, `Sum of Quantity (Units)`, `Sum of Extra Quantity (Units)` (Int64).
- **Delivery Timing** (folder): `Date` (date, FK → `DimDate[Date]`), `Delivery Date` / `Delivery Month` / `Delivery Season` (text), `Year` / `Month` (Int64).
- **Product** (folder): `Item Code`, `Base Part`, `Base Part Number`, `Base Style`, `Base Style Name`, `Style`, `Style Code`, `Style Description`, `Category`, `Product Category`, `Family`, `Product Family`, `Sub-Family`, `Product Sub-Family`, `Gender`, `Product Gender`, `Gender/Stature/Type`, `Garment Type`, `Color`, `Collection`, `Reorder Type` (text); `Global` (text, hidden constant); `Master Style` (DAX calc col).
- **Geography** (folder): `Macro Area`, `Micro Area`, `Sales Area` (text, no data category); `Region` (DAX calc col, no data category).

### DimDate Columns

`Date` (date, key, mark-as-date) · `Year` (Int64) · `Quarter` (Int64) · `Month` (Int64) · `MonthName` (text, Sort-By `Month`) · `Day` (Int64).

### Relationship

| From (Many) | To (One) | Key | Cardinality | Direction | Active |
|-------------|----------|-----|-------------|-----------|--------|
| `Orders[Date]` | `DimDate[Date]` | date | Many-to-One | Single (Dim → Fact) | Yes |

Both parameter tables remain **disconnected** (no relationships).

### Measures (18, host: `Orders`)

| # | Measure | Folder | Format | Pattern |
|---|---------|--------|--------|---------|
| 1 | Total Order $ | Order Metrics | `\$#,##0` | `SUM(Orders[Order $ (USD)])` |
| 2 | Total Order Quantity | Order Metrics | `#,##0` | `SUM(Orders[Order Quantity])` |
| 3 | Total Cost | Order Metrics | `\$#,##0` | `SUM(Orders[Cost])` |
| 4 | Total Dnet | Order Metrics | `\$#,##0` | `SUM(Orders[Dnet])` |
| 5 | Total MSRP | Order Metrics | `\$#,##0` | `SUM(Orders[MSRP])` |
| 6 | Total Margin $ | Order Metrics | `\$#,##0` | `SUM(Orders[Margin $])` |
| 7 | Total Extra Quantity | Order Metrics | `#,##0` | `SUM(Orders[Sum of Extra Quantity (Units)])` |
| 8 | Total Quantity Units | Order Metrics | `#,##0` | `SUM(Orders[Sum of Quantity (Units)])` |
| 9 | Total Order $ (U.S. Cost) | Order Metrics | `\$#,##0` | `SUM(Orders[Order $ (U.S. Cost)])` |
| 10 | Total Order $ (U.S. Dealer Net) | Order Metrics | `\$#,##0` | `SUM(Orders[Order $ (U.S. Dealer Net)])` |
| 11 | Total Order $ (U.S. MSRP) | Order Metrics | `\$#,##0` | `SUM(Orders[Order $ (U.S. MSRP)])` |
| 12 | Margin % | Order Metrics | `0.00%` | `DIVIDE([Total Margin $], [Total Order $])` |
| 13 | Style Count | Style Analysis | `#,##0` | `DISTINCTCOUNT(Orders[Master Style])` |
| 14 | Measure for Rank | Ranking & Top-N | `#,##0` | `SWITCH(TRUE(), …)` over `SELECTEDVALUE('Rank Sort Measure'[Selection])` (hidden sort helper) |
| 15 | Rank | Ranking & Top-N | `#,##0` | `RANKX(ALLSELECTED(Orders[Base Part]), [Measure for Rank], , DESC, Skip)` |
| 16 | Rank (Order $) | Ranking & Top-N | `#,##0` | `RANKX(ALLSELECTED(Orders[Base Part]), [Total Order $], , DESC, Skip)` |
| 17 | Order $ (Percent of Total) | Ranking & Top-N | `0.00%` | `DIVIDE([Total Order $], CALCULATE([Total Order $], ALLSELECTED()))` |
| 18 | Rank Filter Flag | Ranking & Top-N | `0` | `IF([Rank] <= SELECTEDVALUE('Rows Displayed'[Value], 10), 1, 0)` |

### Calculated Columns (2, host: `Orders`)

| Column | DAX | Purpose |
|--------|-----|---------|
| `Master Style` | `LEFT(Orders[Style Code], 8)` | Row-level grouping grain for `Style Count` (`DISTINCTCOUNT`) |
| `Region` | `IF(Orders[Sales Area]="Canada","Canada", IF(Orders[Sales Area]="United States of America","USA", Orders[Macro Area]))` | Geography rollup slicer/axis (preserves Tableau IF/ELSEIF logic) |

Both are columns (not measures) because they define row-level groupings.

### Contracts

N/A for an external API/CLI — PBIP is file-based output. The "contract" is the PBIP folder structure + TMDL parse validity + PBIR schema compliance, validated by `tmdl-validate` and `validate_pbip.py` (see contracts/ for the structural property-order/quoting/required-field rules).

### Agent Context Update

Update the plan reference between the `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers in `.github/copilot-instructions.md` so the SPECKIT block continues to point at the current plan. **This plan keeps the path `specs/001-sales-customer-pbi/plan.md` referenced by that block intact** — if the active feature is switched to this workbook, repoint the marker to `specs/004-q3-dealer-buying-event-pbi/plan.md`; otherwise leave the existing pointer untouched so the block keeps resolving.

**Output**: data-model.md, quickstart.md, research.md, contracts/, updated agent context. Re-check of Constitution gates after design: **ALL PASS** (no new violations introduced).

---

## Phase 2: Implementation Plan

### File Generation Manifest

```
Output/Q3DealerBuyingEvent/
├── Q3DealerBuyingEvent.pbip
├── Q3DealerBuyingEvent.SemanticModel/
│   ├── definition.pbism
│   ├── .platform
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl
│       ├── model.tmdl
│       ├── relationships.tmdl
│       └── tables/
│           ├── Orders.tmdl
│           ├── DimDate.tmdl
│           ├── Rows Displayed.tmdl
│           └── Rank Sort Measure.tmdl
└── Q3DealerBuyingEvent.Report/
    ├── definition.pbir
    ├── .platform
    └── definition/
        ├── report.json
        ├── version.json
        └── pages/
            ├── pages.json
            ├── LaunchReportDashboard/{page.json, visuals/}
            ├── DeliverySeasonSummary/{page.json, visuals/}
            └── DataDetail/{page.json, visuals/}
```

### Build Sequence (model-first, then report, with validation gates)

#### Stage A — Semantic Model

1. **Project scaffold**: `Q3DealerBuyingEvent.pbip` (byPath reference), `.platform` files (SemanticModel + Report), `definition.pbism` (`version` + empty `settings` only), `definition.pbir` (byPath binding to the semantic model), `diagramLayout.json`.
2. **database.tmdl**: `compatibilityLevel: 1567` (TMDL, not TMSL — file starts with bare `database`).
3. **model.tmdl**: culture `en-US`, `defaultPowerBIDataSourceVersion: powerBI_V3`, `ref table` for `Orders`, `DimDate`, `Rows Displayed`, `Rank Sort Measure`; `DimDate` mark-as-date-table annotation.
4. **tables/Orders.tmdl**: M partition (`Csv.Document` for `Q3LaunchData 1.csv` per the Phase 0 data-handling rules), 42 typed source columns, 2 DAX calculated columns (`Master Style`, `Region`), `Global` hidden, all 18 measures with display folders + format strings (`Measure for Rank` hidden). Geography columns get no data category.
5. **tables/DimDate.tmdl**: calculated-table partition (`CALENDAR` + `ADDCOLUMNS`), 6 columns, `MonthName` Sort-By `Month`, marked as date table on `Date`.
6. **tables/Rows Displayed.tmdl** + **tables/Rank Sort Measure.tmdl**: disconnected `DATATABLE` calculated tables (Int64 `Value`; text `Selection`).
7. **relationships.tmdl**: single relationship `Orders[Date]` → `DimDate[Date]`, `manyToOne`, single direction, active.

#### Stage B — Model Validation (GATE — run before report)

8. `tmdl-validate` on the `definition` folder → fix any syntax/indentation/property-order issues.
9. `validate_pbip.py` on `Output/Q3DealerBuyingEvent/` → fix any exit-code-2 errors before proceeding.

#### Stage C — Report Pages

10. Generate `report.json` (minimal PBIR enhanced template), `version.json`, `pages.json`, and the three page folders (16:9, 1280×720) with their visuals, the `Rows Displayed` and `Rank Sort Measure` slicers, and Category/Family/Gender/Region/Color filters. Each visual: title shown, 1px `#E0E0E0` border, alt text, projections `active: true`, 25px edge padding / 20px gaps.

#### Stage D — Final End-to-End Validation (GATE)

11. Re-run JSON validity on `.Report/`, `tmdl-validate` on the model, and `validate_pbip.py` on the project root. Fix all errors (exit code 2 blocks progression).

### Report Page Inventory

| Page (1280×720) | Visuals | Shared controls |
|---|---|---|
| **Launch Report Dashboard** | Overview KPI cards (Total Order $, Total Order Quantity, Style Count, Margin %); top-parts rank table (`Base Part` × Total Order $, Rank, Order $ % of Total) with `Rank Filter Flag = 1` visual filter; category/region breakdowns (by Category, Family, Gender, Macro Area, Region, Color) | `Rows Displayed` slicer; `Rank Sort Measure` slicer; Category / Family / Gender / Region / Color filters |
| **Delivery Season Summary** | Order measures by `Delivery Season` (and `Delivery Month`); season/month trend over `DimDate`; folds in the two Tableau "Slide View" presentation variants | Same shared controls |
| **Data Detail** | Full item-level order table (Item Code, Style, Category, Region, Delivery Season + order/margin/quantity measures) | Same shared controls |

The 49 worksheets and 5 dashboards (incl. the two "Slide View" variants) consolidate into these three non-redundant pages (FR-013); final exact visuals are decided at the report-visual stage.

---

## Implementation Notes

1. **M query path & binding**: Use the absolute CSV path under `Data\Q3 Buyer\Q3LaunchData 1.csv` (Technical Context) via `Csv.Document(File.Contents(...))`. Never reference the absent TWB Excel path. Keep the partition independent — no references to other queries/tables.
2. **Data-handling order in M**: `Source` → `PromoteHeaders` → `RemoveColumns` (6 trailing-space aliases + `Measure for Rank` + `Style Count` + source `Region` + source `Master Style`) → `TransformColumnTypes(..., "en-US")`. Recreate `Master Style` and `Region` as DAX calculated columns afterward.
3. **DimDate**: DAX `CALENDAR` calculated table (not M) — self-derives the range from `Orders[Date]`; mark as date table on `Date`; `MonthName` Sort-By `Month`.
4. **Disconnected parameters**: `Rows Displayed` (Int64 `Value`: 5/10/20/50/10000, default 10) and `Rank Sort Measure` (text `Selection`: 4 values, default "Order $ (Decending)"). NO relationships; consumed via `SELECTEDVALUE`; never filter `Orders` directly.
5. **Ranking**: `RANKX(ALLSELECTED(Orders[Base Part]), …, DESC, Skip)` — competition ties (NOT dense). Swap `Orders[Base Part]` for the entity the visual ranks (e.g. `Orders[Master Style]`, `Orders[Style]`) if a different grain is ranked.
6. **Top-N**: apply `Rank Filter Flag = 1` as a visual-level filter in Desktop (not in PBIR JSON) to realize row limiting. `10000` = "All".
7. **DIVIDE everywhere**: `Margin %` and `Order $ (Percent of Total)` use `DIVIDE()` with no fallback → BLANK() on a zero/blank denominator.
8. **Boolean filters**: never reference a measure inside a `CALCULATE` boolean filter (constitution §3) — the sort switch uses `SWITCH(TRUE())` over `SELECTEDVALUE`, not `CALCULATE` filters.
9. **TMDL quoting**: quote names with spaces/special chars/leading digits — `Order $ (USD)`, `Order $ (U.S. Cost)`, `Sum of Quantity (Units)`, `Sub-Family`, `Gender/Stature/Type`, `Rows Displayed`, `Rank Sort Measure`. Unquoted: `Orders`, `DimDate`, `Style`, `Color`.
10. **lineageTag**: generate unique GUIDs for every table, column, measure, and relationship.
11. **report.json minimalism**: keep `report.json` to `$schema` + `themeCollection` + `settings`; `visual.json` root limited to `$schema`/`name`/`position`/`visual` — no `filters`/`filterConfig` at the root.
12. **copilot-instructions SPECKIT block**: this plan file is the target of the SPECKIT pointer in `.github/copilot-instructions.md`; do not break that marker block — only repoint it when this workbook becomes the active feature.

---

## Validation Strategy

| Stage | Command | Pass criterion |
|---|---|---|
| Model (TMDL) | `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.SemanticModel\definition"` | No syntax/structural errors |
| Project (PBIP) | `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\Q3DealerBuyingEvent"` | Exit code 0 or 1 (no code 2) |
| Report JSON | `Get-ChildItem "Output\Q3DealerBuyingEvent\Q3DealerBuyingEvent.Report" -Recurse -Include "*.json","*.pbir" \| % { Get-Content $_.FullName -Raw \| ConvertFrom-Json \| Out-Null }` | All JSON parses |
| End-to-end | `validate_pbip.py` on the project root | Exit code 0 or 1 |

Errors at any gate are fixed before advancing; exit code 2 (errors) blocks progression.

---

## Artifacts Generated

| Artifact | Path | Purpose |
|----------|------|---------|
| Plan | `specs/004-q3-dealer-buying-event-pbi/plan.md` | This file |
| Research | `specs/004-q3-dealer-buying-event-pbi/research.md` | M / TMDL / DimDate / parameter / PBIR decisions |
| Data Model | `specs/004-q3-dealer-buying-event-pbi/data-model.md` | Tables, columns, relationship, 18 measures, 2 calc columns |
| Quickstart | `specs/004-q3-dealer-buying-event-pbi/quickstart.md` | Build + validation walkthrough |
| Analysis source | `.specify/memory/Q3DealerBuyingEvent/tableau-analysis-output.md` | Upstream TWB analysis input |
| DAX source | `.specify/memory/Q3DealerBuyingEvent/dax-measures-output.md` | Upstream measure / calc-column input |
| Star schema source | `.specify/memory/Q3DealerBuyingEvent/star-schema-output.md` | Upstream table/relationship design input |
| Contracts | `specs/004-q3-dealer-buying-event-pbi/contracts/` | PBIP/TMDL/PBIR structural contracts (no external API) |

---

## Complexity Tracking

No constitution violations — no entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | — | — |

---

## Success Gate

Implementation is complete when:

1. All files generated in `Output/Q3DealerBuyingEvent/` per the manifest.
2. `tmdl-validate` exits with code 0 (zero TMDL errors — SC-009).
3. `validate_pbip.py` exits with code 0 or 1 (no code-2 errors — SC-009).
4. `.pbip` opens in Power BI Desktop without errors (SC-001), with `Orders` (all 1000 CSV rows, correct types, no trailing-space duplicate columns — SC-002/SC-003), a populated `DimDate` with the active `Orders[Date] → DimDate[Date]` relationship (SC-004), all 18 measures + 2 calc columns evaluating without error and reconciling to source totals (SC-005), the two disconnected parameters driving rank ordering and Top-N row limiting (SC-006), percent-of-total returning BLANK() on a zero denominator (SC-007), and currency/whole-number/percentage format strings applied (SC-008).
