"""Data-path P2: the receive highlight refresh is incremental.

Its own window (not the shared smoke fixture) so mutating the find state cannot
leak into the other UI tests.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication      # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def win(app):
    from ui.main_window import MainWindow
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    for _ in range(3):
        app.processEvents()
    yield window
    window.close()


def test_refresh_only_scans_the_new_tail(app, win):
    """A second pass must find the new match and keep the earlier ones."""
    from ui.actions_controller import on_find_text_changed, refresh_find_highlights

    win._find_bar.setVisible(True)
    win.find_edit.setText("AB")
    win._emit_rx_text("AB xx AB", log=False)
    on_find_text_changed(win)
    refresh_find_highlights(win)               # establishes the incremental state
    first = list(win._find_matches)
    assert len(first) == 2

    win._emit_rx_text(" AB", log=False)
    refresh_find_highlights(win)               # incremental pass
    assert len(win._find_matches) == 3
    assert win._find_matches[:2] == first
    assert win._find_state["end"] <= win.rx_view.document().characterCount() - 1


def test_refresh_detects_a_match_that_straddles_the_old_end(app, win):
    """The lookback window must not lose a match split across two arrivals."""
    from ui.actions_controller import on_find_text_changed, refresh_find_highlights

    win._find_bar.setVisible(True)
    win.find_edit.setText("ABCD")
    win._emit_rx_text("xx A", log=False)
    on_find_text_changed(win)
    refresh_find_highlights(win)
    assert win._find_matches == []

    win._emit_rx_text("BCD yy", log=False)     # the match spans the boundary
    refresh_find_highlights(win)
    assert len(win._find_matches) == 1
    start, end = win._find_matches[0]
    assert end - start == 4


def test_new_query_forces_a_full_rescan(app, win):
    from ui.actions_controller import on_find_text_changed, refresh_find_highlights

    win._find_bar.setVisible(True)
    win.find_edit.setText("xx")
    on_find_text_changed(win)
    refresh_find_highlights(win)
    n_xx = len(win._find_matches)

    win.find_edit.setText("yy")
    on_find_text_changed(win)
    refresh_find_highlights(win)
    assert len(win._find_matches) != n_xx or n_xx == 0
    assert win._find_state["query"] == "yy"
