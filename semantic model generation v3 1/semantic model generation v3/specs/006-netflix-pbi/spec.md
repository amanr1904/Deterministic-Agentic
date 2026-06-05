# Feature Specification: Netflix Workbook Power BI Migration

**Feature Branch**: `006-netflix-pbi`  
**Created**: 2026-06-04  
**Status**: Draft  
**Input**: User description: "Migrate 'Netfix Workbook' Tableau workbook to Power BI semantic model (.pbip). Single CSV source, single-table rule, DimDate for time intelligence."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load Netflix Data into Power BI (Priority: P1)

A data analyst opens the generated .pbip file in Power BI Desktop and sees the NetflixTitles table populated with all 12 columns from netflix_titles.csv. They can immediately browse titles, filter by type, rating, or country, and see correct data types for each column.

**Why this priority**: Without data loading successfully, no other analysis is possible. This is the foundational requirement.

**Independent Test**: Open the .pbip in Power BI Desktop, verify the NetflixTitles table appears with all rows from the CSV, and confirm column data types match expectations (integer for show_id/release_year, date for date_added, string for all others).

**Acceptance Scenarios**:

1. **Given** the .pbip file is opened in Power BI Desktop, **When** the model loads, **Then** the NetflixTitles table contains all rows from netflix_titles.csv with correct data types
2. **Given** the model is loaded, **When** the user inspects the Fields pane, **Then** all 12 source columns are visible: show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description
3. **Given** the CSV has null/blank values in director or cast columns, **When** the model loads, **Then** those cells display as blank (not error)

---

### User Story 2 - Analyze Netflix Content by Time Period (Priority: P1)

A data analyst uses the DimDate table to slice Netflix content by year, month, or quarter based on the date_added field. They can see how many titles were added per year and identify trends over time.

**Why this priority**: Time intelligence is the primary analytical capability being migrated from Tableau (the Year calculated field and Year parameter). This enables the core analytical workflow.

**Independent Test**: Create a visual sliced by DimDate[Year], verify it correctly groups Netflix titles by the year they were added, and confirm the date relationship filters correctly.

**Acceptance Scenarios**:

1. **Given** the model is loaded, **When** the user drags DimDate[Year] to a visual axis, **Then** Netflix titles are correctly grouped by the year portion of date_added
2. **Given** a date slicer is placed on a report page, **When** the user selects a specific year, **Then** only titles added in that year appear in related visuals
3. **Given** the DimDate table exists, **When** the user examines relationships, **Then** an active relationship connects NetflixTitles[date_added] to DimDate[Date]

---

### User Story 3 - Use DAX Measures for Content Analysis (Priority: P2)

A data analyst uses pre-built DAX measures to quickly understand the Netflix catalog — total title count, distinct title count, and content distribution by type, rating, genre, and country — without needing to write formulas.

**Why this priority**: Pre-built measures accelerate analysis and ensure consistent metric definitions across reports. They directly migrate the Tableau `COUNTD([show_id])` aggregation pattern used across the source worksheets.

**Independent Test**: Place the Total Titles and Distinct Titles measures on card visuals; verify Total Titles matches the source CSV row count and Distinct Titles matches the count of unique show_id values.

**Acceptance Scenarios**:

1. **Given** the model is loaded, **When** the user places the Total Titles measure on a card, **Then** it displays the total number of rows in NetflixTitles
2. **Given** the model is loaded, **When** the user places the Distinct Titles measure on a card, **Then** it displays the count of unique show_id values (migrating Tableau `COUNTD([show_id])`)
3. **Given** the model is loaded, **When** the user breaks a measure down by type, rating, listed_in (genre), or country, **Then** the count is correctly split across those categories
4. **Given** the model is loaded, **When** the user filters by DimDate[Year] = 2021, **Then** measures correctly reflect only titles added in 2021

---

### Edge Cases

