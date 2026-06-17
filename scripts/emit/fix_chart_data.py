"""fix_chart_data.py — Fix line chart granularity + Customer Distribution histogram."""
import json, os, glob

BASE = "Output/SalesCustomerDashboards"
TMDL_ORDERS = f"{BASE}/SalesCustomerDashboards.SemanticModel/definition/tables/Orders.tmdl"
TMDL_DIMCUST = f"{BASE}/SalesCustomerDashboards.SemanticModel/definition/tables/DimCustomer.tmdl"
PAGES = f"{BASE}/SalesCustomerDashboards.Report/definition/pages"

# ── 1. Patch Orders.tmdl ────────────────────────────────────────────────────
content = open(TMDL_ORDERS, encoding="utf-8").read()

# Fix KPI CY Less PY: text flag → numeric difference
content = content.replace(
    "measure 'KPI CY Less PY' = IF([CY Sales] < [PY Sales], \"⬤\", \"\")",
    "measure 'KPI CY Less PY' = [CY Sales] - [PY Sales]"
)

# Add Order Month Num + Order Month Name before existing 'Order Date (Month)'
NEW_MONTH_COLS = (
    "\tcolumn 'Order Month Num' = MONTH('Orders'[Order Date])\n"
    "\t\tdataType: int64\n"
    "\t\tformatString: 0\n"
    "\t\tlineageTag: a1000000-0000-4000-9000-0000000005de\n"
    "\t\tsummarizeBy: none\n"
    "\n"
    "\t\tannotation SummarizationSetBy = Automatic\n"
    "\n"
    "\tcolumn 'Order Month Name' = FORMAT('Orders'[Order Date], \"MMM\")\n"
    "\t\tdataType: string\n"
    "\t\tlineageTag: a1000000-0000-4000-9000-0000000005df\n"
    "\t\tsummarizeBy: none\n"
    "\t\tsortByColumn: 'Order Month Num'\n"
    "\n"
    "\t\tannotation SummarizationSetBy = Automatic\n"
    "\n"
    "\t"
)
ANCHOR = "\tcolumn 'Order Date (Month)'"
if "Order Month Name" not in content:
    content = content.replace(ANCHOR, NEW_MONTH_COLS + "column 'Order Date (Month)'")
    print("Orders.tmdl: added Order Month Num + Order Month Name")
else:
    print("Orders.tmdl: month columns already present")

with open(TMDL_ORDERS, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(content)
print("Orders.tmdl saved")

# ── 2. DimCustomer.tmdl ─────────────────────────────────────────────────────
# NOTE: Do NOT add calculated columns to DimCustomer that reference Orders.
# CALCULATE(COUNTROWS(Orders)) in a DimCustomer column creates a processing cycle:
#   DimCustomer calc col → needs Orders → Orders relationship needs DimCustomer → CYCLE
# The Customer Distribution histogram is handled by CustomerOrderCounts calculated TABLE
# (see fix_cyclic_ref.py and emit_tmdl.py _build_calculated_table_tmdl).
print("DimCustomer.tmdl: no changes (Nr of Orders moved to CustomerOrderCounts calculated table)")

# ── helper ──────────────────────────────────────────────────────────────────
def col_proj(entity, prop):
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": True
    }

def meas_proj(entity, prop):
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop, "active": True
    }

def read_v(path):
    return json.load(open(path, encoding="utf-8-sig"))

def write_v(path, v):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(v, fh, indent=2, ensure_ascii=False)

# ── 3. Fix 6 KPI sparkline visuals: Category → Order Month Name ─────────────
KPI_VISUALS = [
    ("SalesDashboard",    "visual_kpisales_101"),
    ("SalesDashboard",    "visual_kpiprofit_102"),
    ("SalesDashboard",    "visual_kpiquantity_103"),
    ("CustomerDashboard", "visual_kpicustomers_101"),
    ("CustomerDashboard", "visual_kpisalespercustomers_102"),
    ("CustomerDashboard", "visual_kpiorders_103"),
]
for page, folder in KPI_VISUALS:
    path = f"{PAGES}/{page}/visuals/{folder}/visual.json"
    v = read_v(path)
    v["visual"]["query"]["queryState"]["Category"]["projections"] = [col_proj("Orders", "Order Month Name")]
    write_v(path, v)
    print(f"  Fixed KPI sparkline: {page}/{folder}")

# Also fix any spark_visual_kpi* visuals from previous fix session
for path in glob.glob(f"{PAGES}/*/visuals/spark_visual_kpi*/visual.json"):
    v = read_v(path)
    v["visual"]["query"]["queryState"]["Category"]["projections"] = [col_proj("Orders", "Order Month Name")]
    write_v(path, v)
    print(f"  Fixed spark visual: {os.path.basename(os.path.dirname(path))}")

# ── 4. Fix Customer Distribution: CustomerOrderCounts table (no circular ref) ─
dist_path = f"{PAGES}/CustomerDashboard/visuals/visual_customerdistribution_105/visual.json"
v = read_v(dist_path)
v["visual"]["visualType"] = "clusteredColumnChart"
v["visual"]["query"]["queryState"] = {
    "Category": {"projections": [col_proj("CustomerOrderCounts", "Nr of Orders")]},
    "Y":        {"projections": [col_proj("CustomerOrderCounts", "Customer Count")]}
}
write_v(dist_path, v)
print("Fixed Customer Distribution: CustomerOrderCounts.Nr of Orders + Customer Count")

# ── 5. Update decisions.json ─────────────────────────────────────────────────
d = json.load(open(f"{BASE}/decisions.json", encoding="utf-8-sig"))
for vd in d["visualDecisions"]:
    if vd.get("kpiStack"):
        vd["categoryField"] = "Order Month Name"
    if vd.get("worksheet") == "Customer Distribution":
        vd["category"] = "Nr of Orders"
        vd["categoryIsMeasure"] = False
        vd["categoryEntity"] = "DimCustomer"
        vd["value"] = "Total Customers"
        vd["visualType"] = "clusteredColumnChart"
with open(f"{BASE}/decisions.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(d, fh, indent=2, ensure_ascii=False)
print("decisions.json updated")
print("\nAll fixes done.")
