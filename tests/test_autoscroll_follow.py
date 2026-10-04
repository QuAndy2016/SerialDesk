"""Receive pane: the follow / pause model of auto-scroll (rule UI-30).

One tick used to carry three ideas at once - the persisted *setting*, the *view
position* while the user reads older data, and the tooltip that described them -
so dragging the scrollbar silently rewrote ``autoscroll: false`` into config.json.
These tests keep the three apart: only the user writes the tick, gestures move the
view state, and the hint button is the state's only feedback.

The gestures are driven through ``QAbstractSlider.triggerAction``: that is exactly
what Qt's own mouse, wheel and keyboard handlers call
(``qt-qtbase .../qabstractscrollarea.cpp:1203-1230`` for the keyboard,
``.../qabstractslider.cpp:711`` for the wheel), so these tests drive the same entry
point the user does - and never ``setValue()``, which is the programmatic path.
"""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt           # noqa: E402
from PySide6.QtGui import QMouseEvent, QWheelEvent              # noqa: E402
from PySide6.QtTest import QTest                                # noqa: E402
from PySide6.QtWidgets import (QAbstractSlider, QApplication,    # noqa: E402
                               QStyle, QStyleOptionSlider, QWidget)

import app.config as appconfig                                  # noqa: E402

pytest.importorskip("PySide6")
LINES = 400


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def win(app):
    """One window for the module: construction is far more expensive than a test."""
    from ui.main_window import MainWindow
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    for _ in range(3):
        app.processEvents()
    yield window
    window.close()


def settle(app, times: int = 2) -> None:
    for _ in range(times):
        app.processEvents()


def bar_of(win):
    return win.rx_view.verticalScrollBar()


def feed(win, count: int, first: int = 0) -> None:
    """Append lines the way a received batch does, then follow like the app does."""
    for i in range(first, first + count):
        win._emit_rx_text("data %04d\n" % i, log=False)
    win._scroll_rx_bottom()
    QApplication.processEvents()


def scroll_pages(win, pages: int = 1) -> None:
    """Scroll up the way the PageUp key does (the action Qt routes that key to)."""
    bar = bar_of(win)
    for _ in range(pages):
        bar.triggerAction(QAbstractSlider.SliderAction.SliderPageStepSub)
    QApplication.processEvents()


def drag_handle(win, to_fraction: float) -> None:
    """Drag the scrollbar handle the way a mouse does.

    ``QTest.mouseMove`` sends a move without the button held, which a scrollbar
    ignores, and pressing the groove is a page step rather than a drag - so the
    press has to land on the handle rect and the move has to carry the button
    (qscrollbar.cpp:662-685).
    """
    bar = bar_of(win)
    opt = QStyleOptionSlider()
    bar.initStyleOption(opt)
    start = bar.style().subControlRect(QStyle.ComplexControl.CC_ScrollBar, opt,
                                       QStyle.SubControl.SC_ScrollBarSlider, bar).center()
    end = QPoint(bar.width() // 2,
                 min(max(int(bar.height() * to_fraction), 16), bar.height() - 16))
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QApplication.sendEvent(bar, QMouseEvent(QEvent.Type.MouseMove, QPointF(end),
                                            QPointF(bar.mapToGlobal(end)),
                                            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                            Qt.KeyboardModifier.NoModifier))
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    QApplication.processEvents()


@pytest.fixture(autouse=True)
def fresh_pane(win, tmp_path, monkeypatch):
    """Every test starts at the bottom, following, with the tick on and a blank pane."""
    monkeypatch.setattr(appconfig, "CONFIG_PATH", str(tmp_path / "config.json"))
    win.on_clear()
    win.autoscroll_check.setChecked(True)
    win._set_rx_follow(True)
    feed(win, LINES)
    yield


def test_a_long_pane_actually_has_something_to_scroll_back_to(win):
    """Guard for every other test here: without a scroll range they are vacuous."""
    assert bar_of(win).maximum() > 0


def test_a_user_scroll_pauses_following_without_touching_the_tick(win):
    """UI-30: the tick is the setting, the scroll position is the view state."""
    scroll_pages(win)
    assert win._rx_follow is False
    assert win.autoscroll_check.isChecked() is True


def test_the_status_bar_says_following_is_paused(win):
    """The paused state has one quiet visible feedback: one line in the status bar.

    It has to cost no pane space (user 2026-10-04: "不占位置的轻提示"), so it lives in
    the status bar, and it must be empty - not hidden - while following, otherwise the
    widget would be added and removed while data flows.
    """
    from app.i18n import tr
    hint = win.rx_follow_hint
    assert hint.text() == ""                      # following: nothing to say
    assert hint.parent() is win.statusBar()
    scroll_pages(win)
    assert hint.text() == tr("rx.follow.paused")
    bar_of(win).triggerAction(QAbstractSlider.SliderAction.SliderToMaximum)
    QApplication.processEvents()
    assert hint.text() == ""


def test_the_paused_line_survives_a_language_switch(win):
    """A language switch is another writer of the same string, so it goes through one owner."""
    from app import i18n
    scroll_pages(win)
    assert win.rx_follow_hint.text()
    i18n.set_language("en")
    try:
        win.retranslate()
        QApplication.processEvents()
        assert win.rx_follow_hint.text() == i18n.tr("rx.follow.paused")
        assert "paused" in win.rx_follow_hint.text()
    finally:
        i18n.set_language("zh")
        win.retranslate()
        QApplication.processEvents()
    assert win.rx_follow_hint.text() == i18n.tr("rx.follow.paused")


