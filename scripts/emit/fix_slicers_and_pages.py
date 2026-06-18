"""fix_slicers_and_pages.py — Fix slicer entity bindings, slicer backgrounds, and page backgrounds.

Usage:
    python fix_slicers_and_pages.py <output_dir>
    python fix_slicers_and_pages.py Output/SalesCustomerDashboards
"""
import json, os, glob, argparse

parser = argparse.ArgumentParser(description="Fix slicer bindings and page backgrounds in a PBIP report.")
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
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)

def literal(val):
    return {"expr": {"Literal": {"Value": val}}}

def color_prop(hex_val):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_val}'"}}}}}

# ── Slicer field → correct entity mapping ──────────────────────────────────
SLICER_ENTITY_MAP = {
    "Category":     "DimProduct",
    "Sub-Category": "DimProduct",
    "Region":       "DimLocation",
    "State":        "DimLocation",
    "City":         "DimLocation",
    "SelectYear":   "SelectYear",   # already correct — keep
}

def fix_slicers():
    count = 0
    for visual_json in glob.glob(os.path.join(BASE, "**", "slicer_*.json"), recursive=False):
        pass  # handled below

    for page in ["SalesDashboard", "CustomerDashboard"]:
        visuals_dir = os.path.normpath(os.path.join(BASE, page, "visuals"))
        for folder in os.listdir(visuals_dir):
            if not folder.startswith("slicer_"):
                continue
            path = os.path.normpath(os.path.join(visuals_dir, folder, "visual.json"))
            v = read(path)
            proj = (v["visual"]["query"]["queryState"]
                     .get("Values", {}).get("projections", []))
            if not proj:
                continue
            field = proj[0]["field"].get("Column", {})
            prop = field.get("Property", "")
            correct_entity = SLICER_ENTITY_MAP.get(prop)
            if not correct_entity:
                continue

            # Fix entity binding
            proj[0]["field"]["Column"]["Expression"]["SourceRef"]["Entity"] = correct_entity
            proj[0]["queryRef"] = f"{correct_entity}.{prop}"

            # Fix slicer background → white
            vco = v["visual"].get("visualContainerObjects", {})
            if "background" in vco:
                for bg in vco["background"]:
                    bg["properties"]["color"] = color_prop("#FFFFFF")

            write(path, v)
            print(f"  Fixed {page}/{folder}: {prop} → {correct_entity}")
            count += 1
    print(f"Fixed {count} slicer(s)")

# ── Page.json background → light ──────────────────────────────────────────
def fix_page_backgrounds():
    for page in ["SalesDashboard", "CustomerDashboard"]:
        path = os.path.normpath(os.path.join(BASE, page, "page.json"))
        p = read(path)
        objs = p.get("objects", {})
        # background → light gray
        for bg in objs.get("background", []):
            bg["properties"]["color"] = color_prop("#F5F5F5")
            # Remove transparency override so PBI Desktop respects our color
            bg["properties"].pop("transparency", None)
        # outspace → slightly lighter gray
        for os_obj in objs.get("outspace", []):
            os_obj["properties"]["color"] = color_prop("#EBEBEB")
            os_obj["properties"].pop("transparency", None)
        write(path, p)
        print(f"  Fixed page background: {page}")

if __name__ == "__main__":
    fix_slicers()
    fix_page_backgrounds()
    print("Done")
