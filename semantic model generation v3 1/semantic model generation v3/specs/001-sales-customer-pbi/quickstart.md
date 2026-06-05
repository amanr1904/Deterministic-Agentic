# Quickstart: Sales & Customer Dashboards PBIP

## Prerequisites

- Power BI Desktop (June 2024 or later) with PBIP support enabled
- Source CSV files present at `Data/Sales and Customer/` (Orders.csv, Customers.csv, Location.csv, Products.csv)

## Opening the Project

1. Navigate to `Output/SalesCustomerDashboards/`
2. Double-click `SalesCustomerDashboards.pbip`
3. Power BI Desktop opens with the semantic model and report

## Validation Steps

### 1. Verify Data Loading
- Switch to **Model View** — all 6 tables should appear (Orders, Customers, Location, Products, DimDate, Select Year)
- Click each table → Data Preview should show rows with correct types

### 2. Verify Relationships
- In Model View, confirm relationship lines:
  - Customers → Orders (Customer ID)
  - Location → Orders (Postal Code)
  - Products → Orders (Product ID)
  - DimDate → Orders (Order Date) — active
  - DimDate → Orders (Ship Date) — inactive (dashed line, optional)

### 3. Verify Measures
- Switch to **Report View**
- Add a Card visual → drag `CY Sales` → should show a currency value (K-scaled)
- Add the Select Year slicer → select 2023 → CY Sales updates
- Add `% Diff Sales` card → should show a ▲/▼ percentage (positive or negative)

### 4. Verify Navigation
- Sales Dashboard page: click "Customer Dashboard" button → navigates
- Customer Dashboard page: click "Sales Dashboard" button → navigates

## Running Validators (CLI)

```powershell
# TMDL syntax validation
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\SalesCustomerDashboards\SalesCustomerDashboards.SemanticModel\definition"

# Cross-cutting PBIP validation
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\SalesCustomerDashboards"
```

Both should return exit code 0.

## Known Limitations

- Bookmark toggle button requires manual bookmark creation in Power BI Desktop (PBIP cannot define bookmark states)
- File paths in M queries are absolute — update if moving files to different location
- DimDate is a DAX `CALENDAR` table that auto-spans the full calendar years of `Orders[Order Date]` — it adapts automatically as data grows
