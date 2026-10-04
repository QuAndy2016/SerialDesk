"""Serial parameter controller: framing/encoding resolution, validation, threshold and the payload hint."""
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
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from ui.menus import build_menu
from ui.log_controller import apply_autosave_settings, log_append, log_close, log_header_text, log_open, on_log_line, on_save_log_as, on_save_log_quick, show_autosave_settings
from ui.receive_controller import append_header_split, append_rx_group, emit_rx_text, flush_rx_frames, on_clear, on_received, recolor_rx_view, snapshot_rx_fragments
from ui.send_controller import abort_file_send, apply_checksum, clear_history, finish_file_send, flush_history_save, on_history_fill, on_quick_send, on_send, on_send_file, prune_history_meta, recall_history, remember_send, remove_history_entry, schedule_history_save, send_file_chunk, show_history, update_history_button, update_payload_size
from ui.connection_controller import ensure_port, notify, on_opened_changed, on_reconnect_toggled, on_worker_error, poll_signals, recolor_status_light, refresh_ports, signals_html, toggle_open, update_port_tooltip
from ui.regions import (BAUDRATES, DATA_FIRST_H, DATA_FIRST_V,
                        RECEIVE_MAX_LINES, SPLIT_AUTO, SPLIT_DELIMITED,
                        SPLIT_FIXED, SPLIT_HEADER, SPLIT_MANUAL, SPLIT_TLV,
                        _fixed_row, build_connection_row,
                        build_data_panes, build_send_group, build_status_bar)
from app.i18n import hex_error_message, tr
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII, RX_COLUMN_HEX, column_hex)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.main_window import MainWindow
BYTESIZE_KEYS = [5, 6, 7, 8]
FLOW_KEYS = ["none", "xonxoff", "rtscts"]
PARITY_KEYS = ["N", "O", "E", "M", "S"]
STOPBITS_KEYS = [1, 1.5, 2]
def serial_params(win: MainWindow) -> dict:
    "serial params"
    """Collect the parameter widgets into pyserial open_port kwargs."""
    flow = FLOW_KEYS[win.flow_combo.currentIndex()]
    return {
        "bytesize": BYTESIZE_KEYS[win.dbits_combo.currentIndex()],
        "parity": PARITY_KEYS[win.parity_combo.currentIndex()],
        "stopbits": STOPBITS_KEYS[win.stopbits_combo.currentIndex()],
        "rtscts": flow == "rtscts",
        "xonxoff": flow == "xonxoff",
    }

def baud_value(win: MainWindow) -> int:
    "baud value"
    try:
        return int(win.baud_combo.currentText().strip())
    except ValueError:
        return 115200

def check_baud(win: MainWindow, text: str) -> None:
    "check baud"
    """Mark the baud box invalid (red border) when the typed value is not usable."""
    s = (text or "").strip()
    ok = s.isdigit() and 1 <= int(s) <= 12000000
    if bool(win.baud_combo.property("invalid")) != (not ok):
        win.baud_combo.setProperty("invalid", not ok)
        win.baud_combo.style().unpolish(win.baud_combo)
        win.baud_combo.style().polish(win.baud_combo)

def check_hex_input(win: MainWindow) -> None:
    "check hex input"
    """Live-validate the TX box in HEX mode: red border + tooltip."""
    if win.tx_fmt_combo.currentIndex() != 0:
        win.tx_edit.setStyleSheet("")
        win.tx_edit.setToolTip(tr("tx.input.tip.ascii"))   # 
        return
    try:
        hex_str_to_bytes(win.tx_edit.toPlainText())
    except HexFormatError as exc:
        win.tx_edit.setStyleSheet(f"border: 1px solid {theme.level_color('error')};")
        win.tx_edit.setToolTip(hex_error_message(exc))
        return
    win.tx_edit.setStyleSheet("")
    win.tx_edit.setToolTip(tr("tx.hex.tip"))

def encoding(win: MainWindow) -> str:
    "encoding"
    """Currently selected text encoding."""
    idx = win.encoding_combo.currentIndex()
    return TEXT_ENCODINGS[idx] if 0 <= idx < len(TEXT_ENCODINGS) else "ascii"

