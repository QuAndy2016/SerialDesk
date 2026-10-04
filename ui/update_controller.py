"""Update controller: the quiet startup check, its worker and the result dialogs."""
from __future__ import annotations


import json
import os
import shutil
import sys
import time
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from shiboken6 import isValid      # 2026-10-03: a probe can outlive its window (see _deliver)
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
from ui.params_controller import baud_value, check_baud, check_hex_input, encoding, format_rx, newline_bytes, on_header_changed, on_split_mode_changed, on_tx_fmt_changed, persist_newline, refresh_tx_settings_chip, serial_params, split_threshold_ms, ts_prefix, update_input_placeholder
from ui.layout_controller import control_rows, fit_minimum_width, fit_pane_minimums, fit_settings_btn, fit_tx_edit_height, give_data_area_the_room, lock_control_widths, row_need, saved_sizes, widest_row
from ui.config_controller import apply_config, apply_defaults, on_export_config, on_import_config, persist_theme, reset_settings, set_language, set_theme_dark, set_theme_light, set_theme_system
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
class _UpdateProbe(QObject):
    """carries the worker thread's answer back onto the GUI thread."""

    found = Signal(str)          # a newer tag exists (startup or manual)
    checked = Signal(bool, str)  # manual probe done: (ok, tag_or_reason)


def _deliver(win: MainWindow, signal_name: str, *args) -> None:
    """Hand a probe answer to the GUI thread - if a window is still there to take it.

    2026-10-03 (review): the probe runs on a daemon thread and can outlive the window it
    reports to, because closing a window destroys the C++ object behind it. The emit then
    raised RuntimeError *inside that thread*, and nothing saw it: threading.excepthook only
    writes to stderr, sys.excepthook is never called for thread exceptions, and the packaged
    windowed build has no console - so the traceback vanished. Dropping a late answer is the
    correct outcome: no window means nobody to notify.
    """
    try:
        probe = win._update_probe
        if not isValid(probe):
            return
        getattr(probe, signal_name).emit(*args)
    except RuntimeError:      # PySide refuses access once the C++ object behind it is gone
        return


def init_update_check(win: MainWindow) -> None:
    "init update check"
    """A quiet look at the latest release; nothing is sent about the user."""
    win._update_probe = _UpdateProbe(win)
    win._update_probe.found.connect(win._on_update_found)
    win._update_probe.checked.connect(win._on_update_checked)   # N10 manual probe

    win._update_act = QAction(tr("update.menu", v=""), win)   # 
    win._update_act.setVisible(False)
    win._update_act.triggered.connect(
        lambda: QDesktopServices.openUrl(QUrl(update_check.RELEASES_PAGE)))
    win._settings_menu.addAction(win._update_act)

    win._update_check_act = QAction(tr("update.check"), win, checkable=True)
    win._update_check_act.setToolTip(tr("update.check.tip"))
    win._update_check_act.setChecked(load_config().get("check_updates", True) is not False)
    win._update_check_act.toggled.connect(
        lambda on: save_config({"check_updates": bool(on)}))
    win._settings_menu.addAction(win._update_check_act)

    # N10: a manual "check now" that always reports back (menu item after the toggle)
    win._update_now_act = QAction(tr("update.check.now"), win)
    win._update_now_act.triggered.connect(lambda: probe_updates(win, manual=True))
    win._settings_menu.addAction(win._update_now_act)

    known = str(load_config().get("update_available") or "")
    if known and update_check.is_newer(known, __version__):
        win._show_update(known, notify=False)
    if win._update_check_act.isChecked():
        QTimer.singleShot(2500, win._probe_updates)      # let the window settle

def probe_updates(win: MainWindow, manual: bool = False) -> None:
    """Start a probe; manual=True reports the outcome through `checked`."""
    if manual:
        win._notify(tr("update.checking"), "info", ms=3000)
    import threading
    threading.Thread(target=win._probe_updates_worker, args=(manual,),
                     daemon=True).start()

def probe_updates_worker(win: MainWindow, manual: bool = False) -> None:
    """Worker thread: one GET, five-second timeout, no exceptions escape."""
    try:
        tag = update_check.fetch_latest_tag(raise_on_error=manual)
    except (OSError, ValueError, KeyError):   # a check must never break the app
        if manual:
            _deliver(win, "checked", False, "")
        return
    if manual:
        _deliver(win, "checked", True, tag)
    elif tag:
        _deliver(win, "found", tag)            # queued onto the GUI thread

def on_update_checked(win: MainWindow, ok: bool, tag: str) -> None:
    """N10: a manual probe came back - tell the user what it found."""
    if not ok:
        win._notify(tr("update.fail"), "warn", ms=6000)
        return
    if tag and update_check.is_newer(tag, __version__):
        save_config({"update_available": tag, "update_notified": tag})
        win._show_update(tag, notify=True)
    else:
        win._notify(tr("update.none"), "info", ms=5000)

def on_update_found(win: MainWindow, tag: str) -> None:
    "on update found"
    if not update_check.is_newer(tag, __version__):
        return
    first_time = str(load_config().get("update_notified") or "") != tag
    save_config({"update_available": tag, "update_notified": tag})
    win._show_update(tag, notify=first_time)

def show_update(win: MainWindow, tag: str, notify: bool) -> None:
    "show update"
    win._update_act.setText(tr("update.menu", v=tag))
    win._update_act.setVisible(True)
    if notify:
        win._notify(tr("update.available", v=tag), "info", ms=8000)
