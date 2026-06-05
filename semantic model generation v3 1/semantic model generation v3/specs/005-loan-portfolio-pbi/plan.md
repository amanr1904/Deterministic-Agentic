# Implementation Plan: Loan Portfolio Analysis Migration

**Feature Branch**: `005-loan-portfolio-pbi`  
**Spec**: [specs/005-loan-portfolio-pbi/spec.md](specs/005-loan-portfolio-pbi/spec.md)  
**Output**: `Output/LoanPortfolioAnalysis/`  
**Status**: Ready for Implementation

---

## Technical Context

| Aspect | Decision |
|--------|----------|
| Format | Power BI PBIP (TMDL semantic model) |
| Data Source | CSV files via `Csv.Document(File.Contents(...))` M query |
| Model Type | Star schema (multi-table source from Tableau) |
| Storage Mode | Import |
| Key Strategy | Natural keys (text values) — all tables <1M rows |
| DAX Patterns | VAR/RETURN, DIVIDE(), RANKX, PREVIOUSYEAR, SELECTEDVALUE |
| Validation | `tmdl-validate` + `validate_pbip.py` |
| Output Path | `Output/LoanPortfolioAnalysis/` |

---

## Constitution Check

| Rule | Status | Evidence |
|------|--------|----------|
| §0 Single-Table Rule | ✅ N/A | Multi-table source → star schema decomposition is correct |
| §1 Star Schema | ✅ Pass | FactLoan + 3 dimension tables + DimDate + TopNParameter |
| §2 Naming Conventions | ✅ Pass | FactLoan, DimCustomer, DimPurpose, DimStateRegion, DimDate |
| §3 DAX Standards | ✅ Pass | VAR/RETURN, DIVIDE(), explicit measures, display folders |
| §4 Relationships | ✅ Pass | All many-to-one, single direction, no circular deps |
| §5 M Query Rules | ✅ Pass | Independent loads, QuoteStyle.Csv, no cross-query refs |
| §6 Performance | ✅ Pass | Import mode, natural keys (small dataset) |
| §7 Parameter Migration | ✅ Pass | TopNParameter via GENERATESERIES(1,50,1) disconnected table |
| §8 PBIP Structure | ✅ Pass | Standard folder layout with .pbip, .SemanticModel/, .Report/ |
| §10 Validation | Pending | Run after implementation |

**Gate Evaluation**: ALL PASS — proceed to implementation.

---

## Phase 0: Research

### M Query Patterns for CSV Loading

**Decision**: Use `Csv.Document(File.Contents(absolute_path))` with UTF-8 encoding, comma delimiter, QuoteStyle.Csv.

**Pattern** (per constitution §5):
```m
let
    Source = Csv.Document(
        File.Contents("C:\path\to\file.csv"),
        [Delimiter = ",", Columns = N, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {/* type list */})
in
    ChangedTypes
```

**Key rules**:
- Each table loads independently (no cross-query references)
- Promote headers immediately
- Apply type transformations after header promotion
- Text.Trim on key columns (customer_id, purpose, state) to prevent whitespace mismatches

### TMDL Syntax (from plugins/pbip/skills/tmdl/SKILL.md)

**Decision**: Use tab-based indentation, multi-line DAX with indented block syntax.

**Key rules**:
- `///` (triple-slash) sets Description — must immediately precede declaration
- Indentation is semantic: tabs, one per level
- Only quote names with spaces/special chars/leading digits
- Measures: DAX body indented 2 levels deeper than declaration (depth 3 for table measures)
- `formatString` at depth 2 after DAX body
- `summarizeBy: none` for all key/attribute/non-additive columns
- Boolean flags (`isHidden`, `isKey`) are keywords on their own line

### DimDate Generation via M

**Decision**: Generate DimDate in M query using `List.Dates` to cover the range of loan issue years (2007–2015 based on dataset).

**Pattern**:
```m
let
    StartDate = #date(2007, 1, 1),
    EndDate = #date(2015, 12, 31),
    DateList = List.Dates(StartDate, Duration.TotalDays(EndDate - StartDate) + 1, #duration(1,0,0,0)),
    ToTable = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}, null, ExtraValues.Error),
    ChangedType = Table.TransformColumnTypes(ToTable, {{"Date", type date}}),
    AddYear = Table.AddColumn(ChangedType, "Year", each Date.Year([Date]), Int64.Type),
    AddMonth = Table.AddColumn(AddYear, "Month", each Date.Month([Date]), Int64.Type),
    AddMonthName = Table.AddColumn(AddMonth, "MonthName", each Date.ToText([Date], "MMMM"), type text),
    AddQuarter = Table.AddColumn(AddMonthName, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text)
in
    AddQuarter
```

