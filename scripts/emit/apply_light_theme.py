"""apply_twb_theme.py — Extract theme colors from a Tableau workbook and apply them to all visual.json files.

Reads the actual background, text, and accent colors defined in the .twb XML so the
Power BI report matches the original Tableau theme (dark, light, or branded).

Usage:
    python apply_light_theme.py <output_dir> <twb_path>
    python apply_light_theme.py Output/NetfixWorkbook "Data/Netflix/Netfix Workbook.twb"

Falls back to a generic light theme if no TWB path is given.
"""
import os
import glob
import argparse
import xml.etree.ElementTree as ET


# ── Default light-theme fallback (used when no TWB is provided) ─────────────
DEFAULT_BG        = "#FFFFFF"
DEFAULT_TEXT      = "#333333"
DEFAULT_ACCENT    = "#004263"
DEFAULT_BORDER    = "#E0E0E0"
DEFAULT_SUBTLE_BG = "#F5F5F5"


def _luminance(hex_color: str) -> float:
    """Return relative luminance of a hex color (0=black, 1=white)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def extract_twb_theme(twb_path: str) -> dict:
    """Parse the TWB XML and return a dict with bg, text, accent, border, subtle_bg."""
    tree = ET.parse(twb_path)
    root = tree.getroot()

    bg_color     = None
    text_color   = None
    accent_color = None

    for sr in root.iter("style-rule"):
        element = sr.attrib.get("element", "")
        for fmt in sr.iter("format"):
            attr  = fmt.attrib.get("attr", "")
            value = fmt.attrib.get("value", "")
            if not value.startswith("#") or len(value) != 7:
                continue
            if element in ("table", "worksheet") and attr == "background-color" and bg_color is None:
                bg_color = value.upper()
            if element == "worksheet" and attr == "color" and text_color is None:
                text_color = value.upper()
            if element == "mark" and attr == "mark-color" and accent_color is None:
                accent_color = value.upper()

    # Fallback to defaults for any color not found
    bg     = bg_color     or DEFAULT_BG
    text   = text_color   or DEFAULT_TEXT
    accent = accent_color or DEFAULT_ACCENT

    # Derive border + subtle_bg relative to the background
    is_dark = _luminance(bg) < 0.18
    if is_dark:
        border    = _lighten(bg, 0.15)   # slightly lighter than bg
        subtle_bg = _lighten(bg, 0.08)
    else:
        border    = "#E0E0E0"
        subtle_bg = "#F5F5F5"

    return {
        "bg":        bg,
        "text":      text,
        "accent":    accent,
        "border":    border,
        "subtle_bg": subtle_bg,
        "is_dark":   is_dark,
    }


def _lighten(hex_color: str, amount: float) -> str:
    """Mix hex_color toward white (amount=1) or black (amount=-1)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    target = 255 if amount > 0 else 0
    factor = abs(amount)
    r2 = int(r + (target - r) * factor)
    g2 = int(g + (target - g) * factor)
    b2 = int(b + (target - b) * factor)
    return f"#{r2:02X}{g2:02X}{b2:02X}"


def build_replacements(theme: dict) -> list:
    """
    Map the emit_pbir.py default colors → TWB theme colors.
    Uses a placeholder pass to avoid cascading replacements.
    """
    bg     = theme["bg"]
    text   = theme["text"]
    accent = theme["accent"]
    border = theme["border"]
    subtle = theme["subtle_bg"]

    # emit_pbir default palette → TWB theme
    return [
        # Visual / page backgrounds
        (f"'#FFFFFF'",  f"'__THEME_BG__'"),
        (f"'#F5F5F5'",  f"'__THEME_SUBTLE__'"),
        (f"'#EBEBEB'",  f"'__THEME_SUBTLE__'"),
        # Borders
        (f"'#E0E0E0'",  f"'__THEME_BORDER__'"),
        # Title / accent color
        (f"'#004263'",  f"'__THEME_ACCENT__'"),
        (f"'#2C3E50'",  f"'__THEME_ACCENT__'"),
        # Body text
        (f"'#333333'",  f"'__THEME_TEXT__'"),
        # Axis / label text on dark bg
        (f"'#555555'",  f"'__THEME_TEXT__'"),
        # Resolve placeholders
        (f"'__THEME_BG__'",     f"'{bg}'"),
        (f"'__THEME_SUBTLE__'", f"'{subtle}'"),
        (f"'__THEME_BORDER__'", f"'{border}'"),
        (f"'__THEME_ACCENT__'", f"'{accent}'"),
        (f"'__THEME_TEXT__'",   f"'{text}'"),
    ]


def main():
    parser = argparse.ArgumentParser(description="Apply TWB theme colors to all visual.json files in a PBIP report.")
    parser.add_argument("output_dir", help="Path to the workbook output folder, e.g. Output/NetfixWorkbook")
    parser.add_argument("twb_path",   nargs="?", default=None,
                        help="Optional path to the source .twb file to extract theme colors from")
    args = parser.parse_args()

    output_dir = os.path.normpath(args.output_dir)
    model_name = os.path.basename(output_dir)
    BASE = os.path.join(output_dir, f"{model_name}.Report", "definition", "pages")

    if args.twb_path:
        theme = extract_twb_theme(args.twb_path)
        print(f"TWB theme extracted from: {args.twb_path}")
        print(f"  background : {theme['bg']}  ({'dark' if theme['is_dark'] else 'light'})")
        print(f"  text       : {theme['text']}")
        print(f"  accent     : {theme['accent']}")
        print(f"  border     : {theme['border']}")
        print(f"  subtle_bg  : {theme['subtle_bg']}")
    else:
        theme = {
            "bg": DEFAULT_BG, "text": DEFAULT_TEXT, "accent": DEFAULT_ACCENT,
            "border": DEFAULT_BORDER, "subtle_bg": DEFAULT_SUBTLE_BG, "is_dark": False,
        }
        print("No TWB path provided — applying default light theme.")

    replacements = build_replacements(theme)

    files = glob.glob(os.path.join(BASE, "**", "visual.json"), recursive=True)
    count = 0
    for f in files:
        with open(f, encoding="utf-8-sig") as fh:
            c = fh.read()
        for old, new in replacements:
            c = c.replace(old, new)
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(c)
        count += 1
    print(f"Updated {count} visual files.")


if __name__ == "__main__":
    main()

