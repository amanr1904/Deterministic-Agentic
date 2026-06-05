# Tasks: Loan Portfolio Analysis Migration

**Input**: Design documents from `specs/005-loan-portfolio-pbi/`  
**Prerequisites**: plan.md ✅, spec.md ✅, .specify/memory/star-schema-output.md ✅, .specify/memory/dax-measures-output.md ✅  
**Constitution**: `.specify/memory/constitution.md` (read-only rulebook — never modify)  
**Output Path**: `Output/LoanPortfolioAnalysis/`

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All file paths are relative to workspace root

---

## Phase 1: Setup (Validate & Confirm)

**Purpose**: Validate constitution compliance and confirm all design artifacts are present before generation.

- [ ] T001 Read constitution at .specify/memory/constitution.md and confirm all rules (§0–§10) are understood
- [ ] T002 [P] Verify design artifact exists: .specify/memory/star-schema-output.md (FactLoan, DimCustomer, DimPurpose, DimStateRegion, DimDate, TopNParameter)
- [ ] T003 [P] Verify design artifact exists: .specify/memory/dax-measures-output.md (14 measures, 2 calc columns, 1 What-If parameter)
- [ ] T004 [P] Verify source CSV files exist: Data/Loan/loan.csv, Data/Loan/customer.csv, Data/Loan/loan_purposes.csv, Data/Loan/state_region.csv
- [ ] T005 Validate plan.md constitution check table — all rules must show ✅ Pass before proceeding

**Checkpoint**: All inputs validated — proceed to PBIP generation.

---

## Phase 2: PBIP Generation — Foundational Structure

**Purpose**: Create the PBIP project skeleton that all user stories depend on.

- [ ] T006 Create output directory structure: Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/
- [ ] T007 [P] Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.pbip (project root file with version and semantic model reference)
- [ ] T008 [P] Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition.pbism (schema reference and dataset binding)
- [ ] T009 [P] Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/.platform (platform config JSON)
- [ ] T010 [P] Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/diagramLayout.json (empty diagram layout)
- [ ] T011 Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/database.tmdl (compatibilityLevel 1567, Import mode)
- [ ] T012 Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/model.tmdl (model metadata, culture en-US, default Power BI data source version)
- [ ] T013 [P] Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.Report/definition.pbir (report binding to semantic model via byPath)
- [ ] T014 [P] Generate Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.Report/.platform (platform config JSON)

**Checkpoint**: PBIP skeleton created — table and measure generation can begin.

---

## Phase 3: User Story 1 — Load and Model Loan Data (Priority: P1) 🎯 MVP

**Goal**: Generate all table TMDL files with M queries and establish star schema relationships so data loads correctly in Power BI Desktop.

**Independent Test**: Open .pbip in Power BI Desktop, verify all 6 tables load with correct row counts and relationships display correct cardinality.

### Table Generation (US1)

- [ ] T015 [P] [US1] Generate FactLoan table TMDL in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/FactLoan.tmdl — M query loads Data/Loan/loan.csv with Csv.Document, promote headers, type transforms; columns: loan_id, customer_id, loan_amnt, funded_amnt, int_rate, installment, grade, sub_grade, purpose, state, loan_status, issue_d, IssueDate (date type); summarizeBy: none on keys/text columns
- [ ] T016 [P] [US1] Generate DimCustomer table TMDL in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/DimCustomer.tmdl — M query loads Data/Loan/customer.csv; columns: customer_id (isKey), annual_inc, emp_length, home_ownership, verification_status; Text.Trim on customer_id
- [ ] T017 [P] [US1] Generate DimPurpose table TMDL in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/DimPurpose.tmdl — M query loads Data/Loan/loan_purposes.csv; columns: purpose (isKey), purpose_label; Text.Trim on purpose
- [ ] T018 [P] [US1] Generate DimStateRegion table TMDL in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/DimStateRegion.tmdl — M query loads Data/Loan/state_region.csv; columns: state (isKey), subregion, region; data categories: state→StateOrProvince, region→Continent, subregion→CountryRegion; Text.Trim on state
- [ ] T019 [P] [US1] Generate DimDate table TMDL in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/DimDate.tmdl — M query uses List.Dates to generate 2007-01-01 to 2015-12-31; columns: Date (isKey, type date), Year (Int64), Month (Int64), MonthName (text), Quarter (text); mark as date table
- [ ] T020 [US1] Generate relationships in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/relationships.tmdl — four relationships: FactLoan[customer_id]→DimCustomer[customer_id] (many-to-one, single), FactLoan[purpose]→DimPurpose[purpose] (many-to-one, single), FactLoan[state]→DimStateRegion[state] (many-to-one, single), FactLoan[IssueDate]→DimDate[Date] (many-to-one, single)

**Checkpoint**: US1 complete — star schema established with all tables and relationships.

---

## Phase 4: User Story 2 — Calculate Loan Portfolio Metrics (Priority: P1) 🎯 MVP

