# Feature Specification: Netflix RLS Dashboard Migration (Tableau → Power BI)

**Feature Branch**: `001-netflixrls-pbi`  
**Created**: 2026-06-08  
**Status**: Draft  
**Input**: User description: "Migrate Netflix RLS Tableau workbook to Power BI semantic model with dynamic row-level security"

## Clarifications

### Session 2026-06-08

> Automated pipeline run — ambiguities were resolved with sensible defaults grounded in the Tableau analysis (`.specify/memory/NetflixRLS/tableau-analysis-output.md`) and the migration constitution. No interactive answers were collected; each decision below is documented for downstream plan/model/report stages.

- **Q: How should the multi-valued `country` field be reconciled with single-country RLS entitlements?** → **A:** Normalize via a bridge/expanded table. In Power Query, retain the original `country` string on the title for display, AND split `netflix_titles.country` by comma (trim whitespace) into a normalized one-row-per-country expansion used for the security relationship. RLS matches when the user's entitled `Country` appears within a title's country list (CONTAINS-style match realized through the normalized bridge). The bridge-table normalization is the chosen approach over a direct equality join on the full multi-country string.
- **Q: What identity function and role configuration enforce RLS?** → **A:** Use `USERPRINCIPALNAME()` (email/UPN) matched case-insensitively against `User_Access[Username]`. Implement a single dynamic role named **"Dynamic Country Access"**, replacing the Tableau hardcoded `"user2@maq.com"` predicate.
- **Q: How is the primary title-count measure defined and named?** → **A:** `DISTINCTCOUNT(show_id)`, surfaced as a measure named **"Total Titles"** (equivalent to Tableau's `COUNTD([show_id])`), used as the primary aggregation across all visuals and respecting active RLS.
- **Q: How should `date_added` be handled for the year trend?** → **A:** Parse `date_added` (text like "September 9, 2019") to a Date type in Power Query, then derive a `Year` column / date dimension to drive the "titles by year" trend; unparseable values are excluded gracefully.
- **Q: What report theme should be applied?** → **A:** Dark theme matching the Tableau Netflix dashboard — `#000000` background, white text, red accents (`#aa0000` / `#ff0000`).
- **Q: How should the "Movies and TV Shows distribution" view be rendered?** → **A:** A donut/pie chart sliced by `type`, sized by the distinct title count, with a "percent of total" measure (`DIVIDE` over `CALCULATE(..., ALLSELECTED())` equivalent) shown as the proportional label — replacing the Tableau packed-bubble.

## User Scenarios & Testing *(mandatory)*

This migration converts the Tableau "Netflix RLS" workbook — a Netflix titles analytics dashboard governed by **dynamic row-level security (RLS)** — into a Power BI project (PBIP) containing a semantic model and a report. The defining capability is that each viewer sees only the Netflix titles for the country (or countries) they are entitled to, driven by the signed-in user's identity rather than a hardcoded user.

### User Story 1 - Dynamic Row-Level Security by Country (Priority: P1)

A business user signs into Power BI and opens the Netflix dashboard. The semantic model identifies the user by their sign-in identity, looks up their entitled country in the access mapping table, and silently filters every visual so the user only sees Netflix titles associated with that country. A user mapped to "United States" sees only U.S. titles; a user mapped to "India" sees only Indian titles. No user can see titles for countries they are not entitled to.

**Why this priority**: Row-level security is the defining feature of this workbook. The original Tableau workbook enforces per-user country access through a security calculation and an entitlement mapping table. Without correctly reproducing this security boundary, the migration fails its primary purpose and risks exposing data to unauthorized viewers.

**Independent Test**: Open the published model in Power BI Desktop, use "View as role" with the dynamic role and a sample username from the access mapping table, and confirm every visual filters down to only the titles for that user's entitled country. Switching the simulated user to a different entitled country changes the visible titles accordingly.

**Acceptance Scenarios**:

1. **Given** a user whose sign-in identity maps to a single country in the access table, **When** they view any dashboard visual, **Then** only Netflix titles associated with that country are counted and displayed.
2. **Given** a user whose sign-in identity is not present in the access table, **When** they view the dashboard, **Then** no titles are visible (empty/zero result) rather than all titles.
3. **Given** the security role is tested via "View as role" with a known mapped username, **Then** the visible title counts match the subset of titles for that user's entitled country.
4. **Given** the model is opened by an author with no role applied, **Then** the full unfiltered dataset is visible (authoring view), confirming RLS applies to consumers via the role rather than breaking the model.

---

### User Story 2 - Netflix Content Distribution Dashboard (Priority: P1)

A user opens the migrated dashboard and sees the same nine analytical views that existed in Tableau — content distribution by country, by genre, by rating, by type (Movies vs. TV Shows), by duration, descriptions, and trend over years — rendered with the original dark Netflix-style theme (black background with red accents) on a single dashboard page.

**Why this priority**: The dashboard's visual analytics are the user-facing product. Reproducing all nine views with the correct chart types and the recognizable dark theme delivers the core reporting value alongside the security boundary, making the migration usable as an MVP.

**Independent Test**: Open the report page in Power BI Desktop and confirm all nine visuals render with correct data bindings and the dark theme, matching the layout and chart types described in the source analysis.

**Acceptance Scenarios**:

1. **Given** the report page loads, **When** the user views it, **Then** all nine visuals are present: country-wise distribution (filled map), description table, duration, genre, Movies/TV Shows distribution (proportional/donut), rating, ratings bar chart, Top 10 Genre, and titles-by-year trend.
2. **Given** the dashboard renders, **When** the user inspects the styling, **Then** the page uses a black (#000000) background with red accent coloring consistent with the Netflix theme.
3. **Given** a visual that distinguishes Movies from TV Shows, **When** displayed, **Then** the title type encoding (Movie vs. TV Show) is preserved as color/category.

---

### User Story 3 - Titles Added Over Years Trend (Priority: P2)

A user examines how many Netflix titles were added to the catalog over time by viewing an area/trend chart that plots the distinct count of titles by the year each title was added, split by title type (Movie vs. TV Show).

**Why this priority**: Time-based trend analysis is valuable context for catalog growth but is secondary to the security boundary and the primary distribution visuals. It depends on deriving a clean year value from a date-added field that arrives as text.

**Independent Test**: Confirm the trend visual plots distinct title counts by added-year, the year axis is sorted chronologically, and the Movie/TV Show split is shown — all respecting the active RLS filter.

**Acceptance Scenarios**:

1. **Given** the date-added value is parsed to a proper date, **When** the trend visual renders, **Then** titles are grouped by the year added and ordered chronologically.
2. **Given** an RLS role is active, **When** the trend visual renders, **Then** the yearly counts reflect only the entitled country's titles.

---

### User Story 4 - Top Genres and Ratings Breakdowns (Priority: P3)

A user reviews which genres and content ratings dominate the (entitled) catalog via a Top 10 Genre horizontal bar chart and a ratings breakdown.

**Why this priority**: These breakdowns enrich the analysis but are the least critical slices; they reuse the same distinct-count measure and category fields already required by higher-priority stories.

**Independent Test**: Confirm the Top 10 Genre visual shows the ten genres with the highest distinct title counts in descending order, and the ratings visual breaks counts down by rating — both respecting RLS.

**Acceptance Scenarios**:

1. **Given** the Top 10 Genre visual renders, **When** displayed, **Then** it shows the ten genres with the highest distinct title counts, sorted descending.
2. **Given** the ratings visual renders, **When** displayed, **Then** distinct title counts are broken down by content rating.

---

### Edge Cases

- **Multi-valued country (RLS join accuracy)**: In `netflix_titles`, the `country` field is frequently multi-valued (comma-separated, e.g., "United States, India, South Korea, China"), whereas `User_Access.Country` holds a single country per entitlement row. A direct equality join only matches rows where the full multi-country string exactly equals a single entitlement value, so titles tagged with multiple countries may be incorrectly excluded from (or hidden by) RLS. The country field may need normalization (splitting into one row per country, or a bridge table) so entitlement matches on individual country values.
- **Unmapped user**: When the signed-in user has no row in the access table, the result must be an empty/zero view (deny by default), never the full dataset.
- **Text date parsing**: `date_added` arrives as text; if a value cannot be parsed to a date, the year-trend visual must exclude or gracefully handle the unparseable row rather than error.
- **Missing/blank country**: Titles with a blank or null `country` cannot be matched to any entitlement and will not appear for any user; this is acceptable under deny-by-default but should be noted.
- **Case sensitivity in identity match**: The original calc lowercases both sides; the migrated identity match must be case-insensitive so that mixed-case usernames or country values still match.

## Requirements *(mandatory)*

### Functional Requirements

#### Data Load & Modeling

- **FR-001**: System MUST load two source files via Power Query: `netflix_titles.csv` (title catalog) and `User_Access.csv` (user-to-country entitlement mapping).
- **FR-002**: System MUST import the title columns: show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description.
- **FR-003**: System MUST import the access mapping columns: Username (email) and Country.
- **FR-004**: System MUST parse `date_added` (text) into a proper date value and derive a Year value used for the titles-by-year trend.
- **FR-005**: System MUST organize the model as a star schema with the title catalog as the central (fact-style) table and the user access mapping as the security/dimension table.
- **FR-006**: System MUST relate the access mapping table to the title catalog on country (`User_Access.Country → netflix_titles.country`) so country entitlement propagates to titles.
- **FR-007**: System MUST address the multi-valued `country` field via the chosen **bridge/expanded-table normalization**: in Power Query, retain the original `country` string for display AND split it by comma (trimming whitespace) into a one-row-per-country expansion used for the RLS relationship, so title-to-entitlement matching operates on individual country values (CONTAINS-style match).

#### Measures

- **FR-008**: System MUST provide a measure named **"Total Titles"** defined as `DISTINCTCOUNT(show_id)` (equivalent to Tableau's `COUNTD([show_id])`), used as the primary aggregation across all visuals.
- **FR-009**: System MUST provide a "percent of total" measure for the Movies vs. TV Shows distribution visual, computing each type's share of the (currently filtered) total title count via `DIVIDE` over an all-selected total.
- **FR-010**: All measures MUST respect the active RLS filter so secured users see counts reflecting only their entitled country.

#### Row-Level Security

- **FR-011**: System MUST define a single dynamic RLS role ("Dynamic Country Access") that filters the user access table to the rows where the username equals the signed-in user's identity (using the equivalent of `USERPRINCIPALNAME()`), replacing the hardcoded `"user2@maq.com"` predicate from the Tableau source.
- **FR-012**: The RLS filter MUST be case-insensitive when matching the signed-in identity against stored usernames.
- **FR-013**: System MUST deny by default — a signed-in user with no matching entitlement row sees no titles.
- **FR-014**: The entitlement filter on the access table MUST propagate through the country relationship to the title catalog so all visuals are secured without per-visual configuration.

#### Visuals & Report

- **FR-015**: System MUST reproduce all nine worksheets as Power BI visuals on a single dashboard page:
  - Country wise distribution — filled map keyed on country (Data Category = Country), colored by distinct title count.
  - Description — table of descriptions, filtered to type = "TV Show".
  - Duration — table/listing of duration values.
  - Genre — listing of genres (listed_in).
  - Movies and TV Shows distribution — **donut/pie** chart sliced by type, sized by distinct title count, showing percent of total (replaces the Tableau packed-bubble).
  - Rating — rating listing/visual.
  - Ratings — bar chart of distinct title count by rating.
  - Top 10 Genre — horizontal bar chart of the top 10 genres by distinct title count.
  - Total Movies and TV Shows by Years — area/trend chart of distinct title count by added-year, split by type.
- **FR-016**: The country-wise filled map MUST treat country as a geographic (Country) category so it renders on a map.
- **FR-017**: The "Movies and TV Shows by Years" visual MUST order the year axis chronologically and split by title type.
- **FR-018**: The "Top 10 Genre" visual MUST limit to the ten genres with the highest distinct title counts, sorted descending.
- **FR-019**: The report page MUST apply a dark Netflix theme: black (`#000000`) background, white text, and red accent coloring (`#aa0000` / `#ff0000`), consistent with the source dashboard.
- **FR-020**: The report MUST present the dashboard on a single page reproducing the source dashboard composition (the eight visuals placed on the Tableau "Netflix" dashboard, plus the remaining worksheet views as specified).

#### Output & Validity

- **FR-021**: System MUST produce a valid PBIP project (semantic model + report) that opens in Power BI Desktop without structural, model, or report errors.
- **FR-022**: The migrated `Year` parameter behavior MUST be preserved where it affects the report; if the parameter is not bound to a control in the report, its absence MUST NOT break any visual. *(The source `Year` parameter, default 2024-03-26, has no detected slice usage in the analysis; it is carried as an assumption — see Assumptions.)*

### Key Entities *(include if feature involves data)*

- **Netflix Title (netflix_titles)**: The catalog of Netflix titles. Key attributes: show_id (identifier used for distinct counts), type (Movie/TV Show), title, director, cast, country (where the title is available — multi-valued), date_added (text date the title was added), release_year, rating, duration, listed_in (genre(s)), description. Central table of the star schema; secured by RLS.
- **User Access (User_Access)**: The entitlement mapping table pairing each user to a country. Key attributes: Username (the user's sign-in email), Country (the country that user is entitled to view). Drives dynamic RLS; related to the title catalog on Country.
- **RLS Role — "Dynamic Country Access"**: A security role that filters the User Access table to the signed-in user's row(s) and propagates the entitled country to the title catalog.
- **Total Titles (measure)**: `DISTINCTCOUNT(show_id)`; the primary aggregation across all visuals.
- **Type Share / Percent of Total (measure)**: Each title type's share of the filtered total title count, used by the Movies vs. TV Shows distribution visual.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The generated PBIP project opens in Power BI Desktop with zero structural, model, or report load errors.
- **SC-002**: When tested with "View as role" using the dynamic role and a username drawn from the access mapping table, 100% of visuals filter to only that user's entitled country's titles, and no titles from other countries are visible.
- **SC-003**: A simulated user with no entitlement row sees zero titles across all visuals (deny by default verified).
- **SC-004**: All nine source worksheets are represented on the dashboard page with their corresponding Power BI chart types and correct data bindings.
- **SC-005**: The dashboard page renders with the dark Netflix theme (black background, red accents) matching the source styling.
- **SC-006**: The distinct title count shown for the unfiltered (author) view equals the distinct count of show_id across the loaded catalog, confirming the primary measure is correct.
- **SC-007**: The titles-by-year trend orders years chronologically and the Top 10 Genre visual shows exactly ten genres in descending count order.

## Assumptions

- **Identity provider**: Power BI consumers are authenticated, and the signed-in identity returned by the platform (equivalent to `USERPRINCIPALNAME()`) matches the email format stored in `User_Access.Username`.
- **Hardcoded user replacement**: The Tableau `RLS` calc's hardcoded `"user2@maq.com"` was a single-user test predicate; the migration replaces it with the dynamic signed-in identity to achieve true per-user filtering, as recommended in the source analysis.
- **Single datasource, no blending**: Both CSVs belong to one federated datasource joined by a logical relationship in Tableau; RLS is enforced by a calculated field, not a data blend. The Power BI model reproduces this as one star schema with a security relationship, not a blend.
- **Year parameter**: The source `Year` parameter (date, default 2024-03-26) has no detected binding to any worksheet filter in the analysis. It is assumed to be non-functional in the report and is carried only for fidelity; it must not break any visual if omitted from interactive controls.
- **Country normalization approach**: To make RLS accurate against the multi-valued `country` field, the model normalizes country values via a **bridge/expanded table** (split-by-comma into one row per country) during data preparation, while retaining the original `country` string for display (decided in Clarifications, Session 2026-06-08).
- **Geographic mapping**: Country values are recognizable to Power BI's map engine as countries (Data Category = Country) for the filled map; ambiguous or non-standard country strings may not plot and are out of scope to correct beyond standard mapping.
- **Data scope**: Only the two provided CSVs are in scope; no additional Netflix data sources, incremental refresh, or scheduled refresh configuration is included in this migration.
- **Single dashboard page**: The output is a single report page reproducing the source "Netflix" dashboard; multi-page navigation is out of scope.
