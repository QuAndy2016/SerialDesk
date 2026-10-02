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


def test_quick_send_rows_show_name_and_command_lines(app, win):
    # U182: each row is a name line above the command line, plus the property chip
    row = win.quick_panel._rows[0]
    assert row["name"] is not None and row["edit"] is not None
    assert row["name"] is not row["edit"]
    assert "HEX" in row["chip"].text() and "500" in row["chip"].text()
    assert row["widget"].height() < 80        # two lines, not a tall block


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


def test_rx_view_filter_hides_tx_or_rx(app, win):
    # U163b: the RX/TX filter rebuilds the pane from the fragment store
    win.rx_view.clear()
    win._rx_store = []
    win._emit_rx_text("\n")
    win._emit_rx_text("<- ", meta=True)
    win._emit_rx_text("RXLINE")
    win._emit_rx_text("\n", tx=True)
    win._emit_rx_text("-> ", tx=True, meta=True)
    win._emit_rx_text("TXLINE", tx=True)
    win._on_rx_filter_changed(1)          # RX only
    app.processEvents()
    text = win.rx_view.toPlainText()
    assert "RXLINE" in text and "TXLINE" not in text
    assert "<- " in text and "-> " not in text     # U176: no TX marker in RX only
    win._on_rx_filter_changed(2)          # TX only
    app.processEvents()
    text = win.rx_view.toPlainText()
    assert "TXLINE" in text and "RXLINE" not in text
    assert "-> " in text and "<- " not in text     # U177: TX marker (timestamp) visible
    win._on_rx_filter_changed(0)          # back to all
    app.processEvents()
    assert "RXLINE" in win.rx_view.toPlainText() and "TXLINE" in win.rx_view.toPlainText()


def test_find_highlights_and_case_switch(app, win):
    # U181: the highlight box is persistent and the case switch re-runs the search
    win.rx_view.clear()
    win._rx_store = []
    win._emit_rx_text("AT+CGSN=1 at ok")
    win.find_case_check.setChecked(False)
    win.find_edit.setText("AT")
    app.processEvents()
    assert len(win._find_matches) == 2          # case-insensitive: AT and at
    assert win.rx_view.extraSelections()        # matches are highlighted
    win.find_case_check.setChecked(True)
    app.processEvents()
    assert len(win._find_matches) == 1          # only the upper-case AT
    win.find_edit.setText("at")
    app.processEvents()
    assert len(win._find_matches) == 1          # only the lower-case at


def test_sequence_loop_rule():
    # U170: 0 = endless, otherwise stop once the requested rounds are done
    from ui.quick_send_panel import loop_should_continue
    assert loop_should_continue(1, 1) is False
    assert loop_should_continue(1, 2) is True
    assert loop_should_continue(2, 2) is False
    assert loop_should_continue(99, 0) is True


def test_repeat_count_reads_the_spin(app, win):
    # U171: 0 means endless, any other value is the target
    from ui.actions_controller import repeat_count
    win.repeat_times.setValue(0)
    assert repeat_count(win) == 0
    win.repeat_times.setValue(5)
    assert repeat_count(win) == 5


def test_repeat_tick_stops_after_the_count(app, win):
    # U171: each tick sends once and the loop stops itself at the target
    from ui.actions_controller import on_repeat_tick
    sent = []
    win.on_send = lambda: sent.append(1)
    win.repeat_times.setValue(3)
    win._repeat_count = 0
    for _ in range(3):
        on_repeat_tick(win)
    assert len(sent) == 3
    assert not win._repeat_timer.isActive()


def test_column_hex_rows_and_offset():
    # U163c: pure hexdump formatter - 16 bytes per row, running offset
    from app.display import column_hex
    text, off = column_hex(bytes(range(20)), 0)
    lines = text.split("\n")
    assert len(lines) == 2
    assert lines[0].startswith("00000000  ") and lines[0].endswith("|")
    assert lines[1].startswith("00000010  ")
    assert off == 20


def test_column_hex_mode_renders_rows(app, win):
    # U163c: the HEX cols mode renders hexdump rows into the pane
    win.rx_view.clear()
    win._rx_store = []
    win._col_off = 0
    win.rx_fmt_combo.setCurrentIndex(3)          # HEX cols
    win._append_rx_group(win._format_rx(b"ABCD"), 0.0, True)
    app.processEvents()
    text = win.rx_view.toPlainText()
    assert "00000000" in text and "41 42 43 44" in text and "|ABCD|" in text
    win.rx_fmt_combo.setCurrentIndex(1)          # restore HEX default


