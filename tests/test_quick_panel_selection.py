"""Quick-send selection model (2026-10-03): ticks belong to sequence mode only.

The bug Andy hit: ticking a row looked like a selection, but the tick is the sequence's
member flag, so Delete stayed grey. Outside sequence mode the tick is hidden; inside it,
ticking selects the row so a ticked row can be deleted.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


def test_tick_is_hidden_outside_sequence_mode(app, win):
    panel = win.quick_panel
    panel.seq_check.setChecked(False)
    app.processEvents()
    assert not panel._rows[0]["sel"].isVisible()
    assert panel.selected_entries() == []
    assert not panel.del_btn.isEnabled()


def test_clicking_a_row_arms_delete(app, win):
    panel = win.quick_panel
    entry = panel._rows[0]
    QTest.mouseClick(entry["edit"], Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    app.processEvents()
    assert len(panel.selected_entries()) == 1
    assert panel.del_btn.isEnabled()


def test_in_sequence_mode_a_tick_selects(app, win):
    panel = win.quick_panel
    panel.seq_check.setChecked(True)
    app.processEvents()
    entry = panel._rows[0]
    assert entry["sel"].isVisible()
    entry["sel"].setChecked(True)
    app.processEvents()
    assert len(panel.selected_entries()) == 1
    assert panel.del_btn.isEnabled()
    entry["sel"].setChecked(False)
    panel.seq_check.setChecked(False)
    app.processEvents()
    assert not entry["sel"].isVisible()


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
    panel.delete_selected()
    app.processEvents()
    assert len(panel._rows) == before
    assert seen, "the delete must explain that nothing was selected"


def test_delete_asks_for_confirmation_first(app, win):
    """2026-10-03 (Andy): the button confirms before deleting, and Cancel keeps everything."""
    panel = win.quick_panel
    asked = []
    panel._select_row(panel._rows[0], "replace")
    app.processEvents()
    before = len(panel._rows)

    def cancel(_n):
        asked.append("cancel")
        return False

    panel._confirm_delete = cancel
    panel.delete_with_confirm()
    app.processEvents()
    assert asked == ["cancel"]
    assert len(panel._rows) == before          # Cancel changes nothing

    panel._select_row(panel._rows[0], "replace")
    panel._confirm_delete = lambda _n: True
    panel.delete_with_confirm()
    app.processEvents()
    assert len(panel._rows) == before - 1      # Confirm deletes
    panel.clear_selection()
