#!/usr/bin/env python3
"""Measure how the pixels of the real window divide across the palette (U156 batch 3).

The colour plan claims a 60/30/10 split: mostly base surface, some secondary
surfaces and text, a little accent. A claim like that is only worth something if it
is measured, so this renders the window offscreen (both themes, both languages),
downsamples it and classifies every sampled pixel against the token table.

Usage:  QT_QPA_PLATFORM=offscreen python3 tools/palette_ratio.py [--limit 15]
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage                                  # noqa: E402
from PySide6.QtWidgets import QApplication                        # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.tokens import DARK_TOKENS, LIGHT_TOKENS                   # noqa: E402

#: Which tokens form which slice of the colour budget.
#:
#: The classic 60/30/10 rule comes from web layout, where a page has one dominant
#: neutral. A desktop tool is different: the data panes are large neutral planes, so
#: the honest equivalent is "neutrals dominate, the accent is a signal, not a
#: decoration". These are the measured budgets this project commits to:
#:   planes  >= 85%   (window + data panes + control surfaces)
#:   detail  <= 15%   (lines, borders and text)
#:   accent  <= 5%    (brand/accent colour) and still > 0, so it stays a signal
#:   alert   <= 2%    (error/danger colours)
PLANES = ("bg_base", "surface_1", "surface_input", "surface_soft", "surface_hover",
          "surface_disabled", "surface_pressed", "surface_pressed_alt",
          "scroll_track", "scroll_handle")
DETAIL = ("border_muted", "border_strong", "border_sep", "border_hover",
          "border_hover_rail", "border_secondary", "focus_border",
          "focus_bg", "text_primary", "text_strong", "text_secondary", "text_disabled",
          "chip_text", "selection_text", "selection_bg")
ACCENT = ("accent",)
ALERT = ("invalid", "danger_disabled", "danger_hover", "check_bg", "check_border",
         "check_bg_hover", "check_border_hover", "check_bg_disabled",
         "check_border_disabled", "check_border_off", "check_border_off_disabled",
         "check_fill_hover", "check_fill_disabled")
BUCKETS = {"planes": PLANES, "detail": DETAIL, "accent": ACCENT, "alert": ALERT}

BUDGET = {"planes_min": 85.0, "detail_max": 15.0, "accent_max": 5.0, "alert_max": 2.0}


def hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def bucket_for(token: str) -> str:
    for name, tokens in BUCKETS.items():
        if token in tokens:
            return name
    return "other"


def measure(win, tokens: dict, size=(320, 200)) -> dict:
    image: QImage = win.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    image = image.scaled(*size)
    palette = [(hex_rgb(v), bucket_for(k)) for k, v in tokens.items()]
    counts: dict[str, int] = {}
    total = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixel(x, y)
            r, g, b = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
            best, best_d = None, 1 << 30
            for (tr, tg, tb), bucket in palette:
                d = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2
                if d < best_d:
                    best, best_d = bucket, d
            counts[best] = counts.get(best, 0) + 1
            total += 1
    return {k: 100.0 * v / total for k, v in counts.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=float, default=None, help="fail above this accent share")
    args = ap.parse_args()

    app = QApplication.instance() or QApplication([])
    from app import i18n
    import ui.theme as theme
    from ui.main_window import MainWindow

    failures = []
    for lang in ("zh", "en"):
        for dark in (True, False):
            i18n.set_language(lang)
            theme.set_override(dark)
            win = MainWindow()
            win.resize(1300, 820)
            win.show()
            for _ in range(6):
                app.processEvents()
            theme.set_override(dark)
            theme.apply_theme(app)
            win.retranslate()
            for _ in range(5):
                app.processEvents()
            share = measure(win, DARK_TOKENS if dark else LIGHT_TOKENS)
            label = "%s/%s" % (lang, "dark" if dark else "light")
            print("[%s] " % label + "  ".join(
                "%s=%.1f%%" % (k, share.get(k, 0.0))
                for k in sorted(share, key=lambda k: -share[k])))
            planes = share.get("planes", 0.0)
            detail = share.get("detail", 0.0)
            accent = share.get("accent", 0.0)
            alert = share.get("alert", 0.0)
            if planes < BUDGET["planes_min"]:
                failures.append("%s: planes %.1f%% < %.0f%%" % (label, planes, BUDGET["planes_min"]))
            if detail > BUDGET["detail_max"]:
                failures.append("%s: detail %.1f%% > %.0f%%" % (label, detail, BUDGET["detail_max"]))
            limit = args.limit if args.limit is not None else BUDGET["accent_max"]
            if accent > limit:
                failures.append("%s: accent %.1f%% > %.0f%%" % (label, accent, limit))
            if alert > BUDGET["alert_max"]:
                failures.append("%s: alert %.1f%% > %.0f%%" % (label, alert, BUDGET["alert_max"]))
    theme.set_override(None)
    i18n.set_language("zh")
    if failures:
        print("palette budget FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("palette budget ok (planes >= %.0f%%, detail <= %.0f%%, accent <= %.0f%%)"
          % (BUDGET["planes_min"], BUDGET["detail_max"],
             args.limit if args.limit is not None else BUDGET["accent_max"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
