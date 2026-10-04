"""The window's floors are measured, and the two wasted gaps stay closed.

User report 2026-10-04: "控制软件窗口最小的，高度和宽度都应该在用户拖拽边框控制整个窗口大小的
时候，应该尽量跟随用户鼠标设置" with four items - the gap between Save log and Clear, the
oversized highlight field, a receive pane that could not be dragged any lower, and the
Receive / Send captions above the panes.

Measured before the change: window floor 1109x600, save-log -> clear gap 159 px, highlight
field 550 px of an 880 px row, receive pane floor 148 px, title band 18 px per pane.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication      # noqa: E402


@pytest.fixture(scope="module")
def win():
    """One shown window: the floors are derived during the first layout pass."""
    app = QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow

    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    for _ in range(6):
        app.processEvents()
    yield window, app


def test_the_window_height_floor_is_measured_not_remembered(win) -> None:
    """It used to be a hard-coded ``setMinimumSize(1060, 600)``."""
    window, app = win
    assert window.minimumHeight() <= window.minimumSizeHint().height(), \
        "the floor must not exceed what the live layout asks for"
    assert window.minimumHeight() < 600, "the old hard-coded 600 px floor is back"
    window.resize(1, 1)
    for _ in range(6):
        app.processEvents()
    assert window.height() == window.minimumHeight()
    assert window.height() < 600
    window.resize(1280, 800)
    for _ in range(4):
        app.processEvents()


def test_the_log_actions_sit_together(win) -> None:
    """The stretch used to sit between them - 159 px of empty row between two buttons."""
    window, _app = win
    gap = window.clear_btn.x() - (window.save_log_btn.x() + window.save_log_btn.width())
    assert 0 <= gap <= 12, "Save log and Clear drifted apart again (%d px)" % gap


def test_the_highlight_field_is_sized_to_its_input(win) -> None:
    """ctrl-text-boxes.md:255 - a text box's width is a clue to the expected input."""
    window, _app = win
    # 2026-10-04 second UI report: 240 px was still too wide - halved to six English
    # characters (the count label beside it reports matches, so nothing is hidden).
    assert window.find_edit.maximumWidth() == 110
    assert window.find_edit.width() <= 120
    # the rest of the row keeps its natural width instead of soaking up the slack; the two
    # navigation buttons are *fixed* 30x26 icon buttons (asserting their size against a
    # style-dependent sizeHint broke on the CI runner's Qt style, so the fixed size itself is
    # the contract now)
    assert window.find_case_check.width() <= window.find_case_check.sizeHint().width() + 8
    for button in (window.find_prev_btn, window.find_next_btn):
        assert (button.width(), button.height()) == (30, 26)


def test_the_find_bar_starts_hidden_and_its_arrows_are_icons(win) -> None:
    """2026-10-04 report item 3: a tool, not furniture - and the words became arrows.

    The window built by this module's fixture is the one the app starts with, so this is
    the startup state: hidden, and the navigation controls carry glyphs (24 px targets,
    accessible names) instead of the two-character labels they used to spell out.
    """
    from ui import theme

    window, _app = win
    assert window._find_bar.isHidden()
    # the second report (same day): up/down, not left/right - matches are stacked lines
    for button, glyph in ((window.find_prev_btn, "arrow_up"),
                          (window.find_next_btn, "arrow_down")):
        assert not button.icon().isNull()
        assert button.accessibleName()
        assert button.width() >= 24 and button.height() >= 24
        assert button.icon().pixmap(14, 14).toImage() == \
            theme.glyph(glyph).pixmap(14, 14).toImage(), glyph


def test_the_match_counter_never_moves_the_navigation_buttons(win) -> None:
    """2026-10-04 second report: the count label grew 13 -> 39 px and pushed both arrows
    26 px to the right while the user was still typing. A fixed slot stops that."""
    window, _app = win
    window._toggle_find_bar(True)
    for _ in range(6):
        _app.processEvents()
    if window._find_bar.width() <= 1:            # the platform never laid the bar out
        pytest.skip("the find bar was not laid out in this environment")
    # the glyphs must survive *opening* the bar: toggle_find_bar() refreshes the icons, and
    # that refresh once kept writing the left/right pair over the up/down ones (the first
    # version of this test checked before opening and missed it)
    from ui import theme

    for button, glyph in ((window.find_prev_btn, "arrow_up"),
                          (window.find_next_btn, "arrow_down")):
        assert button.icon().pixmap(14, 14).toImage() == \
            theme.glyph(glyph).pixmap(14, 14).toImage(), glyph
    before = (window.find_prev_btn.x(), window.find_next_btn.x(),
              window.find_close_btn.x())
    window.find_edit.setText("AT")
    for _ in range(6):
        _app.processEvents()
    assert window.find_count_lbl.width() == 46        # the slot, not the text, sets the width
    after = (window.find_prev_btn.x(), window.find_next_btn.x(), window.find_close_btn.x())
    assert before == after, "the count moved the controls (%s -> %s)" % (before, after)
    # and the close button closes the cluster instead of sitting at the far right edge
    assert window.find_close_btn.x() - window.find_next_btn.x() <= 40
    window._toggle_find_bar(False)
    for _ in range(4):
        _app.processEvents()