- What happens when date_added is blank/null in the source CSV? → Titles with null date_added should still appear in NetflixTitles but will not be linked to DimDate (unmatched rows handled by blank key); the "Total Movies and TV Shows by Years" analysis excludes null date_added, matching the Tableau worksheet filter
- What happens when the CSV file path changes? → The M query references a relative path pointing to Data/Netflix/netflix_titles.csv; the user must place the CSV in the expected location
- How does the system handle duplicate show_id values? → Distinct Titles uses DISTINCTCOUNT(show_id) so duplicates are de-duplicated; Total Titles counts raw rows. No uniqueness constraint is enforced on NetflixTitles; DimDate[Date] is the only key column
- How are multi-value country and listed_in (genre) fields counted? → These columns hold comma-separated values (multiple countries/genres per title). Measures count each title once per its full string value, so a title spanning multiple countries/genres is attributed to the combined string, not split across each constituent value. Accurate per-country/per-genre counts would require splitting/unpivoting these fields — deferred to a future enhancement and flagged here for report authors

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load all rows and 12 columns from netflix_titles.csv into a single NetflixTitles table without decomposition into fact/dimension tables (Single-Table Rule §0)
- **FR-002**: System MUST generate a DimDate table at **day grain** spanning the contiguous range from the **minimum to the maximum** non-null date_added value (full calendar years recommended for clean time intelligence), with at minimum: Date, Year, Quarter, Month, MonthName, Day (day-of-month), DayOfWeek columns
- **FR-003**: System MUST create an active many-to-one relationship from NetflixTitles[date_added] to DimDate[Date]
- **FR-004**: System MUST produce a valid .pbip project structure with .pbip manifest, .SemanticModel folder (TMDL definition), and .Report folder (PBIR definition)
- **FR-005**: System MUST assign correct data types: Int64 for show_id and release_year, DateTime for date_added, String for all other columns
- **FR-006**: System MUST generate a DAX-based DimDate table (calculated table or M query) that supports time intelligence functions (TOTALYTD, SAMEPERIODLASTYEAR, etc.)
- **FR-007**: System MUST generate a "Total Titles" measure counting all rows in NetflixTitles (COUNTROWS) and a "Distinct Titles" measure using DISTINCTCOUNT(NetflixTitles[show_id]) to migrate the Tableau `COUNTD([show_id])` aggregation
- **FR-007a**: System MUST ensure the count measures (Total Titles, Distinct Titles) correctly break down by type, rating, listed_in (genre), and country when those columns are placed on a visual axis or legend
- **FR-008**: System MUST use Power Query M expression to load CSV from relative file path pattern pointing to Data/Netflix/netflix_titles.csv
- **FR-009**: System MUST follow naming conventions per constitution §2 (PascalCase for tables/columns, no spaces in technical names)
- **FR-010**: System MUST follow DAX standards per constitution §3 (measures in dedicated measures table or logically grouped, proper formatting)
- **FR-011**: System MUST apply Data Category: Country to the NetflixTitles[country] column to enable geographic map visuals
- **FR-012**: System MUST NOT decompose multi-value fields (country, listed_in, cast, director) into bridge/dimension tables — retain as comma-separated strings in the primary table

### Key Entities

- **NetflixTitles**: The single source table representing the Netflix catalog. Contains all 12 columns from the CSV: show_id (key identifier), type (Movie/TV Show), title, director, cast, country, date_added, release_year, rating, duration, listed_in (genres), description
- **DimDate**: A date dimension table generated via DAX or M query for time intelligence support, at day grain covering the min–max range of date_added. Key column is Date, with derived attributes: Year, Quarter, Month, MonthName, Day (day-of-month), DayOfWeek
- **Measures**: A logical set of count measures — Total Titles (COUNTROWS of NetflixTitles) and Distinct Titles (DISTINCTCOUNT of show_id, migrating Tableau `COUNTD([show_id])`) — that respond to type, rating, genre, country, and date filtering

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The .pbip file opens in Power BI Desktop without errors or warnings
- **SC-002**: NetflixTitles table loads all rows from netflix_titles.csv (row count matches source)
- **SC-003**: All 12 source columns are accessible in the Fields pane with correct data types
- **SC-004**: DimDate table is populated and the relationship to NetflixTitles filters correctly when a date/year is selected
- **SC-005**: The Total Titles measure returns the source row count and the Distinct Titles measure returns the unique show_id count; both respond to date slicer and category (type/rating/genre/country) filtering
- **SC-006**: TMDL validation passes with zero errors (tmdl-validate exits cleanly)
- **SC-007**: PBIP structure validation passes (validate_pbip.py exits with code 0 or 1, no code 2 errors)

## Assumptions

- The netflix_titles.csv file is located at Data/Netflix/netflix_titles.csv relative to the workspace root
- The CSV uses UTF-8 encoding with comma delimiter and standard header row
- date_added column contains dates in a format parseable by Power Query (e.g., "January 1, 2020" or "2020-01-01")
- Blank/null values in date_added are acceptable and will result in unmatched rows (no DimDate link)
- The Year parameter from Tableau (default 2024-03-26) is migrated as a DimDate relationship enabling date slicing, not as a Power BI "What-If" parameter
- Output folder is Output/NetflixAnalysis/ (all .pbip artifacts generated here)
- Single-table rule (constitution §0) applies: no star schema decomposition of the source table
- Mobile layout and row-level security are out of scope for this migration
- Multi-value fields (country, listed_in, cast, director) remain as comma-separated strings in the primary table — no bridge table decomposition unless explicitly requested
- The country column carries a geographic Data Category: Country for map visual support
- The rating column is used as a categorical slicer — no calculated column grouping needed
- The duration column is a mixed-format string ("90 min" / "2 Seasons") — no numeric extraction for initial migration

