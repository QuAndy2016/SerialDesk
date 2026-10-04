"""Quick-send selection model, wired through the real main window.

The 2026-10-04 rebuild split the two flags apart:

* the **tick box** is the sequence's member flag - it exists (visible *and* enabled) only
  in sequence mode, and ticking a row never arms a delete;
* the **click highlight** (``armed``) is the delete target, and the header shows how many
  rows are armed.

An earlier version made a tick *mean* "armed", so ticking and clicking kept overwriting
each other; three bug reports came out of that coupling.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SERIALDESK_SKIP_CONFIRM", "1")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt           # noqa: E402
from PySide6.QtTest import QTest                # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def win(app):
    from app import i18n
    from ui.main_window import MainWindow
    i18n.set_language("zh")
    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    for _ in range(4):
        app.processEvents()
    if not window.quick_panel._rows:
        window.quick_panel.add_row("AT", is_hex=False)
    yield window
    window.close()


def test_tick_is_hidden_and_disabled_outside_sequence_mode(app, win):
    panel = win.quick_panel
    panel.seq_check.setChecked(False)
    app.processEvents()
    row = panel._rows[0]
    assert not row.tick.isVisible() and not row.tick.isEnabled()
    assert panel.armed_rows() == []
    assert not panel.del_btn.isEnabled()


def test_clicking_a_row_arms_delete(app, win):
    panel = win.quick_panel
    row = panel._rows[0]
    QTest.mouseClick(row.text_edit, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    app.processEvents()
    assert row.armed() and panel.del_btn.isEnabled()
    assert panel.armed_lbl.text() == "已选 1"


def test_in_sequence_mode_a_tick_marks_membership_without_arming(app, win):
    panel = win.quick_panel
    panel.clear_selection()               # the window is shared between the tests
    panel.seq_check.setChecked(True)
    app.processEvents()
    row = panel._rows[0]
    assert row.tick.isVisible() and row.tick.isEnabled()
    row.set_ticked(True)
    app.processEvents()
    assert row.ticked() and row.badge.text() == "1"      # ① in the run order
    assert not row.armed()                                # ... but nothing was armed
    row.set_ticked(False)
    panel.seq_check.setChecked(False)
    app.processEvents()
    assert not row.tick.isVisible()


def test_the_disabled_button_explains_itself(app, win):
    panel = win.quick_panel
    panel.clear_selection()
    app.processEvents()
    assert panel.del_btn.toolTip()          # never an unexplained dead button


def test_delete_without_a_selection_says_so(app, win):
    """A click that cannot delete must report why instead of doing nothing."""
    panel = win.quick_panel
    panel.clear_selection()
    app.processEvents()
    seen = []
    panel.log.connect(seen.append)
    before = len(panel._rows)
    panel.delete_armed()
    app.processEvents()
    assert len(panel._rows) == before
    assert seen, "the delete must explain that nothing was selected"


def test_delete_removes_the_row_now_and_offers_the_undo(app, win):
    """No modal box: the row goes immediately and the window offers a 3 s undo."""
    panel = win.quick_panel
    row = panel._rows[0]
    panel.arm_row(row, "replace")
    app.processEvents()
    before = len(panel._rows)
    panel.del_btn.click()
    app.processEvents()
    assert len(panel._rows) == before - 1
    assert panel.count_lbl.text().startswith("%d/" % (before - 1))
    assert win._undo_btn.isVisible()          # the safety net for the missing dialog
    assert win._undo_kind == "row"
    win._undo_delete()
    app.processEvents()
    assert len(panel._rows) == before
    panel.clear_selection()


def click_row(app, row, mods=Qt.KeyboardModifier.NoModifier):
    """Click the row's command box the way a mouse does (focus first, then the press)."""
    QTest.mouseClick(row.text_edit, Qt.MouseButton.LeftButton, mods,
                     QPoint(row.text_edit.width() // 2, row.text_edit.height() // 2))
    for _ in range(2):
        app.processEvents()


def test_ctrl_click_selects_several_rows_for_delete(app, win):
    """The 2026-10-04 report: Ctrl+click wiped the selection instead of extending it.

    Qt focuses the clicked widget *before* delivering the press, so the panel's FocusIn
    branch used to re-arm the row with "replace" and the Ctrl press then toggled it off
    again - a click that should have selected two rows selected none. The gestures here
    go through QTest (focus, propagation and modifiers are Qt's own), which is what the
    older filter-only helper could not reproduce.
    """
    panel = win.quick_panel
    panel.clear_selection()
    app.processEvents()
    click_row(app, panel._rows[0])
    assert panel.armed_lbl.text() == "已选 1"
    click_row(app, panel._rows[2], Qt.KeyboardModifier.ControlModifier)
    assert [row for row in panel._rows if row.armed()] == [panel._rows[0], panel._rows[2]]
    assert panel.armed_lbl.text() == "已选 2"
    assert panel.del_btn.isEnabled()
    panel.clear_selection()


def test_shift_click_extends_the_range_from_the_anchor(app, win):
    """UI-03: the anchor survives, so a second Shift+click covers the rows between."""
    panel = win.quick_panel
    panel.clear_selection()
    app.processEvents()
    click_row(app, panel._rows[0])
    click_row(app, panel._rows[2], Qt.KeyboardModifier.ShiftModifier)
    assert [row for row in panel._rows if row.armed()] == list(panel._rows[0:3])
    panel.clear_selection()


def test_deleting_a_multi_selection_removes_all_and_one_undo_restores_them(app, win):
    """Deleting several rows is one action with one undo payload, not N surprises.

    Rows are compared by object identity, not by their command text: two rows may carry
    the same command legitimately (the shared window's rows do), so a text-based check
    fails whenever another file ran first - which is exactly how a real suite caught it
    (run with tests/test_ui_smoke.py first: 1 failed / 59 passed).
    """
    panel = win.quick_panel
    panel.clear_selection()
    app.processEvents()
    before = len(panel._rows)
    before_texts = sorted(row.text() for row in panel._rows)
    click_row(app, panel._rows[0])
    click_row(app, panel._rows[2], Qt.KeyboardModifier.ControlModifier)
    victims = [row for row in panel._rows if row.armed()]
    assert len(victims) == 2
    panel.del_btn.click()
    app.processEvents()
    assert len(panel._rows) == before - 2
    assert not any(row in panel._rows for row in victims)     # those very rows are gone
    assert win._undo_kind == "row"
    win._undo_delete()
    app.processEvents()
    assert len(panel._rows) == before              # one undo brings both rows back
    assert sorted(row.text() for row in panel._rows) == before_texts
    panel.clear_selection()


def test_clicking_the_tick_never_arms_the_row(app, win):
    """The tick is sequence membership; the click highlight is the delete target."""
    panel = win.quick_panel
    panel.clear_selection()
    panel.seq_check.setChecked(True)
    app.processEvents()
    row = panel._rows[1]
    QTest.mouseClick(row.tick, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(row.tick.width() // 2, row.tick.height() // 2))
    app.processEvents()
    assert row.ticked()
    assert not row.armed()
    assert panel.armed_rows() == []
    row.set_ticked(False)
    panel.seq_check.setChecked(False)
    app.processEvents()