---

## Phase 1: Design

### Star Schema Validation

| Table | Source | Row Type | Keys | Status |
|-------|--------|----------|------|--------|
| FactLoan | loan.csv | Fact (one row per loan) | loan_id (PK), customer_id (FK), purpose (FK), state (FK) | ✅ |
| DimCustomer | customer.csv | Dimension | customer_id (PK) | ✅ |
| DimPurpose | loan_purposes.csv | Dimension | purpose (PK) | ✅ |
| DimStateRegion | state_region.csv | Dimension | state (PK) | ✅ |
| DimDate | M-generated | Dimension | Date (PK) | ✅ |
| TopNParameter | M-generated | Disconnected | TopNValue | ✅ |

### Relationship Integrity

| Relationship | From (Many) | To (One) | Key | Direction | Status |
|-------------|-------------|----------|-----|-----------|--------|
| LoanToCustomer | FactLoan[customer_id] | DimCustomer[customer_id] | Text | Single | ✅ |
| LoanToPurpose | FactLoan[purpose] | DimPurpose[purpose] | Text | Single | ✅ |
| LoanToStateRegion | FactLoan[state] | DimStateRegion[state] | Text | Single | ✅ |
| LoanToDate | FactLoan[IssueDate] | DimDate[Date] | DateTime | Single | ✅ |

- No circular dependencies
- No bidirectional filtering
- TopNParameter is disconnected (no relationship)

### DAX Measure Verification

| # | Measure | Folder | Format | Pattern | Status |
|---|---------|--------|--------|---------|--------|
| 1 | Total Loans | Core Metrics | #,##0 | COUNTROWS | ✅ |
| 2 | Total Funded Amount | Core Metrics | "₹"#,##0 | SUM | ✅ |
| 3 | Total Loan Amount | Core Metrics | "₹"#,##0 | SUM | ✅ |
| 4 | Average Loan Amount | Core Metrics | "₹"#,##0.00 | AVERAGE | ✅ |
| 5 | Average Interest Rate | Core Metrics | 0.00% | AVERAGE | ✅ |
| 6 | Total Installment | Core Metrics | "₹"#,##0.00 | SUM | ✅ |
| 7 | Loan Count by Grade | Core Metrics | #,##0 | SELECTEDVALUE+CALCULATE | ✅ |
| 8 | Default Count | Risk Analysis | #,##0 | CALCULATE+filter | ✅ |
| 9 | Default Rate | Risk Analysis | 0.0% | VAR/DIVIDE | ✅ |
| 10 | Default Risk Category | Risk Analysis | text | VAR/IF | ✅ |
| 11 | PY Loans | Year-over-Year | #,##0 | PREVIOUSYEAR | ✅ |
| 12 | YoY Growth % | Year-over-Year | 0.0%;-0.0%;0.0% | VAR/DIVIDE | ✅ |
| 13 | Highlight Peak Year | Year-over-Year | text | MAXX+ALLSELECTED | ✅ |
| 14 | State Rank | Ranking | 0 | RANKX+ALLSELECTED | ✅ |
| 15 | Top N Filter | Ranking | 0 | RANKX+SELECTEDVALUE | ✅ |
| 16 | Top N Value | Ranking | 0 | SELECTEDVALUE | ✅ |

### Calculated Columns

| Column | Table | Expression | Type | Reason |
|--------|-------|-----------|------|--------|
| DefaultFlag | FactLoan | `IF(FactLoan[loan_status] = "Charged Off", 1, 0)` | Int64 | Row-level flag for CALCULATE filtering |
| IssueDate | FactLoan | `DATE(FactLoan[issue_year], 1, 1)` | DateTime | Date key for DimDate relationship |

### Data Categories

| Column | Table | Category |
|--------|-------|----------|
| state | DimStateRegion | State or Province |
| zip_code | DimCustomer | Postal Code |
| region | DimStateRegion | Continent |
| subregion | DimStateRegion | Country |

---

## Phase 2: Implementation Plan

### File Generation Manifest

```
Output/LoanPortfolioAnalysis/
├── LoanPortfolioAnalysis.pbip
├── LoanPortfolioAnalysis.SemanticModel/
│   ├── definition.pbism
│   ├── .platform
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl
│       ├── model.tmdl
│       ├── relationships.tmdl
│       └── tables/
│           ├── FactLoan.tmdl
│           ├── DimCustomer.tmdl
│           ├── DimPurpose.tmdl
│           ├── DimStateRegion.tmdl
│           ├── DimDate.tmdl
│           └── TopNParameter.tmdl
├── LoanPortfolioAnalysis.Report/
│   ├── definition.pbir
│   ├── .platform
│   └── definition/
│       └── report.json
```

