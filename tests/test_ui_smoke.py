"""Offscreen UI smoke tests: the window's wiring, not its pixels.

These exist so the regressions we have already paid for cannot come back:
sticky selection, Ctrl+A being stolen from text fields, a folded panel that
still costs width, and an input box stuck at one line.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt   # noqa: E402
from PySide6.QtGui import QKeySequence, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication       # noqa: E402

from app import __version__, shortcuts           # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    return application


@pytest.fixture(scope="module")
def win(app):
    """One window for the whole module: construction is expensive (port scan,
    tooltips, layout passes), and these tests are about wiring, not isolation."""
    from ui.main_window import MainWindow
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    for _ in range(3):
        app.processEvents()
    yield window
    window.close()


def test_window_builds_with_the_version_in_the_title(app, win):
    assert __version__ in win.windowTitle()


def test_status_counter_reads_from_the_stats_object(app, win):
    win._stats.reset()
    win._stats.add_tx(5)
    win._stats.add_rx(5)
    win.update_counts()
    text = win.sent_lbl.text()
    assert "5" in text and "TX" in text and "RX" in text


def test_send_input_is_at_least_three_lines_and_does_not_wrap(app, win):
    from PySide6.QtWidgets import QPlainTextEdit
    line = win.tx_edit.fontMetrics().lineSpacing()
    assert win.tx_edit.height() >= 3 * line
    assert win.tx_edit.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap


def test_actions_sit_below_the_input(app, win):
    group_y = win._tx_group.mapTo(win, win._tx_group.rect().topLeft()).y()
    input_y = win.tx_edit.mapTo(win, win.tx_edit.rect().topLeft()).y()
    send_y = win.send_btn.mapTo(win, win.send_btn.rect().topLeft()).y()
    assert group_y < input_y < send_y


def test_quick_send_rows_are_one_line_and_explain_themselves(app, win):
    row = win.quick_panel._rows[0]
    assert row["widget"].height() < 40
    assert "HEX" in row["chip"].text() and "500" in row["chip"].text()


def test_selection_survives_a_row_click_and_clears_outside(app, win):
    panel = win.quick_panel
    panel._select_row(panel._rows[0], "replace")
    assert panel.selected_entry() is not None
    outside = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                          Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                          Qt.KeyboardModifier.NoModifier)
    panel.eventFilter(win.rx_view, outside)
    assert panel.selected_entry() is None


def test_batch_delete_and_undo_restore_the_rows(app, win):
    panel = win.quick_panel
    before = len(panel._rows)
    panel._select_row(panel._rows[0], "replace")
    panel._select_row(panel._rows[1], "toggle")
    panel.delete_selected()
    assert len(panel._rows) == before - 2
    panel.restore_rows([{"text": "a", "hex": True, "delay": 500, "index": 0},
                        {"text": "b", "hex": True, "delay": 500, "index": 1}])
    assert len(panel._rows) == before


def test_keyboard_scope_leaves_text_fields_alone(app, win):
    panel = win.quick_panel
    win.tx_edit.setFocus()
    app.processEvents()
    assert panel._owns_keyboard() is False       # Ctrl+A/Delete must not be stolen
    panel._rows[0]["widget"].setFocus()
    app.processEvents()
    assert panel._owns_keyboard() is True        # focus inside the panel: ours


def test_folded_panel_costs_no_width_and_returns_on_hover(app, win):
    panel = win.quick_panel
    win._on_quick_panel_collapsed(True)
    app.processEvents()
    assert panel.width() == 0 and not panel._rail.isVisible()
    panel.set_rail_visible(True)
    app.processEvents()
    assert panel._rail.isVisible()
    win._on_quick_panel_collapsed(False)
    app.processEvents()
    assert panel.width() > 0


def test_every_documented_shortcut_is_registered(app, win):
    registered = {s.key().toString(QKeySequence.SequenceFormat.PortableText)
                  for s in win.findChildren(__import__("PySide6.QtGui",
                                                       fromlist=["QShortcut"]).QShortcut)}
    documented = set(shortcuts.keys())
    # Delete is handled by the quick-send panel's own event filter, not a QShortcut
    missing = documented - registered - {"Delete", "Esc", "Ctrl+Return"}
    assert not missing, "documented but not registered: %s" % missing

def test_retranslate_renders_after_every_change(app) -> None:
    """Switching language must not blow up on a widget built by another module.

    This gap let a leftover collapsed call sit in ui/retranslate.py unnoticed: the
    overflow audit creates fresh windows, it never re-translates a live one.
    """
    from app import i18n
    from ui.main_window import MainWindow

    win = MainWindow()
    for lang in ("zh", "en", "zh"):
        i18n.set_language(lang)
        win.retranslate()
    assert win.windowTitle()