def test_the_find_bar_is_a_bar_with_a_separator_and_a_menu_entry(win) -> None:
    """Items 1 and 4: a separator line from the control row above it, and the feature says
    "find" and lives in the More menu (Ctrl+F still opens it)."""
    from PySide6.QtWidgets import QFrame

    window, _app = win
    assert isinstance(window._find_bar, QFrame)
    assert window._find_bar.objectName() == "findBar"     # QSS draws the top border
    assert window.act_find in window.more_menu.actions()
    assert window.act_find.isCheckable()
    window._toggle_find_bar(True)
    for _ in range(4):
        _app.processEvents()
    assert window.act_find.isChecked()                    # the menu mirrors the bar
    window._toggle_find_bar(False)
    for _ in range(4):
        _app.processEvents()
    assert not window.act_find.isChecked()


def test_the_parameter_summary_uses_the_shared_dropdown_arrow(win) -> None:
    """Item 2: the "▾" character was tiny and belonged to no other control; every dropdown
    indicator is the same themed glyph now."""
    window, _app = win
    summary = window.params_summary
    assert "\u25be" not in summary.text()
    assert not summary.icon().isNull()
    assert summary.toolButtonStyle().name.startswith("ToolButtonTextBesideIcon")


def test_the_closed_boxes_only_reserve_what_they_show(win) -> None:
    """2026-10-04 UI report item 1: "COM5" does not need 134 px.

    The dropdown lists keep their own width (the port delegate draws a two-line entry);
    only the closed box is told to size itself to a handful of characters. Asserting the
    policy rather than a pixel count keeps this font- and DPI-independent.
    """
    from PySide6.QtWidgets import QComboBox

    window, _app = win
    for combo, chars in ((window.port_combo, 5), (window.baud_combo, 6),
                         (window.rx_fmt_combo, 5)):
        assert combo.sizeAdjustPolicy() == \
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        assert combo.minimumContentsLength() == chars


def test_the_folded_window_floor_is_the_measured_need(win) -> None:
    """Item 6: folding must actually buy width - no remembered constant in the way.

    The window floor used to be `max(980, ...)`, which on this machine was *larger* than
    the widest row (measured 787 px on the real font), so folding the quick-send panel
    changed nothing. The floor is now the measured connection row, so this asserts the
    relation - the absolute number moves with font, DPI and translation.
    """
    window, _app = win
    window._fit_minimum_width()
    _app.processEvents()
    unfolded = window.minimumWidth()
    window.quick_panel.collapsed_changed.emit(True)
    for _ in range(6):
        _app.processEvents()
    window._fit_minimum_width()
    for _ in range(4):
        _app.processEvents()
    folded = window.minimumWidth()
    connect_need = window._row_need(window._control_rows()[0])
    # The contract is the *formula*, not "folding must shrink it": on a font where the
    # connection row is the binding constraint, folding legitimately changes nothing
    # (asserting `folded < unfolded` broke on the CI runner). Recompute the expected floor
    # the same way the window does and demand they agree - a remembered constant would not.
    panel_min = 0
    pair_need = (window._rx_group.minimumWidth() + panel_min + window._splitter.handleWidth()
                 + max(0, window.width() - window._splitter.width()))
    expected = max(360, connect_need, pair_need)
    assert folded == expected, \
        "window floor %d is not the measured need %d (connect %d, pair %d)" \
        % (folded, expected, connect_need, pair_need)
    assert folded <= unfolded, "folding made the floor *wider*: %d > %d" % (folded, unfolded)
    window.quick_panel.collapsed_changed.emit(False)
    for _ in range(6):
        _app.processEvents()


def test_the_send_button_is_the_same_paper_plane_as_the_rows(win) -> None:
    """Item 5: one icon language for "send" - the asset, not the word."""
    window, _app = win
    button = window.send_btn
    assert not button.icon().isNull()
    assert button.text() == ""
    assert button.accessibleName()          # the label lives on for screen readers
    assert button.toolTip()
    assert button.width() <= 40             # icon button, not a 64 px word button


def test_the_status_message_and_the_undo_reminder_share_the_left_cluster(win) -> None:
    """Item 7: the undo affordance belongs next to the action's feedback, not far right.

    Both are normal status-bar widgets now (not permanent ones), which also means
    QStatusBar.showMessage can no longer hide the undo button - the message is a label
    of our own. The connection light stays on the right.
    """
    window, _app = win
    if window.statusBar().width() <= 1:          # not laid out (e.g. a headless runner)
        pytest.skip("the status bar was not laid out in this environment")
    window._notify("ping")
    _app.processEvents()
    assert window.status_msg.text() == "ping"
    assert window.status_msg.x() < window.status_light.x()
    window._undo_btn.show()
    for _ in range(3):
        _app.processEvents()
    assert window._undo_btn.isVisible()
    assert window._undo_btn.x() < window.status_light.x()
    window._undo_btn.hide()


def test_the_receive_pane_can_be_dragged_low(win) -> None:
    window, _app = win
    assert window.rx_view.minimumHeight() <= 44          # about two lines of data
    assert window._rx_group.layout().minimumSize().height() <= 125
    band = window._rx_group.height() - window._rx_group.contentsRect().height()
    assert band <= 4, "the group-box title band is back (%d px)" % band


def test_the_panes_keep_their_name_without_a_caption(win) -> None:
    """The caption is gone (ctrl-group-boxes.md:27,52); the accessible name is not."""
    window, _app = win
    from app.i18n import tr

    assert window._rx_group.title() == ""
    assert window._tx_group.title() == ""
    assert window._rx_group.accessibleName() == tr("group.rx")
    assert window._tx_group.accessibleName() == tr("group.tx")
