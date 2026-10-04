"""Offscreen UI smoke tests: the window's wiring, not its pixels.

These exist so the regressions we have already paid for cannot come back:
sticky selection, Ctrl+A being stolen from text fields, a folded panel that
still costs width, and an input box stuck at one line.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt   # noqa: E402
from PySide6.QtGui import QImage, QKeySequence, QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest                     # noqa: E402
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


def test_send_input_is_compact_and_wraps(app, win):
    """2026-10-02: the pane is about two button rows high and long payloads
    wrap + scroll, so the floor is two lines and wrapping is the default."""
    from PySide6.QtWidgets import QPlainTextEdit
    line = win.tx_edit.fontMetrics().lineSpacing()
    assert win.tx_edit.height() >= 2 * line
    assert win.tx_edit.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth


def test_actions_sit_beside_the_input(app, win):
    """2026-10-02: input left, send/history/repeat in a column on the right.

    The old assertion was "input above the buttons"; the buttons intentionally moved
    to the right edge, so this now checks the column is beside the box, not under it.
    """
    group = win._tx_group
    input_right = win.tx_edit.mapTo(group, win.tx_edit.rect().topRight()).x()
    for name, widget in (("send", win.send_btn), ("history", win.history_btn),
                         ("repeat", win.repeat_btn), ("interval", win.repeat_ms)):
        left = widget.mapTo(group, widget.rect().topLeft()).x()
        assert left >= input_right, "%s is not to the right of the input" % name
    # the box is still inside the send group, below the options row
    assert win.tx_edit.mapTo(group, win.tx_edit.rect().topLeft()).y() > 0


def test_quick_send_rows_are_one_line_with_a_send_icon(app, win):
    """2026-10-04: one command = one line, ``[command][name][send]`` (user request).

    The two-line layout cost 54 px per command; this one keeps the command on the left
    stretch (so every command starts at the same x) and puts label + action on the right.
    """
    from PySide6.QtWidgets import QToolButton

    row = win.quick_panel._rows[0]
    assert row.name_edit is not None and row.text_edit is not None
    assert row.name_edit is not row.text_edit
    tops = {w.geometry().top() for w in (row.text_edit, row.chip, row.name_edit, row.send_btn)}
    assert max(tops) - min(tops) <= 4, "the row is not a single line any more"
    assert row.text_edit.x() < row.name_edit.x() < row.send_btn.x()
    # the format marker replaced the old "HEX · 500 ms" chip; the tooltip spells it out.
    # Do not hard-code which format row 0 carries: a fresh machine seeds ASCII examples
    # first (AT / AT+VERSION?), so it depends on the run's config, not on the wiring.
    row.fmt.setCurrentIndex(0)                          # HEX
    assert row.chip.text() == "H" and "HEX" in row.chip.toolTip()
    assert "500" in row.chip.toolTip()                  # the delay stays visible in the hint
    row.fmt.setCurrentIndex(1)                          # ASCII
    assert row.chip.text() == "A" and "ASCII" in row.chip.toolTip()
    # the paper-plane send button is a real 24x24 target with a name for screen readers
    assert isinstance(row.send_btn, QToolButton)
    assert (row.send_btn.width(), row.send_btn.height()) == (24, 24)
    assert not row.send_btn.icon().isNull() and row.send_btn.accessibleName()
    row.height() < 80                  # two lines, not a tall block


def test_selection_survives_a_row_click_and_clears_on_a_blank_click(app, win):
    panel = win.quick_panel
    panel.arm_row(panel._rows[0], "replace")
    assert panel.selected_row() is not None
    outside = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
                          Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                          Qt.KeyboardModifier.NoModifier)
    # the panel only filters its *own* widgets now (no application-wide filter, which used
    # to keep closed windows alive), so a click on the log no longer reaches it - the
    # selection is dropped by Esc, by a click on the panel's blank area, or by the delete
    panel.eventFilter(panel._content, outside)
    assert panel.selected_row() is None


def test_batch_delete_and_undo_restore_the_rows(app, win):
    panel = win.quick_panel
    before = len(panel._rows)
    panel.arm_row(panel._rows[0], "replace")
    panel.arm_row(panel._rows[1], "toggle")
    panel.delete_armed()
    assert len(panel._rows) == before - 2
    panel.restore_rows([{"text": "a", "hex": True, "delay": 500, "index": 0},
                        {"text": "b", "hex": True, "delay": 500, "index": 1}])
    assert len(panel._rows) == before


def test_keyboard_scope_leaves_text_fields_alone(app, win):
    panel = win.quick_panel
    win.tx_edit.setFocus()
    app.processEvents()
    assert panel._owns_keyboard() is False       # Ctrl+A/Delete must not be stolen
    panel._rows[0].setFocus()
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

    (2026-10-03): interval and count now live inside the repeat chip's popup, so
    "attached" no longer means "visible in the row" - it means reachable from the chip.
    The chip itself is the row control and must be visible.
    """
    from ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    for _ in range(4):
        app.processEvents()
    for widget, name in ((win.repeat_btn, "repeat_btn"), (win.send_btn, "send_btn"),
                         (win.history_btn, "history_btn"), (win.tx_edit, "tx_edit"),
                         (win.repeat_chip, "repeat_chip")):
        assert widget.parentWidget() is not None, "%s has no parent" % name
        assert widget.isVisible(), "%s is not visible" % name
    # the two fields are attached to the chip's popup, not to the row
    holder = win.repeat_chip.menu().actions()[0].defaultWidget()
    for widget, name in ((win.repeat_ms, "repeat_ms"), (win.repeat_times, "repeat_times")):
        assert widget.parentWidget() is not None, "%s has no parent" % name
        assert holder.isAncestorOf(widget), "%s is not inside the repeat chip" % name
    # with no port open the toggle must refuse to start a loop and reset itself
    win.repeat_btn.setChecked(True)
    assert not win._repeat_timer.isActive()
    assert not win.repeat_btn.isChecked()


