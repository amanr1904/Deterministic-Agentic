# Feature Specification: Midnight Census Dashboard — Tableau to Power BI Migration

**Feature Branch**: `003-midnight-census-pbi`  
**Created**: 2026-06-19  
**Status**: Draft  
**Workbook**: Data/Midnight Census/Midnight Census Dashboard.twb  
**Output**: Output/MidnightCensusDashboard/

---

## Overview

Migrate the Midnight Census Dashboard Tableau workbook — a healthcare patient census tracking report — into a fully functional Power BI project (.pbip). The dashboard tracks nightly patient census counts across hospitals and units, supports daily and monthly aggregation, allows filtering by patient class (Adults/Peds/All), and warns users when the selected date range cuts across a partial calendar month.

The source is a single flat CSV file (`Midnight_Census_Template.csv`) with 10 columns and no relationships. The migration produces a semantic model and report layer that faithfully reproduces the Tableau interactivity using Power BI-native constructs.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Census Data Loads and Displays (Priority: P1)

A hospital analyst opens the Power BI report and sees current nightly census counts by unit and hospital, sourced from the CSV file, without any errors or blank visuals.

**Why this priority**: The entire report is built on a single CSV source. If data does not load correctly, nothing else functions.

**Independent Test**: Open the .pbip in Power BI Desktop, refresh data, and verify row counts and column types match the source CSV.

**Acceptance Scenarios**:

1. **Given** the CSV file is present at `Data/Midnight Census/Midnight_Census_Template.csv`, **When** the semantic model is refreshed, **Then** all 10 columns load with correct data types (DEPARTMENT_KEY as integer, Census Date as date, Census Count fields as integers, all dimension columns as text).
2. **Given** data has loaded, **When** a user views the main report page, **Then** census counts are visible grouped by Hospital and Unit without blank or error tiles.
3. **Given** the CSV has missing values in optional dimension columns, **When** data is refreshed, **Then** the model loads without errors and blank values display as blanks (not errors).

---

### User Story 2 — Date Range Filtering (Priority: P1)

A user selects a start date and end date using slicers on the report, and all visuals immediately filter to show only census records within that range.

**Why this priority**: Date range is the primary navigation mechanism in the original dashboard; without it the report is unusable for time-based analysis.

**Independent Test**: Set Start Date to a specific month, set End Date to the same month, and verify only records from that month appear across all visuals.

**Acceptance Scenarios**:

1. **Given** the report is open, **When** the user sets Start Date to 2023-01-01 and End Date to 2023-03-31, **Then** all chart and table visuals show only census records with Census Date between those dates (inclusive).
2. **Given** a date range that spans partial calendar months, **When** the partial data warning is enabled, **Then** the warning strip displays a visible indicator.
3. **Given** the user changes the date range to a period with no data, **When** visuals refresh, **Then** visuals show empty state gracefully (no errors, no crashes).

---

### User Story 3 — Adults/Peds/All Patient Class Filter (Priority: P2)

A user selects "Adults", "Peds", or "All" from a slicer to switch the census count measure between `Census Count Adults`, `Census Count Peds`, or the combined `Census Count`.

**Why this priority**: This is the second most-used interactive control; clinical teams routinely split adult and pediatric populations.

**Independent Test**: Select "Adults", verify the census total matches the sum of `Census Count Adults` from the raw data. Select "Peds", verify it matches `Census Count Peds`.

**Acceptance Scenarios**:

1. **Given** the filter is set to "All", **When** a user views census totals, **Then** values reflect the combined `Census Count` column.
2. **Given** the filter is set to "Adults", **When** a user views census totals, **Then** values reflect `Census Count Adults` only.
3. **Given** the filter is set to "Peds", **When** a user views census totals, **Then** values reflect `Census Count Peds` only.
4. **Given** the filter switches between values, **When** visuals update, **Then** the change reflects immediately without a page reload.

---

### User Story 4 — Monthly vs Daily Aggregation Toggle (Priority: P2)

A user switches between "Monthly" and "Daily" views to see census data summarized by month or broken down by day.

**Why this priority**: The dual-aggregation view is a primary feature of the original dashboard that supports both executive summary (monthly) and operational (daily) use cases.

**Independent Test**: Set Date Agg Level to "Monthly", verify Census Date is grouped by month. Set to "Daily", verify each row represents a single day.

**Acceptance Scenarios**:

