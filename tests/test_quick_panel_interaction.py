"""Quick-send panel: the interaction contract after the 2026-10-04 rebuild.

Two flags, two owners - and the tests keep them apart:

* ``ticked`` is sequence membership (only the tick box writes it);
* ``armed``  is the delete target (only the selection gestures write it).

The rules come from ``local_docs/02_standards/22_desktop_ui_interaction_standard_*.md``
(UI-01..UI-14); each finding of the review that produced this file is named in the test
docstring. The config is redirected to ``tmp_path`` for every test: run from source the
app resolves its data dir to the repository folder, so an unisolated test would edit the
developer's own config.json (ledger E-015).
"""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SERIALDESK_SKIP_CONFIRM", "1")

import pytest                                        # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt   # noqa: E402
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest                                     # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel              # noqa: E402

import app.config as appconfig                       # noqa: E402
import ui.quick_send_panel as qsp                    # noqa: E402
import ui.theme as theme                             # noqa: E402
from app import i18n                                 # noqa: E402
from ui.tokens import DARK_TOKENS                    # noqa: E402

ROWS = [{"text": "AT0", "hex": False, "delay": 0},
        {"text": "AT1", "hex": False, "delay": 0},
        {"text": "AT2", "hex": False, "delay": 0}]

# Panels built by this module are disposed after each test: the module used to leave 17
# live panels behind, and every later test paid for their event filters (suite 61 s -> 115 s).
_CREATED: list = []


@pytest.fixture()
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def dispose_panels(app):
    """Close and really delete every panel a test created."""
    del _CREATED[:]
    yield
    for panel in _CREATED:
        panel.close()
        panel.deleteLater()
    _CREATED.clear()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture()
def config_path(tmp_path, monkeypatch):
    """Point the whole config layer at a throw-away file."""
    path = tmp_path / "config.json"
    monkeypatch.setattr(appconfig, "CONFIG_PATH", str(path))
    i18n.set_language("zh")
    return path


def make_panel(app, path, rows=ROWS):
    """A shown, laid-out panel whose rows come from ``rows``."""
    if rows is not None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"quick_send": rows}, handle, ensure_ascii=False)
    panel = qsp.QuickSendPanel()
    panel.resize(420, 560)
    panel.show()
    for _ in range(4):
        app.processEvents()
    _CREATED.append(panel)
    return panel


def press(panel, widget, mods=Qt.KeyboardModifier.NoModifier):
    """Deliver the left-button press the panel's event filter sees (widget centre)."""
    local = QPointF(widget.width() / 2.0, widget.height() / 2.0)
    glob = QPointF(widget.mapToGlobal(local.toPoint()))
    event = QMouseEvent(QEvent.Type.MouseButtonPress, local, glob,
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mods)
    return panel.eventFilter(widget, event)


def key_event(key, mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, key, mods)


def armed(panel):
    return [index for index, row in enumerate(panel._rows) if row.armed()]


def action_labels(menu):
    """Menu labels without the mnemonic marker or the shortcut Qt appends."""
    return [action.text().split("\t")[0].replace("&", "").lower()
            for action in menu.actions() if not action.isSeparator()]


# -- selection: click / Ctrl / Shift / keyboard ---------------------------------------

def test_shift_click_as_the_first_interaction_still_selects(app, config_path):
    """The anchor exists from construction, so Shift+click never raises (review R2)."""
    panel = make_panel(app, config_path)
    press(panel, panel._rows[1].text_edit, Qt.KeyboardModifier.ShiftModifier)
    assert armed(panel) == [1]                 # no anchor yet -> plain selection
    press(panel, panel._rows[0].text_edit, Qt.KeyboardModifier.ShiftModifier)
    assert armed(panel) == [0, 1]              # now it extends from the anchor


def test_ctrl_click_toggles_one_row(app, config_path):
    """UI-04: Ctrl+click toggles the clicked row and leaves the others alone."""
    panel = make_panel(app, config_path)
    press(panel, panel._rows[0].text_edit)
    press(panel, panel._rows[2].text_edit, Qt.KeyboardModifier.ControlModifier)
    assert armed(panel) == [0, 2]
    press(panel, panel._rows[2].text_edit, Qt.KeyboardModifier.ControlModifier)
    assert armed(panel) == [0]


