"""Actions controller: undo, repeat, echo/scroll, file load, auto-reply, find bar, shortcuts, accessible names and tab order."""
from __future__ import annotations


import json
import os
import shutil
import sys
import time
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
    QAction,
    QKeySequence,
    QActionGroup,
    QColor,
    QIntValidator,
    QShortcut,
    QTextFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QFont,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QStackedWidget,
    QWidgetAction,
    QVBoxLayout,
    QWidget,
)
from app.framing import DEFAULT_SETTLE_MS, FrameAssembler
from app.protocol import (
    TEXT_ENCODINGS,
    append_checksum,
    ascii_str_to_bytes,
    bytes_to_ascii_str,
    bytes_to_hex_str,
    decode_text,
    encode_text,
    hex_str_to_bytes,
    HexFormatError,
)
from app import (
    __version__,
    update as update_check,
    i18n,
)
from app.config import (
    CONFIG_PATH,
    data_dir,
    load_config,
    log_dir,
    save_config,
)
from app.log_sink import LogSink
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.autosave_dialog import AutoSaveDialog
from ui.history_dialog import HistoryDialog
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from ui.menus import build_menu
from ui.log_controller import apply_autosave_settings, log_append, log_close, log_header_text, log_open, on_log_line, on_save_log_as, on_save_log_quick, show_autosave_settings
from ui.receive_controller import append_header_split, append_rx_group, emit_rx_text, flush_rx_frames, on_clear, on_received, recolor_rx_view, snapshot_rx_fragments
from ui.send_controller import abort_file_send, apply_checksum, clear_history, finish_file_send, flush_history_save, on_history_fill, on_quick_send, on_send, on_send_file, prune_history_meta, recall_history, remember_send, remove_history_entry, schedule_history_save, send_file_chunk, show_history, update_history_button, update_payload_size
from ui.connection_controller import ensure_port, notify, on_opened_changed, on_reconnect_toggled, on_worker_error, poll_signals, recolor_status_light, refresh_ports, signals_html, toggle_open, update_port_tooltip
from ui.params_controller import baud_value, check_baud, check_hex_input, encoding, format_rx, newline_bytes, on_header_changed, on_split_mode_changed, on_tx_fmt_changed, persist_newline, refresh_tx_settings_chip, serial_params, split_threshold_ms, ts_prefix, update_input_placeholder
from ui.layout_controller import control_rows, fit_minimum_width, fit_pane_minimums, fit_settings_btn, fit_tx_edit_height, give_data_area_the_room, lock_control_widths, row_need, saved_sizes, widest_row
from ui.config_controller import apply_config, apply_defaults, on_export_config, on_import_config, persist_theme, reset_settings, set_language, set_theme_dark, set_theme_light, set_theme_system
from ui.update_controller import init_update_check, on_update_found, probe_updates, probe_updates_worker, show_update
from ui.dialogs_controller import diagnostics_text, edit_rules, first_run_hint, show_about, show_port_settings, show_shortcuts
from ui.regions import (BAUDRATES, DATA_FIRST_H, DATA_FIRST_V,
                        RECEIVE_MAX_LINES, SPLIT_AUTO, SPLIT_HEADER,
                        SPLIT_MANUAL, _fixed_row, build_connection_row,
                        build_data_panes, build_send_group, build_status_bar)
from app.i18n import hex_error_message, tr
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.main_window import MainWindow
def undo_delete(win: MainWindow) -> None:
    "undo delete"
    """Undo the last destructive action: a deleted row or a cleared pane (U58/U42)."""
    kind, payload = win._undo_kind, win._undo_payload
    win._undo_kind = ""
    win._undo_payload = None
    win._undo_timer.stop()
    win._undo_btn.hide()
    if kind == "clear" and win._cleared_fragments:
        state = win._cleared_state or (False, 0, 0, 0)
        fragments, win._cleared_fragments = win._cleared_fragments, None
        win._line_is_tx, win.rx_bytes, win.tx_bytes, win._sent_count = state
        for text, frag_kind in fragments:
            win._emit_rx_text(text, tx=(frag_kind == 1),
                               meta=(frag_kind == 2), log=False)
        win.update_counts()
        win._cleared_state = None
        win._notify(tr("rx.undo.done"), "info", ms=3000)
        return
    if payload:
        win.quick_panel.restore_rows(payload if isinstance(payload, list) else [payload])
        win._notify(tr("qs.undo.done"), "info", ms=3000)