def test_byte_split_modes_cut_frames_in_the_receive_path(app, win):
    """B3: fixed / delimited / length-prefixed modes route bytes into real frames."""
    from ui import regions

    win.on_clear()
    win.rx_fmt_combo.setCurrentIndex(1)      # HEX, so the assertions are literal

    win.split_combo.setCurrentIndex(regions.SPLIT_FIXED)
    assert win.split_slot.isVisible() and win.split_slot.currentIndex() == 3
    win.split_size_spin.setValue(4)
    win.on_received(0.0, b"AAAA")
    win.on_received(0.0, b"BB")              # half a frame: held back
    win.on_received(0.0, b"BB")
    text = win.rx_view.toPlainText()
    assert "41 41 41 41" in text and "42 42 42 42" in text

    win.on_clear()
    win.split_combo.setCurrentIndex(regions.SPLIT_DELIMITED)
    assert win.split_slot.currentIndex() == 4
    win.split_start_edit.setText("AA")
    win.split_end_edit.setText("55")
    win.on_received(0.0, b"\xaa\x01\x55")
    assert "AA 01 55" in win.rx_view.toPlainText()

    win.on_clear()
    win.split_combo.setCurrentIndex(regions.SPLIT_TLV)
    assert win.split_slot.currentIndex() == 5
    win.split_prefix_spin.setValue(1)
    win.on_received(0.0, b"\x02AB")          # prefix stripped from the shown frame
    assert "41 42" in win.rx_view.toPlainText()

    win.split_combo.setCurrentIndex(regions.SPLIT_AUTO)
    win.on_clear()


def test_long_receive_line_shows_a_hover_tooltip(app, win):
    """U129-A4: a long line can be read in full from a tooltip, text untouched."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QHelpEvent

    win.on_clear()
    win.rx_fmt_combo.setCurrentIndex(0)      # ASCII
    win.ts_check.setChecked(False)
    win.split_combo.setCurrentIndex(1)       # auto (timer path is not used here)
    win._append_rx_group(win._format_rx(b"A" * 400), 0.0, True)

    viewport = win.rx_view.viewport()
    event = QHelpEvent(QEvent.Type.ToolTip, viewport.rect().center(),
                       QPoint(50, 50))
    assert win.eventFilter(viewport, event) is True

    win.on_clear()
    win._append_rx_group(win._format_rx(b"short"), 0.0, True)
    assert win.eventFilter(viewport, QHelpEvent(
        QEvent.Type.ToolTip, viewport.rect().center(), QPoint(50, 50))) is False
    win.on_clear()


def test_quick_send_seeds_examples_on_first_run(app, tmp_path, monkeypatch):
    """U128: a fresh install opens with three real commands, not ten blank rows."""
    from ui import quick_send_panel as qsp

    monkeypatch.setattr(qsp, "CONFIG_PATH", str(tmp_path / "config.json"))
    panel = qsp.QuickSendPanel()
    texts = [e["edit"].text() for e in panel._rows]
    assert texts[:3] == ["AT", "AT+VERSION?", "01 03 00 00 00 02"]
    assert texts[3:] == [""] * (len(texts) - 3)
    assert len(panel._rows) == qsp.DEFAULT_ROWS
    assert panel._rows[0]["edit"].toolTip()          # the seeded rows say why
    panel.deleteLater()


def test_more_menu_holds_the_low_frequency_switches(app, win):
    """U164/U179: only pause/wrap/save-as live in the More menu; auto-scroll is back
    in the row because it is high frequency."""
    assert win.more_btn.menu() is win.more_menu
    for widget in (win.pause_check, win.wrap_check, win.save_log_as_btn):
        assert not widget.isVisible()
    assert win.act_pause.isCheckable() and win.act_wrap.isCheckable()
    assert win.act_pause.isChecked() == win.pause_check.isChecked()
    row = win.ts_check.parentWidget()
    assert row.isAncestorOf(win.autoscroll_check)
    assert win.act_wrap.isChecked() == win.wrap_check.isChecked()
    assert win.act_save_as.text()          # the "Save as" action is in the menu


def test_link_checkbox_mirrors_both_ways(app):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QCheckBox
    from ui.regions import _link_checkbox

    box = QCheckBox()
    action = QAction("mirror")
    action.setCheckable(True)
    _link_checkbox(box, action)
    action.setChecked(True)
    assert box.isChecked()
    box.setChecked(False)
    assert not action.isChecked()


def test_receive_row_keeps_the_low_frequency_controls_out(app, win):
    """U164: frequent controls stay in the row, the rest live in the More menu.

    Font-independent on purpose: the pixel width differs per platform, the
    ownership of the controls does not.
    """
    row = win.ts_check.parentWidget()
    for widget in (win.autoscroll_check, win.save_log_btn, win.clear_btn,
                   win.rx_filter_combo):
        assert row.isAncestorOf(widget)
    for widget in (win.pause_check, win.wrap_check, win.save_log_as_btn):
        assert not row.isAncestorOf(widget)
