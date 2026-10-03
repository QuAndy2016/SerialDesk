"""Connection controller: port list and tooltip, open/close, worker errors, signal read-out and the status light."""
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
from ui.port_delegate import PORT_FULL_ROLE
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from ui.menus import build_menu
from ui.log_controller import apply_autosave_settings, log_append, log_close, log_header_text, log_open, on_log_line, on_save_log_as, on_save_log_quick, show_autosave_settings
from ui.receive_controller import append_header_split, append_rx_group, emit_rx_text, flush_rx_frames, on_clear, on_received, recolor_rx_view, snapshot_rx_fragments
from ui.send_controller import abort_file_send, apply_checksum, clear_history, finish_file_send, flush_history_save, on_history_fill, on_quick_send, on_send, on_send_file, prune_history_meta, recall_history, remember_send, remove_history_entry, schedule_history_save, send_file_chunk, show_history, update_history_button, update_payload_size
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
def on_reconnect_toggled(win: MainWindow, checked: bool) -> None:
    "on reconnect toggled"
    """Persist and apply the auto-reconnect preference (T14)."""
    win.worker.set_auto_reconnect(checked)
    config = load_config()
    config["auto_reconnect"] = bool(checked)
    save_config(config)
    win._notify(tr("conn.auto.on") if checked else tr("conn.auto.off"), "info", ms=3000)

def update_port_tooltip(win: MainWindow) -> None:
    "update port tooltip"
    """Full device description of the selected port, in the tooltip (U83)."""
    idx = win.port_combo.currentIndex()
    full = win.port_combo.itemData(idx, Qt.ItemDataRole.ToolTipRole) if idx >= 0 else None
    if full:
        win.port_combo.setToolTip(str(full))

def notify(win: MainWindow, msg: str, level: str = 'info', ms: int | None = None) -> None:
    "notify"
    """Single exit for status-bar messages.

    level: info (auto 5 s) / warn (auto 10 s) / error (persistent until the
    next action). Colour follows the active theme via theme.level_color().
    """
    sb = win.statusBar()
    sb.setStyleSheet(f"QStatusBar {{ color: {theme.level_color(level)}; }}")
    if ms is None:
        ms = -1 if level == "error" else (10000 if level == "warn" else 5000)
    if ms < 0:
        sb.showMessage(msg)
    else:
        sb.showMessage(msg, ms)

def recolor_status_light(win: MainWindow) -> None:
    "recolor status light"
    """Re-apply the connection indicator colour (theme-aware, U38)."""
    cols = theme.status_colors()
    key = "ok" if win.worker.is_open() else ("idle" if win.port_combo.count() == 0 else "err")
    win.status_light.setStyleSheet(
        f"color: {cols[key]}; font-weight: bold; padding-right: 8px;")

def ensure_port(win: MainWindow) -> bool:
    "ensure port"
    """Guard send actions: nothing is sent, echoed or counted while closed (U61)."""
    if win.worker.is_open():
        return True
    win._notify(tr("err.tx.closed"), "error")
    return False

def on_worker_error(win: MainWindow, text: str) -> None:
    "on worker error"
    """Turn a serial open/IO failure into an actionable message (U37)."""
    low = text.lower()
    if "access is denied" in low or "permission" in low or "denied" in low:
        key = "err.open.denied"
    elif "busy" in low or "in use" in low:
        key = "err.open.busy"
    elif "could not open port" in low or "not found" in low or "no such" in low:
        key = "err.open.missing"
    else:
        key = "err.open.other"
    win._notify(tr(key, e=text), "error")
    if not win.worker.is_open():        # L1-2: an async open failure is a state, not just a toast
        win._opening = False
        _show_status(win, "conn.error", "idle")

def poll_signals(win: MainWindow) -> None:
    "poll signals"
    """Refresh the CTS/DSR/DCD/RI indicators (50 ms timer)."""
    sig = win.worker.signals()
    win.sig_lbl.setText(win._signals_html(sig if sig.get("open") else {}))

def signals_html(win: MainWindow, sig: dict) -> str:
    "signals html"
    """Coloured 高/低 text for CTS/DSR/DCD/RI (U32: never colour alone)."""
    cols = theme.status_colors()
    tips = {"cts": "sig.cts.tip", "dsr": "sig.dsr.tip",
            "dcd": "sig.dcd.tip", "ri": "sig.ri.tip"}
    parts = []
    for name, tip_key in tips.items():
        on = bool(sig.get(name, False))
        col = cols["ok"] if on else cols["idle"]
        word = tr("sig.high") if on else tr("sig.low")
        parts.append(
            f'<span style="color:{col}" title="{tr(tip_key)}">'
            f"{name.upper()} {word}</span>")
    return "&nbsp;&nbsp;".join(parts)

