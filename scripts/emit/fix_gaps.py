"""fix_gaps.py — Fix all 4 identified gaps vs target screenshots.

Usage:
    python fix_gaps.py <output_dir>
    python fix_gaps.py Output/SalesCustomerDashboards
"""
import json, os, argparse

parser = argparse.ArgumentParser(description="Fix visual gaps in a PBIP report.")
parser.add_argument("output_dir", help="Path to the workbook output folder, e.g. Output/SalesCustomerDashboards")
args = parser.parse_args()

output_dir = os.path.normpath(args.output_dir)
MODEL_NAME = os.path.basename(output_dir)
BASE = os.path.normpath(os.path.join(output_dir, f"{MODEL_NAME}.Report", "definition", "pages"))
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json"

def read(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)

def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)

def literal(val):
    return {"expr": {"Literal": {"Value": val}}}

def color_prop(hex_val):
    return {"solid": {"color": {"expr": {"Literal": {"Value": "'"+hex_val+"'"}}}}}

def measure_proj(entity, prop):
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": entity+"."+prop, "nativeQueryRef": prop, "active": True
    }

def col_proj(entity, prop):
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": entity+"."+prop, "nativeQueryRef": prop, "active": True
    }

def std_vco(title_text):
    return {
        "title": [{"properties": {
            "show": literal("true"),
            "text": literal("'"+title_text+"'"),
            "fontColor": color_prop("#004263"),
            "fontSize": literal("12D"),
            "alignment": literal("'left'"),
            "fontFamily": literal("'Segoe UI Semibold'")
        }}],
        "background": [{"properties": {"show": literal("true"), "color": color_prop("#FFFFFF")}}],
        "border": [{"properties": {"show": literal("true"), "color": color_prop("#E0E0E0"), "radius": literal("5D")}}]
    }

# ─────────────────────────────────────────────────────────────────────────────
# GAP 1: Add card + % diff text above each KPI sparkline
# Tableau layout: [title][big number][▲%][sparkline]
# PBI approach: add a card visual (Total Sales/etc.) + a card for % diff
# above each existing sparkline, shrink sparkline down, add card above it
# ─────────────────────────────────────────────────────────────────────────────
KPI_CONFIGS = [
    # (page, spark_folder, total_measure, pct_measure, card_name_suffix, z_card, z_pct)
    ("SalesDashboard",    "visual_kpisales_101",          "CY Sales",              "% Diff Sales",              "sales",    150, 151),
    ("SalesDashboard",    "visual_kpiprofit_102",         "CY Profit",             "% Diff Profit",             "profit",   152, 153),
    ("SalesDashboard",    "visual_kpiquantity_103",       "CY Quantity",           "% Diff Quantity",           "quantity", 154, 155),
    ("CustomerDashboard", "visual_kpicustomers_101",      "CY Customers",          "% Diff Customers",          "customers",156, 157),
    ("CustomerDashboard", "visual_kpisalespercustomers_102","CY Sales per Customer","% Diff Sales per Customers","salespercust",158,159),
    ("CustomerDashboard", "visual_kpiorders_103",         "CY Orders",             "% Diff Orders",             "orders",   160, 161),
]

def fix_kpi_cards():
    for page, spark_folder, total_m, pct_m, suffix, z_card, z_pct in KPI_CONFIGS:
        spark_path = os.path.normpath(os.path.join(BASE, page, "visuals", spark_folder, "visual.json"))
        v = read(spark_path)
        pos = v["position"]
        x, y, w, h = pos["x"], pos["y"], pos["width"], pos["height"]

        # Layout within the KPI box:
        # - Card (big number):  full width, top 30% of height
        # - % diff card:        full width, next 15%
        # - Sparkline:          full width, bottom 55%
        card_h    = round(h * 0.30)
        pct_h     = round(h * 0.15)
        spark_y   = y + card_h + pct_h
        spark_h   = h - card_h - pct_h

        # 1. Resize sparkline to lower portion
        v["position"]["y"]      = spark_y
        v["position"]["height"] = spark_h
        # Remove title from sparkline (title now on card)
        if "title" in v["visual"].get("visualContainerObjects", {}):
            v["visual"]["visualContainerObjects"]["title"][0]["properties"]["show"] = literal("false")
        write(spark_path, v)

        # 2. Card visual — big CY number
        card_vco = std_vco(suffix.replace("salespercust","Total Sales Per Customer")
                            .replace("sales","Total Sales").replace("profit","Total Profit")
                            .replace("quantity","Total Quantity").replace("customers","Total Customers")
                            .replace("orders","Total Orders"))
        # Override: no border/bg on card, just the number
        card_pos = {"x": x, "y": y, "z": z_card, "height": card_h, "width": w, "tabOrder": z_card}
        card_visual = {
            "$schema": SCHEMA,
            "name": "card_"+suffix+"_"+str(z_card),
            "position": card_pos,
            "visual": {
                "visualType": "card",
                "query": {"queryState": {"Values": {"projections": [measure_proj("Orders", total_m)]}}},
                "objects": {
                    "labels": [{"properties": {
                        "color": color_prop("#111111"),
                        "fontSize": literal("28D"),
                        "fontFamily": literal("'Segoe UI Bold'")
                    }}],
                    "categoryLabels": [{"properties": {"show": literal("false")}}]
                },
                "visualContainerObjects": {
                    "title": [{"properties": {"show": literal("true"),
                                "text": literal("'"+_kpi_title(suffix)+"'"),
                                "fontColor": color_prop("#555555"),
                                "fontSize": literal("10D"),
                                "fontFamily": literal("'Segoe UI'")}}],
                    "background": [{"properties": {"show": literal("true"), "color": color_prop("#FFFFFF")}}],
                    "border": [{"properties": {"show": literal("false")}}]
                }
            }
        }
        card_dir = os.path.normpath(os.path.join(BASE, page, "visuals", "card_"+suffix+"_"+str(z_card)))
        write(os.path.join(card_dir, "visual.json"), card_visual)

        # 3. % diff card — small trend indicator
        pct_pos = {"x": x, "y": y+card_h, "z": z_pct, "height": pct_h, "width": w, "tabOrder": z_pct}
        pct_visual = {
            "$schema": SCHEMA,
            "name": "card_pct_"+suffix+"_"+str(z_pct),
            "position": pct_pos,
            "visual": {
                "visualType": "card",
                "query": {"queryState": {"Values": {"projections": [measure_proj("Orders", pct_m)]}}},
                "objects": {
                    "labels": [{"properties": {
                        "color": color_prop("#4CAF50"),
                        "fontSize": literal("11D"),
                        "fontFamily": literal("'Segoe UI'")
                    }}],
                    "categoryLabels": [{"properties": {"show": literal("false")}}]
                },
                "visualContainerObjects": {
                    "title": [{"properties": {"show": literal("false")}}],
                    "background": [{"properties": {"show": literal("true"), "color": color_prop("#FFFFFF")}}],
                    "border": [{"properties": {"show": literal("false")}}]
                }
            }
        }
        pct_dir = os.path.normpath(os.path.join(BASE, page, "visuals", "card_pct_"+suffix+"_"+str(z_pct)))
        write(os.path.join(pct_dir, "visual.json"), pct_visual)
        print("  Fixed KPI: "+page+"/"+suffix)