## Clarifications

### Session 2026-06-04

- Q: Should aggregations use measures or calculated columns? → A: Prefer measures (DAX best practice per constitution §3). Calculated columns only if needed for relationships.
- Q: Should the single CSV source be decomposed into fact/dimension tables? → A: No. Single-table rule (constitution §0) applies. Keep NetflixTitles as the primary table; only DimDate is added for time intelligence.
- Q: How should the Tableau "Year" calculated field and "Year" parameter be migrated? → A: The calculated field (DATETIME([date_added])) maps to the DimDate relationship. The Year parameter (date type) maps to a date slicer on DimDate[Year].
- Q: Should multi-value fields (country, listed_in, cast, director) be split into bridge + dimension tables? → A: No. Per constitution §0 single-table override for single CSV, keep as-is in the primary table. Users may request decomposition later.
- Q: Should the country column have a geographic data category applied? → A: Yes. Apply Data Category: Country (geographic role from Tableau ISO3166_2 mapping) to enable map visuals.
- Q: Should the rating field be grouped into a calculated column (e.g., "Kids", "Teens", "Adults")? → A: No. Keep as-is for use as a categorical slicer — no grouping calculation needed.
- Q: Should the duration field be parsed into numeric columns (minutes / seasons)? → A: No. Keep as a string field for initial migration. Numeric extraction deferred to future enhancement.
- Q: Which count measures should be pre-built? → A: Two — Total Titles (COUNTROWS) and Distinct Titles (DISTINCTCOUNT of show_id, migrating Tableau `COUNTD([show_id])`). Category breakdowns (type/rating/genre/country) are achieved by placing these measures against the relevant columns, not as separate measures.
- Q: How should per-country and per-genre counts handle the comma-separated multi-value fields? → A: For initial migration, counts attribute each title to its full combined string value (no split). Splitting/unpivoting for accurate per-value counts is deferred and flagged for report authors.

### Session 2026-06-05

> Automated migration pass — underspecified areas resolved with constitution-aligned defaults (no interactive blocking). The Session 2026-06-04 decisions for multi-value split (defer), duration parsing (keep as string), measure scope (Total + Distinct), and the Year-parameter→DimDate slicing mapping remain authoritative and are reaffirmed here.

- Q: What range and grain should the DimDate table use? → A: Day grain, spanning the minimum to maximum non-null date_added value (extend to full calendar-year boundaries for clean YTD/SAMEPERIODLASTYEAR behavior). Standard columns: Date, Year, Quarter, Month, MonthName, Day (day-of-month), DayOfWeek. Rationale: matches date_added day-level precision so the active NetflixTitles[date_added]→DimDate[Date] relationship resolves 1:1, and full-year coverage keeps time-intelligence measures contiguous (constitution §0 DimDate convention).
- Q: Is the Tableau "Year" date parameter (default #2024-03-26#) migrated as a Power BI What-If parameter? → A: No. It is represented purely through DimDate[Year] (and the date slicer on DimDate), not as a What-If numeric parameter. Rationale: the Tableau parameter only drove date-based slicing of date_added, which DimDate already provides natively; a What-If parameter would add an unused disconnected table.
- Q: Should comma-separated country/listed_in be split into bridge tables in v1? → A: Defer (reaffirmed). Each title is counted once per its full combined string; bridge/unpivot decomposition is a documented future enhancement. Rationale: single-table rule (constitution §0) for a single flat CSV; avoids premature ETL complexity.
- Q: Should duration ("90 min" vs "2 Seasons") be parsed into numeric + unit columns? → A: No for v1 (reaffirmed) — retain as the original mixed-format string; numeric/unit extraction noted as a future enhancement. Rationale: mixed semantics (minutes vs seasons) need a deliberate split design not required for the current count-oriented measures.
- Q: What is the v1 measure set scope? → A: Total Titles (COUNTROWS) and Distinct Titles (DISTINCTCOUNT of show_id, migrating COUNTD([show_id])); category counts (type/rating/genre/country) are produced by placing these measures against the relevant columns rather than as separate measures. Rationale: minimal, non-redundant measure surface aligned with constitution §3 DAX standards.
