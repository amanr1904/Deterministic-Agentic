# Tasks: Q3 Dealer Buying Event Power BI Migration

## Semantic Model
- [x] T1: Create `Q3DealerBuyingEvent.pbip`
- [x] T2: Create `SemanticModel/.platform`
- [x] T3: Create `SemanticModel/definition.pbism`
- [x] T4: Create `SemanticModel/diagramLayout.json`
- [x] T5: Create `definition/database.tmdl`
- [x] T6: Create `definition/model.tmdl`
- [x] T7: Create `definition/relationships.tmdl`
- [x] T8: Create `tables/LaunchData.tmdl` (44 columns + calc col + 22 measures + M)
- [x] T9: Create `tables/DimDate.tmdl` (generated 2020–2022)
- [x] T10: Create `tables/Parameter_RowsDisplayed.tmdl`
- [x] T11: Create `tables/Parameter_RankSortMeasure.tmdl`

## Report
- [x] T12: Create `Report/.platform`
- [x] T13: Create `Report/definition.pbir`
- [x] T14: Create `Report/definition/report.json`
- [x] T15: Create `Report/definition/version.json`
- [x] T16: Create `pages/pages.json` (5 pages)
- [x] T17: Create page `LaunchReportDashboard` (10 visuals)
- [x] T18: Create page `DeliverySeasonSummary` (5 visuals)
- [x] T19: Create page `DataDetail` (4 visuals)
- [x] T20: Create page `SlideView1` (5 visuals)
- [x] T21: Create page `SlideView2` (5 visuals)

## Validation
- [x] T22: Run `tmdl-validate-windows-x64.exe`
- [x] T23: Run `validate_pbip.py`
- [x] T24: JSON parse-check all report files
- [x] T25: Fix any validation errors
