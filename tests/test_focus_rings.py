"""Every object-named tool button must show a keyboard focus indicator.

2026-10-04 (UI-24): Qt resolves conflicting style properties by selector specificity
(qt-qtbase .../stylesheet-syntax.qdoc:301-308), so ``QToolButton#settingsBtn`` outranks the
generic ``QToolButton:focus`` - the ring never painted for any button whose base rule carries
an object name. Measured before the fix: settings, parameters, More and the quick-send chips
all painted nothing on focus, while a plain combo box did change.

Both themes are checked, and the light theme no longer paints its focus ring with the accent
(that is what the parameter chip's *hover* border uses, so "focused" and "hovered" used to be
the same picture - rule D5).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect        # noqa: E402
from PySide6.QtGui import QImage                # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402

import ui.theme as theme                        # noqa: E402
from ui.tokens import DARK_TOKENS, LIGHT_TOKENS  # noqa: E402

#: window attribute -> the stylesheet selector its base rule uses
CONTROLS = (("_panel_btn", "QToolButton#panelToggle"),
            ("_settings_btn", "QToolButton#settingsBtn"),
            ("params_summary", "QToolButton#paramsBtn"),
            ("more_btn", "QToolButton#moreBtn"))
CHIP_SELECTOR = "QToolButton#qsChip"


@pytest.fixture(scope="module", params=[False, True], ids=["light", "dark"])
def window(request):
    """One window per theme; the previous override is restored on teardown."""
    app = QApplication.instance() or QApplication([])
    before = theme.get_override()
    theme.set_override(request.param)
    theme.apply_theme(app, request.param)

    from ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1280, 800)
    win.show()
    for _ in range(6):
        app.processEvents()
    yield request.param, win, app
    theme.set_override(before)
    theme.apply_theme(app, before)


def _painted(win, widget, pad: int = 3) -> bytes:
    """RGBA bytes of the widget's painted area plus a small ring around it.

    A single border pixel is not a reliable sample - a QSS ``margin`` shifts the painted box
    inside the widget rect (``#settingsBtn`` carries ``margin-left: 8px``) - so compare the
    whole painted region instead: any state change shows up.
    """
    top_left = widget.mapTo(win, QPoint(0, 0))
    rect = QRect(top_left.x() - pad, top_left.y() - pad,
                 widget.width() + 2 * pad, widget.height() + 2 * pad)
    image = win.grab(rect).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    return bytes(image.constBits())


def _rgb(value: str) -> tuple[int, int, int]:
    """Same WCAG maths as tests/test_text_colours.py:16-33."""
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(value: str) -> float:
    def channel(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _assert_ring(window, widget, label: str) -> None:
    _dark, win, app = window
    win.activateWindow()
    widget.clearFocus()
    app.processEvents()
    resting = _painted(win, widget)
    widget.setFocus()
    app.processEvents()
    assert widget.hasFocus(), "%s is not keyboard reachable" % label
    assert _painted(win, widget) != resting, "%s shows no focus indicator" % label
    widget.clearFocus()
    app.processEvents()


@pytest.mark.parametrize("name", [item[0] for item in CONTROLS])
def test_tool_buttons_show_a_focus_ring(window, name) -> None:
    _dark, win, _app = window
    _assert_ring(window, getattr(win, name), name)


def test_quick_send_chip_shows_a_focus_ring(window) -> None:
    _dark, win, _app = window
    _assert_ring(window, win.quick_panel._rows[0].chip, "quick-send chip")


def test_the_focus_ring_is_not_the_accent(window) -> None:
    """D5: focus must be distinguishable from hover - the parameter chip hovers with the
    accent, so the ring is a token of its own in both themes."""
    _dark, _win, _app = window
    dark = theme.resolved_dark()
    tokens = DARK_TOKENS if dark else LIGHT_TOKENS
    sheet = theme.DARK_QSS if dark else theme.LIGHT_QSS
    for _name, selector in CONTROLS + (("chip", CHIP_SELECTOR),):
        assert "%s:focus { border: 1px solid %s; }" % (selector, tokens["focus_ring"]) in sheet
    assert "QToolButton#paramsBtn:focus { border: 1px solid %s; }" % tokens["accent"] not in sheet


def test_the_focus_ring_meets_the_non_text_contrast_floor(window) -> None:
    """WCAG SC 1.4.11 asks for 3:1.

    ``serialdesk_gate/contrast_check.py`` only reads ``border-color:`` declarations, and the
    focus rules use the ``border:`` shorthand - so their colour is measured here instead.
    Known deviation: in the dark theme the ring is 2.68:1 against the *filled* "More" pill
    (the same is true of every filled QPushButton under the dark focus colour chosen on
    2026-10-04); the light theme's ring clears 3:1 on the filled surface as well.
    """
    _dark, _win, _app = window
    dark = theme.resolved_dark()
    tokens = DARK_TOKENS if dark else LIGHT_TOKENS
    assert _contrast(tokens["focus_ring"], tokens["bg_base"]) >= 3.0
    if not dark:
        assert _contrast(tokens["focus_ring"], tokens["border_muted"]) >= 3.0