def test_scrolling_never_rewrites_the_setting(win, tmp_path):
    """The old defect: a glance at history persisted ``autoscroll: false``."""
    win.autoscroll_check.setChecked(False)         # the user's own write...
    win.autoscroll_check.setChecked(True)          # ...leaves auto-scroll on
    config_file = tmp_path / "config.json"
    before = config_file.read_text(encoding="utf-8")
    assert json.loads(before)["autoscroll"] is True
    scroll_pages(win, 2)
    assert config_file.read_text(encoding="utf-8") == before


def test_every_scroll_gesture_obeys_the_same_rule(win):
    """Drag, wheel and keyboard all arrive as slider actions, so one handler covers them."""
    for action in (QAbstractSlider.SliderAction.SliderSingleStepSub,
                   QAbstractSlider.SliderAction.SliderPageStepSub,
                   QAbstractSlider.SliderAction.SliderToMinimum):
        win._set_rx_follow(True)
        bar_of(win).setValue(bar_of(win).maximum())
        bar_of(win).triggerAction(action)
        QApplication.processEvents()
        assert win._rx_follow is False, action


def test_reaching_the_bottom_resumes_following(win):
    """No button is needed: the bottom of the pane *is* the resume gesture.

    Qt routes Key_End to SliderToMaximum on the scrollbar (qabstractslider.cpp:774-776).
    """
    for _ in range(2):
        scroll_pages(win)
        assert win._rx_follow is False
        bar_of(win).triggerAction(QAbstractSlider.SliderAction.SliderToMaximum)
        QApplication.processEvents()
        assert win._rx_follow is True
        assert bar_of(win).value() == bar_of(win).maximum()


def test_a_wheel_over_the_text_pauses_too(win):
    """The wheel is forwarded to the scrollbar inside the framework, not by our code."""
    view = win.rx_view
    bar_of(win).setValue(bar_of(win).maximum())
    win._set_rx_follow(True)
    event = QWheelEvent(QPointF(QPoint(30, 30)), QPointF(view.mapToGlobal(QPoint(30, 30))),
                        QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(view.viewport(), event)
    QApplication.processEvents()
    assert win._rx_follow is False


def test_dragging_the_handle_up_pauses_and_dragging_it_back_follows(win):
    """The gesture that started this change: drag up to read, drag down to follow."""
    drag_handle(win, 0.30)
    assert win._rx_follow is False
    assert win.autoscroll_check.isChecked() is True        # the tick never moved
    assert bar_of(win).value() < bar_of(win).maximum()
    drag_handle(win, 0.98)
    assert bar_of(win).value() == bar_of(win).maximum()
    assert win._rx_follow is True


def test_new_data_does_not_pull_the_view_back_while_paused(win):
    """Reading history means the pane stays where the user put it."""
    scroll_pages(win)
    parked = bar_of(win).value()
    feed(win, 50, first=1000)
    assert bar_of(win).value() == parked
    assert win._rx_follow is False


def test_the_follow_jump_is_not_read_back_as_a_user_gesture(win):
    """A programmatic setValue() emits no actionTriggered (probe, "setValue(max)" row),
    so following the newest line cannot pause the following it just performed."""
    bar = bar_of(win)
    assert win._rx_follow is True
    win._scroll_rx_bottom()
    assert win._rx_follow is True
    bar.setValue(bar.maximum())
    QApplication.processEvents()
    assert win._rx_follow is True


def test_there_is_no_jump_to_latest_button(win):
    """Design intent (user 2026-10-04): "回到最新的按钮不要了，用拖到底实现".

    Scroll position alone carries the state, so the row stays as wide as it was and
    nothing extra appears mid-session - this test is the tripwire against the button
    creeping back in beside the tick.
    """
    assert not hasattr(win, "rx_latest_btn")
    row = win.autoscroll_check.parentWidget()
    names = {child.objectName() for child in row.findChildren(QWidget)}
    assert "rxLatest" not in names


def test_unticking_stops_following_and_ticking_follows_again(win):
    scroll_pages(win)
    win.autoscroll_check.setChecked(False)
    QApplication.processEvents()
    assert win._rx_follow is False
    assert win.rx_follow_hint.text() == ""        # nothing to resume, so nothing to say
    win.autoscroll_check.setChecked(True)
    QApplication.processEvents()
    assert win._rx_follow is True
    assert bar_of(win).value() == bar_of(win).maximum()


def test_the_paused_line_fits_the_status_bar_at_the_narrowest_window(win):
    """The line appears mid-session: the status bar must absorb it without clipping."""
    win.resize(win.minimumWidth(), win.height())
    QApplication.processEvents()
    scroll_pages(win)
    hint = win.rx_follow_hint
    assert hint.text()
    status = win.statusBar()
    if status.width() <= 1:                    # headless runner without a laid-out status bar
        pytest.skip("the status bar was not laid out in this environment")
    assert hint.width() > 0
    assert hint.geometry().right() <= status.width(), "the hint is clipped by the status bar"
    assert win.status_light.isVisible()           # the connection state keeps its place
    win.resize(1100, 700)
    QApplication.processEvents()


def test_nothing_left_to_scroll_ends_the_pause(win):
    """The pause is a position, so it cannot outlive the range it refers to."""
    scroll_pages(win)
    assert win._rx_follow is False
    win.on_clear()
    QApplication.processEvents()
    assert win._rx_follow is True
    feed(win, LINES)
    scroll_pages(win)
    win.rx_view.setPlainText("one short line")
    QApplication.processEvents()
    assert bar_of(win).maximum() == 0
    assert win._rx_follow is True
