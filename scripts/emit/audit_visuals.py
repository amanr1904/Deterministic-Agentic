"""audit_visuals.py — Print a summary of all visuals across all report pages.

Usage:
    python audit_visuals.py <output_dir>
    python audit_visuals.py Output/SalesCustomerDashboards
"""
import json, os, sys, argparse

def main():
    parser = argparse.ArgumentParser(description="Audit visuals in a PBIP report.")
    parser.add_argument("output_dir", help="Path to the workbook output folder, e.g. Output/SalesCustomerDashboards")
    args = parser.parse_args()

    output_dir = os.path.normpath(args.output_dir)
    model_name = os.path.basename(output_dir)
    base = os.path.join(output_dir, f"{model_name}.Report", "definition", "pages")

    pages = sorted(
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
    )
    for page in pages:
        print(f"\n=== {page} ===")
        vdir = os.path.join(base, page, "visuals")
        for folder in sorted(os.listdir(vdir)):
            path = os.path.join(vdir, folder, "visual.json")
            with open(path, encoding="utf-8-sig") as fh:
                v = json.load(fh)
            vt = v["visual"]["visualType"]
            pos = v["position"]
            qs = v["visual"].get("query", {}).get("queryState", {})
            bindings = []
            for role, state in qs.items():
                for p in state.get("projections", []):
                    f = p["field"]
                    col_or_meas = f.get("Column") or f.get("Measure") or {}
                    prop = col_or_meas.get("Property", "?")
                    entity = col_or_meas.get("Expression", {}).get("SourceRef", {}).get("Entity", "?")
                    bindings.append(role + ":" + entity + "." + prop)
            title_val = ""
            titles = v["visual"].get("visualContainerObjects", {}).get("title", [])
            if titles:
                title_val = titles[0].get("properties", {}).get("text", {}).get("expr", {}).get("Literal", {}).get("Value", "")
            print("  " + folder + ": " + vt + " | pos=" + str(pos["x"]) + "," + str(pos["y"]) + " " + str(pos["width"]) + "x" + str(pos["height"]) + " | title=" + str(title_val))
            if bindings:
                print("    " + str(bindings))

if __name__ == "__main__":
    main()