def clear_undo(win: MainWindow) -> None:
    "clear undo"
    win._undo_payload = None
    win._undo_kind = ""
    win._cleared_fragments = None
    win._cleared_state = None
    win._undo_btn.hide()

def on_row_deleted(win: MainWindow, payloads: list[str]) -> None:
    "on row deleted"
    """Offer a short undo window for the deleted quick-send rows (U58/U118)."""
    if isinstance(payloads, dict):
        payloads = [payloads]
    win._undo_payload = [dict(p) for p in payloads]
    win._undo_kind = "row"
    win._undo_btn.setText(tr("undo.label"))
    win._undo_btn.show()
    win._undo_timer.start(3000)
    win._notify(tr("qs.deleted"), "warn", ms=3000)

def on_repeat_toggled(win: MainWindow, checked: bool):
    "on repeat toggled"
    if checked and not win._ensure_port():
        win.repeat_btn.blockSignals(True)     # U61: no repeat loop without a port
        win.repeat_btn.setChecked(False)
        win.repeat_btn.blockSignals(False)
        win.repeat_btn.setText(tr("tx.repeat"))
        return
    win.repeat_btn.setText(tr("tx.repeat.stop") if checked else tr("tx.repeat"))
    if checked:
        win._sent_count = 0
        win.update_counts()
        win._repeat_timer.start(win._repeat_value())
    else:
        win._repeat_timer.stop()

def repeat_value(win: MainWindow) -> int:
    "repeat value"
    """Parse the repeat interval (10-60000 ms), clamped, defaulting to 1000."""
    try:
        value = int((win.repeat_ms.text() or "").strip())
    except ValueError:
        return 1000
    return max(10, min(60000, value))

def on_repeat_interval(win: MainWindow, _text: str):
    "on repeat interval"
    if win._repeat_timer.isActive():
        win._repeat_timer.setInterval(win._repeat_value())

def stop_repeat(win: MainWindow):
    "stop repeat"
    if win.repeat_btn.isChecked():
        win.repeat_btn.setChecked(False)     # triggers _on_repeat_toggled -> stop
    else:
        win._repeat_timer.stop()

def echo_tx(win: MainWindow, data: bytes) -> None:
    "echo tx"
    """Mirror sent bytes into the receive pane as a '->' line (U26)."""
    if not win.echo_tx_check.isChecked() or win._file_timer.isActive():
        return
    if win.rx_view.document().characterCount() > 1:
        win._emit_rx_text("\n", tx=True)
    win._emit_rx_text(win._ts_prefix(time.monotonic()) + MARK_TX, tx=True, meta=True)
    win._emit_rx_text(win._format_rx(data), tx=True)
    win._line_is_tx = True
    win._scroll_rx_bottom()          # U43

def scroll_rx_bottom(win: MainWindow) -> None:
    "scroll rx bottom"
    """Follow the newest line unless the user paused auto-scroll (U43)."""
    if win.autoscroll_check.isChecked():
        bar = win.rx_view.verticalScrollBar()
        bar.setValue(bar.maximum())

def pause_autoscroll(win: MainWindow, _action: int = 0) -> None:
    "pause autoscroll"
    """Manual scrolling means the user is reading: stop following (U43)."""
    if win.autoscroll_check.isChecked():
        win.autoscroll_check.setChecked(False)

def rx_separator(win: MainWindow) -> str:
    "rx separator"
    """Separator used when a HEX group continues an existing line (U59)."""
    return "" if win.rx_fmt_combo.currentIndex() == RX_ASCII else " "

