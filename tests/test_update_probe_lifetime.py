"""Update probe lifetime (2026-10-03 review): a late answer must be dropped, not raised.

The probe runs on a daemon thread and outlives the window it reports to - closing the
window destroys the C++ object behind it. The emit then raised RuntimeError inside that
thread, where nothing catches it (threading.excepthook writes to stderr only,
sys.excepthook never sees thread exceptions, and the packaged windowed build has no
console). These two tests pin both halves: nothing is raised when the window is gone,
and a live window still gets its answer.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

import shiboken6                                # noqa: E402
from PySide6.QtCore import QObject              # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _probe_owner():
    """A stand-in window: probe_updates_worker only ever touches `_update_probe`."""
    from ui import update_controller as uc
    owner = QObject()
    owner._update_probe = uc._UpdateProbe(owner)
    return uc, owner


def test_a_late_answer_is_dropped_when_the_window_is_gone(app, monkeypatch):
    uc, owner = _probe_owner()
    monkeypatch.setattr(uc.update_check, "fetch_latest_tag", lambda **kw: "v9.9.9")
    shiboken6.delete(owner)                     # the window closes mid-probe
    assert not shiboken6.isValid(owner)

    uc.probe_updates_worker(owner)              # startup probe -> found
    uc.probe_updates_worker(owner, manual=True)  # manual probe -> checked


def test_a_live_window_still_gets_the_answer(app, monkeypatch):
    uc, owner = _probe_owner()
    monkeypatch.setattr(uc.update_check, "fetch_latest_tag", lambda **kw: "v9.9.9")
    seen = []
    owner._update_probe.found.connect(seen.append)

    uc.probe_updates_worker(owner)
    app.processEvents()

    assert seen == ["v9.9.9"]
