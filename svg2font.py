#!/usr/bin/env python3

import os
import sys
from tqdm import tqdm
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from svgpathtools import svg2paths


# ----------------------------
# Utils
# ----------------------------

def ask_path(prompt):
    while True:
        p = input(prompt).strip()
        if os.path.exists(p):
            return p
        print("❌ Path does not exist. Try again.")


def collect_fonts(path):
    if os.path.isdir(path):
        fonts = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith((".ttf", ".otf"))
        ]
        if not fonts:
            print("❌ No fonts found in folder.")
            sys.exit(1)
        return fonts
    return [path]


def svg_to_glyph(svg_path, units_per_em):
    paths, _ = svg2paths(svg_path)

    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")

    for p in paths:
        for seg in p:
            for pt in (seg.start, seg.end):
                xmin = min(xmin, pt.real)
                xmax = max(xmax, pt.real)
                ymin = min(ymin, pt.imag)
                ymax = max(ymax, pt.imag)

    width = xmax - xmin
    height = ymax - ymin
    scale = units_per_em / max(width, height)

    pen = TTGlyphPen(None)

    for path in paths:
        first = True

        for seg in path:
            def tx(pt):
                x = (pt.real - xmin) * scale
                y = (pt.imag - ymin) * scale
                return x, units_per_em - y  # flip Y-axis

            if first:
                pen.moveTo(tx(seg.start))
                first = False

            name = seg.__class__.__name__

            if name == "Line":
                pen.lineTo(tx(seg.end))
            elif name == "QuadraticBezier":
                pen.qCurveTo(tx(seg.control), tx(seg.end))
            elif name == "CubicBezier":
                pen.curveTo(
                    tx(seg.control1),
                    tx(seg.control2),
                    tx(seg.end)
                )

        pen.closePath()

    return pen.glyph()


def insert_glyph(font, glyph_name, glyph, replace):
    glyf = font["glyf"]

    if glyph_name in glyf and not replace:
        print(f"⚠️ Glyph {glyph_name} exists — skipped")
        return False

    glyf[glyph_name] = glyph

    advance = font["head"].unitsPerEm
    font["hmtx"][glyph_name] = (advance, 0)

    codepoint = int(glyph_name[3:], 16)
    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[codepoint] = glyph_name

    return True


# ----------------------------
# Main
# ----------------------------

def main():
    print("\n🎨 SVG → Font Glyph Inserter\n")

    font_input = ask_path("📁 Enter font file or folder: ")
    svg_path = ask_path("📄 Enter SVG path: ")

    unicode_hex = input("🔤 Enter Unicode (hex, e.g. E001) [E000]: ").strip().upper()
    if not unicode_hex:
        unicode_hex = "E000"

    if not unicode_hex[0].isalnum():
        print("❌ Invalid Unicode.")
        sys.exit(1)

    glyph_name = f"uni{unicode_hex}"

    replace = (
        input("🔁 Replace if exists? (y/n) [y]: ").strip().lower() or "y"
    ) == "y"

    out_dir = input("💾 Output folder [./out]: ").strip() or "out"
    os.makedirs(out_dir, exist_ok=True)

    fonts = collect_fonts(font_input)

    print("\n⚙️ Processing...\n")

    for font_path in tqdm(fonts, desc="Fonts"):
        font = TTFont(font_path)
        upm = font["head"].unitsPerEm

        glyph = svg_to_glyph(svg_path, upm)
        inserted = insert_glyph(font, glyph_name, glyph, replace)

        if inserted:
            out_path = os.path.join(out_dir, os.path.basename(font_path))
            font.save(out_path)

    print("\n✅ Done!")
    print(f"📦 Output saved in: {out_dir}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Cancelled.")
