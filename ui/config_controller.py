"""Config controller: apply/export/import/reset settings and the theme + language selection."""
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
def apply_config(win: MainWindow) -> None:
    "apply config"
    """Re-apply settings loaded from config.json (used after an import)."""
    cfg = load_config()

    choice = cfg.get("theme", "system")
    if choice == "dark":
        theme.set_override(True)
    elif choice == "light":
        theme.set_override(False)
    else:
        theme.set_override(None)
    theme.apply_theme(QApplication.instance())
    win._recolor_status_light()
    theme.apply_native_dark(win, bool(theme.resolved_dark()))
    win._recolor_rx_view()
    {"dark": win._theme_dark, "light": win._theme_light}.get(
        choice, win._theme_system).setChecked(True)

    i18n.set_language(str(cfg.get("language", "system")))
    win.retranslate()

    win.quick_panel.reload_from_config()

    win._send_history = [str(h) for h in cfg.get("send_history", []) if str(h).strip()][:HISTORY_MAX]
    win._history_meta = win._prune_history_meta(cfg.get("history_meta"))
    win._update_history_button()

    win._auto_rules = [r for r in cfg.get("auto_reply", []) if isinstance(r, dict)]
    win.auto_reply_act.setChecked(bool(cfg.get("auto_reply_enabled", False)))
    win._reply_buf = b""

def apply_defaults(win: MainWindow) -> None:
    "apply defaults"
    """Put every user-facing option back to its default value (U76)."""
    win._set_theme_system()
    win._set_language("system")
    win._reconnect_act.setChecked(False)
    win._log_dir = log_dir()
    win._log_max_bytes = 2 * 1024 * 1024
    win._log_max_seconds = 30 * 60
    win._autosave_dlg.set_values(enabled=False, max_mb=2, max_minutes=30, folder=win._log_dir)
    win._apply_autosave_settings()
    win.autoscroll_check.setChecked(True)
    win.ts_check.setChecked(True)          # U96: timestamps are on by default
    win._send_history = []
    win._update_history_button()
    win._auto_rules = []
    win.auto_reply_act.setChecked(False)
    win._sent_count = 0
    win.update_counts()
    # U82: restoring defaults must also restore the data-first proportions, and
    # they are re-measured so a maximised window gives the log every spare pixel
    win._custom_split_sizes = False
    win._split_room_done = True
    QTimer.singleShot(0, win._give_data_area_the_room)
    win.quick_panel.set_folded(False)      # U88/U106: defaults = panel shown again
    if hasattr(win, "_quick_panel_act"):
        win._quick_panel_act.setChecked(True)
    win._sync_panel_btn(False)   # U161: keep the toggle button in step with the reset
    win.quick_panel.reload_from_config()   # seeds the default rows when config is gone
    win._update_params_summary()

def reset_settings(win: MainWindow) -> None:
    "reset settings"
    """Restore factory defaults after backing the current config up (U76)."""
    box = QMessageBox(win)
    box.setWindowTitle(tr("cfg.reset.title"))
    box.setText(tr("cfg.reset.text"))
    box.setIcon(QMessageBox.Icon.Warning)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    if box.exec() != QMessageBox.StandardButton.Yes:
        return
    backup = ""
    try:
        if os.path.exists(CONFIG_PATH):
            backup = os.path.join(data_dir(), f"config.backup_{time.strftime('%Y%m%d_%H%M%S')}.json")
            shutil.copyfile(CONFIG_PATH, backup)
            os.remove(CONFIG_PATH)
    except OSError as exc:
        win._notify(tr("cfg.reset.fail", e=exc), "error")
        return
    win._apply_defaults()
    save_config({"language": "system", "theme": "system"})
    # the full path is long enough to crowd the status bar, so it lives in the
    # tooltip while the message stays short (U82)
    win.statusBar().setToolTip(tr("cfg.reset.done.tip", path=backup or "-"))
    win._notify(tr("cfg.reset.done"), "info", ms=8000)

def on_import_config(win: MainWindow) -> None:
    "on import config"
    """Merge a previously exported config file back into the current settings."""
    path, _ = QFileDialog.getOpenFileName(win, tr("cfg.import.title"), "", tr("cfg.filter"))
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        win.on_log_line(tr("cfg.import_fail", e=exc))
        return
    if not isinstance(data, dict):
        win.on_log_line(tr("cfg.import_bad"))
        return
    incoming = data.get("config") if isinstance(data.get("config"), dict) else data

    config = load_config()
    for key in ("theme", "language", "quick_send", "send_history", "history_meta",
                "auto_reply", "auto_reply_enabled"):
        if key in incoming:
            config[key] = incoming[key]
    if not save_config(config):
        win.on_log_line(tr("cfg.import_fail", e="config.json"))
        return
    win._apply_config()
    win._notify(tr("cfg.imported", path=path), ms=5000)

def on_export_config(win: MainWindow) -> None:
    "on export config"
    """Write the current settings (quick send, theme, history, rules...) to a JSON file."""
    default = os.path.join(os.path.expanduser("~"),
                           time.strftime("serialdesk_config_%Y%m%d_%H%M%S.json"))
    path, _ = QFileDialog.getSaveFileName(win, tr("cfg.export.title"), default, tr("cfg.filter"))
    if not path:
        return
    payload = {
        "_app": "SerialDesk",
        "_version": __version__,
        "_exported": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": load_config(),
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        win._notify(tr("cfg.exported", path=path), ms=5000)
    except OSError as exc:
        win.on_log_line(tr("cfg.export_fail", e=exc))

def set_language(win: MainWindow, lang: str):
    "set language"
    """Switch UI language, persist the choice, rebuild every visible string."""
    i18n.set_language(lang)
    config = load_config()
    config["language"] = lang
    save_config(config)
    win.retranslate()

def set_theme_system(win: MainWindow):
    "set theme system"
    theme.set_override(None)
    theme.apply_theme(QApplication.instance())
    win._recolor_status_light()
    theme.apply_native_dark(win, bool(theme.resolved_dark()))
    win._recolor_rx_view()
    win._sync_panel_btn()
    win._persist_theme("system")

def set_theme_dark(win: MainWindow):
    "set theme dark"
    theme.set_override(True)
    theme.apply_theme(QApplication.instance())
    win._recolor_status_light()
    theme.apply_native_dark(win, bool(theme.resolved_dark()))
    win._recolor_rx_view()
    win._sync_panel_btn()
    win._persist_theme("dark")

def set_theme_light(win: MainWindow):
    "set theme light"
    theme.set_override(False)
    theme.apply_theme(QApplication.instance())
    win._recolor_status_light()
    theme.apply_native_dark(win, bool(theme.resolved_dark()))
    win._recolor_rx_view()
    win._sync_panel_btn()
    win._persist_theme("light")

def persist_theme(win: MainWindow, choice: str):
    "persist theme"
    config = load_config()
    config["theme"] = choice
    save_config(config)