def _icon_pixels(icon) -> bytes:
    """The icon's pixels - ``QIcon.cacheKey()`` is per instance, so it cannot be compared.

    Two calls to ``button.icon()`` hand back distinct QIcon objects (different keys) even
    when they hold the same image, so the regression test compares what is actually drawn.
    """
    image = icon.pixmap(QSize(16, 16)).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    return bytes(image.constBits())


def test_panel_toggle_button_is_never_blank(app, win):
    # the fold button used to render blank until the first manual toggle
    btn = win._panel_btn
    assert not btn.icon().isNull()          # icon present right after build
    open_icon = _icon_pixels(btn.icon())
    win._on_quick_panel_collapsed(True)
    app.processEvents()
    assert not btn.icon().isNull() and _icon_pixels(btn.icon()) != open_icon
    win._on_quick_panel_collapsed(False)
    app.processEvents()
    assert not btn.icon().isNull() and _icon_pixels(btn.icon()) == open_icon


def test_fold_button_is_a_command_button_not_a_toggle(app, win):
    """2026-10-04 report: it sat there looking "selected" (grey fill + accent border) the
    whole time the panel was open, because it was checkable and checked meant "panel shown".

    Evidence and reasoning: a control whose label/icon changes with the state is a command
    button, not a toggle button (W3C APG button pattern, 08_refs/w3c-aria-practices/
    content/patterns/button/button-pattern.html:32,34). The icon already flips, so the
    button must not carry a checked state at all.
    """
    btn = win._panel_btn
    assert not btn.isCheckable()
    # a real click still folds and unfolds - the arrow icon is the only state cue now
    assert not win.quick_panel.is_folded()
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert win.quick_panel.is_folded()
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert not win.quick_panel.is_folded()
    assert not btn.isChecked()          # no latched "on" look can come back


