"""A4: offscreen smoke tests for the three modeless dialogs.

They exist so a refactor cannot silently break construction, the rule/history
round-trips, or the port-settings enable/disable path.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                   # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication       # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_auto_reply_dialog_rules_round_trip(app):
    from ui.auto_reply_dialog import AutoReplyDialog
    dlg = AutoReplyDialog([{"match": "PING", "reply": "PONG", "hex": False}])
    rules = dlg.rules()
    assert any(r.get("match") == "PING" for r in rules)
    before = len(rules)
    dlg.add_row("X", "Y", False)
    assert len(dlg.rules()) == before + 1
    dlg.deleteLater()


def test_history_dialog_populates_and_emits_fill(app):
    from ui.history_dialog import HistoryDialog
    dlg = HistoryDialog()
    seen = {}
    dlg.fill_requested.connect(lambda t: seen.__setitem__("text", t))
    dlg.set_history(["AT+VERSION?"], {"AT+VERSION?": {"hex": False, "sent": 1}})
    dlg._fill_current()
    assert seen.get("text") == "AT+VERSION?"
    dlg.deleteLater()


def test_port_settings_dialog_open_state_and_retranslate(app):
    from ui.port_settings_dialog import PortSettingsDialog
    dlg = PortSettingsDialog()
    dlg.set_port_open(True)
    dlg.set_port_open(False)
    dlg.retranslate()
    assert dlg.windowTitle() != ""
    dlg.deleteLater()
