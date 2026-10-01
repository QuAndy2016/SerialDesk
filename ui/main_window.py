"""Main window: port selection, baudrate, format dropdowns, quick send panel."""
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
from ui.receive_controller import append_header_split, append_rx_group, emit_rx_text, flush_rx_frames, on_clear, on_received, recolor_rx_view, resume_rx_display, snapshot_rx_fragments
from ui.send_controller import abort_file_send, apply_checksum, clear_history, finish_file_send, flush_history_save, on_history_fill, on_quick_send, on_send, on_send_file, prune_history_meta, recall_history, remember_send, remove_history_entry, schedule_history_save, send_file_chunk, show_history, update_history_button, update_payload_size
from ui.connection_controller import ensure_port, notify, on_opened_changed, on_reconnect_toggled, on_worker_error, poll_signals, recolor_status_light, refresh_ports, signals_html, toggle_open, update_port_tooltip
from ui.params_controller import baud_value, check_baud, check_hex_input, encoding, format_rx, newline_bytes, on_header_changed, on_split_mode_changed, on_tx_fmt_changed, persist_newline, refresh_tx_settings_chip, serial_params, split_threshold_ms, ts_prefix, update_input_placeholder
from ui.layout_controller import control_rows, fit_minimum_width, fit_pane_minimums, fit_settings_btn, fit_tx_edit_height, give_data_area_the_room, lock_control_widths, row_need, saved_sizes, widest_row
from ui.config_controller import apply_config, apply_defaults, on_export_config, on_import_config, persist_theme, reset_settings, set_language, set_theme_dark, set_theme_light, set_theme_system
from ui.update_controller import init_update_check, on_update_checked, on_update_found, probe_updates, probe_updates_worker, show_update
from ui.dialogs_controller import diagnostics_text, edit_rules, first_run_hint, show_about, show_port_settings, show_shortcuts
from ui.actions_controller import apply_accessible_names, check_auto_reply, clear_undo, echo_tx, esc_action, find_next, load_file, on_auto_reply_toggled, on_autoscroll_toggled, on_find_text_changed, on_pause_toggled, on_repeat_interval, on_repeat_toggled, on_row_deleted, on_timestamp_toggled, open_rx_context_menu, pause_autoscroll, repeat_value, rx_separator, scroll_rx_bottom, setup_shortcuts, setup_tab_order, stop_repeat, toggle_find_bar, undo_delete, update_counts, update_params_summary
from ui.startup_controller import build_everything, init_language_and_log, init_state, init_timers, init_worker, restore_settings
from ui.regions import (BAUDRATES, DATA_FIRST_H, DATA_FIRST_V,
                        RECEIVE_MAX_LINES, SPLIT_AUTO, SPLIT_HEADER,
                        SPLIT_MANUAL, _fixed_row, build_connection_row,
                        build_data_panes, build_send_group, build_status_bar)
from app.i18n import hex_error_message, tr

def resource_path(rel: str) -> str:
    """Resolve resource path; works in source and PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if os.path.dirname(base).endswith("ui") or base.endswith("ui"):
        base = os.path.dirname(base)
    return os.path.join(base, rel)




# U79: by default the data pane gets the room - the send pane and the quick-send
# column start at their minimum sizes instead of sharing space evenly.
LEGACY_SPLIT_DEFAULTS = {
    "v_split_sizes": ([420, 260], DATA_FIRST_V),
    "split_sizes": ([820, 340], DATA_FIRST_H),
}
QUICK_PANEL_MIN_W = 332   # the quick-send rows need this (U69)
TX_PANE_MIN_H = 190       # the send pane keeps its rows usable (U63)
CLEAR_UNDO_MAX_LINES = 60000  # above this, clearing is not snapshotted (U42)


# -- receive display modes -------------------------------------------------


# -- split modes -------------------------------------------------------------
SPLIT_OFF = 0

# -- timestamp (U96): an on/off switch with a single fixed format ---------------
TS_PREFIX_TEMPLATE = "[{hms}.{ms:03d}] "      # -> [04:02:10.456]

CHECKSUM_KEYS = ["none", "crc16-modbus", "crc16-ccitt", "crc32", "sum8"]

# -- serial parameters (T1); plain values accepted by pyserial ---------------
BYTESIZE_KEYS = [5, 6, 7, 8]
PARITY_KEYS = ["N", "O", "E", "M", "S"]
STOPBITS_KEYS = [1, 1.5, 2]
FLOW_KEYS = ["none", "xonxoff", "rtscts"]
HISTORY_MAX = 50

LOG_DIR = log_dir()   # U34: per-user (or portable) logs, not next to the bundle
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_MAX_SECONDS = 30 * 60
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent
FILE_CHUNK_BYTES = 4096     # file send chunk size (T6)
FILE_CHUNK_MS = 20          # interval between chunks


def _human_bytes(n: int) -> str:
    """Format a byte count for humans (B / KB / MB)."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