def on_autoscroll_toggled(win: MainWindow, checked: bool) -> None:
    "on autoscroll toggled"
    """Remember the auto-scroll preference (U75)."""
    config = load_config()
    config["autoscroll"] = bool(checked)
    save_config(config)

def on_timestamp_toggled(win: MainWindow, checked: bool) -> None:
    "on timestamp toggled"
    """Remember the timestamp preference (U96)."""
    config = load_config()
    config["timestamp_on"] = bool(checked)
    save_config(config)

def load_file(win: MainWindow, path: str) -> bytes:
    "load file"
    """Read a file to send: .hex parsed as hex text, .txt encoded, anything else raw."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".hex":
        out = bytearray()
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.split("#", 1)[0]
                cleaned = "".join(line.split())
                if not cleaned:
                    continue
                out += hex_str_to_bytes(cleaned)
        return bytes(out)
    if ext in (".txt", ".csv", ".log"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            return encode_text(fh.read(), win._encoding(), False)
    with open(path, "rb") as fh:
        return fh.read()

def on_auto_reply_toggled(win: MainWindow, checked: bool) -> None:
    "on auto reply toggled"
    config = load_config()
    config["auto_reply_enabled"] = bool(checked)
    save_config(config)
    win._reply_buf = b""

def check_auto_reply(win: MainWindow, data: bytes) -> None:
    "check auto reply"
    """Send the configured reply when a match string shows up in the stream."""
    if not win.auto_reply_act.isChecked() or not win._auto_rules:
        return
    win._reply_buf = (win._reply_buf + data)[-512:]
    for rule in win._auto_rules:
        if not rule.get("enabled", True):
            continue
        is_hex = bool(rule.get("hex", False))
        try:
            match = (hex_str_to_bytes(rule.get("match", "")) if is_hex
                     else ascii_str_to_bytes(rule.get("match", "")))
            reply = (hex_str_to_bytes(rule.get("reply", "")) if is_hex
                     else ascii_str_to_bytes(rule.get("reply", "")))
        except ValueError:
            continue
        if match and match in win._reply_buf:
            if reply and win.worker.is_open():
                win.worker.send(reply)
                win.tx_bytes += len(reply)
                win.update_counts()
                win._notify(tr("rb.sent", n=len(reply)), ms=3000)
            win._reply_buf = b""
            break

def on_pause_toggled(win: MainWindow, checked: bool) -> None:
    "on pause toggled"
    """Freeze the receive view; data keeps flowing to the log (U160)."""
    win._rx_paused = bool(checked)
    if bool(checked):
        win._rx_pause_buf = []
        win._notify(tr("rx.pause"), "info", ms=4000)
    else:
        win._resume_rx_display()


def open_rx_context_menu(win: MainWindow, pos) -> None:
    "open rx context menu"
    """Receive-pane right-click: copy selection / copy all (U160)."""
    menu = QMenu(win.rx_view)
    copy_sel = menu.addAction(tr("menu.copy_sel"))
    copy_sel.setEnabled(win.rx_view.textCursor().hasSelection())
    copy_sel.triggered.connect(lambda: win.rx_view.copy())
    copy_all = menu.addAction(tr("menu.copy_all"))
    copy_all.triggered.connect(lambda: _copy_all_rx(win))
    menu.exec(win.rx_view.mapToGlobal(pos))


def _copy_all_rx(win: MainWindow) -> None:
    """Copy the whole receive pane to the clipboard (U160)."""
    QApplication.clipboard().setText(win.rx_view.toPlainText())
    win._notify(tr("rx.copied_all"), "info", ms=2500)


def update_counts(win: MainWindow):
    "update counts"
    """U124: the single status-bar counter (sends, TX bytes, RX bytes)."""
    win.sent_lbl.setText(tr("tx.counter", n=win._sent_count,
                             tx=win.tx_bytes, rx=win.rx_bytes))

def update_params_summary(win: MainWindow) -> None:
    "update params summary"
    """One-line summary of the low-frequency settings (U35-P3)."""
    parity = ["N", "O", "E", "M", "S"][max(0, min(4, win.parity_combo.currentIndex()))]
    data = win.dbits_combo.currentText()
    stop = win.stopbits_combo.currentText()
    flow = win.flow_combo.currentText()
    enc = win.encoding_combo.currentText()
    text = f"{data}{parity}{stop} · {flow} · {enc}"
    if len(text) > 16:                      # U78: elide instead of widening the row
        text = text[:15] + "…"
    win.params_summary.setText(text + " ▾")

FIND_HIGHLIGHT_CAP = 10000  # U160: cap on how many matches get a background colour


def _collect_find_matches(win: MainWindow, text: str) -> list:
    """All matches of `text` in the receive pane, as (start, end) positions (U160)."""
    doc = win.rx_view.document()
    out: list = []
    if not text:
        return out
    needle = QTextCursor(doc)
    while True:
        needle = doc.find(text, needle)
        if needle.isNull():
            break
        out.append((needle.selectionStart(), needle.selectionEnd()))
    return out


def _apply_find_highlights(win: MainWindow, matches: list, current: int) -> None:
    """Highlight every match, the current one stronger (U160)."""
    colours = theme.find_colors()
    selections = []
    for i, (start, end) in enumerate(matches[:FIND_HIGHLIGHT_CAP]):
        extra = QTextEdit.ExtraSelection()
        cursor = QTextCursor(win.rx_view.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        if i == current:
            fmt.setBackground(QColor(colours["current_bg"]))
            fmt.setForeground(QColor(colours["current_fg"]))
        else:
            fmt.setBackground(QColor(colours["other_bg"]))
            fmt.setForeground(QColor(colours["other_fg"]))
        extra.cursor = cursor
        extra.format = fmt
        selections.append(extra)
    win.rx_view.setExtraSelections(selections)


def on_find_text_changed(win: MainWindow) -> None:
    "on find text changed"
    """Re-run the match search when the query changes (U160)."""
    text = win.find_edit.text()
    win._find_matches = _collect_find_matches(win, text)
    win._find_index = 0
    win._find_query = text
    if text and win._find_matches:
        start, end = win._find_matches[0]
        cursor = QTextCursor(win.rx_view.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        win.rx_view.setTextCursor(cursor)
        win.rx_view.centerCursor()
    _apply_find_highlights(win, win._find_matches, 0)
    update_find_count(win)


def update_find_count(win: MainWindow) -> None:
    "update find count"
    """Refresh the n/N label after an index move (U160)."""
    total = len(win._find_matches)
    if total == 0:
        win.find_count_lbl.setText("0/0" if win.find_edit.text() else "")
        return
    shown = min(total, FIND_HIGHLIGHT_CAP)
    suffix = "" if total <= FIND_HIGHLIGHT_CAP else "+"
    win.find_count_lbl.setText(f"{win._find_index + 1}/{shown}{suffix}")


def toggle_find_bar(win: MainWindow, show: bool | None = None) -> None:
    "toggle find bar"
    """Show/hide the receive find bar (U41); closing clears the highlights (U160)."""
    visible = (not win._find_bar.isVisible()) if show is None else show
    win._find_bar.setVisible(visible)
    if visible:
        win.find_edit.setFocus()
        win.find_edit.selectAll()
    else:
        win.rx_view.setExtraSelections([])
        win.find_count_lbl.setText("")


def find_next(win: MainWindow, forward: bool = True) -> None:
    "find next"
    """Jump to the next/previous match in the receive pane (U41/U160)."""
    text = win.find_edit.text()
    matches = getattr(win, "_find_matches", None)
    if matches is None or text != getattr(win, "_find_query", None):
        matches = _collect_find_matches(win, text)
        win._find_matches = matches
        win._find_query = text
        win._find_index = 0
    total = len(matches)
    if not text or total == 0:
        if text:
            win._notify(tr("find.none", text=text), "warn", ms=3000)
        update_find_count(win)
        _apply_find_highlights(win, matches, 0)
        return
    win._find_index = (win._find_index + (1 if forward else -1)) % total
    start, end = matches[win._find_index]
    cursor = QTextCursor(win.rx_view.document())
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    win.rx_view.setTextCursor(cursor)
    win.rx_view.centerCursor()
    _apply_find_highlights(win, matches, win._find_index)
    update_find_count(win)
    win.rx_view.setFocus()

def esc_action(win: MainWindow) -> None:
    "esc action"
    """Esc: leave the find bar, else stop repeat/sequence (U39)."""
    if win._find_bar.isVisible():
        win._toggle_find_bar(False)
        return
    win._stop_repeat()
    win.quick_panel.stop_sequence()

def setup_shortcuts(win: MainWindow) -> None:
    "setup shortcuts"
    """Daily-flow keyboard shortcuts (U39)."""
    for seq, handler in (
        ("Ctrl+Return", win.on_send),
        ("Ctrl+L", win.on_clear),
        ("Ctrl+S", win.on_save_log_quick),
        ("Ctrl+K", lambda: win.tx_edit.setFocus()),
        ("F5", win.toggle_open),
        ("Ctrl+B", win._toggle_quick_panel),          # U88: fold/unfold the panel
        ("Ctrl+,", win._settings_btn.showMenu),        # U110: the platform convention
        ("Ctrl+Up", lambda: win._recall_history(1)),    # U87: older command
        ("Ctrl+Down", lambda: win._recall_history(-1)),  # U87: newer command
        ("Ctrl+F", lambda: win._toggle_find_bar(True)),
        ("Esc", win._esc_action),
    ):
        QShortcut(QKeySequence(seq), win).activated.connect(handler)

def apply_accessible_names(win: MainWindow) -> None:
    "apply accessible names"
    """U122: screen readers need a name per control; the tooltip is the best source."""
    names = ("port_combo", "refresh_btn", "baud_combo", "open_btn", "rx_fmt_combo",
             "params_summary", "_settings_btn", "_panel_btn", "split_combo",
             "split_ms_edit", "header_edit", "ts_check", "echo_tx_check",
             "autoscroll_check", "save_log_btn", "save_log_as_btn", "clear_btn",
             "rx_view", "tx_edit", "nl_combo", "escape_check", "send_btn",
             "history_btn", "repeat_btn", "repeat_ms", "send_file_btn",
             "tx_settings_btn")
    for name in names:
        widget = getattr(win, name, None)
        if widget is None or widget.accessibleName():
            continue
        label = widget.toolTip() or (widget.text() if hasattr(widget, "text") else "")
        if not label:
            from app.i18n import STRINGS
            key = {"port_combo": "port.label", "rx_fmt_combo": "rxfmt.label",
                   "split_combo": "split.label"}.get(name)
            if key and key in STRINGS:
                label = tr(key)
        if label:
            widget.setAccessibleName(label.replace("&", ""))

def setup_tab_order(win: MainWindow) -> None:
    "setup tab order"
    """Explicit Tab order along the five zones (U54, per the U53 grouping spec)."""
    names = ["port_combo", "refresh_btn", "baud_combo", "open_btn",
             "split_combo", "split_ms_edit", "header_edit", "ts_check",
             "echo_tx_check", "autoscroll_check",
             "save_log_btn", "save_log_as_btn", "clear_btn", "rx_view",
             "nl_combo", "escape_check",   # U121: the two pickers live in a popup
             "tx_edit", "send_btn", "history_btn", "repeat_btn", "repeat_ms",
             "send_file_btn"]
    widgets = [w for w in (getattr(win, n, None) for n in names) if w is not None]
    for first, second in zip(widgets, widgets[1:]):
        # U129: a widget inside a popup menu has its own window; Qt refuses the pair
        if first.window() is second.window():
            QWidget.setTabOrder(first, second)
