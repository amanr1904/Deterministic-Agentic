# Implementation Plan: Sales & Customer Dashboards — Tableau to Power BI Migration

**Branch**: `001-sales-customer-pbi` | **Date**: 2026-06-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-sales-customer-pbi/spec.md`

## Summary

Migrate the Tableau **Sales & Customer Dashboards** workbook into a complete Power BI Project (`.pbip`) — semantic model (TMDL) plus report (PBIR). The source is a 4-table, semicolon-delimited, en_DE-locale CSV datasource (Orders + Customers + Location + Products). The migration builds an Import-mode star schema (`Orders` fact + 3 dimensions), a DAX-generated `DimDate`, and a disconnected `Select Year` parameter table that is the sole authority for Current Year / Prior Year. It implements **36 explicit DAX measures** (CY/PY pairs, % Diff, KPI window analogs, Min/Max, LOD analogs, base helpers) and reproduces the two 1200×800 dashboards (Sales Dashboard + Customer Dashboard) as PBIR report pages with their KPI trend charts, Subcategory Comparison, Weekly Trends, Customer Distribution, Top Customers, legends, the Select Year slicer, and Category/Sub-Category/Region/State/City filters. The three unused `Test*` worksheets are excluded. All artifacts land in `Output/SalesCustomerDashboards/` and are gated by the PBIP/TMDL validators.

## Technical Context

**Language/Version**: Power BI Project (PBIP) — TMDL (Tabular Model Definition Language) for the model, PBIR (enhanced report folder format) JSON for the report; Power Query M for ingestion; DAX for measures and the date/parameter tables
**Primary Dependencies**: Power BI Desktop (June 2024+ with PBIP/TMDL/PBIR preview enabled); `Csv.Document` connector; VertiPaq (Import storage)
**Storage**: Import mode (in-memory VertiPaq) over 4 local CSV files in `Data/Sales and Customer/`
**Testing**: `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` (TMDL structural lint) + `plugins/pbip/skills/pbip/scripts/validate_pbip.py` (cross-cutting PBIP/PBIR validation); manual open-in-Desktop smoke test per `quickstart.md`
**Target Platform**: Power BI Desktop / Power BI Service (Import semantic model + interactive report)
**Project Type**: Single deliverable — PBIP project (semantic model + report) under `Output/SalesCustomerDashboards/`
**Performance Goals**: Model loads without schema/relationship errors; ~10k Orders rows + small dimensions → sub-second visual evaluation; single-direction relationships for query efficiency
**Constraints**: en_DE decimal parsing (`,` decimal / `.` thousands) via the `"de-DE"` culture argument of `Table.TransformColumnTypes`; encodings 65001 (Orders, Location) and 1252 (Customers, Products); no measure inside a `CALCULATE` boolean filter; PBIR `visual.json` root limited to `$schema`/`name`/`position`/`visual`; `report.json` must use the minimal enhanced template (no `sections`, `modelExtensions`, `publicCustomVisuals`)
**Scale/Scope**: 6 tables, 4 active relationships (+1 optional inactive Ship Date), 36 measures, 2 report pages (12 dashboard-used worksheets), 0 unused worksheets carried over

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md`:

| Constitution Rule | Plan Compliance | Status |
|---|---|---|
| §0 Single-Table Rule | Source has **4 joined tables** → star-schema decomposition is correct (not single-table) | PASS |
| §1 Star Schema (multi-table) | `Orders` fact + `Customers`/`Location`/`Products` dims; natural keys (Customer ID, Postal Code, Product ID); `DimDate` generated; no snowflaking | PASS |
| §2 Naming Conventions | Unprefixed source tables (`Orders`, `Customers`, `Location`, `Products`) per spec FR-002/003 + DAX refs; `DimDate`, `Select Year` descriptive; columns keep source names; measures Title Case | PASS |
| §3 DAX Standards | Measures over calc columns; VAR/RETURN; `DIVIDE()` everywhere; SELECTEDVALUE for parameter; ALLSELECTED/AVERAGEX-MAXX-MINX for WINDOW; ALLEXCEPT/REMOVEFILTERS for LOD; display folders + format strings | PASS |
| §4 Relationships | All 1:many, single direction Dim→Fact; one active date path (Order Date), Ship Date inactive (USERELATIONSHIP on demand); no bidirectional | PASS |
| §5 M Query | `Csv.Document` + `QuoteStyle.Csv` + `Delimiter=";"` + explicit encodings; each table loads independently (no cross-query joins); `"de-DE"` culture typing | PASS |
| §6 Performance | Import mode; minimal calc columns (date attrs in DAX table only); single-direction filters | PASS |
| §7 Parameter Migration | `Select Year` integer list → disconnected `DATATABLE` + `SELECTEDVALUE` | PASS |
| §8 PBIP Output Structure | Standard `.pbip` + `.SemanticModel/` (TMDL) + `.Report/` (PBIR); minimal `report.json` template | PASS |
| §9 Report Visual Layer | 25px edge / 20px gap, borders, titles, alt text, professional theme; no grey gaps/overlaps | PASS |
| §10 Validation Checklist | tmdl-validate + validate_pbip.py gates at model, report, and end-to-end stages | PASS |

