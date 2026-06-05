# Implementation Plan: Q3 Dealer Buying Event Power BI Migration

## Constitution Compliance
- **Single-Table Rule (§0)**: Tableau workbook uses one flat Excel sheet → keep `LaunchData` as a single table; do NOT split into fact/dimensions.
- **Naming (§2)**: Single-source table `LaunchData` (PascalCase descriptive); `DimDate`; parameter tables prefixed `Parameter_`.
- **DAX (§3)**: VAR/RETURN, DIVIDE, SELECTEDVALUE, RANKX, SWITCH(TRUE()).
- **Relationships (§4)**: Single many-to-one from LaunchData[Date] to DimDate[Date], single direction.
- **M Query (§5)**: `Csv.Document` + `QuoteStyle.Csv` + absolute path.
- **report.json (§8)**: minimal schema, no forbidden properties.

## Phase 1: Semantic Model Structure
1. `Q3DealerBuyingEvent.pbip` (root)
2. `Q3DealerBuyingEvent.SemanticModel/` with `.platform`, `definition.pbism`, `diagramLayout.json`
3. `definition/database.tmdl` (compatibilityLevel 1567)
4. `definition/model.tmdl` (culture, PBI_QueryOrder, ref tables)
5. `definition/relationships.tmdl` (1 relationship)

## Phase 2: Table Definitions (TMDL)
1. `LaunchData.tmdl` — 44 columns + 1 calc column (Region (Derived)) + 22 measures + M partition
2. `DimDate.tmdl` — generated calendar 2020-01-01 → 2022-12-31 + Date Hierarchy
3. `Parameter_RowsDisplayed.tmdl` — disconnected DATATABLE-equivalent via List.Numbers
4. `Parameter_RankSortMeasure.tmdl` — disconnected DATATABLE via Table.FromRows

## Phase 3: Report Definition
1. `Q3DealerBuyingEvent.Report/` with `.platform`, `definition.pbir`
2. `definition/report.json` (minimal schema), `version.json`, `pages/pages.json`
3. Five page folders with `page.json` + visuals subfolders:
   - `LaunchReportDashboard`
   - `DeliverySeasonSummary`
   - `DataDetail`
   - `SlideView1`
   - `SlideView2`
4. Each visual = one folder containing `visual.json` with $schema, name, position, visual block, visualContainerObjects (background, border, title).

## Phase 4: Validation
1. `tmdl-validate-windows-x64.exe` on `Q3DealerBuyingEvent.SemanticModel/definition`
2. `python validate_pbip.py` on `Output/Q3DealerBuyingEvent/`
3. JSON parse-check all `.json` and `.pbir` files
4. Fix any reported issues, re-run until clean

## Risks / Mitigations
- **CSV with trailing-space duplicate columns** → drop in M via `Table.RemoveColumns` to avoid duplicate display names.
- **Parameter-driven measures depend on disconnected tables** → ensure slicers are added to all pages so `SELECTEDVALUE` returns the intended value (fallback supplied).
- **RANKX context** → use `ALLSELECTED(LaunchData[Base Part Number])` to respect visual-level filters.