### Task Sequence

#### Task 1: Create Project Scaffold
- Generate `LoanPortfolioAnalysis.pbip` (JSON, byPath reference)
- Generate `.platform` files for SemanticModel and Report
- Generate `definition.pbism` (v4.2 format)
- Generate `definition.pbir` (byPath binding to semantic model)
- Generate `report.json` (minimal PBIR enhanced schema)
- Generate `diagramLayout.json` (empty layout)

#### Task 2: Generate database.tmdl
- compatibilityLevel: 1601
- Model ID annotation

#### Task 3: Generate model.tmdl
- `ref table` entries for all 6 tables
- Culture: en-US
- Default Power BI DataSource Version: powerBI_V3
- DimDate marked as date table (markAsDateTable annotation)

#### Task 4: Generate FactLoan.tmdl
- M partition: `Csv.Document(File.Contents(...))` for loan.csv
- All source columns with correct dataType and summarizeBy
- Calculated columns: DefaultFlag, IssueDate
- All 16 measures organized by display folder
- Format strings on all measures

#### Task 5: Generate DimCustomer.tmdl
- M partition: `Csv.Document(File.Contents(...))` for customer.csv
- All columns with dataType, summarizeBy: none (dimension)
- Data categories: zip_code → Postal Code

#### Task 6: Generate DimPurpose.tmdl
- M partition: `Csv.Document(File.Contents(...))` for loan_purposes.csv
- Single column: purpose (text, key)

#### Task 7: Generate DimStateRegion.tmdl
- M partition: `Csv.Document(File.Contents(...))` for state_region.csv
- Columns: state, region, subregion
- Data categories: state → State or Province, region → Continent, subregion → Country
- Geography hierarchy: Region → Subregion → State

#### Task 8: Generate DimDate.tmdl
- M partition: Date generation via List.Dates
- Columns: Date (key), Year, Month, MonthName, Quarter
- Mark as date table

#### Task 9: Generate TopNParameter.tmdl
- M partition: `{1..50}` sequence generation
- Single column: TopNValue (Int64)
- No relationships (disconnected)

#### Task 10: Generate relationships.tmdl
- 4 relationships (LoanToCustomer, LoanToPurpose, LoanToStateRegion, LoanToDate)
- All: manyToOne, singleDirection

#### Task 11: Validate
- Run `tmdl-validate` on `Output/LoanPortfolioAnalysis/LoanPortfolioAnalysis.SemanticModel/definition`
- Run `validate_pbip.py` on `Output/LoanPortfolioAnalysis/`
- Fix any errors before completion

---

## Implementation Notes

1. **File paths in M queries**: Use absolute paths to CSV files in `Data/Loan/` folder. The path will be: `C:\Users\AmanRajMAQSoftware\Downloads\semantic model generation v2\semantic model generation v2\Data\Loan\{filename}.csv`

2. **DimDate range**: Generate dates from 2007-01-01 to 2015-12-31 (covers all loan issue years in dataset). Mark as date table with Date column as the key.

3. **TopNParameter**: Implement as M query `{1..50}` pattern (not GENERATESERIES calculated table) — this avoids the calculated table dependency and aligns with M query independence rule.

4. **Calculated columns on FactLoan**: DefaultFlag and IssueDate are calculated columns defined in TMDL with `type: calculated` and DAX expressions.

5. **TMDL indentation**: All files use tabs (one per level). Measure DAX bodies at depth 3 (two extra tabs from the table root).

6. **lineageTag**: Generate unique GUIDs for all objects (tables, columns, measures, relationships).

7. **Currency format**: Use `"₹"#,##0` for monetary values (Indian Rupee locale detected from Tableau workbook).

8. **DimPurpose naming**: The star schema uses "DimPurpose" but the DAX output references "DimLoanPurpose". Standardize to **DimPurpose** (shorter, per §2 naming: `Dim` + singular noun). Update measure references accordingly (no measures directly reference this table).

---

## Artifacts Generated

| Artifact | Path | Purpose |
|----------|------|---------|
| research.md | (inline above) | M query patterns, TMDL syntax, DimDate generation |
| data-model.md | (star schema output) | `.specify/memory/star-schema-output.md` |
| contracts | N/A | No external interfaces (PBIP is file-based output) |
| Plan | `specs/005-loan-portfolio-pbi/plan.md` | This file |

---

## Success Gate

Implementation is complete when:
1. All 13 files generated in `Output/LoanPortfolioAnalysis/`
2. `tmdl-validate` exits with code 0
3. `validate_pbip.py` exits with code 0
4. .pbip opens in Power BI Desktop without errors (manual verification)
