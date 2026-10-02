"""U126/U166/U173/U174: regenerate the UI glyph set on one 16x16 grid.

Draws at 8x and downsamples so the edges are antialiased, and keeps the existing
file names (the QSS and resource_path() references stay untouched). Glyph
colours match what the current assets already use:

    dark theme  -> light glyph  #c8c8d0
    light theme -> dark glyph   #4b4b56
    check: white on dark/accent, near-black on light

Every glyph is now centred by its own ink bounding box before downsampling, so a
glyph can never end up stuck in a corner (U166: the check was drawn at the
top-left; U174: the fold arrow was too). Fold arrows are double chevrons
(<< / >>) per U174.

Run: python3 tools/gen_icons.py
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

S, SS = 16, 8                      # final size, supersample factor
C = S * SS                         # supersampled canvas edge (128)
MID = C / 2.0                      # centre of the supersampled canvas
DARK_GLYPH = "#c8c8d0"
LIGHT_GLYPH = "#4b4b56"
CHECK_ON_DARK = "#ffffff"
CHECK_ON_LIGHT = "#10202a"
CHECK_ON_ACCENT = "#ffffff"
STROKE = 2 * SS                    # 2 px visual weight at the 16 px grid


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _save(im: Image.Image, name: str) -> None:
    """Centre the drawn ink on the canvas, then downsample to 16x16.

    The glyphs are drawn in supersampled coordinates that are easy to reason
    about, not necessarily centred; centring here means each generator can pick
    its own coordinates without having to keep the canvas centre in mind.
    """
    box = im.getbbox()
    if box:
        glyph = im.crop(box)
        centred = Image.new("RGBA", im.size, (0, 0, 0, 0))
        centred.paste(glyph, ((im.size[0] - glyph.size[0]) // 2,
                              (im.size[1] - glyph.size[1]) // 2))
        im = centred
    im.resize((S, S), Image.LANCZOS).save("assets/%s.png" % name)


def _polyline(d: ImageDraw.ImageDraw, pts: list, colour: str, width: int) -> None:
    """A stroked polyline with round caps/joints (PIL has no round line join)."""
    d.line(pts, fill=colour, width=width, joint="curve")
    for p in pts:
        d.ellipse([p[0] - width // 2, p[1] - width // 2,
                   p[0] + width // 2, p[1] + width // 2], fill=colour)


def chevron(direction: str, colour: str) -> None:
    """U174: a DOUBLE chevron (<< or >>) for the fold controls.

    The two chevrons must not overlap: each is `arm` deep and they are separated
    by `gap`, so the apex spacing has to be arm + gap (an earlier version used a
    spacing smaller than arm, which fused them into one fat blob).
    """
    im, d = _canvas()
    half_h, arm, gap = 34, 26, 9
    spacing = arm + gap
    if direction == "right":
        apexes = (MID + spacing / 2.0, MID - spacing / 2.0)
        parts = [[(ax - arm, MID - half_h), (ax, MID), (ax - arm, MID + half_h)]
                 for ax in apexes]
    else:
        apexes = (MID - spacing / 2.0, MID + spacing / 2.0)
        parts = [[(ax + arm, MID - half_h), (ax, MID), (ax + arm, MID + half_h)]
                 for ax in apexes]
    for pts in parts:
        _polyline(d, pts, colour, STROKE)
    _save(im, "arrow_%s_%s" % (direction, "dark" if colour == DARK_GLYPH else "light"))


def triangle(direction: str, colour: str) -> None:
    """A solid triangle for combo-box / spin-box arrows (single, not a chevron)."""
    im, d = _canvas()
    if direction == "up":
        pts = [(30, 72), (98, 72), (64, 30)]
    else:
        pts = [(30, 56), (98, 56), (64, 98)]
    d.polygon(pts, fill=colour)
    _save(im, "arrow_%s_%s" % (direction, "dark" if colour == DARK_GLYPH else "light"))


def check(name: str, colour: str) -> None:
    im, d = _canvas()
    pts = [(38, 68), (56, 86), (90, 44)]
    _polyline(d, pts, colour, STROKE + SS)
    _save(im, name)


def gear(colour: str, suffix: str) -> None:
    """A classic cog: a round body, 6 trapezoid teeth and a round hub hole.

    U173: the previous polygon radii (0.62 * 15 * SS = 74 px) ran past the 64 px
    half-canvas, so the teeth were clipped and the glyph read as a plain ring.
    """
    mask = Image.new("L", (C, C), 0)
    md = ImageDraw.Draw(mask)
    cx = cy = MID
    r_body, r_root, r_out = 36.0, 28.0, 52.0
    hole = 13.0
    md.ellipse([cx - r_body, cy - r_body, cx + r_body, cy + r_body], fill=255)
    teeth = 6
    step = 2 * math.pi / teeth
    aw_out, aw_in = math.radians(11.0), math.radians(16.0)
    for i in range(teeth):
        a = i * step
        md.polygon([
            (cx + r_root * math.cos(a - aw_in), cy + r_root * math.sin(a - aw_in)),
            (cx + r_out * math.cos(a - aw_out), cy + r_out * math.sin(a - aw_out)),
            (cx + r_out * math.cos(a + aw_out), cy + r_out * math.sin(a + aw_out)),
            (cx + r_root * math.cos(a + aw_in), cy + r_root * math.sin(a + aw_in)),
        ], fill=255)
    md.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=0)
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
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