def format_rx(win: MainWindow, data: bytes) -> str:
    "format rx"
    mode = win.rx_fmt_combo.currentIndex()
    if mode == RX_HEX:
        return bytes_to_hex_str(data)
    if mode == RX_ASCII:
        return decode_text(data, win._encoding())
    if mode == RX_COLUMN_HEX:                       # c: hexdump rows, running offset
        text, win._col_off = column_hex(data, getattr(win, "_col_off", 0))
        return text
    hex_s = bytes_to_hex_str(data)
    text_s = decode_text(data, win._encoding())
    return f"{hex_s} | {text_s}"

def ts_prefix(win: MainWindow, ts: float) -> str:
    "ts prefix"
    """'[04:02:10.456] ' when the timestamp switch is on, '' when it is off."""
    if not win.ts_check.isChecked():
        return ""
    wall = ts + win._clock_offset
    ms = int((wall - int(wall)) * 1000)
    return time.strftime(f"[%H:%M:%S.{ms:03d}] ", time.localtime(wall))

def split_threshold_ms(win: MainWindow) -> float | None:
    "split threshold ms"
    """Return current split threshold in ms, or None if splitting off."""
    mode = win.split_combo.currentIndex()
    if mode != SPLIT_MANUAL and mode != SPLIT_AUTO:
        return None
    if mode == SPLIT_MANUAL:
        try:
            return max(0.0, float(win.split_ms_edit.text().strip()))
        except ValueError:
            return None
    # auto: 3.5-char rule (Modbus RTU), with 2 ms USB clustering floor
    try:
        baud = int(win.baud_combo.currentText().strip())
    except ValueError:
        return None
    char_ms = 10.0 / baud * 1000.0  # 8N1: one char = 10 bits
    # 10 ms floor: below that, USB chunk delivery (not the wire) decides
    return max(3.5 * char_ms, 10.0)

def _hex_bytes(text: str) -> bytes:
    "hex bytes"
    """Parse a HEX delimiter field; an empty or half-typed value means none."""
    try:
        return hex_str_to_bytes(text)
    except HexFormatError:
        return b""

def split_byte_params(win: MainWindow) -> dict:
    "split byte params"
    """Rule parameters for the active B3 byte-stream split mode."""
    index = win.split_combo.currentIndex()
    if index == SPLIT_FIXED:
        return {"mode": "fixed", "size": win.split_size_spin.value()}
    if index == SPLIT_DELIMITED:
        return {"mode": "delimited",
                "start": _hex_bytes(win.split_start_edit.text()),
                "end": _hex_bytes(win.split_end_edit.text()),
                "include": True}
    return {"mode": "tlv",
            "prefix_bytes": win.split_prefix_spin.value(),
            "little": win.split_little_check.isChecked(),
            "crc_bytes": 2 if win.split_crc_check.isChecked() else 0}

def on_split_mode_changed(win: MainWindow, index: int):
    "on split mode changed"
    win._flush_rx_frames()   # don't lose a half-collected frame
    win._flush_byte_frames()   # B3: nor a half frame from the previous rule
    if index == SPLIT_MANUAL:
        win.split_slot.setCurrentIndex(1)
        win.split_slot.setVisible(True)
    elif index == SPLIT_HEADER:
        win.split_slot.setCurrentIndex(2)
        win.split_slot.setVisible(True)
    elif index == SPLIT_FIXED:
        win.split_slot.setCurrentIndex(3)
        win.split_slot.setVisible(True)
    elif index == SPLIT_DELIMITED:
        win.split_slot.setCurrentIndex(4)
        win.split_slot.setVisible(True)
    elif index == SPLIT_TLV:
        win.split_slot.setCurrentIndex(5)
        win.split_slot.setVisible(True)
    else:
        # in auto/off mode the slot held a hint that repeated the combo's own
        # label and read like stray text, so the slot simply goes away.
        win.split_slot.setCurrentIndex(0)
        win.split_slot.setVisible(False)

def on_header_changed(win: MainWindow, text: str):
    "on header changed"
    if text.strip() and win.split_combo.currentIndex() != SPLIT_HEADER:
        win.split_combo.setCurrentIndex(SPLIT_HEADER)

