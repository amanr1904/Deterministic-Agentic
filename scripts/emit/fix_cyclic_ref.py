"""fix_cyclic_ref.py — Fix cyclic reference caused by DimCustomer.Nr of Orders.

Root cause: CALCULATE(COUNTROWS(Orders)) in a DimCustomer calculated column
creates a processing cycle:
  DimCustomer calc col needs Orders data
  → Orders relationship needs DimCustomer to be set up first
  → deadlock / cyclic reference

Fix: Remove the calculated column from DimCustomer.
     Replace with a standalone CALCULATED TABLE CustomerOrderCounts
     that pre-aggregates (Nr of Orders, Customer Count) without any cycle.

Usage:
    python fix_cyclic_ref.py <output_dir>
    python fix_cyclic_ref.py Output/SalesCustomerDashboards
"""
import json, os, re, argparse

parser = argparse.ArgumentParser(description="Fix cyclic reference in a PBIP semantic model.")
parser.add_argument("output_dir", help="Path to the workbook output folder, e.g. Output/SalesCustomerDashboards")
args = parser.parse_args()

output_dir = os.path.normpath(args.output_dir)
MODEL_NAME = os.path.basename(output_dir)
BASE  = output_dir
SM    = os.path.join(BASE, f"{MODEL_NAME}.SemanticModel", "definition")
PAGES = os.path.join(BASE, f"{MODEL_NAME}.Report", "definition", "pages")

# ── 1. Remove Nr of Orders from DimCustomer.tmdl ─────────────────────────────
DIMCUST = f"{SM}/tables/DimCustomer.tmdl"
content = open(DIMCUST, encoding="utf-8").read()

if "Nr of Orders" in content:
    # Remove the entire calculated column block (tab-indented)
    content = re.sub(
        r"\n\tcolumn 'Nr of Orders'[^\n]*\n(?:\t\t[^\n]*\n)*\n\t\tannotation SummarizationSetBy = Automatic\n",
        "\n",
        content
    )
    # Fallback: line-by-line removal if regex didn't match
    if "Nr of Orders" in content:
        lines = content.splitlines(keepends=True)
        out, skip = [], False
        for line in lines:
            if "column 'Nr of Orders'" in line:
                skip = True
            if skip and "partition DimCustomer" in line:
                skip = False
            if not skip:
                out.append(line)
        content = "".join(out)

    with open(DIMCUST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    print("Removed Nr of Orders from DimCustomer.tmdl")
else:
    print("DimCustomer.tmdl: Nr of Orders not found, skipped")

# ── 2. Create CustomerOrderCounts.tmdl (calculated table, no circular dep) ───
CALC_TABLE_PATH = f"{SM}/tables/CustomerOrderCounts.tmdl"

# DAX: group customers by their order count, then count customers per bucket
# GROUPBY avoids row-context circular issues; it's a pure table expression
TMDL = (
    "table CustomerOrderCounts\n"
    "\tlineageTag: a1000000-0000-4000-9000-a00000000001\n"
    "\n"
    "\tcolumn 'Nr of Orders'\n"
    "\t\tdataType: int64\n"
    "\t\tformatString: 0\n"
    "\t\tlineageTag: a1000000-0000-4000-9000-a00000000002\n"
    "\t\tsummarizeBy: none\n"
    "\t\tsourceColumn: [Nr of Orders]\n"
    "\n"
    "\t\tannotation SummarizationSetBy = Automatic\n"
    "\n"
    "\tcolumn 'Customer Count'\n"
    "\t\tdataType: int64\n"
    "\t\tformatString: #,0\n"
    "\t\tlineageTag: a1000000-0000-4000-9000-a00000000003\n"
    "\t\tsummarizeBy: sum\n"
    "\t\tsourceColumn: [Customer Count]\n"
    "\n"
    "\t\tannotation SummarizationSetBy = Automatic\n"
    "\n"
    "\tpartition CustomerOrderCounts = calculated\n"
    "\t\tmode: import\n"
    "\t\tsource =\n"
    "\t\t\t\tGROUPBY(\n"
    "\t\t\t\t\tADDCOLUMNS(\n"
    "\t\t\t\t\t\tSUMMARIZE(Orders, Orders[Customer ID]),\n"
    '\t\t\t\t\t\t"Nr of Orders", CALCULATE(DISTINCTCOUNT(Orders[Order ID]))\n'
    "\t\t\t\t\t),\n"
    "\t\t\t\t\t[Nr of Orders],\n"
    '\t\t\t\t\t"Customer Count", SUMX(CURRENTGROUP(), 1)\n'
    "\t\t\t\t)\n"
)

with open(CALC_TABLE_PATH, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(TMDL)
print("Created CustomerOrderCounts.tmdl (calculated table)")

# ── 3. Fix Customer Distribution visual binding ───────────────────────────────
dist_path = f"{PAGES}/CustomerDashboard/visuals/visual_customerdistribution_105/visual.json"
v = json.load(open(dist_path, encoding="utf-8-sig"))
v["visual"]["visualType"] = "clusteredColumnChart"
v["visual"]["query"]["queryState"] = {
    "Category": {"projections": [{
        "field": {"Column": {
            "Expression": {"SourceRef": {"Entity": "CustomerOrderCounts"}},
            "Property": "Nr of Orders"
        }},
        "queryRef": "CustomerOrderCounts.Nr of Orders",
        "nativeQueryRef": "Nr of Orders",
        "active": True
    }]},
    "Y": {"projections": [{
        "field": {"Column": {
            "Expression": {"SourceRef": {"Entity": "CustomerOrderCounts"}},
            "Property": "Customer Count"
        }},
        "queryRef": "CustomerOrderCounts.Customer Count",
        "nativeQueryRef": "Customer Count",
        "active": True
    }]}
}
with open(dist_path, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(v, fh, indent=2, ensure_ascii=False)
print("Updated Customer Distribution visual → CustomerOrderCounts table")

# ── 4. Update decisions.json ──────────────────────────────────────────────────
d = json.load(open(f"{BASE}/decisions.json", encoding="utf-8-sig"))

d["calculatedTables"] = [{
    "name": "CustomerOrderCounts",
    "dax": (
        'GROUPBY('
        'ADDCOLUMNS('
        'SUMMARIZE(Orders, Orders[Customer ID]), '
        '"Nr of Orders", CALCULATE(DISTINCTCOUNT(Orders[Order ID]))'
        '), '
        '[Nr of Orders], '
        '"Customer Count", SUMX(CURRENTGROUP(), 1)'
        ')'
    ),
    "columns": [
        {"name": "Nr of Orders",  "dataType": "int64", "formatString": "0",   "summarizeBy": "none"},
        {"name": "Customer Count","dataType": "int64", "formatString": "#,0", "summarizeBy": "sum"},
    ]
}]

for vd in d["visualDecisions"]:
    if vd.get("worksheet") == "Customer Distribution":
        vd["category"]         = "Nr of Orders"
        vd["categoryEntity"]   = "CustomerOrderCounts"
        vd["categoryIsMeasure"] = False
        vd["value"]            = "Customer Count"
        vd["valueEntity"]      = "CustomerOrderCounts"
        vd["valueIsMeasure"]   = False
        vd["visualType"]       = "clusteredColumnChart"

with open(f"{BASE}/decisions.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(d, fh, indent=2, ensure_ascii=False)
print("Updated decisions.json")

print("\nAll cyclic-ref fixes done.")