1. **Given** Date Agg Level is "Monthly", **When** the bar chart is visible, **Then** the X-axis shows months and values are monthly sums.
2. **Given** Date Agg Level is "Daily", **When** the bar chart is visible, **Then** the X-axis shows individual dates and values are daily counts.
3. **Given** Date Agg Level is "Monthly", **When** the data table is visible, **Then** rows are grouped by month and hospital/unit.
4. **Given** Date Agg Level is "Daily", **When** the data table is visible, **Then** rows show one entry per day per hospital/unit combination.

---

### User Story 5 — Bar Chart vs Data Table View Toggle (Priority: P2)

A user switches between "Bar Chart" and "Data Table" views to see the same data in a visual chart or a tabular format.

**Why this priority**: The original dashboard offers this toggle as a primary navigation control; users export the table view for downstream analysis.

**Independent Test**: Select "Bar Chart" — verify the bar chart visual is shown and the table visual is hidden. Select "Data Table" — verify the reverse.

**Acceptance Scenarios**:

1. **Given** View is set to "Bar Chart", **When** the report renders, **Then** the bar chart visual is visible and the data table visual is hidden.
2. **Given** View is set to "Data Table", **When** the report renders, **Then** the data table visual is visible and the bar chart visual is hidden.
3. **Given** both toggles (View + Date Agg Level) are combined, **When** a user selects "Daily" + "Data Table", **Then** only the daily data table is shown.

---

### User Story 6 — Partial Month Data Warning (Priority: P3)

When the selected date range starts or ends mid-month, a warning indicator appears on the report to alert users that census totals for those boundary months are incomplete.

**Why this priority**: Clinical reporting requires accurate completeness indicators; partial month totals can be misread as low census counts.

**Independent Test**: Set Start Date to the 15th of a month. Verify the partial data warning indicator is visible. Set Start Date to the 1st of a month and End Date to the last day. Verify the warning is not shown.

**Acceptance Scenarios**:

1. **Given** Start Date is set to a day other than the 1st of the month, **When** the report renders, **Then** a warning message is displayed indicating partial data in the start month.
2. **Given** End Date is set to a day other than the last day of the month, **When** the report renders, **Then** a warning message is displayed indicating partial data in the end month.
3. **Given** both Start Date and End Date fall on exact month boundaries, **When** the report renders, **Then** no warning is displayed.

---

### User Story 7 — Dimensional Slicers (Hospital, Unit, Patient Class) (Priority: P3)

A user filters the report by Parent Hospital, Hospital, Unit, and Patient Class using slicers to focus on a specific clinical area.

**Why this priority**: Multi-dimensional filtering is needed for department-level operational reviews.

**Independent Test**: Select a single hospital from the Hospital slicer; verify all visuals show only data for that hospital.

**Acceptance Scenarios**:

1. **Given** the report is open with all slicers at default (all selected), **When** a user selects a single Hospital value, **Then** all visuals filter to show only that hospital's census data.
2. **Given** a hospital is selected, **When** the user also selects a Unit within that hospital, **Then** visuals narrow further to only that unit.
3. **Given** all slicers are active, **When** a user clears all slicer selections, **Then** all data is shown again.

---

### Edge Cases

- What happens when the CSV file path changes or the file is missing? The model should report a data source error gracefully, not a crash.
- How does the report handle Census Date values that fall outside the Start Date / End Date parameter defaults? Records outside defaults are hidden but accessible by adjusting the date range.
- What if `Census Count Adults` + `Census Count Peds` does not sum to `Census Count` for some rows? The migration uses each column independently as authored in the source — no cross-validation is performed.
- What happens when the selected date range has zero records? All visuals display empty state; the partial-month warning logic should not throw a DAX error when the date table returns no rows.
- Can a user select both "Bar Chart" view and "Data Table" view simultaneously? No — the View parameter is mutually exclusive; the semantic model enforces single-value selection.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Data Loading & Source
- **FR-001**: The semantic model MUST load data from `Data/Midnight Census/Midnight_Census_Template.csv` using a Power Query M expression.
- **FR-002**: The model MUST expose all 10 source columns with correct data types: DEPARTMENT_KEY (whole number), Encounter CSN (text), Parent Hospital (text), Hospital (text), Unit (text), Patient Class (text), Census Date (date), Census Count (whole number), Census Count Adults (whole number), Census Count Peds (whole number).
- **FR-003**: The model MUST include a calculated Date dimension table covering the full range of Census Date values to support time-intelligence operations.