**Gate result**: PASS — no violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-sales-customer-pbi/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 — technical decisions
├── data-model.md        # Phase 1 — tables, columns, relationships, measures
├── quickstart.md        # Phase 1 — open + validate walkthrough
├── contracts/
│   └── pbip-contracts.md # Phase 1 — PBIP/TMDL/PBIR structural contracts
├── spec.md              # Feature specification (input)
├── tasks.md             # /speckit.tasks output (separate command)
└── checklists/          # Quality checklists
```

### Source Code (repository root)

```text
Output/SalesCustomerDashboards/
├── SalesCustomerDashboards.pbip
├── SalesCustomerDashboards.SemanticModel/
│   ├── definition.pbism
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl
│       ├── model.tmdl
│       ├── relationships.tmdl
│       ├── expressions.tmdl          # (optional) shared M / culture expressions
│       └── tables/
│           ├── Orders.tmdl           # fact (M partition, hidden FKs, measure cols)
│           ├── Customers.tmdl        # dim
│           ├── Location.tmdl         # dim (geo data categories)
│           ├── Products.tmdl         # dim
│           ├── DimDate.tmdl          # DAX CALENDAR calculated table, marked as date table
│           └── Select Year.tmdl      # disconnected DATATABLE parameter
└── SalesCustomerDashboards.Report/
    ├── definition.pbir
    └── definition/
        ├── report.json               # minimal enhanced template
        ├── version.json
        └── pages/
            ├── pages.json
            ├── SalesDashboard/        # page name ^[\w-]+$
            │   ├── page.json
            │   └── visuals/{visual}/visual.json
            └── CustomerDashboard/
                ├── page.json
                └── visuals/{visual}/visual.json
```

**Structure Decision**: Single PBIP deliverable. The 36 measures are authored on the `Orders` fact table (base/CY/PY/% Diff/KPI/LOD); `DimDate` and `Select Year` are model-generated tables (DAX). Report pages are PBIR enhanced-format folders, one per dashboard, with `pages.json` naming the active page. Input CSVs stay in `Data/Sales and Customer/`; nothing is copied into `Output/`.

## Build Sequence

The migration executes strictly model-first, then report, with validation gates between stages:

1. **Model scaffolding** — `database.tmdl`, `model.tmdl` (culture, default measure table), `definition.pbism`, `diagramLayout.json`.
2. **Source tables** — `Orders.tmdl` (M partition, en_DE typing, hide `Row ID`/`Customer ID`/`Postal Code`/`Product ID`), `Customers.tmdl`, `Location.tmdl` (geo data categories: City→City, State→StateOrProvince, Country/Region→Country, Postal Code→PostalCode; **Region = no geo category**), `Products.tmdl`.
3. **Generated tables** — `DimDate.tmdl` (DAX `CALENDAR` over full calendar years of Order Date; columns Date/Year/Quarter/Month/MonthName/Day/DayOfWeek/WeekNum; MonthName Sort-By Month; mark as date table) and `Select Year.tmdl` (disconnected `DATATABLE` 2020–2023, default 2023).
4. **Measures** — 36 measures from [dax-measures-output.md](../../.specify/memory/SalesCustomerDashboards/dax-measures-output.md) with display folders + format strings (K-scaling `\$#,##0,"K"`, ▲/▼ `▲ 0.0%;▼ -0.0%`).
5. **Relationships** — `relationships.tmdl`: 4 active (Customers/Location/Products/DimDate→Orders, 1:many single-direction) + 1 optional inactive `DimDate[Date]→Orders[Ship Date]`.
6. **Model validation (GATE)** — run `tmdl-validate` on the `definition` folder + `validate_pbip.py` on the project; fix all errors before proceeding.
7. **Report scaffolding** — `definition.pbir` (byPath dataset reference), `report.json` (minimal enhanced template), `version.json`, `pages.json`.
8. **Report pages** — `SalesDashboard` and `CustomerDashboard` page folders (1200×800) with their visuals (below), Select Year slicer, and Category/Sub-Category/Region/State/City filters; exclude `Test KPI`, `Test KPI2`, `Test Max Min`.
9. **Final validation (GATE)** — JSON syntax check on `.Report/`, `tmdl-validate` re-run, and `validate_pbip.py` on the project root; fix any errors, then smoke-test per `quickstart.md`.

