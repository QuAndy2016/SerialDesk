"""U126: regenerate the UI glyph set on one 16x16 grid with a 2px visual stroke.

Draws at 4x and downsamples so the edges are antialiased, and keeps the existing
file names (the QSS and resource_path() references stay untouched). Glyph
colours match what the current assets already use:

    dark theme  -> light glyph  #c8c8d0
    light theme -> dark glyph   #4b4b56
    check: white on dark/accent, near-black on light

Run: python3 tools/gen_icons.py
"""
from __future__ import annotations

from PIL import Image, ImageDraw

S, SS = 16, 8                      # final size, supersample factor
DARK_GLYPH = "#c8c8d0"
LIGHT_GLYPH = "#4b4b56"
CHECK_ON_DARK = "#ffffff"
CHECK_ON_LIGHT = "#10202a"
CHECK_ON_ACCENT = "#ffffff"
STROKE = 2 * SS                    # 2 px visual weight at the 16 px grid


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (S * SS, S * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _save(im: Image.Image, name: str) -> None:
    im.resize((S, S), Image.LANCZOS).save("assets/%s.png" % name)


def chevron(direction: str, colour: str) -> None:
    im, d = _canvas()
    if direction == "right":
        pts = [(20, 14), (38, 32), (20, 50)]
    else:
        pts = [(44, 14), (26, 32), (44, 50)]
    d.line(pts, fill=colour, width=STROKE, joint="curve")
    for p in pts:
        d.ellipse([p[0] - STROKE // 2, p[1] - STROKE // 2,
                   p[0] + STROKE // 2, p[1] + STROKE // 2], fill=colour)
    _save(im, "arrow_%s_%s" % (direction, "dark" if colour == DARK_GLYPH else "light"))


def triangle(direction: str, colour: str) -> None:
    im, d = _canvas()
    if direction == "up":
        pts = [(16, 42), (48, 42), (32, 18)]
    else:
        pts = [(16, 22), (48, 22), (32, 46)]
    d.polygon(pts, fill=colour)
    _save(im, "arrow_%s_%s" % (direction, "dark" if colour == DARK_GLYPH else "light"))


def check(name: str, colour: str) -> None:
    im, d = _canvas()
    pts = [(12, 34), (26, 48), (52, 16)]
    d.line(pts, fill=colour, width=STROKE + SS, joint="curve")
    for p in pts:
        d.ellipse([p[0] - (STROKE + SS) // 2, p[1] - (STROKE + SS) // 2,
                   p[0] + (STROKE + SS) // 2, p[1] + (STROKE + SS) // 2], fill=colour)
    _save(im, name)


def gear(colour: str, suffix: str) -> None:
    """A clean cog drawn on a strict grid: 8 uniform teeth + a centred hub hole."""
    import math
    mask = Image.new("L", (S * SS, S * SS), 0)
    md = ImageDraw.Draw(mask)
    cx = cy = (S * SS) / 2.0
    teeth = 8
    r_out, r_in = 15.0 * SS * 0.62, 13.0 * SS * 0.62
    step = 2 * math.pi / teeth
    half = step * 0.30
    pts = []
    for i in range(teeth):
        a = i * step
        for ang, r in ((a - half * 1.6, r_in), (a - half, r_out),
                       (a + half, r_out), (a + half * 1.6, r_in)):
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    md.polygon(pts, fill=255)
    hole = r_in * 0.42
    md.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=0)
    im = Image.new("RGBA", (S * SS, S * SS), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", im.size, colour), (0, 0), mask)
    _save(im, "gear_%s" % suffix)


def main() -> None:
    for colour in (DARK_GLYPH, LIGHT_GLYPH):
        chevron("left", colour)
        chevron("right", colour)
        triangle("up", colour)
        triangle("down", colour)
    check("check_dark", CHECK_ON_LIGHT)
    check("check_light", CHECK_ON_DARK)
    check("check_accent", CHECK_ON_ACCENT)
    gear(DARK_GLYPH, "dark")
    gear(LIGHT_GLYPH, "light")
    print("icons regenerated on the 16x16 grid")


if __name__ == "__main__":
    main()
