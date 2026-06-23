# Implementation Plan: Midnight Census Dashboard — Tableau to Power BI Migration

**Branch**: `003-midnight-census-pbi` | **Date**: 2026-06-19 | **Spec**: [spec.md](spec.md)  
**Input**: `specs/003-midnight-census-pbi/spec.md`

## Summary

Migrate the Midnight Census Dashboard Tableau workbook to a Power BI PBIP project. The workbook is a single-CSV, 10-column healthcare census tracker with 5 disconnected parameter tables, 19 DAX measures, 1 active relationship (MidnightCensus → DimDate), and a two-page report (main interactive dashboard + Info splash). The technical approach is deterministic: emit TMDL and PBIR JSON using `scripts/pipeline.py generate` from a validated `decisions.json`, then run all three validators before delivery.

---

## Technical Context

**Language/Version**: Python 3.x (emit scripts) + Power BI PBIP / TMDL 1.0  
**Primary Dependencies**: `scripts/emit/emit_tmdl.py`, `scripts/emit/emit_pbir.py`, `scripts/pipeline.py`  
**Storage**: Single flat CSV — `Data/Midnight Census/Midnight_Census_Template.csv` (10 columns, UTF-8)  
**Testing**: `plugins/pbip/hooks/bin/tmdl-validate-windows-x64.exe` + `plugins/pbip/skills/pbip/scripts/validate_pbip.py` + `scripts/validate_semantics.py`  
**Target Platform**: Power BI Desktop (PBIP folder format, compatibility level 1567)  
**Project Type**: Semantic model + report (Power BI PBIP)  
**Performance Goals**: Model refresh < 60 seconds on CSV source; report page load < 5 seconds  
**Constraints**: No RLS, no incremental refresh, no composite model; single-file M query (no dataflow references)  
**Scale/Scope**: 1 fact table, 1 calculated date table, 5 disconnected parameter tables, 19 measures, 2 report pages, ~15 visual containers on main page

---

## Constitution Check

*The project constitution (`constitution.md`) is currently a blank template — no project-level principles have been ratified. Constitution checks pass by default; the pipeline's own validation gates (FR-019, FR-020, FR-021) serve as the governance layer.*

