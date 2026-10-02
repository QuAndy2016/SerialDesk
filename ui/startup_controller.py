"""Startup controller: the six window phases (worker, state, language/log, timers, build, restore)."""
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
from ui.params_controller import baud_value, check_baud, check_hex_input, encoding, format_rx, newline_bytes, on_header_changed, on_split_mode_changed, on_tx_fmt_changed, persist_newline, refresh_tx_settings_chip, serial_params, split_threshold_ms, ts_prefix, update_input_placeholder
from ui.layout_controller import control_rows, fit_minimum_width, fit_pane_minimums, fit_settings_btn, fit_tx_edit_height, give_data_area_the_room, lock_control_widths, row_need, saved_sizes, widest_row
from ui.config_controller import apply_config, apply_defaults, on_export_config, on_import_config, persist_theme, reset_settings, set_language, set_theme_dark, set_theme_light, set_theme_system
from ui.update_controller import init_update_check, on_update_found, probe_updates, probe_updates_worker, show_update
from ui.dialogs_controller import diagnostics_text, edit_rules, first_run_hint, show_about, show_port_settings, show_shortcuts
from ui.actions_controller import apply_accessible_names, check_auto_reply, clear_undo, echo_tx, esc_action, find_next, load_file, on_auto_reply_toggled, on_autoscroll_toggled, on_repeat_interval, on_repeat_toggled, on_row_deleted, on_timestamp_toggled, pause_autoscroll, repeat_value, rx_separator, scroll_rx_bottom, setup_shortcuts, setup_tab_order, stop_repeat, toggle_find_bar, undo_delete, update_counts, update_params_summary
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
HISTORY_MAX = 50
LOG_DIR = log_dir()   # U34: per-user (or portable) logs, not next to the bundle
def init_worker(win: MainWindow) -> None:
    "init worker"
    """Create the serial worker and connect its signals."""
    win.worker = SerialWorker(win)
    win.worker.received.connect(win.on_received)
    win.worker.log.connect(win.on_log_line)
    win.worker.opened.connect(win.on_opened_changed)
    win.worker.error.connect(win._on_worker_error)
    win.worker.send_error.connect(win._on_send_error)
    win.worker.reconnecting.connect(
        lambda n: win._notify(tr("conn.reconnecting", n=n), "warn"))   # T14
    win.worker.reconnected.connect(lambda: win._notify(tr("conn.reconnected"), "info"))
    win.worker.disconnected.connect(lambda _r: win._notify(tr("conn.lost"), "error"))

def init_state(win: MainWindow) -> None:
    "init state"
    """Session state: counters, display flags and the wall-clock offset."""
    win._stats = SessionStats()      # refactor step 1: counters live in app/stats.py
    win._fitting_tx = False
    win._line_is_tx = False   # U59: is the current display line a TX echo?
    win._cap_warned = False   # U45: warn once when the display cap is reached
    win._last_ts: float | None = None
    win._clock_offset = time.time() - time.monotonic()

def init_language_and_log(win: MainWindow) -> None:
    "init language and log"
    """Initial language plus the auto-save sink and its limits."""
    # initial language from config (default: follow system)
    i18n.set_language(str(load_config().get("language", "system")))

    win._log_fp = None            # kept for compatibility; see _log_sink below
    win._log_started = 0.0
    win._log_bytes = 0
    _cfg0 = load_config()                       # U75: configurable auto-save
    win._log_max_bytes = max(1, int(_cfg0.get("autosave_max_mb", 2) or 2)) * 1024 * 1024
    win._log_max_seconds = max(1, int(_cfg0.get("autosave_max_minutes", 30) or 30)) * 60
    win._log_quota_bytes = max(0, int(_cfg0.get("log_quota_mb", 0) or 0)) * 1024 * 1024
    win._log_dir = str(_cfg0.get("log_dir") or "") or LOG_DIR
    win._log_sink = LogSink(win._log_dir, win._log_max_bytes, win._log_max_seconds,
                             header=win._log_header_text)   # refactor step 2

