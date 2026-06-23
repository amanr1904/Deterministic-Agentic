"""One-off: replace stale Excel-schema IR columns with the actual 46-column
cleaned-CSV schema so the deterministic emitter declares columns that match the
physical CSV (csv_partition sets Columns=len(cols), so they MUST match)."""
import json

IR = r"Output/Active2021Q3DealerBuyingEvent/analysis.json"

DATE = {"Date"}
INT = {"Year", "Month", "Order Quantity", "Style Count",
       "Sum of Extra Quantity (Units)", "Sum of Quantity (Units)"}
REAL = {"Cost", "Dnet", "Margin $", "Measure for Rank", "MSRP",
        "Order $ (U.S. Cost)", "Order $ (U.S. Dealer Net)",
        "Order $ (U.S. MSRP)", "Order $ (USD)"}
MEASURE_ROLE = INT | REAL  # numeric -> measure role; Year/Month treated as dims below
DIM_NUMERIC = {"Year", "Month"}

HEADERS = ["Base Part", "Base Part Number", "Base Style", "Base Style Name",
    "Category", "Collection", "Color", "Date", "Delivery Date", "Delivery Month",
    "Delivery Season", "Family", "Garment Type", "Gender", "Gender/Stature/Type",
    "Global", "Item Code", "Macro Area", "Master Style", "Micro Area", "Month",
    "Product Category", "Product Family", "Product Gender", "Product Sub-Family",
    "Region", "Reorder Type", "Sales Area", "Style", "Style Code",
    "Style Description", "Sub-Family", "Year", "Cost", "Dnet", "Margin $",
    "Measure for Rank", "MSRP", "Order $ (U.S. Cost)", "Order $ (U.S. Dealer Net)",
    "Order $ (U.S. MSRP)", "Order $ (USD)", "Order Quantity", "Style Count",
    "Sum of Extra Quantity (Units)", "Sum of Quantity (Units)"]


def dtype(h):
    if h in DATE:
        return "date"
    if h in INT:
        return "integer"
    if h in REAL:
        return "real"
    return "string"


def role(h):
    if h in MEASURE_ROLE and h not in DIM_NUMERIC:
        return "measure"
    return "dimension"


with open(IR, encoding="utf-8") as f:
    ir = json.load(f)

ir["columns"] = [
    {"name": h, "dataType": dtype(h), "role": role(h),
     "datasource": None, "format": None}
    for h in HEADERS
]

with open(IR, "w", encoding="utf-8") as f:
    json.dump(ir, f, indent=2, ensure_ascii=False)

print("IR columns set:", len(ir["columns"]))