#### Measures
- **FR-004**: The model MUST include a `User Defined Census Count` measure that returns `Census Count`, `Census Count Adults`, or `Census Count Peds` based on the active selection of the Adults/Peds filter parameter.
- **FR-005**: The model MUST include a `Start Month Contains Partial Data?` measure implementing: `IF(SELECTEDVALUE('Start Date'[Start Date]) <> STARTOFMONTH(SELECTEDVALUE('Start Date'[Start Date])), 1, 0)`. Returns 1 when the selected Start Date is not the 1st of its month, 0 otherwise. This replaces the Tableau `WINDOW_MIN` table calculation.
- **FR-006**: The model MUST include an `End Month Contains Partial Data?` measure implementing: `IF(SELECTEDVALUE('End Date'[End Date]) <> ENDOFMONTH(SELECTEDVALUE('End Date'[End Date])), 1, 0)`. Returns 1 when the selected End Date is not the last day of its month, 0 otherwise. This replaces the Tableau `WINDOW_MAX` table calculation.
- **FR-007**: The model MUST include a `Partial Months in View?` measure that returns a non-empty warning string when either boundary-month partial-data measure returns 1, and returns blank otherwise.
- **FR-008**: The model MUST include a `Last Refresh Date` measure returning the most recent Census Date in the loaded data.
- **FR-009**: Tableau calculated fields are split by kind: **DAX measures** for all aggregation-level logic (`User Defined Census Count`, `Start Month Contains Partial Data?`, `End Month Contains Partial Data?`, `Partial Months in View?`, `Last Refresh Date`, `Default Start Date`, `Default End Date`); **no calculated columns** are added to the fact table for the CASE-based show/hide fields (`Date agg_Monthly`, `Date agg_Daily`, `View_BarChart`, `View_DataTable`, `Date Range Filter`, `Census Date_CY`) — these are replaced by slicer/bookmark logic and are not needed as persistent columns.

#### Parameters & Slicers
- **FR-010**: The model MUST expose a `Filter Adults/Peds` parameter with values: All, Adults, Peds (default: All). This parameter MUST integrate with `User Defined Census Count`.
- **FR-011**: The model MUST expose a `Date Agg Level` parameter with values: Monthly, Daily (default: Monthly). Report visuals use this to determine which aggregation-level page or visual is shown.
- **FR-012**: The model MUST expose a `View` parameter with values: Bar Chart, Data Table (default: Bar Chart). Report layer uses this to toggle visual visibility via bookmarks.
- **FR-013**: The model MUST support date range filtering through `Start Date` and `End Date` What-If parameter tables, each generated with `GENERATESERIES(DATE(2021,1,1), TODAY()-1, 1)` and exposed as **date slicers** (Between filter type) bound to `Census Date`. No boolean calculated column (`Date Range Filter`) is added to the fact table — the slicer filter is the Power BI equivalent. All census visuals MUST respect the selected date range via the slicer context.

#### Report Layer
- **FR-014**: The report MUST contain a main interactive page reproducing the "Midnight Census" dashboard with: a parameter/slicer control bar (Date Agg Level, View, Start Date, End Date, Filter Adults/Peds), dimensional slicers (Parent Hospital, Hospital, Patient Class, Unit), a partial data warning strip, a primary bar chart visual, a data table visual, and a dynamic filter caption strip.
- **FR-015**: The report MUST implement the View toggle (Bar Chart / Data Table) such that exactly one of the two visual types is visible at a time based on the View parameter selection.
- **FR-016**: The report MUST implement the Date Agg Level toggle (Monthly / Daily) such that the correct aggregation-level visuals are active based on the selection.
- **FR-017**: The report MUST include an Info splash page reproducing the informational content from the Tableau "Info" dashboard (title, description, source, contacts, refresh schedule).
- **FR-018**: The report MUST display a **Card visual** bound to the `Last Refresh Date` measure (`MAX(Midnight_Census_Template[Census Date])`). The card title or subtitle MUST display the static text "Refreshes Daily 2:00 AM", replicating the Tableau title pattern with a fixed caption (Power BI does not surface refresh metadata dynamically in a card).

#### Validation
- **FR-019**: The generated .pbip MUST open in Power BI Desktop without errors or warnings about missing data sources, broken measures, or invalid visual bindings.
- **FR-020**: The TMDL files MUST pass structural validation (`tmdl-validate`) with zero errors.
- **FR-021**: The PBIR JSON files MUST pass schema validation (`validate_pbip.py`) with exit code 0.