### Report Page Inventory

| Page (1200×800) | Visuals | Shared controls |
|---|---|---|
| **Sales Dashboard** | Legend KPI; KPI Sales / KPI Profit / KPI Quantity (line + circle marker, Month axis, Min/Max markers); Legend Subcategory; Subcategory Comparison (clustered bar, Sub-Category × CY/PY Sales + KPI CY Less PY ⬤); Weekly Trends (line, Week axis, CY/PY + KPI Avg flags) | Select Year slicer; Category / Sub-Category / Region / State / City filters; 2 page-nav buttons + 1 filter-toggle button |
| **Customer Dashboard** | Legend KPI; KPI Customers / KPI Sales Per Customers / KPI Orders (line + circle marker, Month axis); Customer Distribution (clustered column, Nr of Orders per Customers × distinct customers); Top Customers (table: Customer Name, CY Sales, CY Orders, last Order Date) | Same shared controls |

## Complexity Tracking

> No constitution violations — section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | — | — |

## Phase 0 — Outline & Research

All open questions from the spec were resolved in the 2026-06-05 clarification pass and captured in [research.md](research.md). Key decisions:

- **en_DE CSV parsing** → `Csv.Document` with `Delimiter=";"`, `QuoteStyle.Csv`, encodings 65001/1252, and `"de-DE"` culture typing.
- **CY/PY authority** → disconnected `Select Year` + `SELECTEDVALUE`; `DimDate` only supplies trend axes.
- **WINDOW_AVG/MAX/MIN** → `AVERAGEX`/`MAXX`/`MINX` over `ALLSELECTED(<axis>)` (week axis for KPI Avg, month axis for Min/Max).
- **LOD FIXED** → `CALCULATE` + `ALLEXCEPT` (CY-scoped order count) and `CALCULATE` + `REMOVEFILTERS` (grand-total CY Sales).
- **Divide-by-zero** → `DIVIDE()` with no fallback → BLANK().
- **Geo data categories** → applied per spec; Region intentionally uncategorized.

**Output**: research.md (all NEEDS CLARIFICATION resolved).

## Phase 1 — Design & Contracts

1. **Entities → [data-model.md](data-model.md)**: 6 tables (Orders fact; Customers/Location/Products dims; DimDate; Select Year), column types/roles, hidden FKs, geo categories, 4+1 relationships, and the 36-measure catalog with format strings and display folders.
2. **Contracts → [contracts/pbip-contracts.md](contracts/pbip-contracts.md)**: PBIP folder contract, TMDL property-order/quoting rules, PBIR `visual.json`/`page.json`/`report.json` required-field and forbidden-property contracts, and validator exit-code expectations.
3. **Agent context update**: point the plan reference between the `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers in `.github/copilot-instructions.md` to `specs/001-sales-customer-pbi/plan.md`.

**Output**: data-model.md, contracts/pbip-contracts.md, quickstart.md, updated agent context file.

## Validation Strategy

| Stage | Command | Pass criterion |
|---|---|---|
| Model (TMDL) | `& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\SalesCustomerDashboards\SalesCustomerDashboards.SemanticModel\definition"` | No syntax/structural errors |
| Project (PBIP) | `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"` | Exit code 0 (no errors) |
| Report JSON | `Get-ChildItem "Output\SalesCustomerDashboards\SalesCustomerDashboards.Report" -Recurse -Include "*.json","*.pbir" \| % { Get-Content $_.FullName -Raw \| ConvertFrom-Json \| Out-Null }` | All JSON parses |
| End-to-end | `validate_pbip.py` on project root | Exit code 0 |

Errors at any gate are fixed before advancing; exit code 2 (errors) blocks progression.
