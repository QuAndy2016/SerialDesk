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

def test_repeat_toolbar_is_attached_and_guarded(app) -> None:
    """Regression (found in v1.6.0 testing): the repeat row was never attached.

    The row was built and filled in, but `act_col.addLayout(repeat_row)` was lost when
    the action area became a single-line toolbar (v1.5.1), so both controls had no
    parent and were invisible - the feature was gone with no error anywhere.
    """
    from ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    for _ in range(4):
        app.processEvents()
    for widget, name in ((win.repeat_btn, "repeat_btn"), (win.repeat_ms, "repeat_ms"),
                         (win.send_btn, "send_btn"), (win.history_btn, "history_btn"),
                         (win.tx_edit, "tx_edit")):
        assert widget.parentWidget() is not None, "%s has no parent" % name
        assert widget.isVisible(), "%s is not visible" % name
    # with no port open the toggle must refuse to start a loop (U61) and reset itself
    win.repeat_btn.setChecked(True)
    assert not win._repeat_timer.isActive()
    assert not win.repeat_btn.isChecked()


def test_panel_toggle_button_is_never_blank(app, win):
    # U161: the fold button used to render blank until the first manual toggle
    btn = win._panel_btn
    assert not btn.icon().isNull()          # icon present right after build
    win._on_quick_panel_collapsed(True)
    app.processEvents()
    assert not btn.icon().isNull() and not btn.isChecked()
    win._on_quick_panel_collapsed(False)
    app.processEvents()
    assert not btn.icon().isNull() and btn.isChecked()


def test_wrap_toggle_switches_line_wrap(app, win):
    # U162-B1: the soft-wrap switch flips qplaintextedit wrap mode both ways
    from PySide6.QtWidgets import QPlainTextEdit
    win._on_wrap_toggled(True)
    app.processEvents()
    assert win.rx_view.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
    win._on_wrap_toggled(False)
    app.processEvents()
    assert win.rx_view.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap


def test_clean_copy_strips_timestamps_and_markers(app, win):
    # U162-B2: the clean copy drops kind-2 (timestamp/marker) fragments
    from ui.actions_controller import _rx_copy_text
    win.rx_view.clear()
    win._emit_rx_text("[00:00:00.000] ", meta=True)
    win._emit_rx_text("<- ", meta=True)
    win._emit_rx_text("HELLO")
    app.processEvents()
    assert _rx_copy_text(win).strip() == "HELLO"
    assert _rx_copy_text(win, current_line=True).strip() == "HELLO"
    assert "<- " in win.rx_view.toPlainText()   # raw still shows the marker


def test_reset_counters_keeps_display(app, win):
    # U163-N2: zeroing the counters must not clear the pane
    win.rx_view.clear()
    win._emit_rx_text("DATA")
    win.rx_bytes, win.tx_bytes, win._sent_count = 42, 7, 3
    win._reset_counters()
    app.processEvents()
    assert (win.rx_bytes, win.tx_bytes, win._sent_count) == (0, 0, 0)
    assert "DATA" in win.rx_view.toPlainText()


def test_focus_inside_row_selects_it(app, win):
    # U163-I2: a FocusIn landing on a row control selects that row (keyboard reach)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtWidgets import QLineEdit
    panel = win.quick_panel
    panel.clear_selection()
    entry = panel._rows[0]
    field = entry["widget"].findChild(QLineEdit)
    panel.eventFilter(field, QFocusEvent(QEvent.Type.FocusIn))
    app.processEvents()
    assert bool(entry["widget"].property("selected")) is True
    panel.clear_selection()
