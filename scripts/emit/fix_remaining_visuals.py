"""fix_remaining_visuals.py — Fix subcategory chart, weekly trends, page titles, legends.

Usage:
    python fix_remaining_visuals.py <output_dir>
    python fix_remaining_visuals.py Output/SalesCustomerDashboards
"""
import json, os, re, argparse

parser = argparse.ArgumentParser(description="Fix remaining visuals in a PBIP report.")
parser.add_argument("output_dir", help="Path to the workbook output folder, e.g. Output/SalesCustomerDashboards")
args = parser.parse_args()

output_dir = os.path.normpath(args.output_dir)
MODEL_NAME = os.path.basename(output_dir)
BASE = os.path.normpath(os.path.join(output_dir, f"{MODEL_NAME}.Report", "definition", "pages"))

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json"

def read(path):
    with open(path, encoding="utf-8-sig") as fh:  # strip BOM on read
        return json.load(fh)

def write(path, obj):
    with open(path, "w", encoding="utf-8") as fh:  # write without BOM
        json.dump(obj, fh, indent=2, ensure_ascii=False)

def literal(val):
    return {"expr": {"Literal": {"Value": val}}}

def color_prop(hex_val):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_val}'"}}}}}

def measure_proj(prop, query_ref=None):
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Orders"}}, "Property": prop}},
        "queryRef": query_ref or f"Orders.{prop}",
        "nativeQueryRef": prop,
        "active": True
    }

def col_proj(entity, prop, query_ref=None):
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": query_ref or f"{entity}.{prop}",
        "nativeQueryRef": prop,
        "active": True
    }

def std_container_objects(title_text, bg="#FFFFFF", border="#E0E0E0"):
    return {
        "title": [{"properties": {
            "show": literal("true"),
            "text": literal(f"'{title_text}'"),
            "fontColor": color_prop("#004263"),
            "fontSize": literal("12D"),
            "alignment": literal("'left'"),
            "fontFamily": literal("'Segoe UI Semibold'")
        }}],
        "background": [{"properties": {"show": literal("true"), "color": color_prop(bg)}}],
        "border": [{"properties": {"show": literal("true"), "color": color_prop(border), "radius": literal("5D")}}]
    }

# ── 1. Subcategory comparison chart ──────────────────────────────────────────
def fix_subcategory():
    path = os.path.normpath(os.path.join(BASE, "SalesDashboard", "visuals",
                                          "visual_subcategorycomparison_106", "visual.json"))
    v = read(path)
    v["visual"]["query"]["queryState"] = {
        "Category": {"projections": [col_proj("DimProduct", "Sub-Category")]},
        "Y": {"projections": [
            measure_proj("CY Sales"),
            measure_proj("PY Sales"),
        ]}
    }
    v["visual"]["objects"] = {
        "categoryAxis": [{"properties": {
            "show": literal("true"),
            "labelColor": color_prop("#333333"),
            "titleColor": color_prop("#333333"),
            "fontSize": literal("9D")
        }}],
        "valueAxis": [{"properties": {
            "show": literal("true"),
            "labelColor": color_prop("#555555"),
            "titleColor": color_prop("#555555")
        }}],
        "labels": [{"properties": {"show": literal("false")}}],
        "legend": [{"properties": {"show": literal("true"), "position": literal("'Top'")}}]
    }
    v["visual"]["visualContainerObjects"] = std_container_objects("Sales & Profit By Subcategory")
    write(path, v)
    print("  Fixed subcategory chart")

# ── 2. Weekly trends chart ────────────────────────────────────────────────────
def fix_weeklytrends():
    path = os.path.normpath(os.path.join(BASE, "SalesDashboard", "visuals",
                                          "visual_weeklytrends_109", "visual.json"))
    v = read(path)
    v["visual"]["query"]["queryState"] = {
        "Category": {"projections": [col_proj("Orders", "Order Date")]},
        "Y": {"projections": [
            measure_proj("CY Sales"),
            measure_proj("PY Sales"),
            measure_proj("CY Profit"),
            measure_proj("PY Profit"),
        ]}
    }
    v["visual"]["objects"] = {
        "categoryAxis": [{"properties": {
            "show": literal("true"),
            "labelColor": color_prop("#555555"),
            "titleColor": color_prop("#555555")
        }}],
        "valueAxis": [{"properties": {
            "show": literal("true"),
            "labelColor": color_prop("#555555"),
            "titleColor": color_prop("#555555")
        }}],
        "labels": [{"properties": {"show": literal("false")}}],
        "legend": [{"properties": {"show": literal("true"), "position": literal("'Top'")}}]
    }
    v["visual"]["visualContainerObjects"] = std_container_objects("Sales & Profit Trends over Time")
    write(path, v)
    print("  Fixed weekly trends chart")

