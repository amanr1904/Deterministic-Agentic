# Quickstart: Netflix Workbook Power BI Migration

Build and validate the `NetflixAnalysis` PBIP project from the clarified spec, star schema, and DAX measures.

## Prerequisites

- Source CSV at `Data/Netflix/netflix_titles.csv`.
- Python available on PATH (for `validate_pbip.py`).
- Plugin validators present under `plugins/pbip/`.

## Build Sequence

### 1. Semantic model

Generate, in order, under `Output/NetflixAnalysis/`:

1. Scaffold — `NetflixAnalysis.pbip`, `.platform` (SemanticModel + Report), `definition.pbism`, `definition.pbir` (byPath → semantic model), `diagramLayout.json`.
2. `definition/database.tmdl` — `compatibilityLevel: 1601`.
3. `definition/model.tmdl` — culture `en-US`, `powerBI_V3`, `ref table` for both tables, DimDate `markAsDateTable`.
4. `definition/tables/NetflixTitles.tmdl` — M partition (`Csv.Document`), 12 typed columns, `dataCategory: Country` on `country`, 5 measures.
5. `definition/tables/DimDate.tmdl` — DAX `CALENDAR` calculated table, 7 columns, `MonthName` sort-by `Month`.
6. `definition/relationships.tmdl` — `NetflixTitles[date_added]` → `DimDate[Date]`, manyToOne, single, active.

### 2. Validate model (before building the report)

```powershell
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixAnalysis\NetflixAnalysis.SemanticModel\definition"
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixAnalysis"
```

Fix any TMDL syntax issues and any `validate_pbip.py` exit-code-2 errors before continuing.

### 3. Report pages

Generate `NetflixAnalysis.Report/definition/report.json` (minimal PBIR enhanced schema) plus page/visual containers for the Tableau worksheets/dashboard:

- Country distribution (map — uses `country` Country/Region category)
- Movies vs TV Shows distribution (Movies Count / TV Shows Count)
- Rating distribution
- Top 10 Genre (`listed_in`, Top-N via visual filter in Desktop)
- Total Movies & TV Shows by Years (Titles Added by Year over `DimDate[Year]`)

Each visual: title shown, 1px `#E0E0E0` border, alt text, projections `active: true`, 25px edges / 20px gaps.

### 4. Final validation

```powershell
Get-ChildItem "Output\NetflixAnalysis\NetflixAnalysis.Report" -Recurse -Include "*.json","*.pbir" | ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null } catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixAnalysis\NetflixAnalysis.SemanticModel\definition"
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixAnalysis"
```

## Success Checks

- [ ] `.pbip` opens in Power BI Desktop with no errors/warnings (SC-001)
- [ ] `NetflixTitles` loads all rows; 12 columns with correct types (SC-002, SC-003)
- [ ] `DimDate` populated; date relationship filters correctly (SC-004)
- [ ] All 5 measures respond to date + category filters (SC-005)
- [ ] `tmdl-validate` exits 0 (SC-006)
- [ ] `validate_pbip.py` exits 0/1, no code-2 errors (SC-007)