def test_ctrl_a_arms_everything_and_sets_the_anchor(app, config_path):
    """R10: Ctrl+A used to leave the anchor stale for the next Shift+click."""
    panel = make_panel(app, config_path)
    panel.setFocus()
    app.processEvents()
    assert panel.eventFilter(panel, key_event(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier))
    assert armed(panel) == [0, 1, 2]
    assert panel._anchor is panel._rows[-1]
    press(panel, panel._rows[0].text_edit, Qt.KeyboardModifier.ShiftModifier)
    assert armed(panel) == [0, 1, 2]


def test_arrow_keys_move_the_row_selection_and_the_focus(app, config_path):
    """UI-09: the arrow keys reach rows, which is how a keyboard user gets to Delete."""
    panel = make_panel(app, config_path)
    row = panel._rows[0]
    press(panel, row)
    row.setFocus()
    app.processEvents()
    assert panel.eventFilter(row, key_event(Qt.Key.Key_Down)) is True
    assert armed(panel) == [1]
    assert QApplication.focusWidget() is panel._rows[1]
    assert panel.eventFilter(panel._rows[1], key_event(Qt.Key.Key_Up)) is True
    assert armed(panel) == [0]


def test_escape_and_an_empty_area_click_clear_the_selection(app, config_path):
    """The armed state is owned by the panel; Esc and its own blank area drop it."""
    panel = make_panel(app, config_path)
    press(panel, panel._rows[0].text_edit)
    assert armed(panel) == [0]
    panel.setFocus()
    app.processEvents()
    assert panel.eventFilter(panel, key_event(Qt.Key.Key_Escape)) is True
    assert armed(panel) == []
    press(panel, panel._rows[1].text_edit)
    press(panel, panel._content)               # the panel's own empty area
    assert armed(panel) == []


# -- context menu ----------------------------------------------------------------------

def test_right_click_keeps_the_standard_edit_menu(app, config_path):
    """R1: Cut/Copy/Paste must survive; the row command is appended to them."""
    panel = make_panel(app, config_path)
    menu = panel.row_context_menu(panel._rows[0].text_edit)
    labels = action_labels(menu)
    assert "copy" in labels and "paste" in labels, labels
    assert i18n.tr("qs.note.menu").lower() in labels, labels
    assert labels.index("copy") < labels.index(i18n.tr("qs.note.menu").lower())
    menu.deleteLater()


def test_a_plain_right_click_on_the_row_offers_the_note(app, config_path):
    """The row frame has no standard menu, so it gets the row command alone."""
    panel = make_panel(app, config_path)
    menu = panel.row_context_menu(panel._rows[0])
    assert action_labels(menu) == [i18n.tr("qs.note.menu").lower()]
    menu.deleteLater()


def test_the_context_menu_event_routes_to_that_menu(app, config_path, monkeypatch):
    """The filter must not swallow the event into a dialog (review R1)."""
    seen = []

    class FakeMenu:
        def exec(self, _pos):
            seen.append("exec")

        def deleteLater(self):
            seen.append("deleteLater")

    panel = make_panel(app, config_path)
    monkeypatch.setattr(panel, "row_context_menu", lambda obj: seen.append("menu") or FakeMenu())
    handled = panel.eventFilter(
        panel._rows[0].text_edit,
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5)))
    assert handled is True and seen == ["menu", "exec", "deleteLater"]


# -- delete ----------------------------------------------------------------------------