---

### Key Entities

- **Midnight_Census_Template** (Fact table): The single flat table sourced from the CSV. Contains one row per nightly census observation per unit. Key fields: DEPARTMENT_KEY, Encounter CSN, Hospital, Unit, Patient Class, Census Date, Census Count, Census Count Adults, Census Count Peds.
- **Date** (Calculated dimension): A generated date table spanning the range of Census Date values. Supports time-intelligence DAX functions used in partial-month detection measures.
- **Filter Adults/Peds** (What-If parameter table): A single-column table with values All, Adults, Peds. Connected to `User Defined Census Count` via SELECTEDVALUE.
- **Date Agg Level** (What-If parameter table): A single-column table with values Monthly, Daily. Consumed by report bookmark logic and any DAX that branches on aggregation level.
- **View** (What-If parameter table): A single-column table with values Bar Chart, Data Table. Consumed by report bookmark logic to show/hide visuals.
- **Start Date / End Date** (What-If date parameters): Single-column date parameter tables generated with `GENERATESERIES(DATE(2021,1,1), TODAY()-1, 1)` (one row per day). Exposed as single-select date slicers (Between filter type) bound to `Census Date`. Used by partial-month detection measures via `SELECTEDVALUE('Start Date'[Start Date])` and `SELECTEDVALUE('End Date'[End Date])`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Power BI report opens in Power BI Desktop in under 30 seconds and displays census data without any error dialogs or broken visual placeholders.
- **SC-002**: After data refresh, total census record count in the Power BI model matches the total row count of `Midnight_Census_Template.csv` (no rows dropped, no duplicates introduced).
- **SC-003**: Setting the Adults/Peds filter to "Adults" produces census totals that exactly match the sum of `Census Count Adults` from the raw CSV for the same date range — verified by comparing raw CSV aggregation against the Power BI visual value.
- **SC-004**: The partial-month warning appears for every test case where Start Date is not the 1st of a month or End Date is not the last day of a month, and is absent for all whole-month ranges.
- **SC-005**: Switching between Bar Chart and Data Table views shows and hides the correct visuals in under 1 second with no page reload required.
- **SC-006**: Switching between Monthly and Daily aggregation levels shows the correct visual in under 1 second with correct axis granularity (month labels vs day labels).
- **SC-007**: All dimensional slicers (Hospital, Unit, Patient Class, Parent Hospital) cross-filter all chart and table visuals correctly — selecting one value shows only matching records in all other visuals.
- **SC-008**: TMDL validation (`tmdl-validate`) returns zero errors on the generated `.SemanticModel/definition/` folder.
- **SC-009**: PBIP validation (`validate_pbip.py`) returns exit code 0 on the `Output/MidnightCensusDashboard/` folder.
- **SC-010**: The migrated report is functionally equivalent to the original Tableau dashboard as assessed by a side-by-side comparison — no worksheet from the Tableau source is left unmigrated without documented justification.

---

## Assumptions

- The active datasource is the CSV (`Midnight_Census_Template.csv`); the inactive Hyper extract datasource (`Midnight_Census_Template.hyper`) is **completely ignored** — it references an absolute developer-machine path and is not used by any worksheet. Only the CSV is loaded via M query.
- The CSV will remain at the relative path `Data/Midnight Census/Midnight_Census_Template.csv` from the workspace root; the M query will use a relative file path pattern.
- No star schema design is needed — the source is a single flat table. A calculated Date table will be added for time-intelligence support only.
- No Row-Level Security (RLS) is required — the original workbook has no RLS configuration.
- The "Sheet 9" placeholder worksheet from Tableau has no content and will not be migrated to a report visual.
- The "Filters Applied Caption" dynamic text strip from Tableau will be approximated using a Power BI card visual with a DAX measure that concatenates active filter values; exact pixel-perfect reproduction is not required.
- The visual toggle mechanism (View parameter + Date Agg Level parameter) will be implemented using **4 bookmarks** covering the full combination matrix: `Bookmark_Monthly_Bar`, `Bookmark_Monthly_Table`, `Bookmark_Daily_Bar`, `Bookmark_Daily_Table`. Each bookmark hides 3 of the 4 primary visuals and shows 1. Navigation buttons on the canvas trigger bookmark switches. No DAX-based `ISFILTERED` hide logic is used — bookmarks are the Power BI equivalent of Tableau's Include/Exclude filter pattern.
- The Info splash page will be reproduced as a static text/card page in Power BI; the exact Tableau freehand text zone layout will be approximated, not pixel-matched.
- Default date range values (Start Date: 2021-01-01, End Date: today minus 1 day) are applied as What-If parameter defaults; users can override them via slicers.
- "Refreshes Daily 2:00 AM" metadata is a display note only — scheduling is not part of this migration scope.
- All generated artifacts will be placed under `Output/MidnightCensusDashboard/` following the workspace output folder convention.
- Power BI Desktop version compatibility target is the current GA release; no preview features will be required.

