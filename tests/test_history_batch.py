"""batch selection and deletion in the send-history dialog."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                            # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication               # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    return application


@pytest.fixture(scope="module")
def win(app):
    from ui.main_window import MainWindow
    window = MainWindow()
    window.resize(1200, 700)
    window.show()
    for _ in range(3):
        app.processEvents()
    yield window
    window.close()


def _seed(win, items: list) -> object:
    """Give the window this history and open the dialog on it."""
    win._send_history = list(items)
    win._history_meta = {}
    win._show_history()
    dlg = win._history_dlg
    dlg.filter_edit.clear()      # a leftover filter would hide the seeded rows
    dlg.list.clearSelection()
    return dlg


def test_batch_delete_removes_every_selected_row(win):
    """multi-select (Ctrl/Shift) deletes the whole selection in one call."""
    dlg = _seed(win, ["A", "B", "C", "D"])
    dlg.list.item(0).setSelected(True)
    dlg.list.item(2).setSelected(True)
    assert dlg._selected_rows() == [0, 2]
    from ui.send_controller import remove_history_entries
    remove_history_entries(win, dlg._selected_rows())
    assert win._send_history == ["B", "D"], win._send_history


def test_select_all_skips_filtered_out_rows(win):
    """Ctrl+A must only touch what is on screen, never the filtered-out rows."""
    dlg = _seed(win, ["AT", "01 03 00 00 00 02", "AT+RST"])
    dlg.filter_edit.setText("AT")                  # hides the Modbus frame
    dlg._select_all_visible()
    rows = dlg._selected_rows()
    assert rows, "the visible matches should be selected"
    for row in rows:
        assert not dlg.list.item(row).isHidden(), row
    assert len(rows) < 3, "the hidden row must not be selected"


def test_single_row_delete_still_works(win):
    """The old one-row path keeps working (the button label falls back)."""
    dlg = _seed(win, ["one", "two"])
    dlg.list.item(1).setSelected(True)
    assert dlg._selected_rows() == [1]
    dlg.del_btn.click()
    assert win._send_history == ["one"], win._send_history
