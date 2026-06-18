"""fix_kpi_visuals.py — Fix KPI sparkline visuals: add PY line, hide y-axis, fix titles.

Usage:
    python fix_kpi_visuals.py <output_dir>
    python fix_kpi_visuals.py Output/SalesCustomerDashboards
"""
import json, os, argparse

parser = argparse.ArgumentParser(description="Fix KPI sparkline visuals in a PBIP report.")
parser.add_argument("output_dir", help="Path to the workbook output folder, e.g. Output/SalesCustomerDashboards")
args = parser.parse_args()

output_dir = os.path.normpath(args.output_dir)
MODEL_NAME = os.path.basename(output_dir)
BASE = os.path.join(output_dir, f"{MODEL_NAME}.Report", "definition", "pages")

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json"

# (page, name, title, cy_measure, py_measure)
KPI_VISUALS = [
    ("SalesDashboard",    "visual_kpisales_101",          "Total Sales",              "CY Sales",              "PY Sales"),
    ("SalesDashboard",    "visual_kpiprofit_102",         "Total Profit",             "CY Profit",             "PY Profit"),
    ("SalesDashboard",    "visual_kpiquantity_103",       "Total Quantity",           "CY Quantity",           "PY Quantity"),
    ("CustomerDashboard", "visual_kpicustomers_101",      "Total Customers",          "CY Customers",          "PY Customers"),
    ("CustomerDashboard", "visual_kpisalespercustomers_102", "Total Sales Per Customer", "CY Sales per Customer", "PY Sales per Customer"),
    ("CustomerDashboard", "visual_kpiorders_103",         "Total Orders",             "CY Orders",             "PY Orders"),
]

def projection(entity, prop, query_ref, native_ref):
    """Column projection (for X-axis fields like Order Date)."""
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop
            }
        },
        "queryRef": query_ref,
        "nativeQueryRef": native_ref,
        "active": True
    }

def measure_proj(entity, prop, query_ref, native_ref):
    """Measure projection (for Y-axis measures like CY Sales)."""
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop
            }
        },
        "queryRef": query_ref,
        "nativeQueryRef": native_ref,
        "active": True
    }

def color_prop(hex_val):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_val}'"}}}}}

def literal(val):
    return {"expr": {"Literal": {"Value": val}}}

def build_kpi_visual(name, pos, title, cy_measure, py_measure):
    return {
        "$schema": SCHEMA,
        "name": name,
        "position": pos,
        "visual": {
            "visualType": "lineChart",
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [projection("Orders", "Order Date", "Orders.Order Date", "Order Date")]
                    },
                    "Y": {
                        "projections": [
                            measure_proj("Orders", cy_measure, f"Orders.{cy_measure}", cy_measure),
                            measure_proj("Orders", py_measure, f"Orders.{py_measure}", py_measure),
                        ]
                    }
                }
            },
            "objects": {
                "categoryAxis": [{
                    "properties": {
                        "show": literal("true"),
                        "labelColor": color_prop("#555555"),
                        "titleColor": color_prop("#555555"),
                        "fontSize": literal("9D")
                    }
                }],
                "valueAxis": [{
                    "properties": {
                        "show": literal("false")
                    }
                }],
                "labels": [{
                    "properties": {
                        "show": literal("false")
                    }
                }],
                "legend": [{
                    "properties": {
                        "show": literal("false")
                    }
                }]
            },
            "visualContainerObjects": {
                "title": [{
                    "properties": {
                        "show": literal("true"),
                        "text": literal(f"'{title}'"),
                        "fontColor": color_prop("#004263"),
                        "fontSize": literal("12D"),
                        "alignment": literal("'left'"),
                        "fontFamily": literal("'Segoe UI Semibold'")
                    }
                }],
                "background": [{
                    "properties": {
                        "show": literal("true"),
                        "color": color_prop("#FFFFFF")
                    }
                }],
                "border": [{
                    "properties": {
                        "show": literal("true"),
                        "color": color_prop("#E0E0E0"),
                        "radius": literal("5D")
                    }
                }]
            }
        }
    }

def main():
    for page, name, title, cy, py in KPI_VISUALS:
        path = os.path.normpath(os.path.join(BASE, page, "visuals", name, "visual.json"))
        with open(path, encoding="utf-8-sig") as fh:
            existing = json.load(fh)
        pos = existing["position"]
        visual = build_kpi_visual(name, pos, title, cy, py)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(visual, fh, indent=2, ensure_ascii=False)
        print(f"  Fixed {page}/{name} -> '{title}'")
    print("Done")

if __name__ == "__main__":
    main()
