"""apply_light_theme.py — Bulk replace dark theme colors with light theme in all visual.json files."""
import os
import glob

BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "Output",
    "SalesCustomerDashboards", "SalesCustomerDashboards.Report",
    "definition", "pages"
)

REPLACEMENTS = [
    # Step 1: dark visual background → white  (use placeholder to avoid cascade)
    ("'#1E1E2D'", "'__WHITE_BG__'"),
    # Step 2: dark purple border → light gray
    ("'#3D3D5C'", "'#E0E0E0'"),
    # Step 3: light gray axis/label text (dark-bg) → dark gray (light-bg)
    ("'#CCCCCC'", "'#555555'"),
    # Step 4: white title font (dark-bg) → dark charcoal (light-bg)
    # NOTE: must run BEFORE resolving placeholder so we never accidentally
    # darken backgrounds that were just converted to white in step 1.
    ("'#FFFFFF'", "'#222222'"),
    # Step 5: resolve placeholder → actual white background
    ("'__WHITE_BG__'", "'#FFFFFF'"),
]

def main():
    files = glob.glob(os.path.join(BASE, "**", "visual.json"), recursive=True)
    count = 0
    for f in files:
        with open(f, encoding="utf-8-sig") as fh:  # strip BOM on read
            c = fh.read()
        for old, new in REPLACEMENTS:
            c = c.replace(old, new)
        with open(f, "w", encoding="utf-8") as fh:  # write without BOM
            fh.write(c)
        count += 1
    print(f"Updated {count} visual files")

if __name__ == "__main__":
    main()