def _border_colour(win, widget) -> str:
    """The colour of the widget's own border, read off a rendered window."""
    top_left = widget.mapTo(win, QPoint(0, 0))
    image = win.grab().toImage()
    return image.pixelColor(top_left.x(), top_left.y() + widget.height() // 2).name()


def test_fold_button_shows_a_focus_ring(app, win):
    """A ``#objectName`` rule outranks the generic ``QToolButton:focus``, so the ring needs
    its own line in the sheet - without it the border never changed under the keyboard
    (measured: it stayed at the resting colour while a focused combo box did change).
    """
    btn = win._panel_btn
    win.activateWindow()
    btn.clearFocus()
    app.processEvents()
    rest = _border_colour(win, btn)
    btn.setFocus()
    app.processEvents()
    assert btn.hasFocus()
    assert _border_colour(win, btn) != rest, "no visible keyboard focus indicator"
    btn.clearFocus()


def test_receive_pane_always_wraps(app, win):
    """2026-10-02: the soft-wrap switch was removed - the pane always wraps.

    The old test flipped win._on_wrap_toggled both ways; the switch no longer exists.
    """
    from PySide6.QtWidgets import QPlainTextEdit
    assert win.rx_view.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
    assert not hasattr(win, "wrap_check") and not hasattr(win, "act_wrap")


def test_clean_copy_strips_timestamps_and_markers(app, win):
    # the clean copy drops kind-2 (timestamp/marker) fragments
    from ui.actions_controller import _rx_copy_text
    win.rx_view.clear()
    win._emit_rx_text("[00:00:00.000] ", meta=True)
    win._emit_rx_text("<- ", meta=True)
    win._emit_rx_text("HELLO")
    app.processEvents()
    assert _rx_copy_text(win).strip() == "HELLO"
    assert _rx_copy_text(win, current_line=True).strip() == "HELLO"
    assert "<- " in win.rx_view.toPlainText()   # raw still shows the marker


def test_clear_button_clears_display_and_counters(app, win):
    """2026-10-02: one clear action - display + counters.

    The split button (clear display / clear+counters / reset counters) is gone; the
    single Clear button and Ctrl+L both zero the counters as well.
    """
    win.rx_view.clear()
    win._emit_rx_text("DATA")
    win.rx_bytes, win.tx_bytes, win._sent_count = 42, 7, 3
    win._on_clear_and_counters()
    app.processEvents()
    assert (win.rx_bytes, win.tx_bytes, win._sent_count) == (0, 0, 0)
    assert "DATA" not in win.rx_view.toPlainText()
    assert not hasattr(win, "_reset_counters") and not hasattr(win, "_clear_menu")


def test_focus_inside_row_selects_it(app, win):
    # a FocusIn landing on a row control selects that row (keyboard reach)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent
    panel = win.quick_panel
    panel.clear_selection()
    row = panel._rows[0]
    panel.eventFilter(row.text_edit, QFocusEvent(QEvent.Type.FocusIn))
    app.processEvents()
    assert row.armed() is True
    panel.clear_selection()


def test_rx_view_filter_hides_tx_or_rx(app, win):
    # b: the RX/TX filter rebuilds the pane from the fragment store
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
    assert "<- " in text and "-> " not in text     # no TX marker in RX only
    win._on_rx_filter_changed(2)          # TX only
    app.processEvents()
    text = win.rx_view.toPlainText()
    assert "TXLINE" in text and "RXLINE" not in text
    assert "-> " in text and "<- " not in text     # TX marker (timestamp) visible
    win._on_rx_filter_changed(0)          # back to all
    app.processEvents()
    assert "RXLINE" in win.rx_view.toPlainText() and "TXLINE" in win.rx_view.toPlainText()


def test_find_highlights_and_case_switch(app, win):
    # the highlight box is persistent and the case switch re-runs the search
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
    # 0 = endless, otherwise stop once the requested rounds are done
    from ui.quick_send_panel import loop_should_continue
    assert loop_should_continue(1, 1) is False
    assert loop_should_continue(1, 2) is True
    assert loop_should_continue(2, 2) is False
    assert loop_should_continue(99, 0) is True


def test_repeat_count_reads_the_rounds_wheel(app, win):
    """2026-10-04: one wheel, exactly like the quick-send panel - ∞ is its default value."""
    from ui.actions_controller import repeat_count
    win.repeat_times.setValue(0)              # 0 is the wheel's ∞ state, never a count
    assert win.repeat_times.endless() and repeat_count(win) == 0
    win.repeat_times.setValue(5)
    assert repeat_count(win) == 5
    win.repeat_times.setValue(9999)           # the wheel clamps at its top
    assert (win.repeat_times.value(), repeat_count(win)) == (999, 999)


def test_the_repeat_wheel_spins_like_the_panel_one(app, win):
    """Same behaviour the sequence panel got: ∞ sits below 1 and above the top."""
    wheel = win.repeat_times
    wheel.setValue(0)
    assert wheel.text() == "\u221e" and wheel.endless()      # default: until stopped
    wheel.stepBy(1)                                          # ∞ -> 1
    assert wheel.value() == 1
    wheel.stepBy(1)
    assert wheel.value() == 2
    wheel.stepBy(-1)
    assert wheel.value() == 1
    wheel.stepBy(-1)                                         # 1 -> ∞
    assert wheel.endless()
    wheel.setValue(999)
    wheel.stepBy(1)                                          # 999 -> ∞ (restart the range)
    assert wheel.endless()
    wheel.stepBy(-1)                                         # ∞ -> 999, the other end
    assert wheel.value() == 999
    assert wheel.valueFromText("\u221e") == 0                 # typing ∞ works too
    wheel.setValue(0)


def test_the_repeat_chip_shows_the_wheel(app, win):
    """The chip keeps the wheel's state visible while the popup is closed."""
    win.repeat_ms.setText("250")
    win.repeat_times.setValue(0)
    assert win.repeat_chip.text() == "250ms\u00d7\u221e"
    win.repeat_times.setValue(7)
    assert win.repeat_chip.text() == "250ms\u00d77"
    win.repeat_times.setValue(0)
    win.repeat_ms.setText("1000")


def test_both_wheels_document_the_cap_and_the_endless_state(app, win):
    """2026-10-04 (R27): the tooltip must name the top of the wheel (999) and say that ∞
    keeps repeating - both wheels, both languages (the wording is checked language-free:
    "999" and the ∞ glyph appear in the zh and the en string)."""
    for label, wheel in (("sequence rounds", win.quick_panel.rounds),
                         ("repeat count", win.repeat_times)):
        tip = wheel.toolTip()
        assert "999" in tip, "%s tooltip does not state the cap" % label
        assert "\u221e" in tip, "%s tooltip does not explain the endless state" % label


def test_repeat_count_falls_back_to_one_send(app, win):
    """2026-10-03 (review): a read failure must not be read as "keep sending forever"."""
    from ui.actions_controller import repeat_count

    class _Boom:
        def endless(self):
            raise ValueError("no value")

    real, win.repeat_times = win.repeat_times, _Boom()
    try:
        assert repeat_count(win) == 1
    finally:
        win.repeat_times = real


def test_repeat_tick_stops_after_the_count(app, win):
    # each tick sends once and the loop stops itself at the target
    from ui.actions_controller import on_repeat_tick
    sent = []
    real_send = win.on_send
    win.on_send = lambda: sent.append(1)
    try:
        win.repeat_times.setValue(3)
        win._repeat_count = 0
        for _ in range(3):
            on_repeat_tick(win)
        assert len(sent) == 3
        assert not win._repeat_timer.isActive()
    finally:
        # the window is shared by this whole module: a stub left behind makes every later
        # send silently do nothing (that is exactly how the 2026-10-04 line-ending test
        # failed with an empty payload list)
        win.on_send = real_send


def test_column_hex_rows_and_offset():
    # c: pure hexdump formatter - 16 bytes per row, running offset
    from app.display import column_hex
    text, off = column_hex(bytes(range(20)), 0)
    lines = text.split("\n")
    assert len(lines) == 2
    assert lines[0].startswith("00000000  ") and lines[0].endswith("|")
    assert lines[1].startswith("00000010  ")
    assert off == 20


def test_column_hex_mode_renders_rows(app, win):
    # c: the HEX cols mode renders hexdump rows into the pane
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
    """a long line can be read in full from a tooltip, text untouched."""
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
    """a fresh install opens with three real commands, not ten blank rows."""
    # the panel persists through app.config now (review R9), so the path lives there
    from app import config as appconfig
    from ui import quick_send_panel as qsp

    monkeypatch.setattr(appconfig, "CONFIG_PATH", str(tmp_path / "config.json"))
    panel = qsp.QuickSendPanel()
    panel.detach_app_filter()          # an app-wide filter would outlive this test
    texts = [row.text() for row in panel._rows]
    assert texts[:3] == ["AT", "AT+VERSION?", "01 03 00 00 00 02"]
    assert texts[3:] == [""] * (len(texts) - 3)
    assert len(panel._rows) == qsp.DEFAULT_ROWS
    assert panel._rows[0].text_edit.toolTip()        # the seeded rows say why
    panel.deleteLater()


def test_more_menu_holds_the_low_frequency_switches(app, win):
    """/only pause/save-as live in the More menu now (the wrap switch was
    removed in 2026-10-02); auto-scroll is back in the row because it is high frequency."""
    assert win.more_btn.menu() is win.more_menu
    for widget in (win.pause_check, win.save_log_as_btn):
        assert not widget.isVisible()
    assert win.act_pause.isCheckable()
    assert win.act_pause.isChecked() == win.pause_check.isChecked()
    row = win.ts_check.parentWidget()
    assert row.isAncestorOf(win.autoscroll_check)
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
    """frequent controls stay in the row, the rest live in the More menu.

    Font-independent on purpose: the pixel width differs per platform, the
    ownership of the controls does not.
    """
    row = win.ts_check.parentWidget()
    for widget in (win.autoscroll_check, win.save_log_btn, win.clear_btn,
                   win.rx_filter_combo):
        assert row.isAncestorOf(widget)
    for widget in (win.pause_check, win.save_log_as_btn):
        assert not row.isAncestorOf(widget)


class _FakeWorker:
    """Enough worker for the send path: it is open and it records payloads."""

    def __init__(self):
        self.sent = []

    def is_open(self):
        return True

    def send(self, payload):
        self.sent.append(payload)
        return True


def test_enter_runs_the_command_instead_of_breaking_the_line(app, win):
    """Windows rule: Enter activates the default button - here that button is Send.

    Reported 2026-10-04: clicking into the box and pressing Enter moved the caret to a new
    line, which both looked like input and could end up inside the payload.
    """
    from PySide6.QtGui import QTextCursor
    fake = _FakeWorker()
    worker, fmt_index, nl_index = win.worker, win.tx_fmt_combo.currentIndex(), \
        win.nl_combo.currentIndex()
    win.worker = fake
    try:
        win.tx_fmt_combo.setCurrentIndex(1)          # ASCII
        win.nl_combo.setCurrentIndex(0)              # no line ending appended
        win.tx_edit.setPlainText("AT")
        win.tx_edit.setFocus()
        cursor = win.tx_edit.textCursor()      # as if typed: the caret sits after the text
        cursor.movePosition(QTextCursor.MoveOperation.End)
        win.tx_edit.setTextCursor(cursor)
        app.processEvents()
        QTest.keyClick(win.tx_edit, Qt.Key.Key_Return)
        app.processEvents()
        assert win.tx_edit.toPlainText() == "AT"     # no line break was inserted
        assert fake.sent == [b"AT"]                  # Enter ran the command
        QTest.keyClick(win.tx_edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        app.processEvents()
        assert win.tx_edit.toPlainText() == "AT\n"   # Shift+Enter is the explicit break
        assert fake.sent == [b"AT"]                  # ... and it did not send
    finally:
        win.worker = worker
        win.tx_fmt_combo.setCurrentIndex(fmt_index)
        win.nl_combo.setCurrentIndex(nl_index)
        win.tx_edit.setPlainText("")
        app.processEvents()


def test_enter_on_an_empty_box_sends_nothing(app, win):
    """No data typed: Enter must not smuggle a blank line into the payload."""
    fake = _FakeWorker()
    worker = win.worker
    win.worker = fake
    try:
        win.tx_edit.setPlainText("")
        win.tx_edit.setFocus()
        app.processEvents()
        QTest.keyClick(win.tx_edit, Qt.Key.Key_Return)
        app.processEvents()
        assert win.tx_edit.toPlainText() == ""
        assert fake.sent == []
    finally:
        win.worker = worker
        win.tx_edit.setPlainText("")
        app.processEvents()


def test_a_trailing_space_is_ignored_and_explained(app, win):
    """A space after the data is not data: ignored at the key, explained once.

    The official rule is "ignore the character and display an input problem balloon that
    explains the valid characters" (ctrl-text-boxes.md:211) - the panel's toast is that
    explanation.
    """
    from PySide6.QtGui import QTextCursor
    seen = []
    win.tx_edit.rejected.connect(seen.append)
    try:
        win.tx_edit.setPlainText("AT")
        win.tx_edit.setFocus()
        cursor = win.tx_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        win.tx_edit.setTextCursor(cursor)
        app.processEvents()
        QTest.keyClick(win.tx_edit, Qt.Key.Key_Space)
        app.processEvents()
        assert win.tx_edit.toPlainText() == "AT"           # nothing trailed
        assert seen == ["tx.reject.trailing_space"]
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        win.tx_edit.setTextCursor(cursor)
        QTest.keyClick(win.tx_edit, Qt.Key.Key_Space)      # between bytes: allowed
        app.processEvents()
        assert win.tx_edit.toPlainText() == "A T"
    finally:
        win.tx_edit.setPlainText("")
        app.processEvents()


def test_the_send_chip_shows_the_line_ending(app, win):
    """A setting that appends bytes must not hide inside a popup (user report 2026-10-04).

    The chip used to read "ASCII · 无" - and that "无" was the *checksum*. A line ending
    left on CRLF from an earlier session therefore appended \\r\\n invisibly.
    """
    win.tx_fmt_combo.setCurrentIndex(1)                  # ASCII: the ending applies
    app.processEvents()
    for index, expected in ((0, "无"), (1, "CR"), (2, "LF"), (3, "CRLF")):
        win.nl_combo.setCurrentIndex(index)
        app.processEvents()
        chip = win.tx_settings_btn.text()
        assert expected in chip, (index, chip)
        assert "校验" in chip, chip                       # ... and the checksum says so too
    win.tx_fmt_combo.setCurrentIndex(0)                  # HEX never appends an ending
    app.processEvents()
    assert "CRLF" not in win.tx_settings_btn.text()
    win.tx_fmt_combo.setCurrentIndex(1)
    win.nl_combo.setCurrentIndex(0)
    app.processEvents()


def test_the_payload_ends_at_the_last_character_when_no_ending_is_chosen(app, win):
    """The reported case: type the command, send, and exactly that arrives - no CR/LF.

    Trailing spaces/blank lines typed into the box never reach the device (the send path
    strips them); the only thing that used to add bytes was the line-ending picker.
    """
    panel = win.quick_panel
    fake = _FakeWorker()
    worker, fmt_index, nl_index = win.worker, win.tx_fmt_combo.currentIndex(), \
        win.nl_combo.currentIndex()
    win.worker = fake
    import ui.send_controller as sc
    try:
        win.tx_fmt_combo.setCurrentIndex(1)              # ASCII
        win.nl_combo.setCurrentIndex(0)                  # 无
        win.tx_edit.setPlainText("ffffffffffffffffffRR  \n")
        app.processEvents()
        sc.on_send(win)          # the controller itself: no sibling test can stub this one
        app.processEvents()
        assert fake.sent == [b"ffffffffffffffffffRR"], (
            "sent=%r text=%r fmt=%s enc=%s"
            % (fake.sent, win.tx_edit.toPlainText(), win.tx_fmt_combo.currentIndex(),
               win._encoding()))
        win.nl_combo.setCurrentIndex(3)                  # explicitly asking for CRLF
        win.tx_edit.setPlainText("ffffffffffffffffffRR")
        sc.on_send(win)
        app.processEvents()
        assert fake.sent[1] == b"ffffffffffffffffffRR\r\n"
    finally:
        win.worker = worker
        win.tx_fmt_combo.setCurrentIndex(fmt_index)
        win.nl_combo.setCurrentIndex(nl_index)
        win.tx_edit.setPlainText("")
        app.processEvents()


def test_quick_send_rows_follow_the_line_ending(app, win):
    """2026-10-02: picking CRLF must also end the quick-send rows.

    An ASCII row gets exactly what a manual send would append; a HEX row stays
    byte-exact, the same rule the send box itself follows in HEX mode.
    """
    panel = win.quick_panel
    fake = _FakeWorker()
    worker, nl_index, crc_index = win.worker, win.nl_combo.currentIndex(), \
        win.checksum_combo.currentIndex()
    win.worker = fake
    try:
        win.checksum_combo.setCurrentIndex(0)        # no checksum, deterministic bytes
        win.nl_combo.setCurrentIndex(3)              # CRLF
        app.processEvents()
        panel.add_row("AT+RST", is_hex=False)
        panel.add_row("01 03 00 00", is_hex=True)
        ascii_entry, hex_entry = panel._rows[-2], panel._rows[-1]
        ascii_entry.send_btn.click()
        hex_entry.send_btn.click()
        app.processEvents()
        assert fake.sent == [b"AT+RST\r\n", b"\x01\x03\x00\x00"]
    finally:
        win.worker = worker
        win.nl_combo.setCurrentIndex(nl_index)
        win.checksum_combo.setCurrentIndex(crc_index)
        panel.delete_entries([panel._rows[-2], panel._rows[-1]])
        app.processEvents()


def test_quick_send_row_payload_carries_its_format(app, win, monkeypatch):
    """The panel tells the controller whether the row is HEX - that flag is what
    decides if the line ending is appended.

    Run from source the app reads the repository's config.json, which can be full of
    a developer's own rows; add_row then refuses and the two rows under test never
    exist. Raise the cap for this test so it never depends on that machine state.
    """
    import ui.quick_send_panel as qsp

    panel = win.quick_panel
    monkeypatch.setattr(qsp, "MAX_ENTRIES", len(panel._rows) + 2)
    seen = []
    panel.send_payload.connect(lambda payload, is_hex: seen.append((payload, is_hex)))
    panel.add_row("AT", is_hex=False)
    panel.add_row("41 54", is_hex=True)
    app.processEvents()
    assert len(panel._rows) >= 2
    panel._send_one(panel._rows[-2])
    panel._send_one(panel._rows[-1])
    app.processEvents()
    assert seen == [(b"AT", False), (b"AT", True)]


def test_row_ticks_belong_to_sequence_mode_only(app, win):
    """the tick is the sequence's member flag, not a delete selection.

    : "the box in front is for sequence sending, not for ticking-then-deleting".
    So a tick must neither be available outside sequence mode nor arm Delete.
    """
    panel = win.quick_panel
    was_seq = panel.seq_check.isChecked()
    panel.seq_check.setChecked(True)        # force the signal, then turn it off again
    panel.seq_check.setChecked(False)
    app.processEvents()
    try:
        assert not any(row.tick.isEnabled() for row in panel._rows)
        assert not panel.del_btn.isEnabled()
    finally:
        panel.seq_check.setChecked(was_seq)
        app.processEvents()


def test_click_selection_is_what_delete_removes(app, win):
    """the click highlight arms Delete and Delete removes that row.

    The grey  saw was the hover background (theme: QFrame#qsRow:hover), which is
    not a selection at all; the selected row now paints with the accent border so the
    two are distinguishable.
    """
    panel = win.quick_panel
    for row in panel._rows:
        row.set_armed(False)
    app.processEvents()
    assert not panel.del_btn.isEnabled()
    entry = panel._rows[0]
    panel.arm_row(entry, "replace")
    app.processEvents()
    assert entry.armed()
    assert panel.del_btn.isEnabled()
    before = len(panel._rows)
    panel.del_btn.click()
    app.processEvents()
    assert len(panel._rows) == before - 1
    assert not panel.del_btn.isEnabled()          # nothing selected any more


def test_delete_button_reads_delete(app, win):
    """2026-10-02: the button is just "Delete" - no "selected", no count."""
    from app.i18n import tr
    assert win.quick_panel.del_btn.text() == tr("qs.del")
    for row in win.quick_panel._rows:
        if row.ticked():
            row.set_ticked(False)
    app.processEvents()
    assert win.quick_panel.del_btn.text() == tr("qs.del")
    assert not win.quick_panel.del_btn.isEnabled()


def test_line_ending_control_is_visible_but_disabled_in_hex(app, win):
    """-A (2026-10-02): the picker must not vanish in HEX mode.

    Hiding the whole group made the option look unsupported - the user could not see
    that it existed or what state it was in. It now stays visible and switches off,
    with the tooltip explaining that HEX is byte-exact.
    """
    from app.i18n import tr
    was = win.tx_fmt_combo.currentIndex()
    try:
        win.tx_fmt_combo.setCurrentIndex(0)          # HEX
        app.processEvents()
        assert win._tx_mod_group.isVisibleTo(win)
        assert not win.nl_combo.isEnabled()
        assert not win.escape_check.isEnabled()
        assert win.nl_combo.toolTip() == tr("tx.newline.hex.tip")
        win.tx_fmt_combo.setCurrentIndex(1)          # ASCII
        app.processEvents()
        assert win._tx_mod_group.isVisibleTo(win)
        assert win.nl_combo.isEnabled()
        assert win.escape_check.isEnabled()
        assert win.nl_combo.toolTip() == tr("tx.newline.tip")
    finally:
        win.tx_fmt_combo.setCurrentIndex(was)
        app.processEvents()


def test_store_rows_and_document_lines_agree_with_embedded_newlines(app, win):
    """2026-10-03 (data-path pass): the store must know every line the pane shows.

    Before this, an ASCII payload containing 0x0A rendered two lines while the
    store held one entry - the filter and every per-line action then worked off a
    row model that did not match the screen.
    """
    from app.display import rows_from_fragments
    from ui.receive_controller import rebuild_rx_view
    win.rx_view.clear()
    win._rx_store = []
    win._emit_rx_text("AA\nBB", tx=False)
    app.processEvents()
    assert win.rx_view.blockCount() == 2
    assert len(rows_from_fragments(win._rx_store)) == 2
    before = win.rx_view.toPlainText()
    rebuild_rx_view(win)
    app.processEvents()
    assert win.rx_view.toPlainText() == before      # rebuild is a no-op visually


def test_status_counts_are_coalesced_not_recomputed_per_batch(app, win):
    """2026-10-03: one status refresh per 100 ms, not one per batch."""
    win.rx_bytes += 1234
    win._schedule_counts()
    app.processEvents()
    assert getattr(win, "_counts_timer", None) is not None
    assert win._counts_timer.isActive()          # a refresh is queued
    win._schedule_counts()                       # more data: no second timer
    assert win._counts_timer.isActive()
    win._counts_timer.stop()
    win.update_counts()                          # the immediate path still works
    assert str(win.rx_bytes) in win.sent_lbl.text().replace(",", "")
    win.rx_bytes -= 1234
    win.update_counts()


def test_dropped_send_frames_are_counted(app, win):
    """2026-10-03: a full TX queue must not drop a frame silently."""
    before = getattr(win, "_tx_dropped", 0)
    win._on_send_error("queue", "64")
    assert win._tx_dropped == before + 1
    win._on_send_error("queue", "64")
    assert win._tx_dropped == before + 2       # the second toast reports the total