| Gate | Status | Notes |
|------|--------|-------|
| All functional requirements traceable to implementation tasks | PASS | FR-001–FR-021 each mapped to a task in tasks.md |
| No circular M-query references (single source) | PASS | Single CSV load; no cross-table M references |
| No RLS folder created | PASS | RLS not detected in source; `roles/` directory must NOT be created |
| Validators run before delivery | PASS (enforced) | Phase 3 is mandatory; errors block delivery |
| No calculated columns on fact table for param-derived logic | PASS (by design) | FR-009 explicitly forbids `Date Range Filter`, `Date agg_*`, `View_*` as calculated columns |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-midnight-census-pbi/
├── plan.md              ← This file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
└── tasks.md             ← /speckit.tasks output (NOT created by /speckit.plan)
```

### Output Artifacts (repository root)

```text
Output/MidnightCensusDashboard/
├── MidnightCensusDashboard.pbip
├── MidnightCensusDashboard.SemanticModel/
│   ├── .platform
│   ├── definition.pbism
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl
│       ├── model.tmdl
│       ├── relationships.tmdl
│       └── tables/
│           ├── MidnightCensus.tmdl          ← fact + 19 measures
│           ├── DimDate.tmdl                 ← CALENDAR(), mark as date table
│           ├── FilterAdultsPeds.tmdl        ← DATATABLE(3 rows)
│           ├── DateAggLevel.tmdl            ← DATATABLE(2 rows)
│           ├── View.tmdl                    ← DATATABLE(2 rows)
│           ├── StartDate.tmdl               ← GENERATESERIES
│           └── EndDate.tmdl                 ← GENERATESERIES
├── MidnightCensusDashboard.Report/
│   ├── .platform
│   ├── definition.pbir
│   └── definition/
│       ├── report.json
│       └── pages/
│           ├── MidnightCensus/
│           │   ├── page.json
│           │   └── visuals/
│           │       ├── slicer-date-agg-level/visual.json
│           │       ├── slicer-view/visual.json
│           │       ├── slicer-start-date/visual.json
│           │       ├── slicer-end-date/visual.json
│           │       ├── slicer-filter-adults-peds/visual.json
│           │       ├── slicer-parent-hospital/visual.json
│           │       ├── slicer-hospital/visual.json
│           │       ├── slicer-patient-class/visual.json
│           │       ├── slicer-unit/visual.json
│           │       ├── card-partial-data-warning/visual.json
│           │       ├── bar-monthly/visual.json
│           │       ├── bar-daily/visual.json
│           │       ├── table-monthly/visual.json
│           │       ├── table-daily/visual.json
│           │       └── card-last-refresh/visual.json
│           └── Info/
│               ├── page.json
│               └── visuals/
│                   └── textbox-info-content/visual.json
```

---

## Phase 0 — Research

**Goal**: Resolve all TMDL syntax questions and the table-naming discrepancy before writing any files.

### R-001 — Table Name Discrepancy (CRITICAL)

**Issue**: The DAX measures output references `Midnight_Census_Template[Census Count]` (the Tableau table name), but the star schema specifies the Power BI table name as `MidnightCensus`.

**Decision**: Use `MidnightCensus` as the Power BI table name (star schema is authoritative). All 19 DAX measure expressions must reference `MidnightCensus[...]`. The M query partition may retain `Midnight_Census_Template` internally as a step name — only the model-exposed table name matters.

**DAX references to update** (from dax-measures-output.md):

| Old reference | Corrected reference |
|--------------|-------------------|
| `Midnight_Census_Template[Census Count]` | `MidnightCensus[Census Count]` |
| `Midnight_Census_Template[Census Count Adults]` | `MidnightCensus[Census Count Adults]` |
| `Midnight_Census_Template[Census Count Peds]` | `MidnightCensus[Census Count Peds]` |
| `Midnight_Census_Template[Census Date]` | `MidnightCensus[Census Date]` |

### R-002 — TMDL Syntax: DATATABLE Parameter Tables

**Verified pattern**:

```tmdl
table 'Filter Adults Peds'
	isHidden
	isPrivate

	column 'Filter Adults/Peds Value'
		dataType: string
		sourceColumn: Filter Adults/Peds Value

	partition 'Filter Adults Peds-Partition' = dax
		mode: import
		source
			= DATATABLE(
				"Filter Adults/Peds Value", STRING,
				{
					{ "(All)" },
					{ "Adults" },
					{ "Peds" }
				}
			)

	annotation PBI_ResultType = Table
```

**Key rules**:
- `isHidden` + `isPrivate` — parameter tables do not appear in the field list
- DAX partition uses `= DATATABLE(...)` syntax (no `let..in`)
- `sourceColumn` must match the DATATABLE header string exactly
- Table/column names with spaces or `/` require single-quote quoting in TMDL

### R-003 — TMDL Syntax: GENERATESERIES Date Parameter Tables

**Verified pattern**:

```tmdl
table 'Start Date'
	isHidden
	isPrivate

	column 'Start Date'
		dataType: dateTime
		formatString: Short Date
		sourceColumn: Start Date

	partition 'Start Date-Partition' = dax
		mode: import
		source
			= GENERATESERIES(
				DATE( 2021, 1, 1 ),
				TODAY(),
				1
			)

	annotation PBI_ResultType = Table
```

**Key rules**:
- GENERATESERIES generates a `[Value]` column — rename via `sourceColumn: Start Date` mapping
- `dataType: dateTime` (not `date` — `date` is not a valid TMDL token)
- Both `Start Date` and `End Date` use the same GENERATESERIES range; only the column name differs

### R-004 — TMDL Syntax: DimDate Calculated Table + Mark as Date Table

**Verified pattern** (key annotations):

```tmdl
table DimDate

	column Date
		dataType: dateTime
		isKey
		formatString: Short Date
		sourceColumn: Date
		summarizeBy: none

	partition DimDate-Partition = dax
		mode: import
		source
			= CALENDAR( DATE( 2021, 1, 1 ), TODAY() )

	annotation PBI_ResultType = Table
	annotation __PBI_MarkAsDateTable_Column = Date
```

- `isKey` on `Date` column signals the date table key
- `annotation __PBI_MarkAsDateTable_Column = Date` enables time-intelligence (DATEADD, STARTOFMONTH, etc.)
- Without this annotation, `EOMONTH()` and `STARTOFMONTH()` in partial-data measures will not work correctly

### R-005 — TMDL Syntax: Computed Columns on DimDate

All columns beyond `Date` are computed columns using `columnType: calculated`:

```tmdl
column Year
	dataType: int64
	columnType: calculated
	expression = YEAR([Date])
	summarizeBy: none