**Goal**: Add core DAX measures and calculated columns to FactLoan table so analysts can evaluate loan portfolio health.

**Independent Test**: Place Total Loans, Total Funded Amount, Default Rate, and Average Interest Rate on card visuals — verify non-error numeric results.

### Calculated Columns (US2)

- [ ] T021 [US2] Add DefaultFlag calculated column to FactLoan table in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/FactLoan.tmdl — DAX: IF(FactLoan[loan_status] = "Charged Off", 1, 0); dataType: int64; formatString: 0

### Core Measures (US2)

- [ ] T022 [P] [US2] Add measure "Total Loans" to FactLoan table TMDL — DAX: COUNTROWS(FactLoan); displayFolder: Core Metrics; formatString: #,##0
- [ ] T023 [P] [US2] Add measure "Total Funded Amount" to FactLoan table TMDL — DAX: SUM(FactLoan[funded_amnt]); displayFolder: Core Metrics; formatString: "₹"#,##0
- [ ] T024 [P] [US2] Add measure "Total Loan Amount" to FactLoan table TMDL — DAX: SUM(FactLoan[loan_amnt]); displayFolder: Core Metrics; formatString: "₹"#,##0
- [ ] T025 [P] [US2] Add measure "Average Loan Amount" to FactLoan table TMDL — DAX: AVERAGE(FactLoan[loan_amnt]); displayFolder: Core Metrics; formatString: "₹"#,##0.00
- [ ] T026 [P] [US2] Add measure "Average Interest Rate" to FactLoan table TMDL — DAX: SUM(FactLoan[int_rate]); displayFolder: Core Metrics; formatString: 0.00%
- [ ] T027 [P] [US2] Add measure "Total Installment" to FactLoan table TMDL — DAX: SUM(FactLoan[installment]); displayFolder: Core Metrics; formatString: "₹"#,##0.00
- [ ] T028 [P] [US2] Add measure "Loan Count by Grade" to FactLoan table TMDL — DAX: uses SELECTEDVALUE + CALCULATE pattern; displayFolder: Core Metrics; formatString: #,##0

### Risk Measures (US2)

- [ ] T029 [P] [US2] Add measure "Default Count" to FactLoan table TMDL — DAX: CALCULATE(COUNTROWS(FactLoan), FactLoan[loan_status] = "Charged Off"); displayFolder: Risk Analysis; formatString: #,##0
- [ ] T030 [P] [US2] Add measure "Default Rate" to FactLoan table TMDL — DAX: VAR _total = [Total Loans] VAR _defaults = [Default Count] RETURN DIVIDE(_defaults, _total, 0); displayFolder: Risk Analysis; formatString: 0.0%
- [ ] T031 [US2] Add measure "Default Risk Category" to FactLoan table TMDL — DAX: VAR _rate = [Default Rate] RETURN IF(_rate > 0.20, "High Risk", "Safe"); displayFolder: Risk Analysis; formatString: text

**Checkpoint**: US2 complete — all core and risk measures return valid values.

---

## Phase 5: User Story 3 — Top N Parameter for Dynamic Filtering (Priority: P2)

**Goal**: Create the TopNParameter disconnected table and associated measures enabling dynamic slicer-based filtering.

**Independent Test**: Set Top N slicer to 5, verify that visuals using Top N Filter show exactly 5 items.

- [ ] T032 [P] [US3] Generate TopNParameter table TMDL in Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition/tables/TopNParameter.tmdl — M query: GENERATESERIES(1, 50, 1) with column TopNValue (Int64, isKey); isHidden: false; no relationship (disconnected)
- [ ] T033 [P] [US3] Add measure "Top N Value" to TopNParameter table TMDL — DAX: SELECTEDVALUE(TopNParameter[TopNValue], 1); displayFolder: Ranking; formatString: 0
- [ ] T034 [US3] Add measure "Top N Filter" to FactLoan table TMDL — DAX: VAR _rank = [State Rank] VAR _n = [Top N Value] RETURN IF(_rank <= _n, 1, 0); displayFolder: Ranking; formatString: 0

**Checkpoint**: US3 complete — parameter slicer controls dynamic filtering.

---

## Phase 6: User Story 4 — Year-over-Year Growth and Trends (Priority: P2)

**Goal**: Add time-intelligence measures that replicate Tableau's table calculations for YoY analysis.

**Independent Test**: Table with Year, Total Loans, YoY Growth % — verify growth percentages match manual (current - prior) / prior computation.

