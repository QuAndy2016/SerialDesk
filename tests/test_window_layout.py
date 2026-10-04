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
    assert window.find_edit.maximumWidth() == 240
    assert window.find_edit.width() <= 260
    # the rest of the row keeps its natural width instead of soaking up the slack
    for widget in (window.find_case_check, window.find_prev_btn, window.find_next_btn):
        assert widget.width() <= widget.sizeHint().width() + 8, \
            "%s was stretched instead of left at its natural width" % widget


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