# ── 3. Page title textboxes "Sales Dashboard" → "Sales Dashboard | 2023" ──────
def fix_page_title(page, current_title, new_title):
    path = os.path.normpath(os.path.join(BASE, page, "visuals", "text_100", "visual.json"))
    v = read(path)
    paragraphs = v["visual"]["objects"]["general"][0]["properties"]["paragraphs"]
    # Replace the first textRun value
    for para in paragraphs:
        for run in para.get("textRuns", []):
            if current_title in run.get("value", ""):
                run["value"] = current_title
                # Add a second run for "| 2023" in blue
                para["textRuns"] = [
                    {"value": current_title, "textStyle": {"fontSize": "18pt", "fontWeight": "bold", "color": "#333333"}},
                    {"value": " | ", "textStyle": {"fontSize": "18pt", "fontWeight": "bold", "color": "#555555"}},
                    {"value": "2023", "textStyle": {"fontSize": "18pt", "fontWeight": "bold", "color": "#1F77B4"}}
                ]
    write(path, v)
    print(f"  Fixed page title: {page} -> '{new_title}'")

# ── 4. Fix garbled legend characters on Sales Dashboard ──────────────────────
GARBLE_MAP = {
    "text_105": ("Sales & Profit By Subcategory", "SalesDashboard",
                 [{"value": "2023 ", "textStyle": {"fontSize": "10pt", "color": "#555555"}},
                  {"value": "●", "textStyle": {"fontSize": "10pt", "color": "#1F77B4"}},
                  {"value": " Profit   ", "textStyle": {"fontSize": "10pt", "color": "#555555"}},
                  {"value": "●", "textStyle": {"fontSize": "10pt", "color": "#FF7F0E"}},
                  {"value": " Loss", "textStyle": {"fontSize": "10pt", "color": "#555555"}}]),
    "text_108": ("Sales & Profit Trends over Time", "SalesDashboard",
                 [{"value": "2023 ", "textStyle": {"fontSize": "10pt", "color": "#555555"}},
                  {"value": "●", "textStyle": {"fontSize": "10pt", "color": "#1F77B4"}},
                  {"value": " Above   ", "textStyle": {"fontSize": "10pt", "color": "#555555"}},
                  {"value": "●", "textStyle": {"fontSize": "10pt", "color": "#FF7F0E"}},
                  {"value": " Below", "textStyle": {"fontSize": "10pt", "color": "#555555"}}]),
}

def fix_legends():
    for name, (hint, page, runs) in GARBLE_MAP.items():
        path = os.path.normpath(os.path.join(BASE, page, "visuals", name, "visual.json"))
        v = read(path)
        v["visual"]["objects"]["general"][0]["properties"]["paragraphs"] = [
            {"textRuns": runs}
        ]
        write(path, v)
        print(f"  Fixed legend text: {page}/{name}")

# ── 5. Customer Distribution chart title ──────────────────────────────────────
def fix_customer_distribution():
    path = os.path.normpath(os.path.join(BASE, "CustomerDashboard", "visuals",
                                          "visual_customerdistribution_105", "visual.json"))
    v = read(path)
    if "visualContainerObjects" in v["visual"]:
        titles = v["visual"]["visualContainerObjects"].get("title", [])
        for t in titles:
            if "text" in t.get("properties", {}):
                t["properties"]["text"] = literal("'Customer Distribution by Nr. of Orders'")
                t["properties"]["fontColor"] = color_prop("#004263")
    write(path, v)
    print("  Fixed customer distribution chart title")

# ── 6. Top Customers table title ──────────────────────────────────────────────
def fix_top_customers():
    path = os.path.normpath(os.path.join(BASE, "CustomerDashboard", "visuals",
                                          "visual_topcustomers_113", "visual.json"))
    v = read(path)
    if "visualContainerObjects" in v["visual"]:
        titles = v["visual"]["visualContainerObjects"].get("title", [])
        for t in titles:
            if "text" in t.get("properties", {}):
                t["properties"]["text"] = literal("'Top 10 Customers by Profit'")
                t["properties"]["fontColor"] = color_prop("#004263")
    write(path, v)
    print("  Fixed top customers table title")

if __name__ == "__main__":
    fix_subcategory()
    fix_weeklytrends()
    fix_page_title("SalesDashboard", "Sales Dashboard", "Sales Dashboard | 2023")
    fix_page_title("CustomerDashboard", "Customer Dashboard", "Customer Dashboard | 2023")
    fix_legends()
    fix_customer_distribution()
    fix_top_customers()
    print("Done")
