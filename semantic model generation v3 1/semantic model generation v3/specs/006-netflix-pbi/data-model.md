# Data Model: Netflix Workbook Power BI Migration

Single-table semantic model (constitution §0). Two tables: `NetflixTitles` (base + measures host) and `DimDate` (generated date dimension). Source: `.specify/memory/NetflixAnalysis/star-schema-output.md`.

---

## Entity: NetflixTitles

- **Source**: `Data/Netflix/netflix_titles.csv` (UTF-8, comma-delimited, promoted headers) via Power Query M.
- **Grain**: One row per Netflix catalog title (`show_id`).
- **Role**: Central base table; hosts all DAX measures.

| Column | Data Type | summarizeBy | Hidden | Data Category | Notes |
|--------|-----------|-------------|--------|---------------|-------|
| `show_id` | Int64 | none | No | — | Degenerate grain key |
| `type` | String | none | No | — | Movie / TV Show slicer |
| `title` | String | none | No | — | Descriptive |
| `director` | String | none | No | — | Multi-value CSV (kept) |
| `cast` | String | none | No | — | Multi-value CSV (kept) |
| `country` | String | none | No | **Country/Region** | FR-011 — enables map visuals |
| `date_added` | DateTime | none | No | — | FK → DimDate[Date] (active, many side) |
| `release_year` | Int64 | none | No | — | Attribute (Do Not Summarize) |
| `rating` | String | none | No | — | Categorical slicer |
| `duration` | String | none | No | — | Mixed "min"/"Seasons" (kept as string) |
| `listed_in` | String | none | No | — | Genre, multi-value CSV (kept) |
| `description` | String | none | No | — | Descriptive |

**Validation rules**:
- All 12 source columns present and visible in Fields pane (FR-002, SC-003).
- `show_id`, `release_year` = Int64; `date_added` = DateTime; remaining = String (FR-005).
- Blank `director`/`cast`/`date_added` render as blank, not error (US1 AS3).

---

## Entity: DimDate

- **Source**: DAX `CALENDAR` calculated table (no CSV / no M query).
- **Grain**: One row per day.
- **Range**: `DATE(YEAR(MIN(date_added)),1,1)` → `DATE(YEAR(MAX(date_added)),12,31)` (full calendar-year boundaries).
- **Mark as Date Table**: Yes, on `Date`.

| Column | Data Type | Expression (within ADDCOLUMNS) |
|--------|-----------|--------------------------------|
| `Date` | DateTime | `CALENDAR(...)` row value (key) |
| `Year` | Int64 | `YEAR([Date])` |
| `Quarter` | Int64 | `QUARTER([Date])` |
| `Month` | Int64 | `MONTH([Date])` |
| `MonthName` | String | `FORMAT([Date], "MMMM")` — sort-by `Month` |
| `Day` | Int64 | `DAY([Date])` (day-of-month) |
| `DayOfWeek` | Int64 | `WEEKDAY([Date])` |

**Validation rules**:
- Contiguous, unique `Date` key (FR-002, FR-006).
- Supports time intelligence (TOTALYTD, SAMEPERIODLASTYEAR).

---

## Relationships

| From (Many) | To (One) | Key | Cardinality | Cross-Filter | Active |
|-------------|----------|-----|-------------|--------------|--------|
| `NetflixTitles[date_added]` | `DimDate[Date]` | DateTime | Many-to-One | Single (Dim → Base) | Yes |

- Only relationship in the model (FR-003, US2 AS3).
- Null `date_added` rows stay in `NetflixTitles` but are unmatched (blank key) — excluded from year trends (edge case / Tableau null filter).
- No bidirectional filtering, no role-playing date, no bridge tables (constitution §4).

---

## Measures (host: NetflixTitles)

| # | Measure | Display Folder | Format | DAX |
|---|---------|----------------|--------|-----|
| 1 | Total Titles | Core Metrics | #,##0 | `COUNTROWS(NetflixTitles)` |
| 2 | Distinct Titles | Core Metrics | #,##0 | `DISTINCTCOUNT(NetflixTitles[show_id])` |
| 3 | Movies Count | Category Counts | #,##0 | `CALCULATE(DISTINCTCOUNT(NetflixTitles[show_id]), KEEPFILTERS(NetflixTitles[type] = "Movie"))` |
| 4 | TV Shows Count | Category Counts | #,##0 | `CALCULATE(DISTINCTCOUNT(NetflixTitles[show_id]), KEEPFILTERS(NetflixTitles[type] = "TV Show"))` |
| 5 | Titles Added by Year | Time Intelligence | #,##0 | `CALCULATE(DISTINCTCOUNT(NetflixTitles[show_id]), KEEPFILTERS(NOT ISBLANK(NetflixTitles[date_added])))` |

- All boolean filters use literal column comparisons inside `KEEPFILTERS` (no measure references — constitution §3).
- Total Titles = source row count (FR-007); Distinct Titles migrates Tableau `COUNTD([show_id])` (FR-007).
- Measures break down by type/rating/listed_in/country when placed on axis/legend (FR-007a).

## Calculated Columns

None — the Tableau `Year` calc field is satisfied by the DimDate relationship.

## What-If Parameters

None — Tableau `Year` date parameter → date slicer on DimDate.
