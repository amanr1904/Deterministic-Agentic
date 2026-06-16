# Feature Specification: Netflix RLS — Tableau to Power BI Migration

**Feature Branch**: `003-netflix-rls-pbi`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "Migrate Netflix RLS Tableau workbook to Power BI semantic model with dynamic row-level security"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dynamic Row-Level Security by Country (Priority: P1)

A business analyst publishes the Netflix catalog report so that each viewer only sees titles from the country (or countries) they are entitled to. When a user opens the report, the system identifies them by their sign-in identity and automatically restricts the visible Netflix titles to the country mapped to that user. A user mapped to "India" sees only titles where the country is India; a user mapped to "United States" sees only United States titles, and so on. No user can see titles outside their entitled country, and the restriction applies to every visual on every page.

**Why this priority**: Row-level security is the defining purpose of this workbook (it is the "RLS" variant). Without correct entitlement enforcement, the migration fails its core confidentiality intent. The original Tableau workbook hardcoded a single user; the Power BI migration must generalize this to all users via a mapping table.

**Independent Test**: Can be fully tested by impersonating different users (e.g., `shashank@maq.com`, `user2@maq.com`, `user3@maq.com`) and confirming that each only sees titles for their mapped country (India, United States, United Kingdom respectively), with all aggregate counts and visuals reflecting only the permitted rows.

**Acceptance Scenarios**:

1. **Given** a user `shashank@maq.com` mapped to "India" in the entitlement table, **When** they view any report page, **Then** all visuals show only Netflix titles where country is India.
2. **Given** a user `user2@maq.com` mapped to "United States", **When** they view the catalog, **Then** they see only United States titles and the total title count reflects only those rows.
3. **Given** a user whose identity does not appear in the entitlement table, **When** they open the report, **Then** they see no titles (empty result set).
4. **Given** a user mapped to a country, **When** they navigate across all worksheet-derived visuals, **Then** the country restriction is applied consistently to every visual without exception.

---

### User Story 2 - Migrate All Catalog Worksheets as Report Visuals (Priority: P2)

A report consumer wants the same analytical views that existed in the Tableau workbook so they can explore the Netflix catalog (distribution by country, genre, rating, duration, type, and trends over years). Each of the nine Tableau worksheets is reproduced as a Power BI visual, organized on a report page that mirrors the original "Netflix" dashboard, so the migrated report delivers equivalent insight.

**Why this priority**: Faithful reproduction of the analytical content is required for the migration to be considered complete and usable. The user has explicitly required that all nine worksheets be migrated as report visuals.

**Independent Test**: Can be tested by opening the migrated report and confirming each of the nine worksheets has a corresponding visual showing equivalent data, plus a dashboard-style page that consolidates them.

**Acceptance Scenarios**:

1. **Given** the migrated report, **When** a consumer opens it, **Then** visuals exist for: Country wise distribution, Description, Duration, Genre, Movies and TV Shows distribution, Rating, Ratings, Top 10 Genre, and Total Movies and TV Shows by Years.
2. **Given** the "Netflix" dashboard in Tableau, **When** the report is opened, **Then** an equivalent consolidated "Netflix" page presents the migrated visuals together.
3. **Given** any migrated visual, **When** it renders, **Then** the title counts shown are distinct counts of titles (matching the Tableau `CountD(show_id)` behavior).

---

### User Story 3 - Year Parameter and Year Field Available for Analysis (Priority: P3)

An analyst wants to filter or group the catalog by the year a title was added to Netflix, using the same Year parameter and Year field that existed in the source workbook, so that time-based exploration is preserved after migration.

**Why this priority**: The Year parameter and the derived Year field exist in the source and support the "Total Movies and TV Shows by Years" view, but they are supporting analytical conveniences rather than the core RLS requirement.

**Independent Test**: Can be tested by confirming a Year parameter (date, default 2024-03-26) is present and a Year field derived from the date a title was added is available for use in time-based visuals.

**Acceptance Scenarios**:

1. **Given** the migrated model, **When** an analyst inspects parameters, **Then** a Year parameter exists with a date data type and default value 2024-03-26.
2. **Given** the migrated model, **When** an analyst uses the "Total Movies and TV Shows by Years" visual, **Then** titles are grouped by the year derived from the date a title was added.

---

