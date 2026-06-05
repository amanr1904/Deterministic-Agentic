# Implementation Plan: Netflix Workbook Power BI Migration

**Feature Branch**: `006-netflix-pbi`  
**Spec**: [specs/006-netflix-pbi/spec.md](specs/006-netflix-pbi/spec.md)  
**Output**: `Output/NetflixAnalysis/`  
**Status**: Ready for Implementation

---

## Summary

Migrate the "Netfix Workbook" Tableau workbook to a Power BI semantic model (.pbip). Single CSV source (netflix_titles.csv) loaded via M query into a denormalized NetflixTitles table (Single-Table Rule §0), with a generated DimDate for time intelligence. 8 DAX measures across 3 display folders. Output as TMDL-based PBIP project.

---

## Technical Context

| Aspect | Decision |
|--------|----------|
| Format | Power BI PBIP (TMDL semantic model) |
| Data Source | CSV file via `Csv.Document(File.Contents(...))` M query |
| Model Type | Single-table (constitution §0) — no decomposition |
| Storage Mode | Import |
| Key Strategy | Natural keys (Date column on DimDate) — dataset <1M rows |
| DAX Patterns | VAR/RETURN, DIVIDE(), RANKX, COUNTROWS |
| Validation | `tmdl-validate` + `validate_pbip.py` |
| Output Path | `Output/NetflixAnalysis/` |

---

## Constitution Check

| Rule | Status | Evidence |
|------|--------|----------|
| §0 Single-Table Rule | ✅ Pass | Single CSV source → keep NetflixTitles intact, add only DimDate |
| §1 Star Schema | ✅ N/A | Single-table rule applies; no multi-table decomposition |
| §2 Naming Conventions | ✅ Pass | NetflixTitles (PascalCase), DimDate, measures in Title Case |
| §3 DAX Standards | ✅ Pass | VAR/RETURN, DIVIDE(), explicit measures, display folders |
| §4 Relationships | ✅ Pass | Single many-to-one, single direction, no circular deps |
| §5 M Query Rules | ✅ Pass | Independent loads, QuoteStyle.Csv, absolute path, no cross-refs |
| §6 Performance | ✅ Pass | Import mode, natural date key (small dataset ~8800 rows) |
| §7 Parameter Migration | ✅ Pass | Tableau Year param → DimDate slicer (no What-If needed) |
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
        File.Contents("C:\Users\AmanRajMAQSoftware\Downloads\semantic model generation v2\semantic model generation v2\Data\Netflix\netflix_titles.csv"),
        [Delimiter = ",", Columns = 12, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
        {"show_id", Int64.Type},
        {"type", type text},
        {"title", type text},
        {"director", type text},
        {"cast", type text},
        {"country", type text},
        {"date_added", type date},
        {"release_year", Int64.Type},
        {"rating", type text},
        {"duration", type text},
        {"listed_in", type text},
        {"description", type text}
    })
in
    ChangedTypes