def init_timers(win: MainWindow) -> None:
    "init timers"
    """The timers and the frame assembler that drive sending and reception."""
    win._send_history: list[str] = []
    win._history_meta: dict = {}   # v0.10.0: text -> {"fmt", "b", "ts"}
    win._history_dlg = None        # U87: lazily created non-modal popup
    win._recall_index = -1         # U87: Ctrl+Up/Down position in the history
    win._recall_draft = ""
    win._sent_count = 0
    win._repeat_timer = QTimer(win)
    win._repeat_timer.timeout.connect(win._on_repeat_tick)
    win._file_timer = QTimer(win)
    win._file_timer.timeout.connect(win._send_file_chunk)
    win._sig_timer = QTimer(win)
    win._sig_timer.timeout.connect(win._poll_signals)
    win._sig_timer.start(50)
    win._cfg_save_timer = QTimer(win)     # U52: debounced config persistence
    # U57: merge USB-fragmented chunks before deciding a line break
    _settle = float(load_config().get("rx_settle_ms", DEFAULT_SETTLE_MS) or DEFAULT_SETTLE_MS)
    win._frames = FrameAssembler(settle_ms=_settle)
    win._frame_timer = QTimer(win)
    win._frame_timer.setSingleShot(True)
    win._frame_timer.timeout.connect(win._flush_rx_frames)
    win._cfg_save_timer.setSingleShot(True)
    win._cfg_save_timer.timeout.connect(win._flush_history_save)
    win._file_data = b""
    win._file_pos = 0
    win._file_path = ""

def build_everything(win: MainWindow) -> None:
    "build everything"
    """Build every region once the state exists (UI, menu, shortcuts, checks)."""
    win._build_settings_button()   # U72: the connect row hosts this button
    win._build_ui()
    win._build_menu()
    win._init_update_check()                          # U127
    QApplication.instance().installEventFilter(win)   # U120: hover the right edge
    if load_config().get("quick_panel_collapsed"):     # U88: restore the folded state
        win._on_quick_panel_collapsed(True)
    win._apply_accessible_names()
    win._setup_tab_order()
    win._setup_shortcuts()
    win._first_run_hint()

def restore_settings(win: MainWindow) -> None:
    "restore settings"
    """Apply the persisted settings: auto-save, history, rules, theme, reconnect."""
    win._autosave_dlg = AutoSaveDialog(win)              # U75
    win._autosave_dlg.settingsChanged.connect(win._apply_autosave_settings)
    _cfg = load_config()
    win._autosave_dlg.set_values(
        enabled=bool(_cfg.get("autosave_enabled", False)),
        max_mb=int(_cfg.get("autosave_max_mb", 2) or 2),
        max_minutes=int(_cfg.get("autosave_max_minutes", 30) or 30),
        quota_mb=int(_cfg.get("log_quota_mb", 0) or 0),
        folder=win._log_dir)

    # send history (T5) from config
    _hcfg = load_config()
    win._send_history = [str(h) for h in _hcfg.get("send_history", [])
                          if str(h).strip()][:HISTORY_MAX]
    win._history_meta = win._prune_history_meta(_hcfg.get("history_meta"))
    win._update_history_button()

    # auto-reply rules (T10) from config
    cfg = load_config()
    win._auto_rules = [r for r in cfg.get("auto_reply", []) if isinstance(r, dict)]
    win._reply_buf = b""
    win.auto_reply_act.setChecked(bool(cfg.get("auto_reply_enabled", False)))

    # initial theme from config (default: follow system)
    choice = load_config().get("theme", "system")
    if choice == "dark":
        theme.set_override(True)
    elif choice == "light":
        theme.set_override(False)
    else:
        theme.set_override(None)
    theme.apply_theme(QApplication.instance())
    win._recolor_status_light()
    theme.apply_native_dark(win, bool(theme.resolved_dark()))

    win.worker.set_auto_reconnect(
        bool(load_config().get("auto_reconnect", False)))    # T14

    win.refresh_timer = QTimer(win)
    win.refresh_timer.timeout.connect(win.refresh_ports)
    win.refresh_timer.start(3000)