class _UpdateProbe(QObject):
    """U127: carries the worker thread's answer back onto the GUI thread."""

    found = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SerialDesk v{__version__}")
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        self.resize(1180, 680)
        self.setMinimumSize(1060, 600)  # U55/U78: the widest control row measures 1059 px

        self._init_worker()

        self._init_state()

        self._init_language_and_log()

        self._init_timers()

        self._build_everything()

        self._restore_settings()


    def _init_worker(self) -> None: return init_worker(self)
    def _init_state(self) -> None: return init_state(self)
    def _init_language_and_log(self) -> None: return init_language_and_log(self)
    def _init_timers(self) -> None: return init_timers(self)
    def _build_everything(self) -> None: return build_everything(self)
    def _restore_settings(self) -> None: return restore_settings(self)

    # -- UI -----------------------------------------------------------------

    def _build_settings_button(self) -> None:
        """Create the Settings button/menu before the row that hosts it (U72)."""
        self._settings_btn = QToolButton()
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.setText(tr("menu.settings"))
        self._settings_btn.setToolTip(tr("menu.settings.tip"))
        self._settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._settings_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._settings_btn.setMinimumHeight(32)       # U110: same height as the row
        self._settings_btn.setMinimumWidth(96)
        self._settings_menu = QMenu(self._settings_btn)
        self._settings_btn.setMenu(self._settings_menu)
        self._fit_settings_btn()
        self.menuBar().hide()   # U72: nothing lives in the menu bar any more

    def _build_menu(self) -> None:
        """Settings menu construction (theme, language, config, panel, update, about, shortcuts). (implementation in ui.menus)."""
        build_menu(self)

    def _on_quick_panel_collapsed(self, collapsed: bool) -> None:
        """Fold the quick-send panel away (or bring it back) and remember it (U88)."""
        # U106: keep the panel widget alive in its rail state instead of hiding it, so
        # the folded panel still shows a labelled strip the user can click to come back.
        self.quick_panel.set_folded(collapsed)
        if hasattr(self, "_quick_panel_act"):
            self._quick_panel_act.setChecked(not collapsed)
        if hasattr(self, "_panel_btn"):
            self._panel_btn.setChecked(not collapsed)
            self._panel_btn.setIcon(QIcon(resource_path(
                "assets/arrow_left_%s.png" % ("dark" if theme.resolved_dark() else "light")))
                if not collapsed else QIcon(resource_path(
                    "assets/arrow_right_%s.png" % ("dark" if theme.resolved_dark() else "light"))))
        save_config({"quick_panel_collapsed": bool(collapsed)})
        self._fit_minimum_width()
        self._notify(tr("qs.collapsed") if collapsed else tr("qs.expanded"),
                     "info", ms=5000 if collapsed else 4000)

    def _toggle_quick_panel(self) -> None:
        """Ctrl+B / menu: fold the quick-send panel when it is showing (U88)."""
        self._on_quick_panel_collapsed(not self.quick_panel.is_folded())

    def _toggle_find_bar(self, show: bool | None = None) -> None: return toggle_find_bar(self, show)

    def _find_next(self, forward: bool = True) -> None: return find_next(self, forward)

    def _esc_action(self) -> None: return esc_action(self)

    # U123: one source of truth for the shortcut list and the help dialog
    SHORTCUT_HELP = (
        ("Ctrl+Return", "sc.send"), ("Ctrl+L", "sc.clear_rx"), ("Ctrl+S", "sc.save_log"),
        ("Ctrl+K", "sc.focus_input"), ("F5", "sc.toggle_open"), ("Ctrl+B", "sc.panel"),
        ("Ctrl+Up", "sc.hist_prev"), ("Ctrl+Down", "sc.hist_next"), ("Ctrl+F", "sc.find"),
        ("Ctrl+,", "sc.settings"), ("Esc", "sc.esc"), ("Delete", "sc.del_quick_row"),
    )

    def _setup_shortcuts(self) -> None: return setup_shortcuts(self)

    def _reset_settings(self) -> None: return reset_settings(self)

    def _apply_defaults(self) -> None: return apply_defaults(self)

    def _apply_autosave_settings(self) -> None: return apply_autosave_settings(self)

    def _show_autosave_settings(self) -> None: return show_autosave_settings(self)

    def _on_autoscroll_toggled(self, checked: bool) -> None: return on_autoscroll_toggled(self, checked)

    def _on_pause_toggled(self, checked: bool) -> None: return on_pause_toggled(self, checked)

    def _on_find_text_changed(self) -> None: return on_find_text_changed(self)

    def _resume_rx_display(self) -> None: return resume_rx_display(self)

    def _open_rx_context_menu(self, pos) -> None: return open_rx_context_menu(self, pos)

    def _on_timestamp_toggled(self, checked: bool) -> None: return on_timestamp_toggled(self, checked)

    def _on_reconnect_toggled(self, checked: bool) -> None: return on_reconnect_toggled(self, checked)

    def _show_port_settings(self) -> None: return show_port_settings(self)

    def _update_payload_size(self) -> None: return update_payload_size(self)

    def _update_port_tooltip(self) -> None: return update_port_tooltip(self)

    def _update_params_summary(self) -> None: return update_params_summary(self)

    def _show_about(self) -> None: return show_about(self)

    # -- update check (U127) -------------------------------------------------

    def _init_update_check(self) -> None: return init_update_check(self)

    def _probe_updates(self) -> None: return probe_updates(self)

    def _probe_updates_worker(self, manual: bool = False) -> None:
        return probe_updates_worker(self, manual)

    def _on_update_found(self, tag: str) -> None: return on_update_found(self, tag)

    def _on_update_checked(self, ok: bool, tag: str) -> None:
        return on_update_checked(self, ok, tag)

    def _show_update(self, tag: str, notify: bool) -> None: return show_update(self, tag, notify)

    def _show_shortcuts(self) -> None: return show_shortcuts(self)

    def _diagnostics_text(self) -> str: return diagnostics_text(self)

    def _first_run_hint(self) -> None: return first_run_hint(self)

    def _set_language(self, lang: str): return set_language(self, lang)

    def _reload_combo(self, combo: QComboBox, items: list[str]):
        """Repopulate a combo box while keeping the current selection."""
        idx = combo.currentIndex()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        combo.setCurrentIndex(min(max(idx, 0), len(items) - 1))
        combo.blockSignals(False)

    def retranslate(self) -> None:
        """Re-apply every translated string after a language change (ui.retranslate)."""
        QTimer.singleShot(0, self._fit_minimum_width)     # U81: labels change size
        QTimer.singleShot(150, self._fit_minimum_width)   # second pass once laid out
        retranslate_ui(self)

    def _set_theme_system(self): return set_theme_system(self)

    def _set_theme_dark(self): return set_theme_dark(self)

    def _set_theme_light(self): return set_theme_light(self)

    def _persist_theme(self, choice: str): return persist_theme(self, choice)

    def _build_status_bar(self) -> None:
        """status bar region (builder lives in ui.regions)."""
        build_status_bar(self)
    def _build_send_group(self) -> None:
        """send group region (builder lives in ui.regions)."""
        build_send_group(self)
    def _build_connection_row(self, root: QWidget) -> None:
        """connection row region (builder lives in ui.regions)."""
        build_connection_row(self, root)
    def _build_data_panes(self, root: QWidget) -> None:
        """data panes region (builder lives in ui.regions)."""
        build_data_panes(self, root)
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)   # keep the connect row close to the top
        root.setSpacing(6)

        # --- connection bar -------------------------------------------------
        self._build_connection_row(root)
        self._build_data_panes(root)
        self._build_status_bar()
        self.setCentralWidget(central)

    def _control_rows(self) -> list: return control_rows(self)

    def _row_need(self, layout: QHBoxLayout) -> int: return row_need(self, layout)

    def _widest_row(self) -> tuple: return widest_row(self)

    def _fit_pane_minimums(self) -> None: return fit_pane_minimums(self)

    def _lock_control_widths(self) -> None: return lock_control_widths(self)

    def _fit_minimum_width(self) -> None: return fit_minimum_width(self)

    def _give_data_area_the_room(self) -> None: return give_data_area_the_room(self)

    def _saved_sizes(self, key: str, default: list) -> list: return saved_sizes(self, key, default)

    NEWLINE_BYTES = {"none": b"", "cr": b"\r", "lf": b"\n", "crlf": b"\r\n"}
    NEWLINE_KEYS = ("none", "cr", "lf", "crlf")

    def _newline_bytes(self) -> bytes: return newline_bytes(self)

    def _persist_newline(self, _index: int = 0) -> None: return persist_newline(self, _index)

    def eventFilter(self, obj: QObject, event: QEvent):  # noqa: N802 - Qt naming
        """U120: while the panel is folded, hovering the right edge brings the rail back."""
        if (event.type() == QEvent.Type.MouseMove and hasattr(self, "quick_panel")
                and self.quick_panel.is_folded()):
            try:
                pos = event.globalPosition().toPoint()
                frame = self.frameGeometry()
                near = (0 <= frame.right() - pos.x() <= 12
                        and frame.top() <= pos.y() <= frame.bottom())
                self.quick_panel.set_rail_visible(near)
            except (AttributeError, TypeError):
                pass
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent):  # noqa: N802 - Qt naming
        """U119: the input follows the pane when the window is resized."""
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_tx_edit_height)

    def changeEvent(self, event: QEvent):  # noqa: N802 - Qt naming
        """U117: a DPI or screen change alters every metric we measured the floors
        from, so recompute them instead of letting the panes clip their contents."""
        if event.type() in (QEvent.Type.ScreenChangeInternal,
                            QEvent.Type.DevicePixelRatioChange):
            QTimer.singleShot(0, self._fit_minimum_width)
        super().changeEvent(event)

    def _fit_tx_edit_height(self) -> None: return fit_tx_edit_height(self)

    def _refresh_tx_settings_chip(self) -> None: return refresh_tx_settings_chip(self)

    def _fit_settings_btn(self) -> None: return fit_settings_btn(self)

    def _apply_accessible_names(self) -> None: return apply_accessible_names(self)

    def _setup_tab_order(self) -> None: return setup_tab_order(self)

    # -- notifications (U30/U36/U37/U38) --------------------------------------

    def _notify(self, msg: str, level: str = 'info', ms: int | None = None) -> None:  # moved to ui/connection_controller.py
        """See ui/connection_controller.py."""
        return notify(self, msg, level, ms)

    def _recolor_status_light(self) -> None: return recolor_status_light(self)

    def _on_row_deleted(self, payloads: list[str]) -> None: return on_row_deleted(self, payloads)

    def _undo_delete(self) -> None: return undo_delete(self)

    def _clear_undo(self) -> None: return clear_undo(self)

    def _ensure_port(self) -> bool: return ensure_port(self)

    def _on_send_error(self, kind: str, detail: str) -> None:
        """Report a write that failed on the worker thread (U52: GUI never blocks)."""
        if kind in ("timeout", "queue", "cts", "degraded"):
            self._stop_repeat()      # U64: stop the loop instead of hammering a stuck device
        if kind == "timeout":
            self._notify(tr("err.tx.timeout"), "error")
        elif kind == "queue":
            self._notify(tr("err.tx.queue", n=detail), "error")
        elif kind == "closed":
            self._notify(tr("err.tx.closed"), "error")
        elif kind == "cts":
            self._notify(tr("err.tx.cts"), "warn")     # U65: dropped, not fatal
        elif kind == "degraded":
            self._notify(tr("err.tx.degraded"), "error")
        else:
            self._notify(tr("err.tx.io", e=detail), "error")

    def _schedule_history_save(self) -> None: return schedule_history_save(self)

    def _flush_history_save(self) -> None: return flush_history_save(self)

    def _on_worker_error(self, text: str) -> None: return on_worker_error(self, text)

    def _check_hex_input(self) -> None: return check_hex_input(self)


    # -- helpers ---------------------------------------------------------------

    # -- config import / export (T15) ----------------------------------------

    def on_export_config(self) -> None:
                                        """Qt slot: export the configuration (ui/config_controller)."""
                                        return on_export_config(self)

    def on_import_config(self) -> None:
                                        """Qt slot: import a configuration file (ui/config_controller)."""
                                        return on_import_config(self)

    def _apply_config(self) -> None: return apply_config(self)

    # -- auto reply (T10) ----------------------------------------------------

    def _on_auto_reply_toggled(self, checked: bool) -> None: return on_auto_reply_toggled(self, checked)

    def _edit_rules(self) -> None: return edit_rules(self)

    def _check_auto_reply(self, data: bytes) -> None: return check_auto_reply(self, data)

    def _recolor_rx_view(self) -> None: return recolor_rx_view(self)

    # -- modem status lines (T9) ---------------------------------------------

    def _poll_signals(self) -> None: return poll_signals(self)

    def _signals_html(self, sig: dict) -> str: return signals_html(self, sig)

    # -- file send (T6) ------------------------------------------------------

    def _baud_value(self) -> int: return baud_value(self)

    def _load_file(self, path: str) -> bytes: return load_file(self, path)

    def on_send_file(self):
                            """Qt slot: send the file picked in the dialog (ui/send_controller)."""
                            return on_send_file(self)

    def _send_file_chunk(self): return send_file_chunk(self)

    def _finish_file_send(self): return finish_file_send(self)

    def _abort_file_send(self): return abort_file_send(self)

    # -- receive log to file (T4) -------------------------------------------

    def _log_header_text(self) -> str: return log_header_text(self)

    def _log_open(self) -> None: return log_open(self)

    def _log_close(self) -> None: return log_close(self)

    def _log_append(self, text: str) -> None: return log_append(self, text)

    def on_save_log_quick(self) -> None:
                                         """Qt slot: save the receive log into the log folder (ui/log_controller)."""
                                         return on_save_log_quick(self)

    def on_save_log_as(self) -> None:
                                      """Qt slot: save the receive log to a chosen path (ui/log_controller)."""
                                      return on_save_log_as(self)

    # -- quick helpers --------------------------------------------------------

    def _emit_rx_text(self, text: str, tx: bool = False, meta: bool = False, log: bool = True) -> None:  # moved to ui/receive_controller.py
        """See ui/receive_controller.py."""
        return emit_rx_text(self, text, tx, meta, log)

    def eventFilter(self, obj: QObject, event: QEvent):  # noqa: N802 - Qt naming
        """Delete the highlighted history entry with the keyboard (U77)."""
        return super().eventFilter(obj, event)

    def _snapshot_rx_fragments(self) -> list: return snapshot_rx_fragments(self)

    def _scroll_rx_bottom(self) -> None: return scroll_rx_bottom(self)

    def _pause_autoscroll(self, _action: int = 0) -> None: return pause_autoscroll(self, _action)

    def _rx_separator(self) -> str: return rx_separator(self)

    def _append_rx_group(self, text: str, ts: float, new_line: bool) -> None:  # moved to ui/receive_controller.py
        """See ui/receive_controller.py."""
        return append_rx_group(self, text, ts, new_line)

    def _echo_tx(self, data: bytes) -> None: return echo_tx(self, data)

    def _show_history(self) -> None: return show_history(self)

    def _on_history_fill(self, text: str) -> None: return on_history_fill(self, text)

    def _recall_history(self, step: int) -> None: return recall_history(self, step)

    def _prune_history_meta(self, raw: list) -> dict: return prune_history_meta(self, raw)

    def _remember_send(self, text: str, fmt: str = '', nbytes: int | None = None):  # moved to ui/send_controller.py
        """See ui/send_controller.py."""
        return remember_send(self, text, fmt, nbytes)

    def _update_history_button(self) -> None: return update_history_button(self)

    def _remove_history_entry(self, row: int) -> None: return remove_history_entry(self, row)

    def _clear_history(self) -> None: return clear_history(self)

    def _on_repeat_toggled(self, checked: bool): return on_repeat_toggled(self, checked)

    def _repeat_value(self) -> int: return repeat_value(self)

    def _on_repeat_interval(self, _text: str): return on_repeat_interval(self, _text)

    def _stop_repeat(self): return stop_repeat(self)

    def _serial_params(self) -> dict: return serial_params(self)

    def _on_tx_fmt_changed(self, index: int): return on_tx_fmt_changed(self, index)

    def _update_input_placeholder(self) -> None: return update_input_placeholder(self)

    def _on_split_mode_changed(self, index: int): return on_split_mode_changed(self, index)

    def _on_header_changed(self, text: str): return on_header_changed(self, text)

    def _split_threshold_ms(self) -> float | None: return split_threshold_ms(self)

    def _encoding(self) -> str: return encoding(self)

    def _format_rx(self, data: bytes) -> str: return format_rx(self, data)

    def _ts_prefix(self, ts: float) -> str: return ts_prefix(self, ts)

    # -- actions -----------------------------------------------------------------

    def refresh_ports(self):
                             """Qt slot: repopulate the port list (ui/connection_controller)."""
                             return refresh_ports(self)

    def toggle_open(self):
                           """Qt slot: open or close the serial port (ui/connection_controller)."""
                           return toggle_open(self)

    def on_opened_changed(self, opened: bool):
                                               """Qt slot: reflect a port open/close in the UI (ui/connection_controller)."""
                                               return on_opened_changed(self, opened)

    def _check_baud(self, text: str) -> None: return check_baud(self, text)

    def _apply_checksum(self, payload: bytes) -> bytes: return apply_checksum(self, payload)

    def on_send(self):
                       """Qt slot: send the input box contents (ui/send_controller)."""
                       return on_send(self)

    def on_quick_send(self, payload: bytes):
                                             """Qt slot: send one quick-send payload (ui/send_controller)."""
                                             return on_quick_send(self, payload)

    def on_received(self, ts: float, data: bytes):
                                                   """Qt slot: handle a chunk of received bytes (ui/receive_controller)."""
                                                   return on_received(self, ts, data)

    def _flush_rx_frames(self) -> None: return flush_rx_frames(self)
    def _append_header_split(self, data: bytes, ts: float): return append_header_split(self, data, ts)

    def on_log_line(self, line: str):
                                      """Qt slot: append a line to the log sink (ui/log_controller)."""
                                      return on_log_line(self, line)

    def on_clear(self):
                        """Qt slot: clear the receive pane and counters (ui/receive_controller)."""
                        return on_clear(self)
    # -- counters (refactor step 1: thin views onto app.stats.SessionStats) -----

    @property
    def rx_bytes(self) -> int:
        """Received byte count, a view onto SessionStats."""
        return self._stats.rx_bytes

    @rx_bytes.setter
    def rx_bytes(self, value: int) -> None:
        """Set the received byte count."""
        self._stats.rx_bytes = int(value)

    @property
    def tx_bytes(self) -> int:
        """Transmitted byte count, a view onto SessionStats."""
        return self._stats.tx_bytes

    @tx_bytes.setter
    def tx_bytes(self, value: int) -> None:
        """Set the transmitted byte count."""
        self._stats.tx_bytes = int(value)

    @property
    def _sent_count(self) -> int:
        return self._stats.sends

    @_sent_count.setter
    def _sent_count(self, value: int) -> None:
        self._stats.sends = int(value)

    def update_counts(self):
                             """Qt slot: refresh the status-bar counters (ui/actions_controller)."""
                             return update_counts(self)

    def showEvent(self, event: QShowEvent):  # noqa: N802 - Qt naming
        """On first show, let the data area claim its room before the user sees a jump."""
        super().showEvent(event)
        theme.apply_native_dark(self, bool(theme.resolved_dark()))   # U51 (frame exists now)
        if not getattr(self, "_split_room_done", False):
            self._split_room_done = True

            def _first_layout() -> None:
                self._give_data_area_the_room()   # U79
                self._fit_minimum_width()         # U81

            QTimer.singleShot(0, _first_layout)

    def closeEvent(self, event: QCloseEvent):
        """Persist the layout, stop the timers and shut the worker down without hanging."""
        self._sig_timer.stop()
        self._flush_history_save()
        try:   # U35: remember the layout the user dragged
            config = load_config()
            config["split_sizes"] = self._splitter.sizes()
            config["v_split_sizes"] = self._v_splitter.sizes()
            save_config(config)
        except (AttributeError, RuntimeError):
            pass
        self.worker.close_port()     # U64: non-blocking; the worker closes the port
        self.worker.wait(1500)       # bounded wait so quitting can never hang
        self._log_close()
        self.refresh_timer.stop()
        self.quick_panel.save()
        self.worker.close_port()
        super().closeEvent(event)