def on_tx_fmt_changed(win: MainWindow, index: int):
    "on tx fmt changed"
    """-A: in HEX mode the line-ending / escape controls stay visible but disabled.

    Hiding them (the old behaviour) made the option look unsupported - the user could
    not see that the setting existed or what state it was in. HEX sends bytes exactly,
    so the two controls switch off and the label explains why instead of vanishing.
    """
    ascii_mode = index == 1
    win._tx_mod_group.setVisible(True)
    for widget in (win.nl_combo, win.escape_check, win._nl_lbl):
        widget.setEnabled(ascii_mode)
    win.nl_combo.setToolTip(tr("tx.newline.tip" if ascii_mode else "tx.newline.hex.tip"))
    win.escape_check.setToolTip(tr("tx.escape.tip" if ascii_mode else "tx.escape.hex.tip"))
    win._nl_lbl.setToolTip(tr("tx.newline.tip" if ascii_mode else "tx.newline.hex.tip"))
    win._tx_mod_group.setToolTip("" if ascii_mode else tr("tx.newline.hex.tip"))
    win._update_input_placeholder()   # hint follows the send format

def newline_bytes(win: MainWindow) -> bytes:
    "newline bytes"
    """the bytes the "line ending" picker appends (ASCII mode only)."""
    index = min(max(0, win.nl_combo.currentIndex()), len(win.NEWLINE_KEYS) - 1)
    return win.NEWLINE_BYTES[win.NEWLINE_KEYS[index]]

def persist_newline(win: MainWindow, _index: int = 0) -> None:
    "persist newline"
    key = win.NEWLINE_KEYS[min(max(0, win.nl_combo.currentIndex()), 3)]
    save_config({"newline": key})      # save_config merges, other keys survive
    refresh_tx_settings_chip(win)      # the chip must show what will be appended

def refresh_tx_settings_chip(win: MainWindow) -> None:
    "refresh tx settings chip"
    """Keep the chip in step with the pickers it hides - including the line ending.

    2026-10-04 (user report): typing ``ffffffffffffffffffRR`` and pressing send produced
    ``...RR\\r\\n``. The payload builder was right (the box is stripped first) - the *line
    ending picker* was still on CRLF from an earlier session, and it lives inside this
    popup while the chip only showed "ASCII · 无", where that "无" is the checksum. A
    setting that silently appends bytes must be visible (visibility of system status).
    """
    fmt = "HEX" if win.tx_fmt_combo.currentIndex() == 0 else "ASCII"
    # keep the at-a-glance summary and add the caret that says "this opens".
    parts = [fmt]
    if win.tx_fmt_combo.currentIndex() == 1:      # HEX never appends an ending
        parts.append(tx_ending_text(win))
    parts.append("%s%s" % (tr("tx.checksum.label"), win.checksum_combo.currentText()))
    win.tx_settings_btn.setText(" · ".join(parts) + " \u25be")


def tx_ending_text(win: MainWindow) -> str:
    "tx ending text"
    """The line ending as the chip shows it: short, and never confused with the checksum."""
    key = win.NEWLINE_KEYS[min(max(0, win.nl_combo.currentIndex()), 3)]
    return tr("tx.nl.none") if key == "none" else {"cr": "CR", "lf": "LF", "crlf": "CRLF"}[key]

def refresh_repeat_chip(win: MainWindow) -> None:
    "refresh repeat chip"
    """the repeat chip shows interval and count at a glance - the same idea as
    the format chip. The two fields live inside, their state stays visible outside."""
    ms = (win.repeat_ms.text() or "").strip() or "?"
    count = "\u221e" if win.repeat_times.endless() else str(win.repeat_times.value())
    win.repeat_chip.setText("%sms\u00d7%s" % (ms, count))


def update_input_placeholder(win: MainWindow) -> None:
    "update input placeholder"
    """Keep the send box and the frame-header box hints in step with the format."""
    if not hasattr(win, "tx_edit"):
        return          # the format row is built before the input box
    hex_mode = win.tx_fmt_combo.currentIndex() == 0
    win.tx_edit.setPlaceholderText(tr("tx.placeholder.hex" if hex_mode else "tx.placeholder.ascii"))
    if hasattr(win, "header_edit"):
        win.header_edit.setPlaceholderText(
            tr("header.placeholder.hex" if hex_mode else "header.placeholder.ascii"))