def _fit_port_popup(win: MainWindow) -> None:
    """U172: the closed box shows "COM5"; widen the popup so the full name fits."""
    combo = win.port_combo
    fm = combo.fontMetrics()
    widest = 0
    for i in range(combo.count()):
        full = combo.itemData(i, PORT_FULL_ROLE) or combo.itemText(i)
        widest = max(widest, fm.horizontalAdvance(str(full)))
    combo.view().setMinimumWidth(max(widest + 40, combo.width()))


def refresh_ports(win: MainWindow):
    "refresh ports"
    current = win.port_combo.currentText() or str(load_config().get("last_port") or "")   # N12
    win.port_combo.blockSignals(True)
    win.port_combo.clear()
    for dev, desc in list_serial_ports():
        # U83/U172: the closed box keeps the short name (never truncated); the full
        # description goes to the tooltip and to the widened dropdown popup.
        win.port_combo.addItem(dev, dev)
        if desc:
            full = f"{dev} — {desc}"
            last = win.port_combo.count() - 1
            win.port_combo.setItemData(last, full, Qt.ItemDataRole.ToolTipRole)
            win.port_combo.setItemData(last, full, PORT_FULL_ROLE)
    _fit_port_popup(win)
    if current:
        idx = win.port_combo.findData(current)
        if idx < 0:
            idx = win.port_combo.findText(str(current))
        if idx >= 0:
            win.port_combo.setCurrentIndex(idx)
    win.port_combo.blockSignals(False)
    win._update_port_tooltip()

def toggle_open(win: MainWindow):
    "toggle open"
    if win.worker.is_open():
        win.worker.close_port()
        win.open_btn.setText(tr("port.open"))
    else:
        if win.port_combo.count() == 0:
            win._notify(tr("status.no_port"), "warn")
            return
        device = win.port_combo.currentData()
        try:
            baud = int(win.baud_combo.currentText().strip())
        except ValueError:
            win._notify(tr("status.bad_baud"), "error")
            return
        win._opening = True                     # L1-2: a slow open must not look idle
        _show_status(win, "conn.connecting", "idle")
        ok = win.worker.open_port(device, baud, **win._serial_params())
        if not ok:
            win._opening = False
            _show_status(win, "conn.error", "idle")
        if ok:
            win.refresh_timer.stop()  # keep port list stable while open
            save_config({"last_port": device})   # N12: reuse it next launch


def _show_status(win: MainWindow, key: str, color: str) -> None:
    "show status"
    """L1-2 / standard clause 9: one place that paints the connection state light."""
    colors = theme.status_colors()
    win.status_light.setText(tr(key))
    win.status_light.setStyleSheet(
        "color: %s; font-weight: bold; padding-right: 8px;"
        % colors.get(color, colors.get("idle", "#888888")))

def on_opened_changed(win: MainWindow, opened: bool):
    "on opened changed"
    if opened:
        win._opening = False
        win.open_btn.setText(tr("port.close"))
        port = win.port_combo.currentData() or ""
        baud = win.baud_combo.currentText().strip()
        win.status_light.setText(tr("status.connected", port=port, baud=baud))
        win.status_light.setStyleSheet(
            f"color: {theme.status_colors()['ok']}; font-weight: bold; padding-right: 8px;")
        win._notify(tr("status.opened"))
        for combo in win._param_combos:
            combo.setEnabled(False)
        win._port_dlg.set_port_open(True)     # U73: explain the lock
    else:
        win.open_btn.setText(tr("port.open"))
        win.status_light.setText(tr("status.disconnected"))
        win.status_light.setStyleSheet(
            f"color: {theme.status_colors()['err']}; font-weight: bold; padding-right: 8px;")
        win._stop_repeat()
        win._abort_file_send()
        win.quick_panel.stop_sequence()
        win._flush_rx_frames()   # flush the tail frame on close (U57)
        win.refresh_timer.start()
        for combo in win._param_combos:
            combo.setEnabled(True)
        win._port_dlg.set_port_open(False)    # U73
        if not win.worker.is_open():
            win._notify(tr("status.closed"))
