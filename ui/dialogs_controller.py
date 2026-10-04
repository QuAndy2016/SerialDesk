"""Dialogs controller: about, shortcut reference, diagnostics text, port settings, reply rules and the first-run hint."""
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
def show_about(win: MainWindow) -> None:
    "show about"
    """About box: version, runtime versions and the project link."""
    import PySide6
    import serial as _serial

    box = QMessageBox(win)
    box.setWindowTitle(tr("about.title"))
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(tr("about.text", version=__version__,
                   pyside=PySide6.__version__, pyserial=_serial.__version__))
    box.setIcon(QMessageBox.Icon.Information)
    # E3: hand the user something useful to paste into an issue
    copy_btn = box.addButton(tr("about.copy"), QMessageBox.ButtonRole.ActionRole)
    box.exec()
    if box.clickedButton() is copy_btn:
        QApplication.clipboard().setText(win._diagnostics_text())
        win._notify(tr("about.copied"), "info", ms=3000)

def show_shortcuts(win: MainWindow) -> None:
    "show shortcuts"
    """the shortcut list the app never showed anywhere."""
    rows = "\n".join("%-12s %s" % (key, tr(label))
                      for key, label in win.SHORTCUT_HELP)
    box = QMessageBox(win)
    box.setWindowTitle(tr("menu.shortcuts"))
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(rows)
    box.setIcon(QMessageBox.Icon.Information)
    box.exec()

def diagnostics_text(win: MainWindow) -> str:
    "diagnostics text"
    """/E3: what a bug report needs, in one copyable block."""
    import platform
    import sys
    import PySide6
    try:
        import serial as _serial
        pyserial = _serial.__version__
    except ImportError:
        pyserial = "-"
    # Framing evidence (2026-10-04): the split mode's window has to clear the USB adapter's
    # own batching delay, so report what this machine actually delivers. A max gap near the
    # window is the early warning for "one frame shown as two lines".
    stats = getattr(win, "_frames", None)
    gaps = stats.gap_stats() if stats is not None and hasattr(stats, "gap_stats") else {}
    if gaps.get("count"):
        framing = ("Chunk gaps: n=%d, p95=%.1f ms, max=%.1f ms (window %.0f ms)"
                   % (gaps["count"], gaps["p95"], gaps["max"], stats.settle_ms))
    else:
        framing = "Chunk gaps: none yet (send some data, then reopen this dialog)"
    return "\n".join((
        "SerialDesk %s" % __version__,
        "OS: %s" % platform.platform(),
        "Python %s / PySide6 %s / pyserial %s" % (sys.version.split()[0], PySide6.__version__, pyserial),
        "Port: %s @ %s" % (win.port_combo.currentData() or "-", win.baud_combo.currentText().strip()),
        "Format: %s / RX %s" % (win.tx_fmt_combo.currentText(), win.rx_fmt_combo.currentText()),
        "Split: %s / %s" % (win.split_combo.currentText(),
                            "%.0f ms window" % (stats.settle_ms if stats else 0.0)),
        framing,
        "Log folder: %s" % win._log_dir,
        "Last error log: %s" % os.path.join(data_dir(), "logs", "lasterror.log"),
    ))

def show_port_settings(win: MainWindow) -> None:
    "show port settings"
    """Show the port-settings dialog, reflecting the current lock state."""
    win._port_dlg.set_port_open(win.worker.is_open())   # 
    win._port_dlg.show()
    win._port_dlg.raise_()
    win._port_dlg.activateWindow()

def edit_rules(win: MainWindow) -> None:
    "edit rules"
    dlg = AutoReplyDialog(win._auto_rules, win)
    if not dlg.exec():
        return
    win._auto_rules = dlg.rules()
    config = load_config()
    config["auto_reply"] = win._auto_rules
    save_config(config)
    win._notify(tr("rb.saved", n=len(win._auto_rules)), ms=5000)

def first_run_hint(win: MainWindow) -> None:
    "first run hint"
    """One restrained hint on the very first launch."""
    cfg = load_config()
    if cfg.get("first_run_done"):
        return
    win._notify(tr("hint.first_run"), "info", ms=8000)
    cfg["first_run_done"] = True
    save_config(cfg)