```

**Key rules**:
- Each table loads independently (no cross-query references)
- Promote headers immediately
- Apply type transformations after header promotion
- `date_added` parsed as `type date` (Power Query handles "Month Day, Year" format)
- Null/blank values in director, cast, country are acceptable (no error handling needed)

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

**Decision**: Generate DimDate in M query using `List.Dates` to cover the date range of Netflix content additions (2008–2026).

**Pattern**:
```m
let
    StartDate = #date(2008, 1, 1),
    EndDate = #date(2026, 12, 31),
    DateList = List.Dates(StartDate, Duration.TotalDays(EndDate - StartDate) + 1, #duration(1,0,0,0)),
    ToTable = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}, null, ExtraValues.Error),
    ChangedType = Table.TransformColumnTypes(ToTable, {{"Date", type date}}),
    AddYear = Table.AddColumn(ChangedType, "Year", each Date.Year([Date]), Int64.Type),
    AddMonth = Table.AddColumn(AddYear, "Month", each Date.Month([Date]), Int64.Type),
    AddMonthName = Table.AddColumn(AddMonth, "MonthName", each Date.ToText([Date], "MMMM"), type text),
    AddQuarter = Table.AddColumn(AddMonthName, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
    AddDayOfWeek = Table.AddColumn(AddQuarter, "DayOfWeek", each Date.DayOfWeekName([Date]), type text)
in
    AddDayOfWeek
```

**Rationale**: Netflix dataset has date_added values from 2008 through 2021+. Extending to 2026 future-proofs the date table for ongoing use.

---

## Phase 1: Design

### Star Schema Validation (Single-Table Rule)

| Table | Source | Type | Keys | Status |
|-------|--------|------|------|--------|
| NetflixTitles | netflix_titles.csv | Primary (single-table) | show_id (natural identifier, NOT enforced PK) | ✅ |
| DimDate | M-generated | Dimension | Date (PK, isKey=true) | ✅ |

**Single-Table Rule Compliance**: ✅
- Only 1 source CSV → no decomposition
- NetflixTitles retains all 12 columns intact
- Multi-value fields (country, listed_in, cast, director) kept as comma-separated strings
- DimDate is the only added table (for time intelligence only)

### Relationship Integrity

| Relationship | From (Many) | To (One) | Key Type | Direction | Status |
|-------------|-------------|----------|----------|-----------|--------|
| TitlesToDate | NetflixTitles[date_added] | DimDate[Date] | Date | Single | ✅ |

- No circular dependencies (only 1 relationship)
- No bidirectional filtering
- Unmatched rows: titles with null date_added will not link to DimDate (expected behavior)

### DAX Measure Verification

| # | Measure | Table | Folder | Format | Column Refs | Status |
|---|---------|-------|--------|--------|-------------|--------|
| 1 | Total Titles | NetflixTitles | Core Metrics | #,##0 | COUNTROWS(NetflixTitles) | ✅ |
| 2 | Total Movies | NetflixTitles | Core Metrics | #,##0 | NetflixTitles[type] | ✅ |
| 3 | Total TV Shows | NetflixTitles | Core Metrics | #,##0 | NetflixTitles[type] | ✅ |
| 4 | % Movies | NetflixTitles | Core Metrics | 0.0% | [Total Movies], [Total Titles] | ✅ |
| 5 | % TV Shows | NetflixTitles | Core Metrics | 0.0% | [Total TV Shows], [Total Titles] | ✅ |
| 6 | Genre Rank | NetflixTitles | Ranking | #,##0 | NetflixTitles[listed_in], [Total Titles] | ✅ |
| 7 | Is Top 10 Genre | NetflixTitles | Ranking | #,##0 | [Genre Rank] | ✅ |
| 8 | Titles Added This Year | NetflixTitles | Year-over-Year | #,##0 | NetflixTitles[date_added] | ✅ |

**All 8 measures reference valid columns**: `type`, `listed_in`, `date_added` all exist in NetflixTitles. No broken references.

### Calculated Columns

| # | Column Name | Table | Expression | Type | Purpose |
|---|-------------|-------|-----------|------|---------|
| — | (none required) | — | — | — | All Tableau calculated fields handled via DimDate relationship |

### Data Categories

| Column | Table | Category |
|--------|-------|----------|
| country | NetflixTitles | Country |

---

## Phase 2: Implementation Plan

### File Generation Manifest

```
Output/NetflixAnalysis/
├── NetflixAnalysis.pbip
├── NetflixAnalysis.SemanticModel/
│   ├── definition.pbism
│   ├── .platform
│   ├── diagramLayout.json
│   └── definition/
│       ├── database.tmdl
│       ├── model.tmdl
│       ├── relationships.tmdl
│       └── tables/
│           ├── NetflixTitles.tmdl
│           └── DimDate.tmdl
├── NetflixAnalysis.Report/
│   ├── definition.pbir
│   ├── .platform
│   └── definition/
│       └── report.json
```

### Task Sequence

#### Task 1: Create Project Scaffold
- Generate `NetflixAnalysis.pbip` (JSON, byPath reference to SemanticModel)
- Generate `.platform` files for SemanticModel and Report
- Generate `definition.pbism` (version 4.2)
- Generate `definition.pbir` (version 4.0, byPath binding to semantic model)
- Generate `report.json` (minimal PBIR enhanced schema — themeCollection + settings)
- Generate `diagramLayout.json` (empty layout)

#### Task 2: Generate database.tmdl
- compatibilityLevel: 1601
- Model ID annotation (GUID)

#### Task 3: Generate model.tmdl
- `ref table` entries for NetflixTitles and DimDate
- Culture: en-US
- Default Power BI DataSource Version: powerBI_V3
- DimDate marked as date table

#### Task 4: Generate NetflixTitles.tmdl
- M partition: `Csv.Document(File.Contents(...))` for netflix_titles.csv
- 12 source columns with correct dataType:
  - show_id: Int64, summarizeBy: none
  - type: text, summarizeBy: none
  - title: text, summarizeBy: none
  - director: text, summarizeBy: none
  - cast: text, summarizeBy: none
  - country: text, summarizeBy: none, dataCategory: Country
  - date_added: dateTime (date)
  - release_year: Int64, summarizeBy: none
  - rating: text, summarizeBy: none
  - duration: text, summarizeBy: none
  - listed_in: text, summarizeBy: none
  - description: text, summarizeBy: none
- 8 DAX measures organized by display folder:
  - Core Metrics: Total Titles, Total Movies, Total TV Shows, % Movies, % TV Shows
  - Ranking: Genre Rank, Is Top 10 Genre
  - Year-over-Year: Titles Added This Year
- Format strings on all measures

#### Task 5: Generate DimDate.tmdl
- M partition: Date generation via List.Dates (2008-01-01 to 2026-12-31)
- Columns: Date (key, isKey=true), Year, Month, MonthName, Quarter, DayOfWeek
- All columns: summarizeBy: none
- Mark as date table (annotation)

#### Task 6: Generate relationships.tmdl
- 1 relationship: NetflixTitles[date_added] → DimDate[Date]
- Type: manyToOne, singleDirection

#### Task 7: Validate
- Run `tmdl-validate` on `Output/NetflixAnalysis/NetflixAnalysis.SemanticModel/definition`
- Run `validate_pbip.py` on `Output/NetflixAnalysis/`
- Fix any errors before completion

---

## Implementation Notes

1. **File path in M query**: Use absolute path `C:\Users\AmanRajMAQSoftware\Downloads\semantic model generation v2\semantic model generation v2\Data\Netflix\netflix_titles.csv`

2. **DimDate range**: Generate dates from 2008-01-01 to 2026-12-31 (covers all Netflix date_added values plus future buffer). Mark as date table with Date column as the key.

3. **date_added parsing**: The CSV contains dates in "Month Day, Year" format (e.g., "January 1, 2020"). Power Query's `type date` handles this natively. Null/blank values remain as null (no error).

4. **No calculated columns**: All Tableau calculated fields map to DimDate relationship or DAX measures. No calculated columns needed on NetflixTitles.

5. **TMDL indentation**: All files use tabs (one per level). Measure DAX bodies at depth 3 (two extra tabs from the table root).

6. **lineageTag**: Generate unique GUIDs for all objects (tables, columns, measures, relationships).

7. **Multi-value fields**: `country`, `listed_in`, `cast`, `director` remain as comma-separated strings. No bridge table decomposition per constitution §0 single-table override.

8. **Data Category**: Apply `dataCategory: Country` to NetflixTitles[country] for geographic map visual support.

---

## Artifacts Generated

| Artifact | Path | Purpose |
|----------|------|---------|
| Research | (inline above — Phase 0) | M query patterns, TMDL syntax, DimDate generation |
| Data Model | `.specify/memory/star-schema-output.md` | Star schema design (referenced, not regenerated) |
| DAX Measures | `.specify/memory/dax-measures-output.md` | 8 measures with full definitions |
| Contracts | N/A | No external interfaces (PBIP is file-based output) |
| Plan | `specs/006-netflix-pbi/plan.md` | This file |

---

## Success Gate

Implementation is complete when:
1. All 10 files generated in `Output/NetflixAnalysis/`
2. `tmdl-validate` exits with code 0
3. `validate_pbip.py` exits with code 0 or 1 (no code 2 errors)
4. .pbip opens in Power BI Desktop without errors (manual verification)

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
