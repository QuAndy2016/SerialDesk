#!/usr/bin/env python3
"""Generate the image icon set from one design grid (U156 batch 3-4).

Before this script the assets were hand-drawn at 12x8, 8x12, 14x14 and 16x16 with
different weights, so the arrows, the tick and the gear never quite matched. Every
icon here is drawn on the same 24-unit grid with the same stroke, supersampled and
downscaled, and coloured from the theme tokens - so "consistent" is reproducible
instead of a promise.

Usage:
    python3 tools/make_icons.py [--out assets] [--preview /var/www/.../icons.png]
"""

from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GRID = 24.0          # design grid, all coordinates below are in grid units
STROKE = 2.4         # one weight for every glyph
SUPER = 8            # supersampling factor before downscaling

#: icon colours per theme (kept next to the glyphs: these are image pixels, not QSS)
ICON_COLOURS = {
    "dark": {"line": "#c8c8d0", "tick": "#e8fbff"},
    "light": {"line": "#4a4a55", "tick": "#ffffff"},
}

#: filename -> (width, height, glyph, theme)  width/height are the QSS display sizes
ICONS = {
    "arrow_down_%s.png": (14, 14, "down"),   # B4: was 10x6 - too small next to a spin box
    "arrow_up_%s.png": (14, 14, "up"),       # B4: was 8x5
    "arrow_left_%s.png": (8, 12, "left"),
    "arrow_right_%s.png": (8, 12, "right"),
    "gear_%s.png": (14, 14, "gear"),
}
CHECKS = {"check_accent.png": "dark", "check_light.png": "light"}


def to_px(points, scale):
    return [(x / GRID * scale, y / GRID * scale) for x, y in points]


def chevron_points(which: str, width: float, height: float):
    """Chevron in *target* pixels: fitting the square grid into a 10x6 box squashed it."""
    if which == "down":
        return [(0.18 * width, 0.30 * height), (0.50 * width, 0.75 * height), (0.82 * width, 0.30 * height)]
    if which == "up":
        return [(0.18 * width, 0.70 * height), (0.50 * width, 0.25 * height), (0.82 * width, 0.70 * height)]
    if which == "left":
        return [(0.62 * width, 0.12 * height), (0.30 * width, 0.50 * height), (0.62 * width, 0.88 * height)]
    return [(0.38 * width, 0.12 * height), (0.70 * width, 0.50 * height), (0.38 * width, 0.88 * height)]


def draw_stroke(draw, points, colour, stroke, ss):
    """One polyline with round caps, drawn in supersampled target space."""
    pts = [(x * ss, y * ss) for x, y in points]
    draw.line(pts, fill=colour, width=max(1, int(round(stroke * ss))), joint="curve")
    radius = stroke * ss / 2.0
    for px, py in (pts[0], pts[-1]):
        draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=colour)


def gear_mask(size: int, supersample: int = SUPER) -> Image.Image:
    """An 8-tooth gear with a round hole, as an alpha mask."""
    side = size * supersample
    mask = Image.new("L", (side, side), 0)
    d = ImageDraw.Draw(mask)
    cx = cy = side / 2
    outer_r, inner_r, hole_r = side * 0.44, side * 0.34, side * 0.15
    teeth = 8
    points = []
    for i in range(teeth * 2):
        angle = (i / (teeth * 2)) * 2 * 3.141592653589793
        radius = outer_r if i % 2 == 0 else inner_r
        points.append((cx + radius * __import__("math").cos(angle),
                       cy + radius * __import__("math").sin(angle)))
    d.polygon(points, fill=255)
    d.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=255)
    d.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r], fill=0)
    return mask


def make_glyph(glyph: str, width: int, height: int, colour: str) -> Image.Image:
    """Render one glyph at the requested display size with smooth edges.

    Every glyph is drawn in target pixels (not scaled from the grid): a 10x6 arrow and
    a 14x14 gear must both look intentional, and scaling a 24-unit grid into 6 px made
    the chevrons into blobs.
    """
    rgb = tuple(int(colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    ss = SUPER
    canvas = Image.new("RGBA", (width * ss, height * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    if glyph == "gear":
        mask = gear_mask(max(width, height))
        canvas.paste(Image.new("RGBA", canvas.size, rgb), (0, 0), mask.resize(canvas.size, Image.LANCZOS))
    elif glyph == "tick":
        draw_stroke(draw, [(0.16 * width, 0.55 * height), (0.40 * width, 0.78 * height),
                           (0.85 * width, 0.25 * height)], rgb, 1.8, ss)
    else:
        draw_stroke(draw, chevron_points(glyph, width, height), rgb, 1.5, ss)
    return canvas.resize((width, height), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets")
    ap.add_argument("--preview", default=None)
    args = ap.parse_args()

    written = []
    for pattern, (w, h, glyph) in ICONS.items():
        for theme in ("dark", "light"):
            name = pattern % theme
            image = make_glyph(glyph, w, h, ICON_COLOURS[theme]["line"])
            path = os.path.join(args.out, name)
            image.save(path)
            written.append((name, image.size))
    for name, theme in CHECKS.items():
        image = make_glyph("tick", 14, 14, ICON_COLOURS[theme]["tick"])
        path = os.path.join(args.out, name)
        image.save(path)
        written.append((name, image.size))

    for name, size in written:
        print("%-26s %dx%d" % (name, size[0], size[1]))

    if args.preview:
        pad, cell = 22, 130
        cols = 4
        rows = (len(written) + cols - 1) // cols
        preview = Image.new("RGB", (cols * (cell + pad) + pad, rows * (cell + pad) + pad), (30, 30, 46))
        draw = ImageDraw.Draw(preview)
        for index, (name, _size) in enumerate(written):
            image = Image.open(os.path.join(args.out, name)).convert("RGBA")
            scale = 8 if max(image.size) <= 16 else max(1, int(cell / max(image.size)))
            image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
            x = pad + (index % cols) * (cell + pad) + (cell - image.width) // 2
            y = pad + (index // cols) * (cell + pad) + (cell - image.height) // 2
            preview.paste(image, (x, y), image)
            draw.text((pad + (index % cols) * (cell + pad), pad + (index // cols) * (cell + pad) - 12),
                      name.replace(".png", ""), fill=(200, 200, 210))
        preview.save(args.preview)
        print("preview:", args.preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
