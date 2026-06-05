# Phase 0 Research: Netflix Workbook Power BI Migration

All spec ambiguities were resolved during the 2026-06-04 / 2026-06-05 clarification sessions. No `NEEDS CLARIFICATION` items remain. This document records the technical decisions backing the plan.

---

## Decision 1 — CSV ingestion via Power Query M

- **Decision**: Load `netflix_titles.csv` with `Csv.Document(File.Contents(...))`, `Delimiter = ","`, `Encoding = 65001`, `QuoteStyle = QuoteStyle.Csv`, promote headers, then apply explicit type transforms.
- **Rationale**: `QuoteStyle.Csv` (constitution §5) keeps quoted multi-value fields (`country`, `cast`, `listed_in`) — which embed commas — as single columns. UTF-8 (65001) preserves title/description text. Types applied right after header promotion per §5.
- **Alternatives considered**: `QuoteStyle.None` (rejected — would split quoted comma fields); auto-detected types (rejected — explicit transforms guarantee Int64 for `show_id`/`release_year` and date for `date_added`).

## Decision 2 — DimDate via DAX CALENDAR (not M)

- **Decision**: Generate `DimDate` as a DAX calculated table using `CALENDAR` over full-calendar-year boundaries of non-null `date_added`, with `ADDCOLUMNS` deriving Year/Quarter/Month/MonthName/Day/DayOfWeek.
- **Rationale**: Self-derives the range from `date_added` (no hardcoded dates), needs no separate query/CSV, and avoids cross-table load-order risk. Full Jan 1 → Dec 31 coverage keeps YTD / SAMEPERIODLASTYEAR contiguous.
- **Alternatives considered**: M `List.Dates` generation (rejected — adds a second query and a manual range; DAX auto-derives); importing a date CSV (rejected — unnecessary dependency).

## Decision 3 — Single-table model (no decomposition)

- **Decision**: Keep `NetflixTitles` as one table; add only `DimDate`.
- **Rationale**: Single flat CSV → constitution §0 Single-Table Rule. Decomposing a flat file creates fragile keys and data loss; VertiPaq handles the denormalized table efficiently.
- **Alternatives considered**: Star-schema split into Type/Rating/Genre/Country dimensions + bridge tables (rejected — violates §0 for single-source flat files; deferred as a future enhancement).

## Decision 4 — Tableau Year parameter → date slicer

- **Decision**: Migrate the Tableau `Year` date parameter (default `#2024-03-26#`) as a date slicer on `DimDate[Year]` / `DimDate[Date]`, not a What-If parameter.
- **Rationale**: The parameter only drove date-based slicing of `date_added`, which `DimDate` provides natively (constitution §7 — date range → date slicer). A What-If table would be disconnected and unused.
- **Alternatives considered**: What-If `GENERATESERIES` table (rejected — adds an unused disconnected table).

## Decision 5 — Measures over calculated columns

- **Decision**: Express all aggregations as 5 explicit measures on `NetflixTitles`; no calculated columns.
- **Rationale**: Constitution §3 prefers measures; columns only for relationships/row filtering. The Tableau `Year` calc field is covered by the DimDate relationship, so no calculated column is needed.
- **Alternatives considered**: Calculated `Year` column on NetflixTitles (rejected — redundant with DimDate); per-rating/genre/country measures (rejected — achieved by placing the two count measures against those columns; keeps the surface lean).

## Decision 6 — Boolean filter pattern (KEEPFILTERS + literal)

- **Decision**: Movies/TV Shows/Titles-Added measures use `CALCULATE(DISTINCTCOUNT(...), KEEPFILTERS(column = literal))` / `KEEPFILTERS(NOT ISBLANK(column))`.
- **Rationale**: Constitution §3 / TMDL rules forbid measure references inside CALCULATE boolean filters; literal comparisons on a column are safe and respect existing filter context via `KEEPFILTERS`.
- **Alternatives considered**: `CALCULATE(..., column = literal)` without KEEPFILTERS (acceptable but KEEPFILTERS preserves user-applied type filters); FILTER iterator (rejected — unnecessary).

## Decision 7 — Geographic Data Category on country

- **Decision**: Apply `dataCategory: Country` to `NetflixTitles[country]`.
- **Rationale**: Migrates the Tableau `[Country].[ISO3166_2]` geographic role (FR-011) so Power BI map visuals resolve countries.
- **Alternatives considered**: Leaving country uncategorized (rejected — breaks map auto-geocoding).

## Decision 8 — TMDL authoring rules (`plugins/pbip/skills/tmdl/SKILL.md`)

- **Decision**: Tab-based semantic indentation; `///` descriptions precede declarations; quote only names needing it (none here); measure DAX at depth 3 with `formatString` after the body; `summarizeBy: none` for keys/attributes; `DimDate` marked as date table; `MonthName` sort-by `Month`.
- **Rationale**: Matches the validated TMDL grammar the `tmdl-validate` linter enforces.

## Decision 9 — PBIR report format (`plugins/pbip/skills/pbir-format/SKILL.md`)

- **Decision**: Minimal `report.json` (`$schema` + `themeCollection` + `settings`); visual containers carry only `$schema`/`name`/`position`/`visual`; no `filters`/`filterConfig` at visual root. Top-10 Genre filtering handled via DAX/visual filter in Desktop.
- **Rationale**: PBI Desktop rejects undefined root properties ("schema does not allow additional properties"). Minimal compliant JSON prevents load failures.

---

## Resolved Unknowns Summary

| Topic | Resolution |
|-------|-----------|
| DimDate range/grain | Day grain, min→max non-null `date_added`, extended to full calendar years |
| Year parameter | Date slicer on DimDate (no What-If) |
| Multi-value fields | Kept as comma-separated strings (split deferred) |
| duration parsing | Kept as string (numeric extraction deferred) |
| Measure scope | Total Titles, Distinct Titles, Movies Count, TV Shows Count, Titles Added by Year |
| country geo role | Data Category: Country |
