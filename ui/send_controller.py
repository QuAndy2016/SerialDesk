"""Send path controller: payload size, checksum, sending, file chunks, history recall and the history popup."""
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
from app.increment import DEFAULT_CFG, apply_increment, has_placeholder   # U180
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
CHECKSUM_KEYS = ["none", "crc16-modbus", "crc16-ccitt", "crc32", "sum8"]
FILE_CHUNK_BYTES = 4096     # file send chunk size (T6)
FILE_CHUNK_MS = 20          # interval between chunks
HISTORY_MAX = 50
def _human_bytes(n: int) -> str:
    """Format a byte count for humans (B / KB / MB)."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"
def update_payload_size(win: MainWindow) -> None:
    "update payload size"
    """Show how many bytes the current input would send (U74)."""
    text = win.tx_edit.toPlainText().strip()
    if not text:
        win.tx_size_lbl.setText("")
        return
    try:
        if win.tx_fmt_combo.currentIndex() == 0:
            payload = hex_str_to_bytes(text)
        else:
            payload = encode_text(text, win._encoding(), win.escape_check.isChecked())
    except ValueError:
        win.tx_size_lbl.setText(tr("tx.payload.bad"))
        return
    payload = win._apply_checksum(payload)
    if win.tx_fmt_combo.currentIndex() == 1:
        payload += win._newline_bytes()
    win.tx_size_lbl.setText(tr("tx.payload", n=len(payload)))

def schedule_history_save(win: MainWindow) -> None:
    "schedule history save"
    """Debounce history persistence: one write per 2 s instead of per click (U52)."""
    win._cfg_save_timer.start(2000)

def flush_history_save(win: MainWindow) -> None:
    "flush history save"
    """Write the send history to config.json (called by the debounce timer)."""
    win._cfg_save_timer.stop()
    config = load_config()
    config["send_history"] = win._send_history
    config["history_meta"] = win._prune_history_meta(win._history_meta)
    save_config(config)

def on_send_file(win: MainWindow):
    "on send file"
    """Start (or cancel) sending a file in chunks with progress feedback."""
    if win._file_timer.isActive():
        win._abort_file_send()
        return
    if not win.worker.is_open():
        win._notify(tr("file.no_port"), ms=5000)
        return
    filters = ";;".join([tr("file.filter.all"), tr("file.filter.hex"),
                         tr("file.filter.text"), tr("file.filter.bin")])
    path, _ = QFileDialog.getOpenFileName(win, tr("file.dialog.title"), "", filters)
    if not path:
        return
    try:
        data = win._load_file(path)
    except (OSError, ValueError) as exc:
        win.on_log_line(tr("file.error", e=exc))
        return
    if not data:
        return
    win._file_data = data
    win._file_pos = 0
    win._file_path = path
    baud = win._baud_value()
    eta = max(1, int(len(data) / max(1.0, baud / 10.0)))
    win.file_progress.setValue(0)
    win.file_progress.show()
    win.file_info_lbl.setText(tr("file.info", size=_human_bytes(len(data)), baud=baud, eta=eta))
    win.send_file_btn.setText(tr("btn.cancel_send"))
    win._file_timer.start(FILE_CHUNK_MS)

def send_file_chunk(win: MainWindow):
    "send file chunk"
    if not win.worker.is_open():
        win._abort_file_send()
        return
    chunk = win._file_data[win._file_pos:win._file_pos + FILE_CHUNK_BYTES]
    if not chunk:
        win._finish_file_send()
        return
    win.worker.send(chunk)
    win._file_pos += len(chunk)
    win.tx_bytes += len(chunk)
    win.update_counts()
    total = len(win._file_data)
    pct = int(win._file_pos * 100 / total)
    win.file_progress.setValue(pct)
    win.file_info_lbl.setText(tr("file.progress", sent=_human_bytes(win._file_pos),
                                  total=_human_bytes(total), pct=pct))

def finish_file_send(win: MainWindow):
    "finish file send"
    size = _human_bytes(len(win._file_data))
    name = os.path.basename(win._file_path)
    win._file_timer.stop()
    win.send_file_btn.setText(tr("btn.send_file"))
    win.file_progress.setValue(100)
    win.file_progress.hide()
    win._notify(tr("file.done", name=name, size=size), ms=5000)

def abort_file_send(win: MainWindow):
    "abort file send"
    win._file_timer.stop()
    win.send_file_btn.setText(tr("btn.send_file"))
    win.file_info_lbl.setText("")
    win.file_progress.setValue(0)
    win.file_progress.hide()

def show_history(win: MainWindow) -> None:
    "show history"
    """Open (or raise) the non-modal history popup (U87)."""
    if win._history_dlg is None:
        win._history_dlg = HistoryDialog(win)
        win._history_dlg.fill_requested.connect(win._on_history_fill)
        win._history_dlg.delete_requested.connect(win._remove_history_entries)
        win._history_dlg.clear_requested.connect(win._clear_history)
    win._history_dlg.set_history(win._send_history, win._history_meta)
    win._history_dlg.show()
    win._history_dlg.raise_()
    win._history_dlg.activateWindow()

def on_history_fill(win: MainWindow, text: str) -> None:
    "on history fill"
    """Recall a stored command into the send box (U87)."""
    win.tx_edit.setPlainText(text)
    win.tx_edit.setFocus()
    win._recall_index = -1
    if win._history_dlg is not None:
        win._history_dlg.close()

def recall_history(win: MainWindow, step: int) -> None:
    "recall history"
    """Walk the send history with Ctrl+Up / Ctrl+Down (U87).

    step +1 goes further back in time (older), -1 comes towards the newest;
    stepping past the newest restores whatever was typed before browsing.
    """
    if not win._send_history:
        win._notify(tr("tx.history.empty"), "info", ms=2500)
        return
    if win._recall_index < 0:
        win._recall_draft = win.tx_edit.toPlainText()
        win._recall_index = 0
    else:
        win._recall_index += step
    if win._recall_index < 0:
        win._recall_index = -1
        win.tx_edit.setPlainText(win._recall_draft)
        return
    win._recall_index = min(win._recall_index, len(win._send_history) - 1)
    win.tx_edit.setPlainText(win._send_history[win._recall_index])

def prune_history_meta(win: MainWindow, raw: list) -> dict:
    "prune history meta"
    """Keep only the metadata of commands that are still in the history (v0.10.0)."""
    if not isinstance(raw, dict):
        return {}
    allowed = set(win._send_history)
    out = {}
    for text, meta in raw.items():
        if str(text) in allowed and isinstance(meta, dict):
            out[str(text)] = meta
    return out

def remember_send(win: MainWindow, text: str, fmt: str = '', nbytes: int | None = None):
    "remember send"
    """Push a sent command into the dedup history (max HISTORY_MAX) and persist it."""
    text = text.strip()
    if not text:
        return
    win._send_history = [text] + [h for h in win._send_history if h != text]
    win._send_history = win._send_history[:HISTORY_MAX]
    record = {"fmt": fmt, "ts": time.time()}
    if isinstance(nbytes, int):
        record["b"] = nbytes
    win._history_meta[text] = record
    win._history_meta = win._prune_history_meta(win._history_meta)
    win._update_history_button()
    win._schedule_history_save()

def update_history_button(win: MainWindow) -> None:
    "update history button"
    """Keep the History button (label, tooltip, enabled state) in sync (U87)."""
    n = len(win._send_history)
    win.history_btn.setText(tr("tx.history.btn", n=n))
    win.history_btn.setToolTip(tr("tx.history.btn.tip", n=n))
    win.history_btn.setEnabled(n > 0)
    if win._history_dlg is not None:
        win._history_dlg.set_history(win._send_history, win._history_meta)

def remove_history_entries(win: MainWindow, rows: list) -> None:
    """Drop several entries at once (U183) and persist.

    Rows are deleted from the highest index down so the earlier indices stay valid.
    """
    clean = sorted({int(r) for r in rows if 0 <= int(r) < len(win._send_history)},
                   reverse=True)
    if not clean:
        return
    removed = []
    for row in clean:
        text = win._send_history.pop(row)
        win._history_meta.pop(text, None)
        removed.append(text)
    win._update_history_button()
    win._schedule_history_save()
    if len(removed) == 1:
        win._notify(tr("tx.history.removed", text=removed[0]), "info", ms=3000)
    else:
        win._notify(tr("tx.history.removed.n", n=len(removed)), "info", ms=3000)


def remove_history_entry(win: MainWindow, row: int) -> None:
    "remove history entry"
    """Drop one entry from the send history and persist (U77)."""
    remove_history_entries(win, [row])

def clear_history(win: MainWindow) -> None:
    "clear history"
    """Forget every remembered command (U77)."""
    if not win._send_history:
        return
    win._send_history = []
    win._history_meta = {}
    win._update_history_button()
    win._schedule_history_save()
    win._notify(tr("tx.history.cleared"), "info", ms=3000)

def apply_checksum(win: MainWindow, payload: bytes) -> bytes:
    "apply checksum"
    mode = CHECKSUM_KEYS[win.checksum_combo.currentIndex()]
    return append_checksum(payload, mode)

def increment_cfg(win: MainWindow) -> dict:
    "increment cfg"
    """U180: the increment settings as a plain dict (safe if the chip is missing)."""
    def _int(widget, default: int) -> int:
        try:
            return int(widget.value())
        except (AttributeError, TypeError, ValueError):
            return default
    try:
        return {"start": _int(win.inc_start, 0), "step": _int(win.inc_step, 1),
                "width": int(win.inc_width.currentText()),
                "endian": "le" if win.inc_endian.currentIndex() == 1 else "big",
                "base": 16 if win.inc_base.currentIndex() == 1 else 10,
                "wrap": bool(win.inc_wrap.isChecked())}
    except AttributeError:
        return dict(DEFAULT_CFG)


def increment_enabled(win: MainWindow) -> bool:
    "increment enabled"
    """U180: is the send auto-increment switched on?"""
    box = getattr(win, "inc_check", None)
    return bool(box is not None and box.isChecked())


def on_increment_changed(win: MainWindow, *_args) -> None:
    "on increment changed"
    """U180: persist the settings and reset the counter to `start` on any change."""
    cfg = increment_cfg(win)
    cfg["enabled"] = increment_enabled(win)
    config = load_config()
    config["increment"] = cfg
    save_config(config)
    win._inc_value = cfg["start"]
    chip = getattr(win, "inc_chip", None)
    if chip is not None:
        chip.setText(tr("inc.chip.on") if cfg["enabled"] else tr("inc.chip"))


def reset_increment(win: MainWindow) -> None:
    "reset increment"
    """U180: put the counter back to its start value."""
    win._inc_value = increment_cfg(win)["start"]
    win._notify(tr("inc.reset.done"), "info", ms=2500)


def on_send(win: MainWindow):
    "on send"
    template = win.tx_edit.toPlainText().strip()
    if not template:
        return
    text = template
    exhausted = False
    if increment_enabled(win):
        cfg = increment_cfg(win)
        if not has_placeholder(template):
            win._notify(tr("inc.no_token"), "warn", ms=3500)
        else:
            text, nxt = apply_increment(
                template, is_hex=(win.tx_fmt_combo.currentIndex() == 0),
                value=int(getattr(win, "_inc_value", cfg["start"])), cfg=cfg)
            if nxt is None:
                exhausted = True          # this frame is the last one
            else:
                win._inc_value = nxt
    try:
        if win.tx_fmt_combo.currentIndex() == 0:
            payload = hex_str_to_bytes(text)
        else:
            payload = encode_text(text, win._encoding(), win.escape_check.isChecked())
    except HexFormatError as exc:
        win._notify(hex_error_message(exc), "error")
        return
    except ValueError as exc:
        win._notify(tr("log.send_error", e=exc), "error")
        return
    if not win._ensure_port():
        return
    payload = win._apply_checksum(payload)
    if win.tx_fmt_combo.currentIndex() == 1:
        payload += win._newline_bytes()
    if not win.worker.send(payload):
        return          # U61: never echo or count a frame that was not queued
    win._echo_tx(payload)
    win.tx_bytes += len(payload)
    win._sent_count += 1
    win._remember_send(
        template,          # U180: the history keeps the {i} template, not the value
        "hex" if win.tx_fmt_combo.currentIndex() == 0 else "ascii",
        len(payload))
    win.update_counts()
    if exhausted:
        win._stop_repeat()
        win.quick_panel.stop_sequence()
        win._notify(tr("inc.done"), "warn", ms=4000)

def on_quick_send(win: MainWindow, payload: bytes, is_hex: bool = False):
    "on quick send"
    """Send one quick-send row (button or sequence step).

    2026-10-02 (Andy): the send box's line-ending picker also ends quick-send rows.
    An ASCII row gets the same bytes the manual send would append; a HEX row is
    byte-exact (and the send box behaves the same way in HEX mode).
    """
    if not win.worker.is_open():     # U61: quick send / sequence obey the same rule
        win.quick_panel.stop_sequence()
        win._notify(tr("err.tx.closed"), "error")
        return
    payload = win._apply_checksum(payload)
    if not is_hex:
        payload += win._newline_bytes()
    if not win.worker.send(payload):
        win.quick_panel.stop_sequence()
        return
    win._echo_tx(payload)
    # U103: quick send / sequence / repeat go through here, so the send counter
    # has to move too - otherwise "已发送 N 次" stayed at the manual-send count
    # while the TX byte counter kept climbing.
    win.tx_bytes += len(payload)
    win._sent_count += 1
    win.update_counts()