def _kpi_title(suffix):
    return {"sales":"Total Sales","profit":"Total Profit","quantity":"Total Quantity",
            "customers":"Total Customers","salespercust":"Total Sales Per Customer",
            "orders":"Total Orders"}.get(suffix, suffix)


# ─────────────────────────────────────────────────────────────────────────────
# GAP 2: Customer Distribution — fix binding
# Should be: Category=Nr of Orders per Customer (measure used as bins),
# but since it's a distribution, use column chart with
# Category=Order ID count bucket → actually best as:
# X=Nr of Orders per Customer, Y=Total Customers (count distinct)
# ─────────────────────────────────────────────────────────────────────────────
def fix_customer_distribution():
    path = os.path.normpath(os.path.join(BASE, "CustomerDashboard", "visuals",
                                          "visual_customerdistribution_105", "visual.json"))
    v = read(path)
    # Correct binding: X axis = Nr of Orders per Customer (measure as category bins),
    # Y axis = Total Customers (count of customers in each bin)
    v["visual"]["query"]["queryState"] = {
        "Category": {"projections": [measure_proj("Orders", "Nr of Orders per Customer")]},
        "Y": {"projections": [measure_proj("Orders", "Total Customers")]}
    }
    v["visual"]["visualType"] = "clusteredColumnChart"
    # Clean axis labels
    v["visual"]["objects"] = {
        "categoryAxis": [{"properties": {
            "show": literal("true"),
            "labelColor": color_prop("#555555"),
            "title": literal("false")
        }}],
        "valueAxis": [{"properties": {
            "show": literal("true"),
            "labelColor": color_prop("#555555"),
            "title": literal("false")
        }}],
        "labels": [{"properties": {"show": literal("true"), "color": color_prop("#333333")}}]
    }
    write(path, v)
    print("  Fixed Customer Distribution binding")


# ─────────────────────────────────────────────────────────────────────────────
# GAP 3: Top Customers table — fix columns
# Target: Rank | Customer Name | Last Order | 2023 Profit | 2023 Sales | Orders
# ─────────────────────────────────────────────────────────────────────────────
def fix_top_customers():
    path = os.path.normpath(os.path.join(BASE, "CustomerDashboard", "visuals",
                                          "visual_topcustomers_113", "visual.json"))
    v = read(path)
    v["visual"]["query"]["queryState"] = {
        "Values": {"projections": [
            col_proj("DimCustomer", "Customer Name"),
            col_proj("Orders", "Order Date"),      # Last Order date
            measure_proj("Orders", "CY Profit"),
            measure_proj("Orders", "CY Sales"),
            measure_proj("Orders", "CY Orders"),
        ]}
    }
    write(path, v)
    print("  Fixed Top Customers table columns")


# ─────────────────────────────────────────────────────────────────────────────
# GAP 4: Subcategory chart — add KPI CY Less PY series (profit bars)
# Target: left bars = CY Sales / PY Sales, right bars = KPI CY Less PY
# PBI approach: add KPI CY Less PY as a third Y series
# ─────────────────────────────────────────────────────────────────────────────
def fix_subcategory():
    path = os.path.normpath(os.path.join(BASE, "SalesDashboard", "visuals",
                                          "visual_subcategorycomparison_106", "visual.json"))
    v = read(path)
    existing = v["visual"]["query"]["queryState"]["Y"]["projections"]
    # Add KPI CY Less PY as third projection if not already there
    already = [p["nativeQueryRef"] for p in existing]
    if "KPI CY Less PY" not in already:
        existing.append(measure_proj("Orders", "KPI CY Less PY"))
    write(path, v)
    print("  Fixed Subcategory chart: added KPI CY Less PY series")


if __name__ == "__main__":
    fix_kpi_cards()
    fix_customer_distribution()
    fix_top_customers()
    fix_subcategory()
    print("Done")
