"""Author decisions.json for the Q3 Dealer Buying Event migration.
Single-flat model over the cleaned 46-col CSV + 2 parameter datatables.
visualDecisions are derived from each worksheet name (the breakdown dimension is
encoded in the Tableau worksheet title)."""
import json

OUT = r"Output/Active2021Q3DealerBuyingEvent"
IR = f"{OUT}/analysis.json"
ir = json.load(open(IR, encoding="utf-8"))

FACT = "LaunchData"
BLUE = "#4e79a7"

measures = [
    {"table": FACT, "name": "Total Order $",
     "dax": "SUM('LaunchData'[Order $ (USD)])",
     "formatString": "\\$#,0", "displayFolder": "Orders",
     "description": "Total order value in USD."},
    {"table": FACT, "name": "Total Order Units",
     "dax": "SUM('LaunchData'[Order Quantity])",
     "formatString": "#,0", "displayFolder": "Orders",
     "description": "Total order quantity (units)."},
    {"table": FACT, "name": "Total Units",
     "dax": "SUM('LaunchData'[Sum of Quantity (Units)])",
     "formatString": "#,0", "displayFolder": "Orders",
     "description": "Total quantity of units."},
    {"table": FACT, "name": "Distinct Style Count",
     "dax": "DISTINCTCOUNT('LaunchData'[Master Style])",
     "formatString": "#,0", "displayFolder": "Orders",
     "description": "Distinct count of master styles (Tableau Style Count)."},
    {"table": FACT, "name": "Order $ % of Total",
     "dax": "DIVIDE([Total Order $], CALCULATE([Total Order $], ALLSELECTED('LaunchData')))",
     "formatString": "0.0%", "displayFolder": "Orders",
     "description": "Percent of total order $ (Tableau Order $ (Percent of Total))."},
    {"table": FACT, "name": "Rank Measure",
     "dax": ("VAR sel = SELECTEDVALUE('Rank Sort Measure'[Rank Sort Measure], "
             "\"Order $ (Decending)\")\n"
             "RETURN SWITCH(TRUE(),\n"
             "    sel = \"Order Units (Decending)\" || sel = \"Order Units (Accending)\", "
             "[Total Order Units],\n"
             "    [Total Order $])"),
     "formatString": "#,0", "displayFolder": "Rank",
     "description": "Parameter-driven rank basis (Rank Sort Measure)."},
]

param_tables = [
    {"name": "Rows Displayed", "role": "param", "sourceType": "datatable",
     "datatable": {"columns": [{"name": "Rows Displayed", "type": "INT64",
                                "dataType": "integer"}],
                   "rows": [[5], [10], [20], [50], [10000]]}},
    {"name": "Rank Sort Measure", "role": "param", "sourceType": "datatable",
     "datatable": {"columns": [{"name": "Rank Sort Measure", "type": "STRING",
                                "dataType": "string"}],
                   "rows": [["Order $ (Decending)"], ["Order Units (Decending)"],
                            ["Order $ (Accending)"], ["Order Units (Accending)"]]}},
]

fact_table = {"name": FACT, "role": "fact", "sourceType": "csv",
              "sourceFile": "Q3LaunchData_clean.csv",
              "keyColumns": ["Item Code"], "dedupKey": None}


def decide(name: str):
    n = name.lower().strip()
    val = "Total Order $"
    if "top parts" in n:
        return {"visualType": "tableEx",
                "tableColumns": [
                    {"entity": FACT, "prop": "Base Part", "isMeasure": False},
                    {"entity": FACT, "prop": "Total Order $", "isMeasure": True},
                    {"entity": FACT, "table": FACT, "prop": "Order $ Rank",
                     "isMeasure": True,
                     "rankMeasure": {"by": "Rank Measure", "over": "'LaunchData'",
                                     "overCol": "Base Part"}}],
                "tableTopN": {"count": 10},
                "reason": "Tableau Top Parts ranked table; Top-N by rank measure."}
    if n in ("launch summary", "launch summary (slide)"):
        return {"visualType": "card", "value": val,
                "reason": "Single-value Launch Summary total (Order $)."}
    if "style count" in n:
        return {"visualType": "card", "value": "Distinct Style Count",
                "reason": "Single-value distinct style count."}
    if "sales by date" in n:
        return {"visualType": "areaChart", "category": "Date", "value": val,
                "color": BLUE, "reason": "Order $ trend over Date."}
    if n in ("data", "sheet 48"):
        return {"visualType": "tableEx",
                "reason": "Crosstab detail table."}
    dim = None
    if "macroarea" in n:
        dim = "Region"
    elif "category" in n:
        dim = "Category"
    elif "garment type" in n:
        dim = "Garment Type"
    elif "gender" in n:
        dim = "Gender"
    elif "sub-family" in n or "sub family" in n:
        dim = "Sub-Family"
    elif "family" in n:
        dim = "Family"
    elif "delivery season" in n:
        dim = "Delivery Season"
    elif "color" in n:
        dim = "Color"
    if dim:
        return {"visualType": "clusteredBarChart", "category": dim, "value": val,
                "color": BLUE, "sort": "valueDesc",
                "reason": f"Order $ by {dim} (Tableau bar/text breakdown)."}
    return {"visualType": "card", "value": val,
            "reason": "Fallback single-value summary."}


visual_decisions = []
for w in ir.get("worksheets", []):
    nm = w["name"]
    d = decide(nm)
    d = {"worksheet": nm, **d}
    visual_decisions.append(d)

theme = {
    "pageBackground": "#FFFFFF",
    "outspace": "#F5F5F5",
    "visualBackground": "#FFFFFF",
    "border": "#D4D4D4",
    "titleColor": "#1F1F1F",
    "titleFont": "Segoe UI Semibold",
    "foreground": "#1F1F1F",
    "dataColors": ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2",
                   "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"],
}

decisions = {
    "decisionsVersion": "1.0",
    "modelName": "Active2021Q3DealerBuyingEvent",
    "tableStrategy": "single-flat",
    "suppressTextZones": True,
    "tables": [fact_table] + param_tables,
    "relationships": [],
    "measures": measures,
    "calculatedColumns": [],
    "fieldParameters": [],
    "visualDecisions": visual_decisions,
    "theme": theme,
    "navBar": {"enabled": True, "orientation": "horizontal"},
    "filterPanel": {"enabled": False},
}

with open(f"{OUT}/decisions.json", "w", encoding="utf-8") as f:
    json.dump(decisions, f, indent=2, ensure_ascii=False)
print("decisions.json written:", len(visual_decisions), "visualDecisions,",
      len(measures), "measures,", len([fact_table] + param_tables), "tables")