### Edge Cases

- **User not in entitlement table**: A signed-in user with no row in the entitlement mapping table sees no titles (empty, not an error).
- **User mapped to multiple countries**: If a user has more than one entitlement row, they see the union of all mapped countries' titles.
- **Country value mismatch / casing**: The original Tableau predicate compared country values case-insensitively (used `LOWER()` on both sides). In Power BI, relationships on text keys are case-insensitive by default, so a direct relationship on the country string reproduces the original matching behavior without an explicit `LOWER()` transformation (see Clarifications).
- **Multi-country titles**: The catalog `country` field may contain multiple comma-separated countries for a single title (e.g., "United States, India"). This migration uses an exact-match single-key relationship, so a multi-country title only matches an entitlement whose country equals the full comma-separated string. Splitting multi-country rows is documented as a possible future enhancement and is explicitly out of scope here (see Clarifications).
- **Missing date a title was added**: Titles where the added-date is blank or cannot be interpreted as a date cannot be assigned a Year; these are excluded from year-based grouping but still counted in non-time visuals.
- **Blank country in catalog**: Titles with no country value cannot match any entitlement and are therefore not visible to any restricted user.

## Clarifications

### Session 2026-06-09

- Q: Should country matching for RLS be exact, or normalized for case/whitespace differences between the catalog and entitlement tables? → A: Use a direct, single-direction relationship `User_Access[Country] → netflix_titles[country]` on the country string. Power BI relationships on text keys are case-insensitive by default, so this reproduces the Tableau `LOWER()`-based comparison without an explicit normalization step. Dynamic RLS is applied as a filter on the entitlement table: `User_Access[Username] = USERPRINCIPALNAME()`. The relationship is single-direction (User_Access → netflix_titles). Multi-country titles (comma-separated `country` values) are matched only on the full exact string; row-splitting is a documented future enhancement and is out of scope for this migration.
- Q: How does the Year parameter map, and what is the role of the Year field (`DATETIME([date_added])`)? → A: The Year parameter maps to a disconnected What-If/parameter (date type, default 2024-03-26) that is not related to any table. The `Year` field (`DATETIME([date_added])`) becomes a Date column derived from `date_added`, used as the axis for the "Total Movies and TV Shows by Years" time-series visual.
- Q: What Power BI visual type should each of the nine worksheets use? → A: Apply sensible defaults — Country wise distribution: filled map (fallback clustered bar chart); Total Movies and TV Shows by Years: line chart; Genre and Top 10 Genre: clustered bar chart; Rating and Ratings: clustered bar chart; Movies and TV Shows distribution: clustered bar chart (or donut for the two-category Movie/TV split); Duration: table; Description: table (or card). Final visual choices may be refined during report generation, but these defaults govern the migration.

## Requirements *(mandatory)*

### Functional Requirements

#### Data & Model
- **FR-001**: System MUST include a catalog table representing Netflix titles with the fields: show id, type, title, director, cast, country, date added, release year, rating, duration, listed-in (genre), and description, sourced from `Data/Netflix RLS/netflix_titles.csv`.
- **FR-002**: System MUST include an entitlement (user-access) mapping table with the fields: username and country, sourced from `Data/Netflix RLS/User_Access.csv`.
- **FR-003**: System MUST relate the entitlement table to the catalog table with a single-direction relationship on the country string (`User_Access[Country] → netflix_titles[country]`) so that the mapped country propagates the visibility restriction to catalog titles. Matching relies on Power BI's default case-insensitive text-key comparison (no explicit `LOWER()` normalization); multi-country catalog values are matched on the full exact string only.
- **FR-004**: System MUST provide a measure that returns the distinct count of titles (distinct count of show id), used as the primary metric across visuals, matching the Tableau `CountD(show_id)` behavior.
- **FR-005**: System MUST provide a Year field of Date data type derived from the date a title was added (equivalent to the Tableau `Year = DATETIME([date_added])` calculation), used as the axis for the "Total Movies and TV Shows by Years" time-series visual.
- **FR-006**: System MUST provide a Year parameter of date type with default value 2024-03-26 as a disconnected What-If/parameter (not related to any table), preserving the source parameter.