```

**Rule**: No `sourceColumn` on computed columns — use `expression` instead.

### R-006 — Relationship TMDL Syntax

```tmdl
relationship MidnightCensus_CensusDate_DimDate_Date
	fromTable: MidnightCensus
	fromColumn: 'Census Date'
	toTable: DimDate
	toColumn: Date
	crossFilteringBehavior: singleCross
```

- `fromTable` = many-side (fact); `toTable` = one-side (dimension)
- `crossFilteringBehavior: singleCross` = single direction (DimDate → MidnightCensus)
- Cardinality defaults to many-to-one when from=many, to=one (key column)

### R-007 — CSV M Query Absolute Path

```powerquery
let
    Source = Csv.Document(
        File.Contents("C:\...\Data\Midnight Census\Midnight_Census_Template.csv"),
        [Delimiter=",", Columns=10, Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(
        #"Promoted Headers",
        {
            {"DEPARTMENT_KEY",      Int64.Type},
            {"Encounter CSN",       type text},
            {"Parent Hospital",     type text},
            {"Hospital",            type text},
            {"Unit",                type text},
            {"Patient Class",       type text},
            {"Census Date",         type date},
            {"Census Count",        Int64.Type},
            {"Census Count Adults", Int64.Type},
            {"Census Count Peds",   Int64.Type}
        }
    )
in
    #"Changed Type"
```

**Note**: `File.Contents()` requires an absolute path. The `decisions.json` carries a relative-path hint; the emit script must prepend the workspace root to construct the full path for the user's machine.

---

## Phase 1 — Design & Contracts

### Data Model

**Tables**:

| Table | Type | Partition Kind | Rows (approx) |
|-------|------|---------------|---------------|
| `MidnightCensus` | Fact | M (Csv.Document) | CSV row count |
| `DimDate` | Dimension | DAX (CALENDAR) | ~2000 (2021–today) |
| `Filter Adults Peds` | Parameter | DAX (DATATABLE) | 3 |
| `Date Agg Level` | Parameter | DAX (DATATABLE) | 2 |
| `View` | Parameter | DAX (DATATABLE) | 2 |
| `Start Date` | Parameter | DAX (GENERATESERIES) | ~2000 |
| `End Date` | Parameter | DAX (GENERATESERIES) | ~2000 |

**MidnightCensus columns** (all from CSV — no calculated columns):

| Column | TMDL dataType | Summarize | Role |
|--------|--------------|-----------|------|
| DEPARTMENT_KEY | int64 | none | Degenerate dimension |
| Encounter CSN | string | none | Degenerate dimension |
| Parent Hospital | string | none | Slicer attribute |
| Hospital | string | none | Slicer attribute |
| Unit | string | none | Slicer attribute |
| Patient Class | string | none | Slicer attribute |
| Census Date | dateTime | none | FK → DimDate[Date] |
| Census Count | int64 | sum | Base measure column |
| Census Count Adults | int64 | sum | Base measure column |
| Census Count Peds | int64 | sum | Base measure column |

**DimDate columns** (all `summarizeBy: none`, all `columnType: calculated` except `Date`):

| Column | dataType | Expression |
|--------|----------|------------|
| Date | dateTime | (CALENDAR source column — `isKey`) |
| DateKey | int64 | `YEAR([Date])*10000+MONTH([Date])*100+DAY([Date])` |
| Year | int64 | `YEAR([Date])` |
| Quarter | int64 | `QUARTER([Date])` |
| QuarterName | string | `"Q" & QUARTER([Date])` |
| YearQuarter | string | `FORMAT([Date],"YYYY") & " Q" & QUARTER([Date])` |
| Month | int64 | `MONTH([Date])` |
| MonthName | string | `FORMAT([Date],"MMMM")` |
| MonthShort | string | `FORMAT([Date],"MMM")` |
| YearMonth | string | `FORMAT([Date],"YYYY-MM")` |
| Day | int64 | `DAY([Date])` |
| DayOfWeek | int64 | `WEEKDAY([Date],2)` |
| DayOfWeekName | string | `FORMAT([Date],"dddd")` |
| WeekNumber | int64 | `WEEKNUM([Date],2)` |
| IsWeekend | boolean | `WEEKDAY([Date],2) >= 6` |
| StartOfMonth | dateTime | `DATE(YEAR([Date]),MONTH([Date]),1)` |
| EndOfMonth | dateTime | `EOMONTH([Date],0)` |

**Relationships**:

| From (many) | Column | To (one) | Column | Direction | Active |
|-------------|--------|----------|--------|-----------|--------|
| MidnightCensus | Census Date | DimDate | Date | Single (DimDate → MidnightCensus) | Yes |

*All 5 parameter tables are fully disconnected — no relationships.*

### Measures Inventory (19 total — all on `MidnightCensus` table)

**Display Folder: Parameters**

| # | Measure | Format | DAX summary |
|---|---------|--------|-------------|
| 1 | Selected Filter Adults/Peds | text | `SELECTEDVALUE('Filter Adults Peds'[Filter Adults/Peds Value], "(All)")` |
| 2 | Selected Date Agg Level | text | `SELECTEDVALUE('Date Agg Level'[Date Agg Level Value], "Monthly")` |
| 3 | Selected View | text | `SELECTEDVALUE('View'[View Value], "Bar Chart")` |
| 4 | Selected Start Date | Short Date | `COALESCE(SELECTEDVALUE('Start Date'[Start Date]), STARTOFYEAR(TODAY()))` |
| 5 | Selected End Date | Short Date | `COALESCE(SELECTEDVALUE('End Date'[End Date]), TODAY()-1)` |

**Display Folder: Census Measures**

| # | Measure | Format | DAX summary |
|---|---------|--------|-------------|
| 6 | Total Census Count | #,0 | `SUM(MidnightCensus[Census Count])` |
| 7 | Total Census Count Adults | #,0 | `SUM(MidnightCensus[Census Count Adults])` |
| 8 | Total Census Count Peds | #,0 | `SUM(MidnightCensus[Census Count Peds])` |
| 9 | User Defined Census Count | #,0 | SWITCH on `'Filter Adults Peds'` → Total / Adults / Peds |
| 10 | Last Refresh Date | Short Date | `MAX(MidnightCensus[Census Date])` |
| 11 | Default Start Date | Short Date | `STARTOFYEAR(TODAY())` |
| 12 | Default End Date | Short Date | `TODAY()-1` |
| 13 | Start Month Contains Partial Data? | 0 | `IF(DAY(_startDate)<>1, 1, 0)` |
| 14 | End Month Contains Partial Data? | 0 | `IF(_endDate<>EOMONTH(_endDate,0), 1, 0)` |
| 15 | Partial Months in View? | text | Warning string or `""` |
| 16 | Is Monthly | 0 | `IF(SELECTEDVALUE('Date Agg Level'...)="Monthly", 1, 0)` |
| 17 | Is Daily | 0 | `IF(SELECTEDVALUE('Date Agg Level'...)="Daily", 1, 0)` |
| 18 | Is Bar Chart | 0 | `IF(SELECTEDVALUE('View'...)="Bar Chart", 1, 0)` |
| 19 | Is Data Table | 0 | `IF(SELECTEDVALUE('View'...)="Data Table", 1, 0)` |

### Report Page Design

**Page 1: MidnightCensus** (`displayName: "Midnight Census"`, `^[\w-]+$` compliant)

Canvas: 1366×768, 25px edge padding, 20px inter-visual gap, font: Segoe UI / Aptos 10pt.

| Zone | Visual type | Binding |
|------|-------------|---------|
| Control bar — Date Agg Level | Slicer (tile/horizontal) | `'Date Agg Level'[Date Agg Level Value]` |
| Control bar — View | Slicer (tile/horizontal) | `'View'[View Value]` |
| Control bar — Start Date | Slicer (date, Between) | `'Start Date'[Start Date]` |
| Control bar — End Date | Slicer (date, Between) | `'End Date'[End Date]` |
| Control bar — Filter Adults/Peds | Slicer (tile/horizontal) | `'Filter Adults Peds'[Filter Adults/Peds Value]` |
| Top filter — Parent Hospital | Slicer (vertical list) | `MidnightCensus[Parent Hospital]` |
| Top filter — Hospital | Slicer (vertical list) | `MidnightCensus[Hospital]` |
| Top filter — Patient Class | Slicer (vertical list) | `MidnightCensus[Patient Class]` |
| Left sidebar — Unit | Slicer (vertical list) | `MidnightCensus[Unit]` |
| Warning strip | Card | `[Partial Months in View?]` |
| Primary — bar-monthly | Clustered bar chart | X: `DimDate[YearMonth]`, Y: `[User Defined Census Count]` |
| Primary — bar-daily | Clustered bar chart | X: `DimDate[Date]`, Y: `[User Defined Census Count]` |
| Primary — table-monthly | Table | Rows: `DimDate[YearMonth]`, `MidnightCensus[Hospital]`, `MidnightCensus[Unit]`; Value: `[User Defined Census Count]` |
| Primary — table-daily | Table | Rows: `DimDate[Date]`, `MidnightCensus[Hospital]`, `MidnightCensus[Unit]`; Value: `[User Defined Census Count]` |
| Bottom — Last Refresh | Card | `[Last Refresh Date]`; subtitle: "Refreshes Daily 2:00 AM" (static) |

**Visibility strategy for the 4 toggled visuals**: Use visual-level filters in `filterConfig` referencing the `Is*` measures. Each visual is filtered to only render when its corresponding measure = 1. If visual-level measure filters are rejected by PBIR schema validation, fall back to documenting a manual bookmark setup in `quickstart.md`.

**Page 2: Info** (`displayName: "Info"`, page name `Info` — `^[\w-]+$` compliant)

- Single TextBox visual, no data bindings
- Content: Title "Patient Days — Midnight Census", General Description, Content/Definitions, Source (CDW-H / custom SQL from ADT, ENCOUNTER, LOCATION, PATIENT masters), Contacts (Austin Gilmore, BI Analyst), Refresh schedule (Daily 08:30 AM)

### PBIP Root File Contracts

**`MidnightCensusDashboard.pbip`**:
```json
{
  "version": "1.0",
  "artifacts": [
    { "report": { "byPath": "MidnightCensusDashboard.Report" } }
  ],
  "settings": { "enableAutoRecovery": true }
}
```

**`MidnightCensusDashboard.Report/definition.pbir`**:
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/1.0.0/schema.json",
  "version": "1.0",
  "datasetReference": {
    "byPath": { "path": "../MidnightCensusDashboard.SemanticModel" }
  }
}
```

**`MidnightCensusDashboard.SemanticModel/definition.pbism`**:
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definition/1.0.0/schema.json",
  "version": "1.0"
}
```

---

## Phase 2 — Implementation Order

Executed by the `pbip-generator` subagent using `scripts/pipeline.py generate`. Tasks are defined in `tasks.md`.

| Step | Artifact | Depends on |
|------|----------|-----------|
| 1 | `decisions.json` | analysis.json + dax-measures-output.md + star-schema-output.md |
| 2 | `.platform` files (SemanticModel + Report) | decisions.json |
| 3 | `definition.pbism` + `MidnightCensusDashboard.pbip` + `definition.pbir` | decisions.json |
| 4 | `database.tmdl` | decisions.json |
| 5 | `model.tmdl` | database.tmdl |
| 6 | `relationships.tmdl` | MidnightCensus.tmdl + DimDate.tmdl |
| 7 | `tables/MidnightCensus.tmdl` | R-007 (M query pattern), all 19 measures (R-001 corrections applied) |
| 8 | `tables/DimDate.tmdl` | R-004 + R-005 patterns |
| 9 | `tables/FilterAdultsPeds.tmdl` | R-002 pattern |
| 10 | `tables/DateAggLevel.tmdl` | R-002 pattern |
| 11 | `tables/View.tmdl` | R-002 pattern |
| 12 | `tables/StartDate.tmdl` | R-003 pattern |
| 13 | `tables/EndDate.tmdl` | R-003 pattern |
| 14 | **Run tmdl-validate** | All .tmdl files complete |
| 15 | `report.json` | decisions.json |
| 16 | `pages/MidnightCensus/page.json` | report.json |
| 17 | `pages/MidnightCensus/visuals/*.json` (15 visuals) | page.json + all table/measure names confirmed |
| 18 | `pages/Info/page.json` | report.json |
| 19 | `pages/Info/visuals/textbox-info-content/visual.json` | page.json |
| 20 | **Run validate_pbip.py** | All files complete |
| 21 | **Run validate_semantics.py** | All TMDL files complete |

### Key Implementation Risks

| Risk | Mitigation |
|------|-----------|
| `File.Contents()` absolute path breaks on other machines | Document path-update step in `quickstart.md`; use workspace-relative hint in `decisions.json` |
| DimDate computed columns need `columnType: calculated` + `expression` (not `sourceColumn`) | Confirmed in R-005; enforce during TMDL authoring |
| GENERATESERIES column rename from `[Value]` to named column | Use `sourceColumn` mapping in TMDL column definition (confirmed in R-003) |
| `Partial Months in View?` returns `""` — card may show blank tile | Acceptable; empty string = no warning shown. No error state |
| Visual-level measure filters may not be supported in PBIR schema | Test in Power BI Desktop; fallback: document bookmark setup in quickstart.md |
| `Census Date` stored as dateTime but source is date | Use `formatString: Short Date` on the column; no data loss |

---

## Phase 3 — Validation

Run all validators in sequence. **Errors block delivery — fix and re-run; do not skip.**

### Step 1 — TMDL Structural Syntax

```powershell
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" `
  "Output\MidnightCensusDashboard\MidnightCensusDashboard.SemanticModel\definition"
```

Expected: zero errors. Fix indentation, quoting, or property-order violations before proceeding.

### Step 2 — Cross-Cutting PBIP Validation

```powershell
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" `
  "Output\MidnightCensusDashboard"
```

Expected: exit code 0. Exit code 2 = blocking errors. Checks: `.pbip` root, `.platform` files, `definition.pbir` byPath target, page name regex (`MidnightCensus` and `Info` both comply), orphan pages, semantic model format detection.

### Step 3 — Semantic Consistency

```powershell
python "scripts\validate_semantics.py" `
  "Output\MidnightCensusDashboard\MidnightCensusDashboard.SemanticModel"
```

Checks: measure expression parse errors, dangling table references, column name mismatches, relationship column existence.

### Step 4 — Report JSON Syntax

```powershell
Get-ChildItem "Output\MidnightCensusDashboard\MidnightCensusDashboard.Report" `
  -Recurse -Include "*.json","*.pbir" | ForEach-Object {
    try   { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null }
    catch { Write-Error "Invalid JSON: $($_.FullName) — $_" }
  }
```

### Step 5 — Manual Smoke Test (Power BI Desktop)

1. Open `Output/MidnightCensusDashboard/MidnightCensusDashboard.pbip`
2. Update CSV path in Power Query to local absolute path → Refresh
3. Verify row count matches `Midnight_Census_Template.csv` (SC-002)
4. Verify all 19 measures resolve without DAX errors (FR-019)
5. Test `Filter Adults/Peds = Adults` → totals match CSV SUM of `Census Count Adults` (SC-003)
6. Set `Start Date` to the 15th of a month → partial data warning appears (SC-004)
7. Set `Start Date` = 1st, `End Date` = last day of same month → no warning (SC-004)
8. Verify `Last Refresh Date` card shows a date and "Refreshes Daily 2:00 AM" caption (FR-018)

### Acceptance Criteria Traceability

| Success Criterion | Validated By |
|-------------------|-------------|
| SC-001: Opens without errors < 30s | Smoke test step 1 |
| SC-002: Row count matches CSV | Smoke test step 3 |
| SC-003: Adults filter totals correct | Smoke test step 5 |
| SC-004: Partial-month warning correct | Smoke test steps 6–7 |
| FR-019: No broken measures/sources | tmdl-validate + validate_pbip.py + smoke test |
| FR-020: Zero TMDL errors | tmdl-validate exit code 0 |
| FR-021: PBIR schema passes | validate_pbip.py exit code 0 |

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| 5 disconnected parameter tables (DATATABLE / GENERATESERIES) | Faithful reproduction of Tableau's 5 interactive parameters; required by FR-010–FR-013 | Hardcoded filters cannot replicate the slicer-driven SWITCH logic in `User Defined Census Count` |
| DimDate calculated table (17 columns) | FR-003 + time-intelligence for partial-month detection; EOMONTH/STARTOFMONTH require a marked date table | Storing date columns on the fact table prevents `__PBI_MarkAsDateTable` and breaks DAX time-intelligence functions |
| 4 visibility-toggle measures (Is Monthly, Is Daily, Is Bar Chart, Is Data Table) | FR-015/FR-016 require conditional visual display; measures provide a programmatic hook for visual-level filters | Bookmarks alone cannot be generated deterministically from code during the emit phase |