---

## Clarifications

### Session 2026-06-19

- Q: Should `User Defined Census Count`, partial-month flags, and `Last Refresh Date` be measures or calculated columns? → A: **Measures**. All aggregation-level logic (`User Defined Census Count`, `Start Month Contains Partial Data?`, `End Month Contains Partial Data?`, `Partial Months in View?`, `Last Refresh Date`, `Default Start Date`, `Default End Date`) are DAX measures. The CASE-based show/hide Tableau fields (`Date agg_Monthly`, `Date agg_Daily`, `View_BarChart`, `View_DataTable`, `Date Range Filter`, `Census Date_CY`) are not migrated as calculated columns — they are replaced by slicer and bookmark logic and carry no value as persistent row-level columns.
- Q: How should Tableau parameters be implemented in Power BI? → A: `Filter Adults/Peds`, `Date Agg Level`, and `View` are **What-If parameter tables** (single string-column tables with 3, 2, and 2 rows respectively), each exposed as a single-select slicer. `Start Date` and `End Date` are **What-If date parameter tables** generated with `GENERATESERIES(DATE(2021,1,1), TODAY()-1, 1)` and exposed as date slicers (Between filter type).
- Q: How should the View + Date Agg Level visual show/hide pattern be implemented? → A: **4 bookmarks**, one per combination: `Bookmark_Monthly_Bar`, `Bookmark_Monthly_Table`, `Bookmark_Daily_Bar`, `Bookmark_Daily_Table`. Each bookmark hides 3 of the 4 primary visuals and shows 1. Navigation buttons on the canvas trigger bookmark switches. No DAX `ISFILTERED` hide logic is used — bookmarks are the Power BI equivalent of Tableau's Include/Exclude filter pattern.
- Q: What is the DAX pattern for `Start Month Contains Partial Data?` and `End Month Contains Partial Data?` (replacing Tableau WINDOW_MIN/MAX table calcs)? → A: `Start Month Contains Partial Data? = IF(SELECTEDVALUE('Start Date'[Start Date]) <> STARTOFMONTH(SELECTEDVALUE('Start Date'[Start Date])), 1, 0)`. `End Month Contains Partial Data? = IF(SELECTEDVALUE('End Date'[End Date]) <> ENDOFMONTH(SELECTEDVALUE('End Date'[End Date])), 1, 0)`. Both use boundary comparisons against the What-If parameter SELECTEDVALUE rather than table calculations.
- Q: Should Sheet 9 (empty placeholder) be migrated to a report visual? → A: **No**. Sheet 9 is an empty Tableau placeholder with no encodings, marks, or data. No visual container is generated for it in the report layer.
- Q: How should `Last Refresh Date` be displayed in the report? → A: As a **Card visual** bound to `MAX(Midnight_Census_Template[Census Date])`. The card subtitle displays the static text "Refreshes Daily 2:00 AM", replicating the Tableau title metadata pattern. Power BI does not surface refresh-engine timestamps dynamically in a card, so this is a static caption.
- Q: Should the inactive Hyper extract datasource be loaded or referenced in the migration? → A: **No**. The Hyper datasource references an absolute developer-machine path (`C:/Users/AmanRajMAQSoftware/Downloads/...`) and is inactive in the workbook. It is completely ignored. Only `Midnight_Census_Template.csv` is loaded.
- Q: Should `Date Range Filter` be implemented as a calculated boolean column on the fact table? → A: **No**. It is implemented as a **date slicer** (Between filter type) on `Census Date`, with `Start Date` and `End Date` What-If parameter values as the bounds. No boolean column is added to `Midnight_Census_Template`. This is the direct Power BI equivalent of the Tableau `[Census Date] >= [Start Date] AND [Census Date] <= [End Date]` row-level filter.