#### Row-Level Security (central feature)
- **FR-007**: System MUST enforce dynamic row-level security so that each viewer sees only the catalog titles for the country (or countries) mapped to their sign-in identity.
- **FR-008**: System MUST identify the current viewer by their sign-in identity (user principal name) and match it against the username column of the entitlement table (`User_Access[Username] = USERPRINCIPALNAME()`).
- **FR-009**: System MUST restrict the entitlement table to rows where the username equals the current viewer's identity, and propagate the resulting country restriction to the catalog table through the country relationship (`User_Access[Country] → netflix_titles[country]`).
- **FR-010**: System MUST apply the row-level security restriction to every visual on every report page without exception.
- **FR-011**: System MUST return an empty result set (no titles) for any viewer whose identity is not present in the entitlement table.
- **FR-012**: System MUST NOT hardcode any single user identity in the security rule (the source workbook's hardcoded `user2@maq.com` predicate MUST be generalized to all users via the mapping table).

#### Report Visuals
- **FR-013**: System MUST migrate all nine Tableau worksheets as Power BI report visuals using these default visual types: Country wise distribution (filled map, fallback clustered bar chart), Total Movies and TV Shows by Years (line chart), Genre (clustered bar chart), Top 10 Genre (clustered bar chart), Rating (clustered bar chart), Ratings (clustered bar chart), Movies and TV Shows distribution (clustered bar chart or donut for the Movie/TV split), Duration (table), and Description (table or card).
- **FR-014**: System MUST provide a consolidated report page equivalent to the Tableau "Netflix" dashboard that presents the migrated visuals together.
- **FR-015**: System MUST ensure all title-count visuals reflect the row-level-security restriction (counts shown are only for the viewer's entitled country).

### Key Entities *(include if feature involves data)*

- **Netflix Title (catalog)**: Represents a single Netflix title. Key attributes: show id (identifier), type (Movie/TV Show), title, director, cast, country, date added, release year, rating, duration, listed-in (genre), description. This is the secured table — its visibility is restricted by row-level security on country.
- **User Access (entitlement mapping)**: Represents a mapping of a user identity to an entitled country. Key attributes: username (the viewer's sign-in identity), country (the country the user is allowed to see). Drives dynamic row-level security. Sample rows: `shashank@maq.com` → India, `user2@maq.com` → United States, `user3@maq.com` → United Kingdom.
- **Country relationship**: Links entitlement country to catalog country, propagating the allowed country from the entitlement table to the catalog table.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of report visuals enforce the country entitlement — for any test user, no title from a non-entitled country is ever visible in any visual.
- **SC-002**: All three sample users see exactly the titles for their mapped country: `shashank@maq.com` sees only India titles, `user2@maq.com` sees only United States titles, `user3@maq.com` sees only United Kingdom titles.
- **SC-003**: A user with no entitlement row sees zero titles, with no error displayed.
- **SC-004**: All nine source worksheets are represented by an equivalent visual in the migrated report (9 of 9 migrated), plus one consolidated "Netflix" page.
- **SC-005**: Title counts in every visual match the distinct count of show id for the viewer's entitled subset (no double-counting and no inclusion of restricted rows).
- **SC-006**: The Year parameter (default 2024-03-26) and the Year field are present and usable in the time-based visual.

## Assumptions

- The viewer's sign-in identity (user principal name) corresponds to the `username` values stored in the entitlement table (email-style identities such as `user2@maq.com`).
- Country values in the catalog table and the entitlement table use the same naming convention, so an entitlement country can match a catalog country directly via a case-insensitive text-key relationship (see Clarifications).
- Only the two CSV files in `Data/Netflix RLS/` (`netflix_titles.csv` and `User_Access.csv`) are in scope; no external databases or additional sources are introduced.
- The distinct-count-of-titles metric is the primary measure used across the migrated visuals, consistent with the source workbook's use of `CountD(show_id)`.
- The single Tableau "Netflix" dashboard maps to a single consolidated Power BI report page; individual worksheets may also appear as standalone visuals on that page.
- The `Action (Country)` group in the source is a hidden auto-generated dashboard-action artifact and is NOT migrated as a user-defined grouping.
- The `ATTR()` aggregation in the Tableau RLS predicate is a Tableau-specific level-of-detail construct; in Power BI the equivalent restriction is achieved through the entitlement relationship and security filter, so no direct `ATTR()` equivalent is required.
