"""Log and auto-save controller: session segments, rotation, manual save and the auto-save dialog."""
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
from app.log_sink import LogSink, prune_log_dir
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.autosave_dialog import AutoSaveDialog
from ui.history_dialog import HistoryDialog
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from ui.menus import build_menu
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
def log_header_text(win: MainWindow) -> str:
    "log header text"
    """Context for the log segment, so a shared capture can be reproduced (N3)."""
    port = win.port_combo.currentData() or "-"
    return tr("log.header", app="SerialDesk", version=__version__, port=port,
              baud=win.baud_combo.currentText().strip(),
              fmt=win.tx_fmt_combo.currentText(), rx=win.rx_fmt_combo.currentText(),
              when=time.strftime("%Y-%m-%d %H:%M:%S"))

def log_open(win: MainWindow) -> None:
    "log open"
    """Open a new log segment under logs/ (auto-save mode)."""
    win._log_sink.configure(win._log_dir, win._log_max_bytes, win._log_max_seconds)
    try:
        win._log_path = win._log_sink.open()
        prune_log_dir(win._log_dir, getattr(win, "_log_quota_bytes", 0),
                      keep=win._log_path)       # U163d: folder quota, oldest first
        win._log_fp = True                      # legacy flag: "a segment is open"
        win._notify(tr("log.autosave.on", path=win._log_path), ms=5000)
    except OSError as exc:
        win._log_fp = None
        win.on_log_line(tr("log.save_fail", e=exc))   # noqa: BLE001 - surfaced to the user

def log_close(win: MainWindow) -> None:
    "log close"
    win._log_sink.close()
    win._log_fp = None

def log_append(win: MainWindow, text: str) -> None:
    "log append"
    """Append a chunk of received text to the auto-save file, rotating when needed."""
    if win._log_fp is None:
        return
    try:
        win._log_sink.configure(win._log_dir, win._log_max_bytes, win._log_max_seconds)
        win._log_sink.append(text)
        win._log_bytes = win._log_sink.bytes_written
        win._log_path = win._log_sink.path
    except OSError as exc:
        win._log_close()
        win.on_log_line(tr("log.save_fail", e=exc))   # noqa: BLE001 - surfaced to the user

def on_save_log_quick(win: MainWindow) -> None:
    "on save log quick"
    """One-click save of the receive pane into logs/ (U25-D)."""
    try:
        os.makedirs(win._log_dir, exist_ok=True)
        path = os.path.join(win._log_dir, time.strftime("serial_RX_%Y%m%d_%H%M%S.txt"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(win.rx_view.toPlainText())
            fh.write("\n")
        win._notify(tr("log.saved", path=path), ms=5000)
    except OSError as exc:
        win.on_log_line(tr("log.save_fail", e=exc))

def on_save_log_as(win: MainWindow) -> None:
    "on save log as"
    """Save the receive pane to a user-chosen path (U25-D)."""
    try:
        os.makedirs(win._log_dir, exist_ok=True)      # U97: the configured log folder
    except OSError:
        pass
    default = os.path.join(win._log_dir, time.strftime("serial_%Y%m%d_%H%M%S.txt"))
    path, _ = QFileDialog.getSaveFileName(win, tr("log.save.title"), default, "Text (*.txt)")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(win.rx_view.toPlainText())
            fh.write("\n")
        win._notify(tr("log.saved", path=path), ms=5000)
    except OSError as exc:
        win.on_log_line(tr("log.save_fail", e=exc))

def on_log_line(win: MainWindow, line: str):
    "on log line"
    win._notify(line, ms=5000)

def apply_autosave_settings(win: MainWindow) -> None:
    "apply autosave settings"
    """Apply the auto-save dialog values live and remember them (U75)."""
    values = win._autosave_dlg.values()
    win._log_max_bytes = max(1, int(values["max_mb"])) * 1024 * 1024
    win._log_max_seconds = max(1, int(values["max_minutes"])) * 60
    win._log_quota_bytes = max(0, int(values.get("quota_mb", 0))) * 1024 * 1024
    if values["dir"]:
        win._log_dir = values["dir"]
    config = load_config()
    config["autosave_enabled"] = bool(values["enabled"])
    config["autosave_max_mb"] = int(values["max_mb"])
    config["autosave_max_minutes"] = int(values["max_minutes"])
    config["log_quota_mb"] = max(0, int(values.get("quota_mb", 0)))
    config["log_dir"] = win._log_dir
    save_config(config)
    prune_log_dir(win._log_dir, win._log_quota_bytes,
                  keep=win._log_path if win._log_fp else "")   # U163d
    if values["enabled"]:
        if win._log_fp is None:
            win._log_open()
        if win._log_fp is None:
            # U97: opening the file failed - the dialog is the only switch now, so
            # it must fall back to "off" instead of showing an enabled state.
            config["autosave_enabled"] = False
            save_config(config)
            win._autosave_dlg.set_values(
                enabled=False, max_mb=max(1, int(values["max_mb"])),
                max_minutes=max(1, int(values["max_minutes"])), folder=win._log_dir)
    else:
        win._log_close()

def show_autosave_settings(win: MainWindow) -> None:
    "show autosave settings"
    """Open the auto-save settings dialog (U75)."""
    win._autosave_dlg.show()
    win._autosave_dlg.raise_()
    win._autosave_dlg.activateWindow()
