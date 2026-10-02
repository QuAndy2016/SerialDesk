#!/usr/bin/env python3
"""UI gate for SerialDesk: run this before every commit that touches the interface.

Three checks, all mechanical - the point is that the design rules cannot be
"remembered", they have to be run:

  1. contrast   - every colour pair in ui/theme.py against WCAG thresholds
                  (known debt lives in tools/contrast_baseline.txt; NEW debt fails)
  2. overflow   - no visible control may stick out of its parent at four window
                  states (CN/EN x minimum/maximised, both divider extremes)
  3. tests      - the unit + smoke suite

Exit code 1 when anything fails, so CI and a pre-commit hook can both use it.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MIN_WINDOW_WIDTH = 1366   # U164: the screen bound we care about (reported, not enforced)
MIN_WIDTH_BASELINE = os.path.join(ROOT, "tools", "minwidth_baseline.txt")
MIN_WIDTH_GROWTH = 1.10   # a row that grows 10% is a regression (the one we fixed was +30%)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


def check_contrast() -> int:
    # the checker is vendored so CI can run it without the agent's skill folder
    script = os.path.join(ROOT, "tools", "contrast_check.py")
    if not os.path.exists(script):
        script = os.path.expanduser("~/.agents/skills/desktop-app-design/scripts/contrast_check.py")
    baseline = os.path.join(ROOT, "tools", "contrast_baseline.txt")
    if not os.path.exists(script):
        print("[contrast] skipped: checker not found")
        return 0
    args = [sys.executable, script, os.path.join(ROOT, "ui", "theme.py"),
            "--tokens", os.path.join(ROOT, "ui", "tokens.py")]
    if os.path.exists(baseline):
        args += ["--allow", baseline]
    proc = run(args)
    print("[contrast]", proc.stdout.strip() or proc.stderr.strip())
    return proc.returncode


def check_overflow() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    from app import i18n
    import ui.theme as theme
    from ui.main_window import MainWindow

    # widgets that are deliberately drawn outside their parent
    allow = {"seqOrd", "qsRail"}
    problems = []
    for lang in ("zh", "en"):
        i18n.set_language(lang)
        for label, width, height in (("minimum", 1070, 600), ("wide", 1920, 1080)):
            for hv in ([200, 500], [500, 200]):
                i18n.set_language(lang)
                win = MainWindow()
                win.resize(width, height)
                win.show()
                for _ in range(4):
                    app.processEvents()
                win._fit_minimum_width()
                win._splitter.setSizes(hv)
                for _ in range(3):
                    app.processEvents()
                for widget in win.findChildren(QWidget):
                    if not widget.isVisible() or widget.parentWidget() is None:
                        continue
                    if widget.objectName() in allow:
                        continue
                    if widget.window() is not win.window():
                        continue        # popups and dialogs have their own geometry
                    parent, rect = widget.parentWidget(), widget.geometry()
                    if (rect.left() < -2 or rect.top() < -2
                            or rect.right() > parent.width() + 2
                            or rect.bottom() > parent.height() + 2):
                        problems.append("%s/%s/%sx%s: %s %r sticks out of %s %s" % (
                            lang, label, width, height, type(widget).__name__,
                            widget.objectName(), type(parent).__name__,
                            (parent.width(), parent.height())))
                win.close()
    if problems:
        print("[overflow] %d violations" % len(problems))
        for line in problems[:12]:
            print("   ", line)
        return 1
    print("[overflow] clean (2 languages x 2 window states x 2 divider positions)")
    return 0


def _read_minwidth_baseline() -> dict:
    """platform -> px from tools/minwidth_baseline.txt (empty when missing)."""
    out = {}
    try:
        with open(MIN_WIDTH_BASELINE, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    key, _, value = line.partition("=")
                    try:
                        out[key.strip()] = int(value.strip())
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def check_min_width() -> int:
    """U164: catch a receive row that grew again - on any platform.

    The overflow check resizes the window to 1070 px and lets _fit_minimum_width()
    raise the floor to whatever the rows need, so a row that is simply too wide
    passes there. This check measures that floor and compares it to the baseline
    recorded for *this* platform: the number itself is font-metric driven (Linux
    1156 px vs a font-less Windows runner at 1731 px), so an absolute limit would
    fail CI for a difference the user never sees.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app import i18n
    from ui.main_window import MainWindow

    measured = []
    for lang in ("zh", "en"):
        i18n.set_language(lang)
        win = MainWindow()
        win.resize(1070, 600)
        win.show()
        for _ in range(4):
            app.processEvents()
        win._fit_minimum_width()
        for _ in range(2):
            app.processEvents()
        measured.append((lang, win.minimumWidth()))
        win.close()

    worst = max(width for _lang, width in measured)
    shown = ", ".join("%s=%d" % pair for pair in measured)
    baseline = _read_minwidth_baseline().get(sys.platform)
    fits = "fits %d" % MIN_WINDOW_WIDTH if worst <= MIN_WINDOW_WIDTH else \
        "wider than %d on this platform's fonts" % MIN_WINDOW_WIDTH
    if baseline is None:
        print("[min-width] %s (%s; no baseline for %s)" % (shown, fits, sys.platform))
        return 0
    if worst > baseline * MIN_WIDTH_GROWTH:
        print("[min-width] regression: %s (baseline %s=%d, limit +%d%%)"
              % (shown, sys.platform, baseline, int((MIN_WIDTH_GROWTH - 1) * 100)))
        return 1
    print("[min-width] ok (%s; baseline %s=%d; %s)" % (shown, sys.platform, baseline, fits))
    return 0


def check_tests() -> int:
    proc = run([sys.executable, "-m", "pytest", "-q"])
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:] or [""]
    print("[tests]", tail[0])
    return proc.returncode


def main() -> int:
    results = {"contrast": check_contrast(), "overflow": check_overflow(),
               "min-width": check_min_width(), "tests": check_tests()}
    bad = [name for name, code in results.items() if code]
    print("\nUI gate:", "FAILED -> " + ", ".join(bad) if bad else "all clear")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
