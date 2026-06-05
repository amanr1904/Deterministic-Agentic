# Feature Specification: Loan Portfolio Analysis Migration

**Feature Branch**: `005-loan-portfolio-pbi`  
**Created**: 2026-06-04  
**Status**: Draft  
**Input**: Migrate 'Loan Portfolio Analysis' Tableau workbook to Power BI semantic model (.pbip)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load and Model Loan Data (Priority: P1)

A business analyst opens the generated .pbip file in Power BI Desktop and sees all four data tables loaded with correct data from CSV files. The star schema relationships are established, and data flows correctly across dimensions.

**Why this priority**: Without correct data loading and relationships, no downstream analysis or measures will function.

**Independent Test**: Open the .pbip in Power BI Desktop, verify all tables appear in the model view with row counts matching source CSVs, and confirm relationships show correct cardinality arrows.

**Acceptance Scenarios**:

1. **Given** the .pbip file is opened in Power BI Desktop, **When** the model refreshes, **Then** all four tables load data without errors
2. **Given** tables are loaded, **When** viewing the model diagram, **Then** relationships between Loan→Customer (customer_id), Loan→LoanPurposes (purpose), and Loan→StateRegion (state) are visible and active
3. **Given** relationships are active, **When** filtering by a dimension (e.g., region), **Then** the fact table (Loan) filters correctly through the relationship

---

### User Story 2 - Calculate Loan Portfolio Metrics (Priority: P1)

A business analyst drags DAX measures onto a report canvas and sees correct aggregated values for Total Loans, Total Funded Amount, Default Rate, and Average Interest Rate — matching the logic from the original Tableau workbook.

**Why this priority**: Core measures are the primary analytical value of the workbook; without correct calculations the migration has no utility.

**Independent Test**: Create a card visual for each measure and compare values against known Tableau output or manual CSV calculations.

**Acceptance Scenarios**:

1. **Given** data is loaded, **When** the "Total Loans" measure is evaluated, **Then** it returns the count of all loan records
2. **Given** data is loaded, **When** the "Total Funded Amount" measure is evaluated, **Then** it returns the sum of funded_amount across all loans
3. **Given** data is loaded, **When** the "Default Rate" measure is evaluated, **Then** it returns the ratio of loans with status "Charged Off" to total loans
4. **Given** a filtered context (e.g., by state), **When** "Default Risk Category" is evaluated, **Then** it returns "High Risk" when Default Rate > 20%, otherwise "Safe"
5. **Given** data is loaded, **When** "Average Interest Rate" measure is evaluated, **Then** it returns SUM of int_rate (matching Tableau's SUM aggregation behavior)

---

### User Story 3 - Use Top N Parameter for Dynamic Filtering (Priority: P2)

A report consumer adjusts the "Top N" parameter (integer, 1–50) and the report dynamically shows only the top N items by the relevant ranking metric, replicating the Tableau INDEX()-based filtering behavior.

**Why this priority**: The parameter enables interactive exploration but is secondary to correct data loading and core measures.

**Independent Test**: Set Top N to 5 in the slicer, verify that only 5 rows/items appear in visuals that use the Top N filter logic.

**Acceptance Scenarios**:

1. **Given** the report is open, **When** the Top N parameter is set to 10, **Then** ranked visuals display exactly 10 items
2. **Given** the Top N parameter exists, **When** its value is changed between 1 and 50, **Then** the visual updates dynamically without errors
3. **Given** default settings, **When** the report first loads, **Then** the Top N parameter defaults to 1

---

### User Story 4 - Analyze Year-over-Year Growth and Trends (Priority: P2)

A business analyst views YoY Growth % and Highlight Peak Year measures that replicate Tableau's table calculation behavior — showing percentage growth between consecutive years and highlighting the year with maximum loan volume.

**Why this priority**: Trend analysis is valuable but depends on correct base measures being in place first.

**Independent Test**: Create a table with issue_year, Total Loans, and YoY Growth %. Verify growth percentages align with manual calculation of (current year count - prior year count) / prior year count.

**Acceptance Scenarios**:

1. **Given** loan data grouped by issue_year, **When** "YoY Growth %" is evaluated, **Then** it shows the percentage change in loan count from the previous year
2. **Given** a year context, **When** "Highlight Peak Year" is evaluated, **Then** it identifies the year with the maximum loan count across all years
3. **Given** the first year in the dataset, **When** "YoY Growth %" is evaluated, **Then** it returns BLANK (no prior year for comparison)

---

### User Story 5 - Rank States by Loan Volume (Priority: P3)

A business analyst sees states ranked by loan metrics using the State Rank measure, replicating Tableau's RANK table calculation in DAX.

**Why this priority**: Ranking is an enhancement over basic aggregations and depends on correct measure foundations.

**Independent Test**: Create a table with state, Total Loans, and State Rank. Verify the state with the most loans has rank 1.

**Acceptance Scenarios**:

1. **Given** loan data, **When** "State Rank" is evaluated in a table by state, **Then** states are ranked by loan count with 1 being the highest
2. **Given** a filtered context, **When** the ranking is recalculated, **Then** ranks adjust to the filtered subset

---

### Edge Cases

- What happens when a loan record has a NULL customer_id? The relationship should handle missing keys gracefully (unmatched rows remain in fact table).
- What happens when loan_status contains values other than "Charged Off" or "Fully Paid"? Default Flag should return 0 for any non-"Charged Off" status.
- What happens when Top N parameter is set to a value exceeding available rows? All available rows should display without error.
- What happens when a year has no prior year for YoY calculation? The measure returns BLANK.
- What happens when int_rate contains NULL values? SUM should treat NULLs as 0 per DAX default behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load data from four CSV files (loan.csv, customer.csv, loan_purposes.csv, state_region.csv) located in the Data/Loan/ folder — these correspond to the multi-table "customer" datasource in Tableau. Pre-aggregated/filtered views (loan_count_by_year.csv, loan_with_region.csv) are excluded as their data is derivable from the primary source.
- **FR-002**: System MUST establish a star schema with loan.csv as the central fact table and customer.csv, loan_purposes.csv, state_region.csv as dimension tables
- **FR-003**: System MUST create active relationships: Loan→Customer (customer_id, many-to-one), Loan→LoanPurposes (purpose, many-to-one), Loan→StateRegion (state, many-to-one)
- **FR-004**: System MUST generate DAX measures: Total Loans (COUNT of loan_id), Total Funded Amount (SUM of funded_amount), Default Rate (ratio of defaults to total loans), Default Risk Category (categorical based on Default Rate threshold of 0.20). Default Flag MUST be implemented as a calculated column (row-level classification: 1 if loan_status = "Charged Off", else 0).
- **FR-005**: System MUST generate DAX measures: YoY Growth % (percentage change in loan count year-over-year using OFFSET or PREVIOUSYEAR pattern), Highlight Peak Year (identifies maximum loan count year using CALCULATE+ALL pattern), State Rank (ranks states by loan volume using RANKX), Average Interest Rate (SUM of int_rate)
- **FR-006**: System MUST create a "Top N" parameter as an integer What-If parameter with range 1–50 and default value 1, implemented as a disconnected table using GENERATESERIES(1, 50, 1) with a corresponding slicer-bound measure
- **FR-007**: System MUST implement Top N Filter logic that limits displayed items to the top N ranked entries
- **FR-008**: System MUST produce a valid .pbip project structure at Output/LoanPortfolioAnalysis/ with proper .SemanticModel/ and .Report/ folders
- **FR-009**: System MUST generate TMDL files that pass validation (tmdl-validate and validate_pbip.py)
- **FR-010**: System MUST apply data categories to geographic columns: state→State/Province, zip_code→Postal Code, region→Continent, subregion→Country/Region

### Key Entities

- **Loan (Fact)**: Central transaction table containing loan_id, customer_id, amounts, rates, status, dates, and descriptive fields. Primary grain: one row per loan.
- **Customer (Dimension)**: Customer demographic and financial attributes. Linked via customer_id.
- **Loan Purposes (Dimension)**: Reference table of loan purpose categories. Linked via purpose.
- **State Region (Dimension)**: Geographic hierarchy mapping states to subregions and regions. Linked via state.
- **Top N Parameter**: Disconnected GENERATESERIES table (1–50) enabling dynamic filtering of ranked results via slicer-bound measure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The .pbip file opens in Power BI Desktop without any load errors or warnings
- **SC-002**: All four tables display correct row counts matching the source CSV files (loan.csv, customer.csv, loan_purposes.csv, state_region.csv)
- **SC-003**: All three relationships resolve correctly — filtering a dimension filters the fact table as expected
- **SC-004**: All 9 DAX measures return non-error values when placed on a report canvas
- **SC-005**: The Top N parameter slicer allows selection between 1 and 50, and visuals respond to parameter changes
- **SC-006**: Default Rate calculation matches manual computation: count of "Charged Off" loans / total loan count
- **SC-007**: YoY Growth % returns correct percentage differences between consecutive years
- **SC-008**: State Rank assigns rank 1 to the state with the highest loan count
- **SC-009**: TMDL validation (tmdl-validate) and project validation (validate_pbip.py) both pass with exit code 0

## Assumptions

- All source CSV files exist in the Data/Loan/ folder and are well-formed (consistent headers, no encoding issues)
- The "customer" multi-table logical model in Tableau will be decomposed into separate Power BI tables with explicit relationships (star schema) using natural keys from the original Tableau joins
- Pre-aggregated views (loan_count_by_year.csv, loan_with_region.csv) are excluded from the model; their metrics are derivable from measures on the primary star schema
- Tableau's LOOKUP-based YoY Growth will be translated to a DAX time-intelligence pattern using OFFSET or PREVIOUSYEAR logic
- Tableau's WINDOW_MAX will be translated to a DAX CALCULATE + ALL pattern
- Tableau's RANK will be translated to DAX RANKX
- Tableau's INDEX() <= Parameter for Top N will be translated to a DAX RANKX-based filter combined with a GENERATESERIES disconnected table
- The "Average Interest Rate" field uses SUM (matching Tableau's stated aggregation), not AVERAGE — this preserves source behavior
- Default Flag is a calculated column (row-level determination) rather than a measure, per DAX best practice for row-level classification
- Output folder Output/LoanPortfolioAnalysis/ will be created fresh; no prior artifacts need preservation
- Constitution rules (.specify/memory/constitution.md) will govern naming conventions, DAX formatting, and M query patterns during implementation

## Clarifications

### Session 2026-06-04

- Q: Measure vs calculated column for Default Flag? → A: Calculated column (row-level classification is a property of the row, not an aggregation). All other metrics remain DAX measures per constitution §3 best practices.
- Q: How to handle the multi-table "customer" datasource with joined tables (loan, customer, loan_purposes, state_region)? → A: Star schema decomposition using natural keys from Tableau's join definitions (customer_id, purpose, state). Each table becomes an independent Power BI table with explicit relationships.
- Q: How to translate Tableau table calculations (YoY Growth %, Highlight Peak Year, State Rank, Top N Filter)? → A: Map to DAX equivalents per constitution §3 — YoY Growth via OFFSET/PREVIOUSYEAR, Highlight Peak Year via CALCULATE+ALL, State Rank via RANKX, Top N via RANKX+disconnected parameter table.
- Q: What data categories should be applied to geographic columns? → A: state→State/Province, zip_code→Postal Code, region→Continent, subregion→Country/Region. Enables map visuals and geographic drill-down in Power BI.
- Q: How to implement the Top N parameter (integer 1–50)? → A: What-If parameter using GENERATESERIES(1, 50, 1) as a disconnected table with a slicer-bound measure (Top N Value). Filtering logic uses RANKX ≤ [Top N Value].
- Q: Should standalone datasources (loan.csv alone, loan_count_by_year.csv, loan_with_region.csv) be loaded as separate tables? → A: No. These are pre-aggregated/filtered views of the same underlying data. Use only the multi-table "customer" datasource (loan.csv + customer.csv + loan_purposes.csv + state_region.csv) as the primary source. Yearly counts are derivable via measures on the fact table.