def test_clicking_delete_removes_the_armed_row(app, config_path):
    """The reported flow: click a row, press Delete, the row and the counter go."""
    panel = make_panel(app, config_path)
    QTest.mouseClick(panel._rows[0].text_edit, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    app.processEvents()
    assert armed(panel) == [0] and panel.del_btn.isEnabled()
    assert panel.armed_lbl.text() == i18n.tr("qs.armed", n=1)
    QTest.mouseClick(panel.del_btn, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(panel.del_btn.width() // 2, panel.del_btn.height() // 2))
    app.processEvents()
    assert len(panel._rows) == len(ROWS) - 1
    assert panel.count_lbl.text() == "%d/%d" % (len(ROWS) - 1, qsp.MAX_ENTRIES)
    assert panel.armed_lbl.text() == ""


def test_delete_is_immediate_and_reports_the_undo_payload(app, config_path):
    """No modal box: the action is undoable, so it happens and the window offers undo."""
    panel = make_panel(app, config_path)
    panel.arm_row(panel._rows[1], "replace")
    payloads = []
    panel.deleted.connect(payloads.append)
    panel.delete_armed()
    assert payloads == [[{"text": "AT1", "hex": False, "delay": 0, "index": 1,
                          "name": "", "note": ""}]]
    assert [row.text() for row in panel._rows] == ["AT0", "AT2"]


def test_delete_without_a_selection_says_so(app, config_path):
    """A click that cannot delete must report why instead of doing nothing."""
    panel = make_panel(app, config_path)
    seen = []
    panel.log.connect(seen.append)
    panel.delete_armed()
    assert seen == [i18n.tr("qs.del.none")]
    assert len(panel._rows) == len(ROWS)


def test_delete_inside_the_command_box_is_left_to_the_text(app, config_path):
    """The character key belongs to the text box; the arming stays visible instead."""
    panel = make_panel(app, config_path)
    row = panel._rows[1]
    press(panel, row.text_edit)
    row.text_edit.setFocus()
    app.processEvents()
    before = len(panel._rows)
    handled = panel.eventFilter(row.text_edit, key_event(Qt.Key.Key_Delete))
    assert handled is False
    assert len(panel._rows) == before
    assert panel.armed_lbl.text() == i18n.tr("qs.armed", n=1)
    assert panel.del_btn.text() == i18n.tr("qs.del")      # the button never resizes


def test_restore_puts_a_deleted_row_back_in_place(app, config_path):
    """The undo contract: text, format, delay, name and note come back at the old index."""
    panel = make_panel(app, config_path)
    row = panel._rows[1]
    row.name_edit.setText("query")
    row.note = "keep me"
    panel.arm_row(row, "replace")
    payloads = []
    panel.deleted.connect(payloads.append)
    panel.delete_armed()
    panel.restore_rows(payloads[0])
    assert [r.text() for r in panel._rows] == ["AT0", "AT1", "AT2"]
    restored = panel._rows[1]
    assert restored.name() == "query" and restored.note == "keep me"


# -- sequence membership (a tick is NOT a selection) -----------------------------------

def test_ticking_a_row_marks_membership_and_does_not_arm_it(app, config_path):
    """The 2026-10-04 coupling is gone: a tick never touches the delete selection (R7)."""
    panel = make_panel(app, config_path)
    panel.seq_check.setChecked(True)
    press(panel, panel._rows[2].text_edit)          # arm one row by hand
    panel._rows[0].set_ticked(True)
    app.processEvents()
    assert armed(panel) == [2]                      # the tick did not steal it
    assert panel._rows[0].badge.text() == "1"
    assert panel.sequence_rows() == [panel._rows[0]]
    panel.delete_armed()
    assert [row.text() for row in panel._rows] == ["AT0", "AT1"]   # AT2 went, AT0 stayed


def test_the_tick_box_is_clickable_once_sequence_mode_is_on(app, config_path):
    """R14: the boxes are built while the mode is off, so they start disabled."""
    panel = make_panel(app, config_path)
    box = panel._rows[0].tick
    assert not box.isEnabled() and not box.isVisible()
    panel.seq_check.setChecked(True)
    app.processEvents()
    assert box.isVisible() and box.isEnabled()
    QTest.mouseClick(box, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(box.width() // 2, box.height() // 2))
    app.processEvents()
    assert box.isChecked() is True
    assert panel._rows[0].badge.text() == "1"


def test_leaving_sequence_mode_keeps_the_ticked_membership(app, config_path):
    """R5: switching the mode off used to wipe the membership and its order."""
    panel = make_panel(app, config_path)
    panel.seq_check.setChecked(True)
    panel._rows[0].set_ticked(True)
    panel._rows[2].set_ticked(True)
    app.processEvents()
    panel.seq_check.setChecked(False)
    app.processEvents()
    assert not panel._rows[0].tick.isVisible() and not panel._rows[0].tick.isEnabled()
    assert not panel._rows[0].badge.isVisible()
    panel.seq_check.setChecked(True)
    app.processEvents()
    assert [row.ticked() for row in panel._rows] == [True, False, True]
    assert panel._rows[0].badge.text() == "1" and panel._rows[2].badge.text() == "2"
    panel.save()
    saved = json.load(open(config_path, encoding="utf-8"))["quick_send"]
    assert [row["sel"] for row in saved] == [True, False, True]


def test_the_sequence_runs_the_ticked_rows_in_order(app, config_path):
    """Run walks the ticked rows, honours the loop count and reports every step."""
    panel = make_panel(app, config_path)
    sent = []
    panel.send_payload.connect(lambda payload, is_hex: sent.append(payload))
    panel.seq_check.setChecked(True)
    panel._rows[0].set_ticked(True)
    panel._rows[2].set_ticked(True)
    panel.rounds.setValue(2)
    panel.toggle_sequence()
    QTest.qWait(120)                                # every row's delay is 0
    assert sent == [b"AT0", b"AT2", b"AT0", b"AT2"]
    assert panel._running is False
    assert panel.rounds_lbl.text() == i18n.tr("qs.seq.sent", n=2)


def test_the_rounds_wheel_spins_between_infinity_and_one(app, config_path):
    """One control: ∞ is a value of the wheel, not a second switch.

    Windows' spin-control guide: "At the end of a range of valid values, restart the
    range... the user is spinning a wheel of values" and "use text instead of special
    numeric values - allow users to spin to these special values".
    """
    panel = make_panel(app, config_path)
    wheel = panel.rounds
    assert wheel.endless() and wheel.text() == "\u221e"       # default: until stopped
    assert panel._loops_value() == 0
    wheel.stepBy(1)                                           # ∞ -> 1
    assert (wheel.value(), panel._loops_value()) == (1, 1)
    wheel.stepBy(1)
    assert wheel.value() == 2
    wheel.stepBy(-1)
    assert wheel.value() == 1
    wheel.stepBy(-1)                                          # 1 -> ∞
    assert wheel.endless() and wheel.text() == "\u221e"
    wheel.setValue(ROUNDS_MAX := 999)
    wheel.stepBy(1)                                           # 999 -> ∞ (restart the range)
    assert wheel.endless()
    wheel.stepBy(-1)                                          # ∞ -> 999, the wheel's other end
    assert wheel.value() == ROUNDS_MAX
    wheel.setValue(3)
    assert panel._loops_value() == 3
    wheel.lineEdit().setText("7")                             # typing a number still works
    wheel.interpretText()
    assert wheel.value() == 7
    wheel.lineEdit().setText("\u221e")                        # ... and so does typing ∞
    wheel.interpretText()
    assert wheel.endless()


def test_stop_cancels_the_pending_step(app, config_path):
    """R4: the last row's delay used to be a static timer that Stop could not cancel."""
    panel = make_panel(app, config_path, [{"text": "AT0", "hex": False, "delay": 0},
                                          {"text": "AT1", "hex": False, "delay": 60}])
    sent = []
    panel.send_payload.connect(lambda payload, is_hex: sent.append(payload))
    panel.seq_check.setChecked(True)
    panel.toggle_sequence()
    QTest.qWait(10)                                 # both rows went; the last one is waiting
    panel.stop_sequence()
    QTest.qWait(120)                                # let any leftover timer fire
    assert sent == [b"AT0", b"AT1"]
    assert panel._running is False
    assert panel.rounds_lbl.text() == ""            # no phantom round


# -- layout stability (the panel sits in a splitter) -----------------------------------

def test_arming_a_row_never_resizes_the_panel(app, config_path):
    """R15: anything that grows in the control row drags the splitter with it."""
    panel = make_panel(app, config_path)
    panel.seq_check.setChecked(True)
    app.processEvents()
    widths = [panel.minimumSizeHint().width()]
    for row in panel._rows:
        row.set_ticked(True)
        app.processEvents()
        widths.append(panel.minimumSizeHint().width())
    for row in panel._rows:
        row.set_ticked(False)
        app.processEvents()
        widths.append(panel.minimumSizeHint().width())
    panel.arm_row(panel._rows[0], "replace")
    app.processEvents()
    widths.append(panel.minimumSizeHint().width())
    assert len(set(widths)) == 1, widths


def test_both_counters_stay_fully_visible(app, config_path):
    """A stable panel is no good if the counters get squeezed to nothing."""
    panel = make_panel(app, config_path)
    panel.seq_check.setChecked(True)
    panel.arm_row(panel._rows[0], "replace")
    panel._rounds_sent = 12
    panel._refresh_rounds()
    app.processEvents()
    for label in (panel.rounds_lbl, panel.armed_lbl, panel.count_lbl):
        assert label.width() >= label.sizeHint().width(), (label.objectName(), label.width())
    assert panel.armed_lbl.text() == i18n.tr("qs.armed", n=1)


# -- configuration ---------------------------------------------------------------------

def test_a_damaged_config_value_still_builds_the_panel(app, config_path):
    """R6 (Blocker): a broken value must never stop the window from opening."""
    panel = make_panel(app, config_path,
                       [{"text": "a", "hex": True, "delay": "abc"},
                        {"text": "b", "hex": True}])
    assert len(panel._rows) == 2
    assert panel._rows[0].delay_ms() == 500
    assert panel._rows[0].delay.text() == "500"
    assert panel._rows[0].text() == "a"


def test_missing_and_over_range_delays_fall_back_to_documented_values(app, config_path):
    """The same guard covers null, lists and over-range values."""
    panel = make_panel(app, config_path,
                       [{"text": "a", "delay": None},
                        {"text": "b", "delay": 99999},
                        {"text": "c", "delay": [1]},
                        {"text": "d"}])
    assert [row.delay_ms() for row in panel._rows] == [500, 60000, 500, 500]


def test_more_rows_than_the_limit_are_clamped_and_reported(app, config_path):
    """R11: extra rows were dropped without a word."""
    panel = qsp.QuickSendPanel()
    _CREATED.append(panel)
    messages = []
    panel.log.connect(messages.append)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump({"quick_send": [{"text": "r%d" % i, "delay": 0}
                                  for i in range(qsp.MAX_ENTRIES + 6)]}, handle)
    panel.reload_from_config()
    assert len(panel._rows) == qsp.MAX_ENTRIES
    assert messages


def test_save_uses_the_shared_atomic_writer(app, config_path):
    """R9: one writer for the whole file, and it stamps the config version."""
    panel = make_panel(app, config_path)
    panel.add_row("AT", is_hex=False)
    panel.save()
    data = json.load(open(config_path, encoding="utf-8"))
    assert data["config_version"] == appconfig.CONFIG_VERSION
    assert len(data["quick_send"]) == len(panel._rows)
    assert not os.path.exists(str(config_path) + ".tmp")


def test_send_reports_format_errors_instead_of_sending(app, config_path):
    """A bad HEX row raises the panel's error signal and sends nothing."""
    panel = make_panel(app, config_path, [{"text": "ZZ", "hex": True, "delay": 0}])
    sent, errors = [], []
    panel.send_payload.connect(lambda payload, is_hex: sent.append(payload))
    panel.error.connect(errors.append)
    panel._send_one(panel._rows[0])
    assert sent == [] and errors and "Z" in errors[0]


def test_an_empty_row_says_why_it_cannot_send(app, config_path):
    """An empty row logs instead of emitting an empty payload."""
    panel = make_panel(app, config_path, [{"text": "", "hex": False, "delay": 0}])
    sent, logs = [], []
    panel.send_payload.connect(lambda payload, is_hex: sent.append(payload))
    panel.log.connect(logs.append)
    panel._send_one(panel._rows[0])
    assert sent == [] and logs == [i18n.tr("qs.empty")]


# -- the folded rail --------------------------------------------------------------------

def test_the_folded_rail_is_styled_for_its_real_class(app):
    """R8: the QSS targeted QToolButton, but the rail is a plain QWidget."""
    assert "QWidget#qsRail" in theme.DARK_QSS and "QWidget#qsRail" in theme.LIGHT_QSS
    assert "QToolButton#qsRail" not in theme.DARK_QSS
    assert "QToolButton#qsRail" not in theme.LIGHT_QSS
    rail = qsp.RailStrip()
    rail.setStyleSheet(theme.DARK_QSS)      # widget-scoped: an app-wide sheet re-polishes all
    rail.resize(RAIL_W := qsp.RAIL_W, 180)
    border = rail.grab().toImage().pixelColor(0, 90).name()
    assert border == DARK_TOKENS["border_strong"], (border, RAIL_W)