- [ ] T035 [P] [US4] Add measure "PY Loans" to FactLoan table TMDL — DAX: CALCULATE([Total Loans], PREVIOUSYEAR(DimDate[Date])); displayFolder: Year-over-Year; formatString: #,##0
- [ ] T036 [P] [US4] Add measure "YoY Growth %" to FactLoan table TMDL — DAX: VAR _current = [Total Loans] VAR _prior = [PY Loans] RETURN DIVIDE(_current - _prior, _prior); displayFolder: Year-over-Year; formatString: 0.0%;-0.0%;0.0%
- [ ] T037 [US4] Add measure "Highlight Peak Year" to FactLoan table TMDL — DAX: VAR _maxLoans = MAXX(ALLSELECTED(DimDate[Year]), [Total Loans]) VAR _currentLoans = [Total Loans] RETURN IF(_currentLoans = _maxLoans, "Peak", BLANK()); displayFolder: Year-over-Year; formatString: text

**Checkpoint**: US4 complete — YoY measures return correct trend values.

---

## Phase 7: User Story 5 — Rank States by Loan Volume (Priority: P3)

**Goal**: Add RANKX-based state ranking measure replicating Tableau's RANK table calculation.

**Independent Test**: Table with state, Total Loans, State Rank — verify state with most loans has rank 1.

- [ ] T038 [US5] Add measure "State Rank" to FactLoan table TMDL — DAX: RANKX(ALLSELECTED(DimStateRegion[state]), [Total Loans],, DESC, Dense); displayFolder: Ranking; formatString: 0

**Checkpoint**: US5 complete — states rank correctly by loan volume.

---

## Phase 8: Validation (Schema & Integrity)

**Purpose**: Run all validation tools to confirm PBIP project opens cleanly in Power BI Desktop.

- [ ] T039 Run TMDL structural validation: `plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe "Output\LoanPortfolioAnalysis\LoanPortfolioAnalysis.SemanticModel\definition"` — fix any syntax/indentation/property-order errors
- [ ] T040 [P] Run JSON parse validation on all .json and .pbir files in Output/LoanPortfolioAnalysis/ — confirm no malformed JSON
- [ ] T041 Run cross-cutting PBIP validation: `python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\LoanPortfolioAnalysis"` — exit code must be 0
- [ ] T042 Verify M query safety: no cross-query references between table expressions, each partition loads independently
- [ ] T043 Verify relationship integrity: no circular dependencies, no bidirectional filtering, TopNParameter has no relationships
- [ ] T044 Verify DAX measure references: all measure-to-measure references resolve (e.g., [Default Rate] uses [Total Loans] and [Default Count] which both exist)
- [ ] T045 Fix any validation errors found in T039–T044 and re-run validators until exit code 0

**Checkpoint**: All validations pass — .pbip ready for Power BI Desktop.

---

## Dependencies

```
Phase 1 (T001–T005) → Phase 2 (T006–T014) → Phase 3 US1 (T015–T020) → Phase 4 US2 (T021–T031)
                                                                        → Phase 5 US3 (T032–T034) [depends on T038 for State Rank ref]
                                                                        → Phase 6 US4 (T035–T037) [depends on T022 Total Loans]
Phase 4 + Phase 5 + Phase 6 → Phase 7 US5 (T038) [Note: T034 Top N Filter references State Rank]
Phase 3–7 ALL complete → Phase 8 Validation (T039–T045)
```

### Parallel Execution Opportunities

| Tasks | Reason |
|-------|--------|
| T002, T003, T004 | Independent file existence checks |
| T007, T008, T009, T010, T013, T014 | Independent project skeleton files |
| T015, T016, T017, T018, T019 | Independent table TMDL files (no cross-references) |
| T022–T028, T029–T030 | Independent measures (different DAX expressions, same file but parallelizable in generation) |
| T032, T033 | TopNParameter table and its measure |
| T035, T036 | PY Loans and YoY Growth (T036 depends on T035 measure existing) |
| T039, T040 | TMDL validate and JSON parse are independent tools |

---

## Implementation Strategy

1. **MVP Scope**: Phases 1–4 (US1 + US2) deliver a fully functional semantic model with data loading and core measures
2. **Incremental Add**: Phases 5–7 add parameter filtering, time intelligence, and ranking
3. **Gate**: Phase 8 validation MUST pass before declaring the migration complete
4. **Constitution Reference**: All naming, DAX patterns, M query patterns, and structural decisions reference `.specify/memory/constitution.md` — never modify it
5. **TMDL Skill**: Read `plugins/pbip/skills/tmdl/SKILL.md` before writing any .tmdl file
6. **PBIR Skill**: Read `plugins/pbip/skills/pbir-format/SKILL.md` before writing definition.pbir

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 45 |
| Phase 1 (Setup) | 5 tasks |
| Phase 2 (Foundational PBIP) | 9 tasks |
| Phase 3 / US1 (Tables + Relationships) | 6 tasks |
| Phase 4 / US2 (Core Measures) | 11 tasks |
| Phase 5 / US3 (Top N Parameter) | 3 tasks |
| Phase 6 / US4 (YoY Growth) | 3 tasks |
| Phase 7 / US5 (State Rank) | 1 task |
| Phase 8 (Validation) | 7 tasks |
| Parallel Opportunities | 6 groups |
| MVP Scope | Phases 1–4 (31 tasks) |
