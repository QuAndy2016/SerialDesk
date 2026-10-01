"""Main window: port selection, baudrate, format dropdowns, quick send panel."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QIcon

from PySide6.QtGui import (
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
from app import __version__
from app.config import CONFIG_PATH, data_dir, load_config, log_dir, save_config
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.autosave_dialog import AutoSaveDialog
from ui.history_dialog import HistoryDialog
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from app import i18n
from app.i18n import hex_error_message, tr

def resource_path(rel: str) -> str:
    """Resolve resource path; works in source and PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if os.path.dirname(base).endswith("ui") or base.endswith("ui"):
        base = os.path.dirname(base)
    return os.path.join(base, rel)


def _fixed_row(layout) -> QWidget:
    """Wrap a control row so it keeps its natural height (U70).

    A nested layout handed straight to a vertical box absorbs spare space and
    centres its widgets, which made the split row drift downwards whenever the
    receive group grew. A holder with a Fixed vertical policy pins it to the top.
    """
    holder = QWidget()
    layout.setContentsMargins(0, 2, 0, 2)   # U92: drop Qt's default 9 px top/bottom, which
    holder.setLayout(layout)                #      made every control row 18 px taller than
    holder.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return holder                            #      the widgets inside it needed


RECEIVE_MAX_LINES = 20000   # receive-pane display cap (U45)
# U79: by default the data pane gets the room - the send pane and the quick-send
# column start at their minimum sizes instead of sharing space evenly.
DATA_FIRST_V = [520, 190]
DATA_FIRST_H = [880, 332]
LEGACY_SPLIT_DEFAULTS = {
    "v_split_sizes": ([420, 260], DATA_FIRST_V),
    "split_sizes": ([820, 340], DATA_FIRST_H),
}
QUICK_PANEL_MIN_W = 332   # the quick-send rows need this (U69)
TX_PANE_MIN_H = 190       # the send pane keeps its rows usable (U63)
CLEAR_UNDO_MAX_LINES = 60000  # above this, clearing is not snapshotted (U42)

BAUDRATES = [
    110, 330, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400,
    56000, 57600, 115200, 128000, 230400, 256000, 460800, 500000,
    512000, 600000, 750000, 921600, 1000000, 1500000, 2000000, 3000000,
]

# -- receive display modes -------------------------------------------------
RX_ASCII = 0
RX_HEX = 1
RX_HEX_ASCII = 2

# -- split modes -------------------------------------------------------------
SPLIT_OFF = 0
SPLIT_AUTO = 1
SPLIT_MANUAL = 2
SPLIT_HEADER = 3

# -- timestamp (U96): an on/off switch with a single fixed format ---------------
TS_PREFIX_TEMPLATE = "[{hms}.{ms:03d}] "      # -> [04:02:10.456]

CHECKSUM_KEYS = ["none", "crc16-modbus", "crc16-ccitt", "crc32", "sum8"]

# -- serial parameters (T1); plain values accepted by pyserial ---------------
BYTESIZE_KEYS = [5, 6, 7, 8]
PARITY_KEYS = ["N", "O", "E", "M", "S"]
STOPBITS_KEYS = [1, 1.5, 2]
FLOW_KEYS = ["none", "xonxoff", "rtscts"]
HISTORY_MAX = 50
from app.config import log_dir

LOG_DIR = log_dir()   # U34: per-user (or portable) logs, not next to the bundle
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_MAX_SECONDS = 30 * 60
MARK_RX = "<- "          # direction markers, ASCII so monospace stays aligned (U26)
MARK_TX = "-> "
FILE_CHUNK_BYTES = 4096     # file send chunk size (T6)
FILE_CHUNK_MS = 20          # interval between chunks


def _human_bytes(n: int) -> str:
    """Format a byte count for humans (B / KB / MB)."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SerialDesk v{__version__}")
        self.setWindowIcon(QIcon(resource_path("assets/icon.ico")))
        self.resize(1180, 680)
        self.setMinimumSize(1060, 600)  # U55/U78: the widest control row measures 1059 px

        self.worker = SerialWorker(self)
        self.worker.received.connect(self.on_received)
        self.worker.log.connect(self.on_log_line)
        self.worker.opened.connect(self.on_opened_changed)
        self.worker.error.connect(self._on_worker_error)
        self.worker.send_error.connect(self._on_send_error)
        self.worker.reconnecting.connect(
            lambda n: self._notify(tr("conn.reconnecting", n=n), "warn"))   # T14
        self.worker.reconnected.connect(lambda: self._notify(tr("conn.reconnected"), "info"))
        self.worker.disconnected.connect(lambda _r: self._notify(tr("conn.lost"), "error"))

        self.rx_bytes = 0
        self.tx_bytes = 0
        self._line_is_tx = False   # U59: is the current display line a TX echo?
        self._cap_warned = False   # U45: warn once when the display cap is reached
        self._last_ts: float | None = None
        self._clock_offset = time.time() - time.monotonic()

        # initial language from config (default: follow system)
        i18n.set_language(str(load_config().get("language", "system")))

        self._log_fp = None
        self._log_started = 0.0
        self._log_bytes = 0
        _cfg0 = load_config()                       # U75: configurable auto-save
        self._log_max_bytes = max(1, int(_cfg0.get("autosave_max_mb", 2) or 2)) * 1024 * 1024
        self._log_max_seconds = max(1, int(_cfg0.get("autosave_max_minutes", 30) or 30)) * 60
        self._log_dir = str(_cfg0.get("log_dir") or "") or LOG_DIR
        self._send_history: list[str] = []
        self._history_meta: dict = {}   # v0.10.0: text -> {"fmt", "b", "ts"}
        self._history_dlg = None        # U87: lazily created non-modal popup
        self._recall_index = -1         # U87: Ctrl+Up/Down position in the history
        self._recall_draft = ""
        self._sent_count = 0
        self._repeat_timer = QTimer(self)
        self._repeat_timer.timeout.connect(self.on_send)
        self._file_timer = QTimer(self)
        self._file_timer.timeout.connect(self._send_file_chunk)
        self._sig_timer = QTimer(self)
        self._sig_timer.timeout.connect(self._poll_signals)
        self._sig_timer.start(50)
        self._cfg_save_timer = QTimer(self)     # U52: debounced config persistence
        # U57: merge USB-fragmented chunks before deciding a line break
        _settle = float(load_config().get("rx_settle_ms", DEFAULT_SETTLE_MS) or DEFAULT_SETTLE_MS)
        self._frames = FrameAssembler(settle_ms=_settle)
        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.timeout.connect(self._flush_rx_frames)
        self._cfg_save_timer.setSingleShot(True)
        self._cfg_save_timer.timeout.connect(self._flush_history_save)
        self._file_data = b""
        self._file_pos = 0
        self._file_path = ""

        self._build_settings_button()   # U72: the connect row hosts this button
        self._build_ui()
        self._build_menu()
        if load_config().get("quick_panel_collapsed"):     # U88: restore the folded state
            self._on_quick_panel_collapsed(True)
        self._setup_tab_order()
        self._setup_shortcuts()
        self._first_run_hint()
        self._autosave_dlg = AutoSaveDialog(self)              # U75
        self._autosave_dlg.settingsChanged.connect(self._apply_autosave_settings)
        _cfg = load_config()
        self._autosave_dlg.set_values(
            enabled=bool(_cfg.get("autosave_enabled", False)),
            max_mb=int(_cfg.get("autosave_max_mb", 2) or 2),
            max_minutes=int(_cfg.get("autosave_max_minutes", 30) or 30),
            folder=self._log_dir)

        # send history (T5) from config
        _hcfg = load_config()
        self._send_history = [str(h) for h in _hcfg.get("send_history", [])
                              if str(h).strip()][:HISTORY_MAX]
        self._history_meta = self._prune_history_meta(_hcfg.get("history_meta"))
        self._update_history_button()

        # auto-reply rules (T10) from config
        cfg = load_config()
        self._auto_rules = [r for r in cfg.get("auto_reply", []) if isinstance(r, dict)]
        self._reply_buf = b""
        self.auto_reply_act.setChecked(bool(cfg.get("auto_reply_enabled", False)))

        # initial theme from config (default: follow system)
        choice = load_config().get("theme", "system")
        if choice == "dark":
            theme.set_override(True)
        elif choice == "light":
            theme.set_override(False)
        else:
            theme.set_override(None)
        theme.apply_theme(QApplication.instance())
        self._recolor_status_light()
        theme.apply_native_dark(self, bool(theme.resolved_dark()))

        self.worker.set_auto_reconnect(
            bool(load_config().get("auto_reconnect", False)))    # T14

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_ports)
        self.refresh_timer.start(3000)

    # -- UI -----------------------------------------------------------------

    def _build_settings_button(self) -> None:
        """Create the Settings button/menu before the row that hosts it (U72)."""
        self._settings_btn = QToolButton()
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.setText(tr("menu.settings"))
        self._settings_btn.setToolTip(tr("menu.settings"))
        self._settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._settings_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._settings_btn.setMinimumHeight(26)
        self._settings_menu = QMenu(self._settings_btn)
        self._settings_btn.setMenu(self._settings_menu)
        self._fit_settings_btn()
        self.menuBar().hide()   # U72: nothing lives in the menu bar any more

    def _build_menu(self):
        # U33: one "Settings" button in the top-right corner holds theme/language/config
        view_menu = self._settings_menu
        # U88: the panel can be folded away, so it needs an entry outside itself
        self._quick_panel_act = QAction(tr("menu.quick_panel"), self)
        self._quick_panel_act.setCheckable(True)
        self._quick_panel_act.setChecked(True)
        self._quick_panel_act.triggered.connect(
            lambda: self._on_quick_panel_collapsed(not self._quick_panel_act.isChecked()))
        view_menu.addAction(self._quick_panel_act)
        view_menu.addSeparator()
        self._theme_menu = view_menu.addMenu(tr("theme.menu"))
        view_menu = self._theme_menu
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)

        choice = load_config().get("theme", "system")

        self._theme_system = QAction(tr("theme.system"), self, checkable=True)
        self._theme_dark = QAction(tr("theme.dark"), self, checkable=True)
        self._theme_light = QAction(tr("theme.light"), self, checkable=True)

        for act in (self._theme_system, self._theme_dark, self._theme_light):
            self._theme_group.addAction(act)
            view_menu.addAction(act)

        if choice == "dark":
            self._theme_dark.setChecked(True)
        elif choice == "light":
            self._theme_light.setChecked(True)
        else:
            self._theme_system.setChecked(True)

        self._theme_system.triggered.connect(self._set_theme_system)
        self._theme_dark.triggered.connect(self._set_theme_dark)
        self._theme_light.triggered.connect(self._set_theme_light)

        # language submenu (U19) - sibling of the theme submenu inside Settings
        self._lang_menu = self._settings_menu.addMenu(tr("menu.language"))
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        self._lang_system = QAction(tr("lang.system"), self, checkable=True)
        self._lang_zh = QAction(tr("lang.zh"), self, checkable=True)
        self._lang_en = QAction(tr("lang.en"), self, checkable=True)
        for act in (self._lang_system, self._lang_zh, self._lang_en):
            self._lang_group.addAction(act)
            self._lang_menu.addAction(act)
        lang_now = i18n.get_language()
        {"zh": self._lang_zh, "en": self._lang_en}.get(lang_now, self._lang_system).setChecked(True)
        self._lang_system.triggered.connect(lambda: self._set_language("system"))
        self._lang_zh.triggered.connect(lambda: self._set_language("zh"))
        self._lang_en.triggered.connect(lambda: self._set_language("en"))

        # config import / export (T15)
        self._cfg_menu = self._settings_menu.addMenu(tr("cfg.menu"))
        self._reset_act = QAction(tr("cfg.reset"), self)
        self._reset_act.triggered.connect(self._reset_settings)
        self._settings_menu.addAction(self._reset_act)
        self._settings_menu.addSeparator()

        self._cfg_export_act = QAction(tr("cfg.export"), self)
        self._cfg_import_act = QAction(tr("cfg.import"), self)
        self._cfg_export_act.triggered.connect(self.on_export_config)
        self._cfg_import_act.triggered.connect(self.on_import_config)
        self._cfg_menu.addAction(self._cfg_export_act)
        self._cfg_menu.addAction(self._cfg_import_act)

        # U44: about box (version is otherwise invisible in the UI)
        self._autosave_act = QAction(tr("as.menu"), self)
        self._autosave_act.setToolTip(tr("as.note"))
        self._autosave_act.triggered.connect(self._show_autosave_settings)
        self._settings_menu.addAction(self._autosave_act)

        # U98: the auto-reply switch and its rules belong with the settings, not in
        # the middle of the send row next to the file button where they used to sit.
        self.auto_reply_act = QAction(tr("rb.enable"), self, checkable=True)
        self.auto_reply_act.setToolTip(tr("rb.enable.tip"))
        self.auto_reply_act.setChecked(bool(load_config().get("auto_reply_enabled", False)))
        self.auto_reply_act.toggled.connect(self._on_auto_reply_toggled)
        self._settings_menu.addAction(self.auto_reply_act)

        self.rules_act = QAction(tr("rb.rules.menu"), self)
        self.rules_act.triggered.connect(self._edit_rules)
        self._settings_menu.addAction(self.rules_act)

        self._settings_menu.addSeparator()
        self._reconnect_act = QAction(tr("conn.auto"), self, checkable=True)
        self._reconnect_act.setToolTip(tr("conn.auto.tip"))
        self._reconnect_act.setChecked(bool(load_config().get("auto_reconnect", False)))
        self._reconnect_act.toggled.connect(self._on_reconnect_toggled)
        self._settings_menu.addAction(self._reconnect_act)

        self._about_act = QAction(tr("about.menu"), self)
        self._about_act.triggered.connect(self._show_about)
        self._settings_menu.addAction(self._about_act)

    def _on_quick_panel_collapsed(self, collapsed: bool) -> None:
        """Fold the quick-send panel away (or bring it back) and remember it (U88)."""
        # U106: keep the panel widget alive in its rail state instead of hiding it, so
        # the folded panel still shows a labelled strip the user can click to come back.
        self.quick_panel.set_folded(collapsed)
        if hasattr(self, "_quick_panel_act"):
            self._quick_panel_act.setChecked(not collapsed)
        save_config({"quick_panel_collapsed": bool(collapsed)})
        self._fit_minimum_width()
        self._notify(tr("qs.collapsed") if collapsed else tr("qs.expanded"),
                     "info", ms=5000 if collapsed else 4000)

    def _toggle_quick_panel(self) -> None:
        """Ctrl+B / menu: fold the quick-send panel when it is showing (U88)."""
        self._on_quick_panel_collapsed(not self.quick_panel.is_folded())

    def _toggle_find_bar(self, show: bool | None = None) -> None:
        """Show/hide the receive find bar (U41)."""
        visible = (not self._find_bar.isVisible()) if show is None else show
        self._find_bar.setVisible(visible)
        if visible:
            self.find_edit.setFocus()
            self.find_edit.selectAll()

    def _find_next(self, forward: bool = True) -> None:
        """Jump to the next/previous match in the receive pane (U41)."""
        text = self.find_edit.text()
        if not text:
            return
        flags = QTextDocument.FindFlag(0) if forward else QTextDocument.FindFlag.FindBackward
        if not self.rx_view.find(text, flags):
            cursor = self.rx_view.textCursor()
            # wrap around: forward restarts at the top, backward at the bottom
            cursor.movePosition(QTextCursor.MoveOperation.Start if forward
                                else QTextCursor.MoveOperation.End)
            self.rx_view.setTextCursor(cursor)
            if not self.rx_view.find(text, flags):
                self._notify(tr("find.none", text=text), "warn", ms=3000)
                return
        self.rx_view.setFocus()

    def _esc_action(self) -> None:
        """Esc: leave the find bar, else stop repeat/sequence (U39)."""
        if self._find_bar.isVisible():
            self._toggle_find_bar(False)
            return
        self._stop_repeat()
        self.quick_panel.stop_sequence()

    def _setup_shortcuts(self) -> None:
        """Daily-flow keyboard shortcuts (U39)."""
        for seq, handler in (
            ("Ctrl+Return", self.on_send),
            ("Ctrl+L", self.on_clear),
            ("Ctrl+S", self.on_save_log_quick),
            ("Ctrl+K", lambda: self.tx_edit.setFocus()),
            ("F5", self.toggle_open),
            ("Ctrl+B", self._toggle_quick_panel),          # U88: fold/unfold the panel
            ("Ctrl+Up", lambda: self._recall_history(1)),    # U87: older command
            ("Ctrl+Down", lambda: self._recall_history(-1)),  # U87: newer command
            ("Ctrl+F", lambda: self._toggle_find_bar(True)),
            ("Esc", self._esc_action),
        ):
            QShortcut(QKeySequence(seq), self).activated.connect(handler)

    def _reset_settings(self) -> None:
        """Restore factory defaults after backing the current config up (U76)."""
        box = QMessageBox(self)
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
            self._notify(tr("cfg.reset.fail", e=exc), "error")
            return
        self._apply_defaults()
        save_config({"language": "system", "theme": "system"})
        # the full path is long enough to crowd the status bar, so it lives in the
        # tooltip while the message stays short (U82)
        self.statusBar().setToolTip(tr("cfg.reset.done.tip", path=backup or "-"))
        self._notify(tr("cfg.reset.done"), "info", ms=8000)

    def _apply_defaults(self) -> None:
        """Put every user-facing option back to its default value (U76)."""
        self._set_theme_system()
        self._set_language("system")
        self._reconnect_act.setChecked(False)
        self._log_dir = log_dir()
        self._log_max_bytes = 2 * 1024 * 1024
        self._log_max_seconds = 30 * 60
        self._autosave_dlg.set_values(enabled=False, max_mb=2, max_minutes=30, folder=self._log_dir)
        self._apply_autosave_settings()
        self.autoscroll_check.setChecked(True)
        self.ts_check.setChecked(True)          # U96: timestamps are on by default
        self._send_history = []
        self._update_history_button()
        self._auto_rules = []
        self.auto_reply_act.setChecked(False)
        self._sent_count = 0
        self.sent_lbl.setText(tr("tx.sent_count", n=0))
        # U82: restoring defaults must also restore the data-first proportions, and
        # they are re-measured so a maximised window gives the log every spare pixel
        self._custom_split_sizes = False
        self._split_room_done = True
        QTimer.singleShot(0, self._give_data_area_the_room)
        self.quick_panel.set_folded(False)      # U88/U106: defaults = panel shown again
        if hasattr(self, "_quick_panel_act"):
            self._quick_panel_act.setChecked(True)
        self.quick_panel.reload_from_config()   # seeds the default rows when config is gone
        self._update_params_summary()

    def _apply_autosave_settings(self) -> None:
        """Apply the auto-save dialog values live and remember them (U75)."""
        values = self._autosave_dlg.values()
        self._log_max_bytes = max(1, int(values["max_mb"])) * 1024 * 1024
        self._log_max_seconds = max(1, int(values["max_minutes"])) * 60
        if values["dir"]:
            self._log_dir = values["dir"]
        config = load_config()
        config["autosave_enabled"] = bool(values["enabled"])
        config["autosave_max_mb"] = int(values["max_mb"])
        config["autosave_max_minutes"] = int(values["max_minutes"])
        config["log_dir"] = self._log_dir
        save_config(config)
        if values["enabled"]:
            if self._log_fp is None:
                self._log_open()
            if self._log_fp is None:
                # U97: opening the file failed - the dialog is the only switch now, so
                # it must fall back to "off" instead of showing an enabled state.
                config["autosave_enabled"] = False
                save_config(config)
                self._autosave_dlg.set_values(
                    enabled=False, max_mb=max(1, int(values["max_mb"])),
                    max_minutes=max(1, int(values["max_minutes"])), folder=self._log_dir)
        else:
            self._log_close()

    def _show_autosave_settings(self) -> None:
        """Open the auto-save settings dialog (U75)."""
        self._autosave_dlg.show()
        self._autosave_dlg.raise_()
        self._autosave_dlg.activateWindow()

    def _on_autoscroll_toggled(self, checked: bool) -> None:
        """Remember the auto-scroll preference (U75)."""
        config = load_config()
        config["autoscroll"] = bool(checked)
        save_config(config)

    def _on_timestamp_toggled(self, checked: bool) -> None:
        """Remember the timestamp preference (U96)."""
        config = load_config()
        config["timestamp_on"] = bool(checked)
        save_config(config)

    def _on_reconnect_toggled(self, checked: bool) -> None:
        """Persist and apply the auto-reconnect preference (T14)."""
        self.worker.set_auto_reconnect(checked)
        config = load_config()
        config["auto_reconnect"] = bool(checked)
        save_config(config)
        self._notify(tr("conn.auto.on") if checked else tr("conn.auto.off"), "info", ms=3000)

    def _show_port_settings(self) -> None:
        """Show the port-settings dialog (U35-P3), reflecting the current lock state."""
        self._port_dlg.set_port_open(self.worker.is_open())   # U73
        self._port_dlg.show()
        self._port_dlg.raise_()
        self._port_dlg.activateWindow()

    def _update_payload_size(self) -> None:
        """Show how many bytes the current input would send (U74)."""
        text = self.tx_edit.toPlainText().strip()
        if not text:
            self.tx_size_lbl.setText("")
            return
        try:
            if self.tx_fmt_combo.currentIndex() == 0:
                payload = hex_str_to_bytes(text)
            else:
                payload = encode_text(text, self._encoding(), self.escape_check.isChecked())
        except ValueError:
            self.tx_size_lbl.setText(tr("tx.payload.bad"))
            return
        payload = self._apply_checksum(payload)
        if self.tx_fmt_combo.currentIndex() == 1 and self.crlf_check.isChecked():
            payload += b"\r\n"
        self.tx_size_lbl.setText(tr("tx.payload", n=len(payload)))

    def _update_port_tooltip(self) -> None:
        """Full device description of the selected port, in the tooltip (U83)."""
        idx = self.port_combo.currentIndex()
        full = self.port_combo.itemData(idx, Qt.ItemDataRole.ToolTipRole) if idx >= 0 else None
        if full:
            self.port_combo.setToolTip(str(full))

    def _update_params_summary(self) -> None:
        """One-line summary of the low-frequency settings (U35-P3)."""
        parity = ["N", "O", "E", "M", "S"][max(0, min(4, self.parity_combo.currentIndex()))]
        data = self.dbits_combo.currentText()
        stop = self.stopbits_combo.currentText()
        flow = self.flow_combo.currentText()
        enc = self.encoding_combo.currentText()
        text = f"{data}{parity}{stop} · {flow} · {enc}"
        if len(text) > 16:                      # U78: elide instead of widening the row
            text = text[:15] + "…"
        self.params_summary.setText(text + " ▾")

    def _show_about(self) -> None:
        """About box: version, runtime versions and the project link (U44)."""
        import PySide6
        import serial as _serial

        box = QMessageBox(self)
        box.setWindowTitle(tr("about.title"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr("about.text", version=__version__,
                       pyside=PySide6.__version__, pyserial=_serial.__version__))
        box.setIcon(QMessageBox.Icon.Information)
        box.exec()

    def _first_run_hint(self) -> None:
        """One restrained hint on the very first launch (U48)."""
        cfg = load_config()
        if cfg.get("first_run_done"):
            return
        self._notify(tr("hint.first_run"), "info", ms=8000)
        cfg["first_run_done"] = True
        save_config(cfg)

    def _set_language(self, lang: str):
        """Switch UI language, persist the choice, rebuild every visible string."""
        i18n.set_language(lang)
        config = load_config()
        config["language"] = lang
        save_config(config)
        self.retranslate()

    def _reload_combo(self, combo, items):
        """Repopulate a combo box while keeping the current selection."""
        idx = combo.currentIndex()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        combo.setCurrentIndex(min(max(idx, 0), len(items) - 1))
        combo.blockSignals(False)

    def retranslate(self):
        QTimer.singleShot(0, self._fit_minimum_width)     # U81: labels change size
        QTimer.singleShot(150, self._fit_minimum_width)   # second pass once laid out
        """Re-apply every translated string (called after a language change)."""
        self._settings_btn.setText(tr("menu.settings"))
        self._theme_menu.setTitle(tr("theme.menu"))
        self._lang_menu.setTitle(tr("menu.language"))
        self._cfg_menu.setTitle(tr("cfg.menu"))
        self._cfg_export_act.setText(tr("cfg.export"))
        self._cfg_import_act.setText(tr("cfg.import"))
        self._theme_system.setText(tr("theme.system"))
        self._theme_dark.setText(tr("theme.dark"))
        self._theme_light.setText(tr("theme.light"))
        self._lang_system.setText(tr("lang.system"))
        self._port_lbl.setText(tr("port.label"))
        self._baud_lbl.setText(tr("baud.label"))
        self.refresh_btn.setText(tr("port.refresh"))
        self.baud_combo.setToolTip(tr("baud.tip"))
        self.open_btn.setText(tr("port.close") if self.worker.is_open() else tr("port.open"))
        self._rx_fmt_lbl.setText(tr("rxfmt.label"))
        self.rx_fmt_combo.setToolTip(tr("rxfmt.tip"))
        self._rx_group.setTitle(tr("group.rx"))
        self._split_lbl.setText(tr("split.label"))
        self._reload_combo(self.split_combo, [
            tr("split.off"), tr("split.auto"), tr("split.manual"), tr("split.header")])
        self.split_combo.setToolTip(tr("split.tip"))
        self.split_ms_edit.setToolTip(tr("split.ms.tip"))
        self.header_edit.setPlaceholderText(tr("header.placeholder.hex"))
        self.header_edit.setToolTip(tr("header.tip"))
        self.ts_check.setText(tr("ts.label"))
        self.ts_check.setToolTip(tr("ts.tip"))
        self.clear_btn.setText(tr("btn.clear"))
        self.save_log_btn.setText(tr("btn.save_log_quick"))
        self.save_log_btn.setToolTip(tr("sc.save.tip"))
        self.save_log_as_btn.setText(tr("btn.save_log_as"))
        self.dtr_check.setToolTip(tr("sig.tip"))
        self.rts_check.setToolTip(tr("sig.tip"))
        self._sig_out_lbl.setText(tr("sig.out"))
        self._sig_out_lbl.setToolTip(tr("sig.out.tip"))
        self._sig_in_lbl.setText(tr("sig.in"))
        self._sig_in_lbl.setToolTip(tr("sig.in.tip"))
        self.dtr_check.setToolTip(tr("sig.dtr.tip"))
        self.rts_check.setToolTip(tr("sig.rts.tip"))
        self.sig_lbl.setToolTip(tr("sig.in.tip"))
        self._poll_signals()
        self.auto_reply_act.setText(tr("rb.enable"))
        self.auto_reply_act.setToolTip(tr("rb.enable.tip"))
        self.rules_act.setText(tr("rb.rules.menu"))
        self.send_file_btn.setText(tr("btn.cancel_send") if self._file_timer.isActive()
                                    else tr("btn.send_file"))
        self.send_file_btn.setToolTip(tr("btn.send_file"))
        self.echo_tx_check.setText(tr("rx.echo_tx"))
        self.echo_tx_check.setToolTip(tr("rx.echo_tx.tip"))
        self.autoscroll_check.setText(tr("rx.autoscroll"))
        self.autoscroll_check.setToolTip(tr("rx.autoscroll.tip"))
        self._reconnect_act.setText(tr("conn.auto"))
        self._reconnect_act.setToolTip(tr("conn.auto.tip"))
        self.params_summary.setToolTip(tr("portset.tip"))
        self._update_params_summary()
        self._port_dlg.retranslate()
        self._update_params_summary()
        self._dbit_lbl.setText(tr("params.databits"))
        self._parity_lbl.setText(tr("params.parity"))
        self._stopbit_lbl.setText(tr("params.stopbits"))
        self._flow_lbl.setText(tr("params.flow"))
        self._reload_combo(self.parity_combo, [tr("parity.none"), tr("parity.odd"), tr("parity.even"),
                                               "Mark", "Space"])
        self._reload_combo(self.flow_combo, [tr("flow.none"), tr("flow.sw"), tr("flow.hw")])
        for combo in self._param_combos:
            combo.setToolTip(tr("params.tip"))
        self._update_history_button()
        self.repeat_btn.setText(tr("tx.repeat.stop") if self.repeat_btn.isChecked()
                               else tr("tx.repeat"))
        self.repeat_btn.setToolTip(tr("tx.repeat.tip"))
        self.repeat_ms.setToolTip(tr("tx.interval.tip"))
        self._repeat_lbl.setText(tr("tx.interval.label"))
        self.tx_edit.setPlaceholderText(tr("tx.placeholder.hex"))   # U86 (set by the format below)
        self.tx_size_lbl.setToolTip(tr("tx.payload.tip"))
        self._reset_act.setText(tr("cfg.reset"))
        self._autosave_act.setText(tr("as.menu"))
        self._autosave_act.setToolTip(tr("as.note"))
        self._autosave_dlg.retranslate()
        self._update_payload_size()
        self._undo_btn.setText(tr("qs.undo"))
        self._undo_btn.setToolTip(tr("qs.deleted"))
        self.split_hint_lbl.setText(
            tr("split.auto.hint") if self.split_combo.currentIndex() == SPLIT_AUTO else tr("split.off.hint"))
        self.sent_lbl.setText(tr("tx.sent_count", n=self._sent_count))
        self._enc_lbl.setText(tr("params.encoding"))
        self.encoding_combo.setToolTip(tr("params.encoding.tip"))
        self.escape_check.setText(tr("tx.escape"))
        self.escape_check.setToolTip(tr("tx.escape.tip"))
        self.crlf_check.setText(tr("tx.crlf"))
        self.crlf_check.setToolTip(tr("tx.crlf.tip"))
        self._tx_group.setTitle(tr("group.tx"))
        self._tx_fmt_lbl.setText(tr("txfmt.label"))
        self.tx_fmt_combo.setToolTip(tr("txfmt.tip"))
        self._crc_lbl.setText(tr("crc.label"))
        self._reload_combo(self.checksum_combo, [
            tr("crc.none"), "CRC16-Modbus", "CRC16-CCITT", "CRC32", "SUM8"])
        self.checksum_combo.setToolTip(tr("crc.tip"))
        self.send_btn.setText(tr("btn.send"))
        self.quick_panel.retranslate()
        self._notify(tr("status.opened") if self.worker.is_open() else tr("status.idle"))
        if self.worker.is_open():
            port = self.port_combo.currentData() or ""
            baud = self.baud_combo.currentText().strip()
            self.status_light.setText(tr("status.connected", port=port, baud=baud))
        else:
            self.status_light.setText(tr("status.disconnected"))

    def _set_theme_system(self):
        theme.set_override(None)
        theme.apply_theme(QApplication.instance())
        self._recolor_status_light()
        theme.apply_native_dark(self, bool(theme.resolved_dark()))
        self._recolor_rx_view()
        self._persist_theme("system")

    def _set_theme_dark(self):
        theme.set_override(True)
        theme.apply_theme(QApplication.instance())
        self._recolor_status_light()
        theme.apply_native_dark(self, bool(theme.resolved_dark()))
        self._recolor_rx_view()
        self._persist_theme("dark")

    def _set_theme_light(self):
        theme.set_override(False)
        theme.apply_theme(QApplication.instance())
        self._recolor_status_light()
        theme.apply_native_dark(self, bool(theme.resolved_dark()))
        self._recolor_rx_view()
        self._persist_theme("light")

    def _persist_theme(self, choice: str):
        config = load_config()
        config["theme"] = choice
        save_config(config)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)   # keep the connect row close to the top
        root.setSpacing(6)

        # --- connection bar -------------------------------------------------
        bar = QHBoxLayout()
        self._port_lbl = QLabel(tr("port.label"))     # U100: these two were English-only
        bar.addWidget(self._port_lbl)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(170)   # U78: keep the whole row under 1040 px
        bar.addWidget(self.port_combo)

        self.refresh_btn = QPushButton(tr("port.refresh"))
        self.refresh_btn.clicked.connect(self.refresh_ports)
        bar.addWidget(self.refresh_btn)

        self._baud_lbl = QLabel(tr("baud.label"))
        bar.addWidget(self._baud_lbl)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([str(b) for b in BAUDRATES])
        self.baud_combo.setEditable(True)
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setToolTip(tr("baud.tip"))
        self.baud_combo.setMinimumWidth(112)          # U49/U78: 1000000/3000000 still fit
        self.baud_combo.setMinimumContentsLength(7)
        self.baud_combo.lineEdit().textChanged.connect(self._check_baud)
        bar.addWidget(self.baud_combo)

        self.open_btn = QPushButton(tr("port.open"))
        self.open_btn.clicked.connect(self.toggle_open)
        self.open_btn.setToolTip(tr("sc.open.tip"))
        bar.addWidget(self.open_btn)

        bar.addSpacing(12)
        self._rx_fmt_lbl = QLabel(tr("rxfmt.label"))
        bar.addWidget(self._rx_fmt_lbl)
        self.rx_fmt_combo = QComboBox()
        self.rx_fmt_combo.addItems(["ASCII", "HEX", "HEX+ASCII"])
        self.rx_fmt_combo.setCurrentIndex(RX_HEX)
        self.rx_fmt_combo.setToolTip(tr("rxfmt.tip"))
        bar.addWidget(self.rx_fmt_combo)

        bar.addSpacing(12)
        # U84 (revised): the wire-format summary and its dialog opener are one compact
        # control - label plus button cost ~245 px and no label needed shortening.
        self.params_summary = QToolButton()
        self.params_summary.setObjectName("paramsBtn")
        self.params_summary.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.params_summary.setToolTip(tr("portset.tip"))
        self.params_summary.clicked.connect(self._show_port_settings)
        self.port_set_btn = self.params_summary   # the open/close lock hint uses this
        bar.addWidget(self.params_summary)

        bar.addSpacing(10)
        bar.addWidget(self._settings_btn)   # U72: same line as Port / Baud / Open

        bar.addStretch(1)
        root.addLayout(bar)

        # U35-P3: the parameter widgets now live in their own dialog; the main
        # window keeps the same attribute names so the rest of the code is unchanged.
        self._port_dlg = PortSettingsDialog(self)
        for _name in ("dbits_combo", "parity_combo", "stopbits_combo", "flow_combo",
                      "encoding_combo", "dtr_check", "rts_check", "sig_lbl",
                      "_dbit_lbl", "_parity_lbl", "_stopbit_lbl", "_flow_lbl",
                      "_enc_lbl", "_sig_out_lbl", "_sig_in_lbl"):
            setattr(self, _name, getattr(self._port_dlg, _name))
        self.dtr_check.toggled.connect(self.worker.set_dtr)
        self.rts_check.toggled.connect(self.worker.set_rts)
        self._param_combos = [self.dbits_combo, self.parity_combo,
                              self.stopbits_combo, self.flow_combo]
        for combo in self._param_combos:
            combo.setToolTip(tr("params.tip"))
            combo.currentIndexChanged.connect(self._update_params_summary)
        self.encoding_combo.currentIndexChanged.connect(self._update_params_summary)
        self._update_params_summary()

        # --- main splitter: left (rx/tx) + right (quick send) ---------------
        splitter = QSplitter()

        left = QWidget()
        self._left_column = left      # U101: its floor is measured, not hard-coded
        left_layout = QVBoxLayout(left)

        # receive group -----------------------------------------------------
        self._rx_group = QGroupBox(tr("group.rx"))
        rx_group = self._rx_group
        rx_layout = QVBoxLayout(rx_group)
        rx_layout.setContentsMargins(8, 2, 8, 6)   # controls hug the top of the group
        rx_layout.setSpacing(4)

        rx_opts = QHBoxLayout()
        self._split_lbl = QLabel(tr("split.label"))
        rx_opts.addWidget(self._split_lbl)
        self.split_combo = QComboBox()
        self.split_combo.addItems([tr("split.off"), tr("split.auto"), tr("split.manual"), tr("split.header")])
        self.split_combo.setCurrentIndex(SPLIT_AUTO)
        self.split_combo.setToolTip(tr("split.tip"))
        self.split_combo.currentIndexChanged.connect(self._on_split_mode_changed)
        rx_opts.addWidget(self.split_combo)

        # U50: one fixed-width slot whose content follows the split mode
        self.split_ms_edit = QLineEdit("10")
        self.split_ms_edit.setValidator(QIntValidator(0, 60000, self))
        self.split_ms_edit.setMaximumWidth(104)
        self.split_ms_edit.setToolTip(tr("split.ms.tip"))

        self.header_edit = QLineEdit()      # U94: never pre-fill a value the user did not type
        self.header_edit.setPlaceholderText(tr("header.placeholder.hex"))
        self.header_edit.setToolTip(tr("header.tip"))
        self.header_edit.textChanged.connect(self._on_header_changed)
        self._update_input_placeholder()   # U94: hint follows the send format

        self.split_hint_lbl = QLabel(tr("split.auto.hint"))
        self.split_hint_lbl.setEnabled(False)

        self.split_slot = QStackedWidget()
        self.split_slot.setMinimumWidth(132)   # the mode hint must not clip
        self.split_slot.addWidget(self.split_hint_lbl)   # 0 auto / off
        self.split_slot.addWidget(self.split_ms_edit)    # 1 manual
        self.split_slot.addWidget(self.header_edit)      # 2 by header
        rx_opts.addWidget(self.split_slot)

        # U96: one row, not two. The stream settings come first, then the display
        # switches, then the log actions; Clear stays alone at the far right (U95's
        # rule for destructive actions), which is what the stretch is there for.
        # The in-row Auto-save switch is gone (U97) - the settings dialog owns it.
        rx_opts.addSpacing(12)
        self.ts_check = QCheckBox(tr("ts.label"))                   # U96: on/off only
        self.ts_check.setChecked(bool(load_config().get("timestamp_on", True)))
        self.ts_check.setToolTip(tr("ts.tip"))
        self.ts_check.toggled.connect(self._on_timestamp_toggled)
        rx_opts.addWidget(self.ts_check)

        rx_opts.addSpacing(12)
        self.echo_tx_check = QCheckBox(tr("rx.echo_tx"))
        self.echo_tx_check.setChecked(True)          # echo sent data by default (U26)
        self.echo_tx_check.setToolTip(tr("rx.echo_tx.tip"))
        rx_opts.addWidget(self.echo_tx_check)
        rx_opts.addSpacing(12)
        self.autoscroll_check = QCheckBox(tr("rx.autoscroll"))   # U43
        self.autoscroll_check.setChecked(bool(load_config().get("autoscroll", True)))   # U75: default on
        self.autoscroll_check.setToolTip(tr("rx.autoscroll.tip"))
        self.autoscroll_check.toggled.connect(self._on_autoscroll_toggled)
        rx_opts.addWidget(self.autoscroll_check)

        rx_opts.addSpacing(18)
        self.save_log_btn = QPushButton(tr("btn.save_log_quick"))
        self.save_log_btn.setToolTip(tr("log.quick.tip"))
        self.save_log_btn.clicked.connect(self.on_save_log_quick)
        rx_opts.addWidget(self.save_log_btn)

        self.save_log_as_btn = QPushButton(tr("btn.save_log_as"))
        self.save_log_as_btn.clicked.connect(self.on_save_log_as)
        rx_opts.addWidget(self.save_log_as_btn)

        rx_opts.addStretch(1)
        self.clear_btn = QPushButton(tr("btn.clear"))
        self.clear_btn.clicked.connect(self.on_clear)
        self.clear_btn.setToolTip(tr("sc.clear.tip"))
        rx_opts.addWidget(self.clear_btn)
        rx_layout.addWidget(_fixed_row(rx_opts))
        # U95: the slot only exists for manual/header mode; set that before the log view
        # is created, so the initial state must not run the full change handler.
        self.split_slot.setVisible(self.split_combo.currentIndex() in (SPLIT_MANUAL, SPLIT_HEADER))

        # RX/TX counters live in the status bar (Z4): global state, and it frees
        # ~140 px of horizontal room for the single receive row (U35-P2).
        self.sent_lbl = QLabel(tr("tx.sent_count", n=0))   # U98: out of the send area
        self.statusBar().addPermanentWidget(self.sent_lbl)
        self.rx_count_label = QLabel("RX: 0 B | TX: 0 B")
        self.statusBar().addPermanentWidget(self.rx_count_label)

        # U41: find bar, hidden until Ctrl+F
        self._find_bar = QWidget()
        find_row = QHBoxLayout(self._find_bar)
        find_row.setContentsMargins(0, 0, 0, 0)
        self._find_lbl = QLabel(tr("find.label"))
        find_row.addWidget(self._find_lbl)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText(tr("find.placeholder"))
        self.find_edit.returnPressed.connect(lambda: self._find_next(True))
        find_row.addWidget(self.find_edit, 1)
        self.find_prev_btn = QPushButton(tr("find.prev"))
        self.find_prev_btn.clicked.connect(lambda: self._find_next(False))
        find_row.addWidget(self.find_prev_btn)
        self.find_next_btn = QPushButton(tr("find.next"))
        self.find_next_btn.clicked.connect(lambda: self._find_next(True))
        find_row.addWidget(self.find_next_btn)
        self.find_close_btn = QPushButton("\u00d7")
        self.find_close_btn.setObjectName("qsDel")
        self.find_close_btn.setFixedWidth(28)
        self.find_close_btn.setToolTip(tr("find.close.tip"))
        self.find_close_btn.clicked.connect(lambda: self._toggle_find_bar(False))
        find_row.addWidget(self.find_close_btn)
        self._find_bar.setSizePolicy(QSizePolicy.Policy.Preferred,
                                    QSizePolicy.Policy.Fixed)   # U70
        self._find_bar.hide()
        rx_layout.addWidget(self._find_bar)

        self.rx_view = QPlainTextEdit()
        self.rx_view.setReadOnly(True)
        self.rx_view.verticalScrollBar().actionTriggered.connect(self._pause_autoscroll)   # U43
        self.rx_view.setMaximumBlockCount(RECEIVE_MAX_LINES)   # U45
        rx_layout.addWidget(self.rx_view, 1)   # U70: the view absorbs all spare height
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)   # U35-P0: draggable
        self._v_splitter.setChildrenCollapsible(False)          # U63: never collapse a pane
        self._v_splitter.addWidget(rx_group)
        self._v_splitter.setStretchFactor(0, 3)
        rx_group.setMinimumHeight(170)                          # U63: keep both panes usable

        # send group ----------------------------------------------------------
        self._tx_group = QGroupBox(tr("group.tx"))
        tx_group = self._tx_group
        tx_layout = QVBoxLayout(tx_group)
        tx_layout.setContentsMargins(8, 2, 8, 6)
        tx_layout.setSpacing(4)

        # U74: payload options above, the input owning the middle with the primary
        # Send button beside it, then the repeat controls and the file row. The old
        # layout squeezed the input to ~134 px (a control column ate ~83% of the
        # width) and capped its height at 90 px, so the send area looked like a toy.
        tx_fmt_row = QHBoxLayout()
        self._tx_fmt_lbl = QLabel(tr("txfmt.label"))
        tx_fmt_row.addWidget(self._tx_fmt_lbl)
        self.tx_fmt_combo = QComboBox()
        self.tx_fmt_combo.addItems(["HEX", "ASCII"])
        self.tx_fmt_combo.setToolTip(tr("txfmt.tip"))
        tx_fmt_row.addWidget(self.tx_fmt_combo)
        self._crc_lbl = QLabel(tr("crc.label"))
        tx_fmt_row.addWidget(self._crc_lbl)
        self.checksum_combo = QComboBox()
        self.checksum_combo.addItems([tr("crc.none"), "CRC16-Modbus", "CRC16-CCITT", "CRC32", "SUM8"])
        self.checksum_combo.setToolTip(tr("crc.tip"))
        tx_fmt_row.addWidget(self.checksum_combo)

        # U98: the text decorations only mean something for ASCII, so they live in one
        # group that disappears in HEX mode (same rule as U50). U99: measured in English
        # they pushed the minimum window width up, so they sit in the action column now
        # instead of the option row - the fallback recorded in the U99 plan.
        self._tx_mod_group = QWidget()
        mod_row = QHBoxLayout(self._tx_mod_group)
        mod_row.setContentsMargins(0, 0, 0, 0)
        mod_row.setSpacing(10)
        self.crlf_check = QCheckBox(tr("tx.crlf"))
        self.crlf_check.setToolTip(tr("tx.crlf.tip"))
        mod_row.addWidget(self.crlf_check)
        self.escape_check = QCheckBox(tr("tx.escape"))
        self.escape_check.setChecked(True)
        self.escape_check.setToolTip(tr("tx.escape.tip"))
        mod_row.addWidget(self.escape_check)

        # U99: file sending moved up beside the checksum box, so the row below only
        # carries the input box and the actions.
        tx_fmt_row.addSpacing(18)
        self.send_file_btn = QPushButton(tr("btn.send_file"))
        self.send_file_btn.setToolTip(tr("btn.send_file"))
        self.send_file_btn.clicked.connect(self.on_send_file)
        tx_fmt_row.addWidget(self.send_file_btn)
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.file_progress.setMaximumWidth(120)
        self.file_progress.hide()          # U108: idle progress bar read as a divider
        tx_fmt_row.addWidget(self.file_progress)
        self.file_info_lbl = QLabel("")
        tx_fmt_row.addWidget(self.file_info_lbl, 1)
        # U99: the payload hint lives in the top-right corner, one size smaller.
        self.tx_size_lbl = QLabel("")
        self.tx_size_lbl.setToolTip(tr("tx.payload.tip"))
        # the app stylesheet drives the widget font, so the smaller size is asked for
        # by object name (QLabel#payloadHint) instead of a QFont that QSS would override
        self.tx_size_lbl.setObjectName("payloadHint")
        tx_fmt_row.addWidget(self.tx_size_lbl)
        tx_layout.addWidget(_fixed_row(tx_fmt_row))
        self.tx_fmt_combo.currentIndexChanged.connect(self._on_tx_fmt_changed)
        self.tx_fmt_combo.currentIndexChanged.connect(self._check_hex_input)
        self._on_tx_fmt_changed(self.tx_fmt_combo.currentIndex())

        tx_row = QHBoxLayout()
        self.tx_edit = QPlainTextEdit()
        self._update_input_placeholder()   # U86: keep the format-specific hint
        self.tx_edit.setMinimumHeight(90)       # U98: the row merge pays for this
        self.tx_edit.textChanged.connect(self._check_hex_input)
        tx_row.addWidget(self.tx_edit, 1)

        tx_row.addSpacing(10)
        tx_sep = QFrame()                        # U98: input area | action area
        tx_sep.setObjectName("vSep")
        tx_sep.setFrameShape(QFrame.Shape.VLine)
        tx_sep.setFixedWidth(1)
        tx_row.addWidget(tx_sep)
        tx_row.addSpacing(10)

        # U99: every action lives in the right-hand column - Send/History on the first
        # line and the repeat controls right below them - so the left side of the row
        # is nothing but the input box.
        actions = QWidget()
        act_col = QVBoxLayout(actions)
        act_col.setContentsMargins(0, 0, 0, 0)
        act_col.setSpacing(8)
        act_col.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.send_btn = QPushButton(tr("btn.send"))
        self.send_btn.clicked.connect(self.on_send)
        self.send_btn.setDefault(True)
        self.send_btn.setMinimumWidth(104)
        self.send_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.send_btn.setToolTip(tr("sc.send.tip"))
        btn_row.addWidget(self.send_btn)
        # U87: the history is a popup now, so it costs one compact button beside the
        # primary action instead of a whole row of its own.
        self.history_btn = QPushButton(tr("tx.history.btn", n=0))
        self.history_btn.setToolTip(tr("tx.history.btn.tip", n=0))
        self.history_btn.setMinimumWidth(104)
        self.history_btn.setProperty("secondary", True)   # U98: a reference, not a peer
        self.history_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.history_btn.setEnabled(False)
        self.history_btn.clicked.connect(self._show_history)
        btn_row.addWidget(self.history_btn)
        btn_row.addStretch(1)
        act_col.addLayout(btn_row)

        repeat_row = QHBoxLayout()
        repeat_row.setSpacing(8)
        # U98: "Repeat send" starts and stops a process, so it is a toggle button that
        # reads "Stop repeat" while running - a checkbox stood in for an action before.
        self.repeat_btn = QPushButton(tr("tx.repeat"))
        self.repeat_btn.setCheckable(True)
        self.repeat_btn.setToolTip(tr("tx.repeat.tip"))
        self.repeat_btn.toggled.connect(self._on_repeat_toggled)
        repeat_row.addWidget(self.repeat_btn)
        self._repeat_lbl = QLabel(tr("tx.interval.label"))   # U31: unit lives in the label
        repeat_row.addWidget(self._repeat_lbl)
        self.repeat_ms = QLineEdit("1000")
        self.repeat_ms.setValidator(QIntValidator(10, 60000, self))
        self.repeat_ms.setMaximumWidth(112)
        self.repeat_ms.setToolTip(tr("tx.interval.tip"))
        self.repeat_ms.textChanged.connect(self._on_repeat_interval)
        repeat_row.addWidget(self.repeat_ms)
        repeat_row.addStretch(1)
        act_col.addLayout(repeat_row)

        mod_holder = QHBoxLayout()
        mod_holder.addWidget(self._tx_mod_group)
        mod_holder.addStretch(1)
        act_col.addLayout(mod_holder)
        act_col.addStretch(1)
        tx_row.addWidget(actions)
        tx_layout.addLayout(tx_row, 1)          # the input takes every spare pixel

        self._v_splitter.addWidget(tx_group)
        self._v_splitter.setStretchFactor(1, 2)
        tx_group.setMinimumHeight(140)                          # U63/U98/U99
        self._v_splitter.setCollapsible(0, False)   # U63: flags must be set after
        self._v_splitter.setCollapsible(1, False)   #      the panes are added
        _stored_v = load_config().get("v_split_sizes")
        _stored_h = load_config().get("split_sizes")
        self._custom_split_sizes = bool(
            (isinstance(_stored_v, list) and _stored_v not in (DATA_FIRST_V, [420, 260]))
            or (isinstance(_stored_h, list) and _stored_h not in (DATA_FIRST_H, [820, 340])))
        self._v_splitter.setSizes(self._saved_sizes("v_split_sizes", DATA_FIRST_V))
        left_layout.addWidget(self._v_splitter, 1)

        splitter.addWidget(left)

        # right: quick send panel ---------------------------------------------
        self.quick_panel = QuickSendPanel()
        self.quick_panel.send_payload.connect(self.on_quick_send)
        self.quick_panel.log.connect(self.on_log_line)
        self.quick_panel.error.connect(lambda m: self._notify(m, "error"))
        self.quick_panel.deleted.connect(self._on_row_deleted)
        splitter.addWidget(self.quick_panel)
        self.quick_panel.collapsed_changed.connect(self._on_quick_panel_collapsed)   # U88
        splitter.setCollapsible(0, False)           # U63: same, after the panes exist
        splitter.setCollapsible(1, False)
        self._splitter = splitter
        splitter.setChildrenCollapsible(False)                  # U63: no zero-width panes
        left.setMinimumWidth(360)   # U63 floor; _fit_minimum_width() raises it to fit the rows
        splitter.setSizes(self._saved_sizes("split_sizes", DATA_FIRST_H))

        root.addWidget(splitter, 1)

        # status bar with connection indicator -------------------------------
        for _sig in (self.tx_edit.textChanged,
                     self.tx_fmt_combo.currentIndexChanged,
                     self.checksum_combo.currentIndexChanged,
                     self.crlf_check.toggled,
                     self.escape_check.toggled,
                     self.encoding_combo.currentIndexChanged):
            _sig.connect(self._update_payload_size)      # U74: live payload size
        self._update_payload_size()

        self.status_light = QLabel(tr("status.disconnected"))
        self.status_light.setStyleSheet(
            f"color: {theme.status_colors()['idle']}; font-weight: bold; padding-right: 8px;")
        self.statusBar().addPermanentWidget(self.status_light)
        # U58: 3 s undo affordance for a deleted quick-send row
        self._undo_payload: dict | None = None
        self._undo_kind = ""
        self._cleared_fragments: list | None = None
        self._cleared_state = None
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.timeout.connect(self._clear_undo)
        self._undo_btn = QPushButton(tr("qs.undo"))
        self._undo_btn.setToolTip(tr("qs.deleted"))
        self._undo_btn.hide()
        self._undo_btn.clicked.connect(self._undo_delete)
        self.statusBar().addPermanentWidget(self._undo_btn)
        self._notify(tr("status.idle"))
        self.setCentralWidget(central)

    def _control_rows(self) -> list:
        """Every horizontal control row whose width must fit (U81)."""
        rows = []
        central = self.centralWidget()
        top = central.layout().itemAt(0)
        if top is not None and top.layout() is not None:
            rows.append(top.layout())
        for group in (self._rx_group, self._tx_group):
            lay = group.layout()
            if lay is None:
                continue
            for i in range(lay.count()):
                wid = lay.itemAt(i).widget()
                if wid is not None and wid.layout() is not None:
                    rows.append(wid.layout())
        return rows

    def _row_need(self, layout) -> int:
        """Minimum width one row needs.

        Qt's own layout minimum accounts for the items' minimums, the layout's
        internal spacing and its contents margins; adding them up by hand missed a
        few pixels per combo box and left rows slightly too narrow (U81).
        """
        return int(layout.minimumSize().width())

    def _widest_row(self) -> tuple:
        """(need, row widget) of the widest control row (U81)."""
        best = (0, None)
        for lay in self._control_rows():
            wid = lay.parentWidget()
            need = self._row_need(lay)
            if need > best[0]:
                best = (need, wid)
        return best

    def _fit_pane_minimums(self) -> None:
        """Hard width floor per pane so a divider drag can never squeeze its rows (U81).

        Pushing the constraint onto the panes (instead of only computing one global
        window minimum) means every splitter position stays safe: the splitter cannot
        compress a pane below the width its widest control row actually needs.
        """
        for group in (self._rx_group, self._tx_group):
            lay = group.layout()
            if lay is None:
                continue
            widest, holder = 0, None
            for i in range(lay.count()):
                wid = lay.itemAt(i).widget()
                if wid is not None and wid.layout() is not None:
                    need = self._row_need(wid.layout())
                    if need > widest:
                        widest, holder = need, wid
            if holder is None:
                continue
            pad = max(0, group.width() - holder.width())   # group frame + margins
            group.setMinimumWidth(widest + pad)

    def _lock_control_widths(self) -> None:
        """Text controls never shrink below their label (U101).

        Qt already refuses to go under minimumSizeHint for most widgets, but an
        explicit minimum or a nested layout can still squeeze one; locking the width to
        the current sizeHint - recomputed on every language switch - keeps every label
        readable at every splitter position without ever touching the font.
        """
        controls = (self._port_lbl, self._baud_lbl, self.refresh_btn, self.open_btn,
                    self._settings_btn, self._crc_lbl, self._repeat_lbl,
                    self.tx_fmt_combo, self.checksum_combo,
                    self.ts_check, self.echo_tx_check, self.autoscroll_check,
                    self.crlf_check, self.escape_check,
                    self.save_log_btn, self.save_log_as_btn, self.clear_btn,
                    self.send_file_btn, self.repeat_btn, self.send_btn, self.history_btn)
        for wdg in controls:
            if wdg is None:
                continue
            wdg.setMinimumWidth(max(wdg.minimumWidth(), wdg.sizeHint().width()))
            if isinstance(wdg, (QPushButton, QCheckBox)):
                # U101: height stays put as well - a button must not grow with the row
                wdg.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _fit_minimum_width(self) -> None:
        """Window floor = the connection bar (spans the window) or both panes side by side.

        Derived at start-up and after a language switch, because the needed width
        follows the actual font, DPI scale and translation - a hard-coded value is
        only right for the machine it was measured on.
        """
        self._lock_control_widths()          # U101: before measuring, pin the labels
        # let the layouts recompute with the current font and translation first, or
        # measurements taken right after a language switch use the old label widths
        for lay in self._control_rows():
            lay.activate()
        central = self.centralWidget().layout()
        if central is not None:
            central.activate()
        self._fit_pane_minimums()
        # U101: the left column (both panes, stacked vertically) must be able to hold
        # its own rows, or dragging the horizontal divider clips them. A vertical
        # splitter's width floor is the widest pane, not the sum - and neither pane's
        # cached hint is reliable at this point, so take the measured floors directly.
        pane_need = max(self._rx_group.minimumWidth(), self._tx_group.minimumWidth())
        pad = max(0, self._left_column.width() - self._v_splitter.width())
        self._left_column.setMinimumWidth(max(360, pane_need + pad))
        rows = self._control_rows()
        connect_need = self._row_need(rows[0]) if rows else 0
        panel_min = (RAIL_W if self.quick_panel.is_folded() else
                     max(QUICK_PANEL_MIN_W, self.quick_panel.minimumSizeHint().width()))
        pair_need = (self._rx_group.minimumWidth() + panel_min + self._splitter.handleWidth()
                     + max(0, self.width() - self._splitter.width()))
        self.setMinimumWidth(max(980, connect_need, pair_need))

    def _give_data_area_the_room(self) -> None:
        """First run: hand every spare pixel to the receive pane (U79).

        The send pane and the quick-send column start at their minimum sizes, so
        the data display area gets the maximum room by default. Once the user
        drags a divider, their proportions are stored and honoured instead.
        """
        if self._custom_split_sizes:
            return
        h = self._v_splitter.height()
        w = self._splitter.width()
        if h > TX_PANE_MIN_H + 40:
            self._v_splitter.setSizes([h - TX_PANE_MIN_H, TX_PANE_MIN_H])
        if w > QUICK_PANEL_MIN_W + 80:
            self._splitter.setSizes([w - QUICK_PANEL_MIN_W, QUICK_PANEL_MIN_W])

    def _saved_sizes(self, key: str, default: list) -> list:
        """Restore a persisted splitter size list, falling back to the default (U35)."""
        value = load_config().get(key)
        legacy, upgraded = LEGACY_SPLIT_DEFAULTS.get(key, (None, default))
        if isinstance(value, list) and len(value) == len(default):
            try:
                sizes = [int(v) for v in value]
            except (TypeError, ValueError):
                return list(default)
            # a stored list that is exactly the old default was never dragged by
            # the user, so upgrading it to the new default is safe (U79)
            if legacy is not None and sizes == list(legacy):
                return list(upgraded)
            return sizes
        return list(default)

    def _fit_settings_btn(self) -> None:
        """Size the Settings button to its label plus padding (U60: "Settings" must fit)."""
        text = self._settings_btn.text()
        width = self._settings_btn.fontMetrics().horizontalAdvance(text) + 46
        self._settings_btn.setMinimumWidth(max(92, width))

    def _setup_tab_order(self) -> None:
        """Explicit Tab order along the five zones (U54, per the U53 grouping spec)."""
        names = ["port_combo", "refresh_btn", "baud_combo", "open_btn",
                 "split_combo", "split_ms_edit", "header_edit", "ts_check",
                 "echo_tx_check", "autoscroll_check",
                 "save_log_btn", "save_log_as_btn", "clear_btn", "rx_view",
                 "tx_fmt_combo", "checksum_combo", "crlf_check", "escape_check",
                 "tx_edit", "send_btn", "history_btn", "repeat_btn", "repeat_ms",
                 "send_file_btn"]
        widgets = [w for w in (getattr(self, n, None) for n in names) if w is not None]
        for first, second in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(first, second)

    # -- notifications (U30/U36/U37/U38) --------------------------------------

    def _notify(self, msg: str, level: str = "info", ms: int | None = None) -> None:
        """Single exit for status-bar messages.

        level: info (auto 5 s) / warn (auto 10 s) / error (persistent until the
        next action). Colour follows the active theme via theme.level_color().
        """
        sb = self.statusBar()
        sb.setStyleSheet(f"QStatusBar {{ color: {theme.level_color(level)}; }}")
        if ms is None:
            ms = -1 if level == "error" else (10000 if level == "warn" else 5000)
        if ms < 0:
            sb.showMessage(msg)
        else:
            sb.showMessage(msg, ms)

    def _recolor_status_light(self) -> None:
        """Re-apply the connection indicator colour (theme-aware, U38)."""
        cols = theme.status_colors()
        key = "ok" if self.worker.is_open() else ("idle" if self.port_combo.count() == 0 else "err")
        self.status_light.setStyleSheet(
            f"color: {cols[key]}; font-weight: bold; padding-right: 8px;")

    def _on_row_deleted(self, payload: dict) -> None:
        """Offer a short undo window for a deleted quick-send row (U58)."""
        self._undo_payload = dict(payload)
        self._undo_kind = "row"
        self._undo_btn.setText(tr("undo.label"))
        self._undo_btn.show()
        self._undo_timer.start(3000)
        self._notify(tr("qs.deleted"), "warn", ms=3000)

    def _undo_delete(self) -> None:
        """Undo the last destructive action: a deleted row or a cleared pane (U58/U42)."""
        kind, payload = self._undo_kind, self._undo_payload
        self._undo_kind = ""
        self._undo_payload = None
        self._undo_timer.stop()
        self._undo_btn.hide()
        if kind == "clear" and self._cleared_fragments:
            state = self._cleared_state or (False, 0, 0, 0)
            fragments, self._cleared_fragments = self._cleared_fragments, None
            self._line_is_tx, self.rx_bytes, self.tx_bytes, self._sent_count = state
            for text, frag_kind in fragments:
                self._emit_rx_text(text, tx=(frag_kind == 1),
                                   meta=(frag_kind == 2), log=False)
            self.sent_lbl.setText(tr("tx.sent_count", n=self._sent_count))
            self.update_counts()
            self._cleared_state = None
            self._notify(tr("rx.undo.done"), "info", ms=3000)
            return
        if payload:
            self.quick_panel.restore_row(payload)
            self._notify(tr("qs.undo.done"), "info", ms=3000)

    def _clear_undo(self) -> None:
        self._undo_payload = None
        self._undo_kind = ""
        self._cleared_fragments = None
        self._cleared_state = None
        self._undo_btn.hide()

    def _ensure_port(self) -> bool:
        """Guard send actions: nothing is sent, echoed or counted while closed (U61)."""
        if self.worker.is_open():
            return True
        self._notify(tr("err.tx.closed"), "error")
        return False

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

    def _schedule_history_save(self) -> None:
        """Debounce history persistence: one write per 2 s instead of per click (U52)."""
        self._cfg_save_timer.start(2000)

    def _flush_history_save(self) -> None:
        """Write the send history to config.json (called by the debounce timer)."""
        self._cfg_save_timer.stop()
        config = load_config()
        config["send_history"] = self._send_history
        config["history_meta"] = self._prune_history_meta(self._history_meta)
        save_config(config)

    def _on_worker_error(self, text: str) -> None:
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
        self._notify(tr(key, e=text), "error")

    def _check_hex_input(self) -> None:
        """Live-validate the TX box in HEX mode: red border + tooltip (U36)."""
        if self.tx_fmt_combo.currentIndex() != 0:
            self.tx_edit.setStyleSheet("")
            self.tx_edit.setToolTip(tr("tx.input.tip.ascii"))   # U86
            return
        try:
            hex_str_to_bytes(self.tx_edit.toPlainText())
        except HexFormatError as exc:
            self.tx_edit.setStyleSheet(f"border: 1px solid {theme.level_color('error')};")
            self.tx_edit.setToolTip(hex_error_message(exc))
            return
        self.tx_edit.setStyleSheet("")
        self.tx_edit.setToolTip(tr("tx.hex.tip"))


    # -- helpers ---------------------------------------------------------------

    # -- config import / export (T15) ----------------------------------------

    def on_export_config(self) -> None:
        """Write the current settings (quick send, theme, history, rules...) to a JSON file."""
        default = os.path.join(os.path.expanduser("~"),
                               time.strftime("serialdesk_config_%Y%m%d_%H%M%S.json"))
        path, _ = QFileDialog.getSaveFileName(self, tr("cfg.export.title"), default, tr("cfg.filter"))
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
            self._notify(tr("cfg.exported", path=path), ms=5000)
        except OSError as exc:
            self.on_log_line(tr("cfg.export_fail", e=exc))

    def on_import_config(self) -> None:
        """Merge a previously exported config file back into the current settings."""
        path, _ = QFileDialog.getOpenFileName(self, tr("cfg.import.title"), "", tr("cfg.filter"))
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            self.on_log_line(tr("cfg.import_fail", e=exc))
            return
        if not isinstance(data, dict):
            self.on_log_line(tr("cfg.import_bad"))
            return
        incoming = data.get("config") if isinstance(data.get("config"), dict) else data

        config = load_config()
        for key in ("theme", "language", "quick_send", "send_history", "history_meta",
                    "auto_reply", "auto_reply_enabled"):
            if key in incoming:
                config[key] = incoming[key]
        if not save_config(config):
            self.on_log_line(tr("cfg.import_fail", e="config.json"))
            return
        self._apply_config()
        self._notify(tr("cfg.imported", path=path), ms=5000)

    def _apply_config(self) -> None:
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
        self._recolor_status_light()
        theme.apply_native_dark(self, bool(theme.resolved_dark()))
        self._recolor_rx_view()
        {"dark": self._theme_dark, "light": self._theme_light}.get(
            choice, self._theme_system).setChecked(True)

        i18n.set_language(str(cfg.get("language", "system")))
        self.retranslate()

        self.quick_panel.reload_from_config()

        self._send_history = [str(h) for h in cfg.get("send_history", []) if str(h).strip()][:HISTORY_MAX]
        self._history_meta = self._prune_history_meta(cfg.get("history_meta"))
        self._update_history_button()

        self._auto_rules = [r for r in cfg.get("auto_reply", []) if isinstance(r, dict)]
        self.auto_reply_act.setChecked(bool(cfg.get("auto_reply_enabled", False)))
        self._reply_buf = b""

    # -- auto reply (T10) ----------------------------------------------------

    def _on_auto_reply_toggled(self, checked: bool) -> None:
        config = load_config()
        config["auto_reply_enabled"] = bool(checked)
        save_config(config)
        self._reply_buf = b""

    def _edit_rules(self) -> None:
        dlg = AutoReplyDialog(self._auto_rules, self)
        if not dlg.exec():
            return
        self._auto_rules = dlg.rules()
        config = load_config()
        config["auto_reply"] = self._auto_rules
        save_config(config)
        self._notify(tr("rb.saved", n=len(self._auto_rules)), ms=5000)

    def _check_auto_reply(self, data: bytes) -> None:
        """Send the configured reply when a match string shows up in the stream."""
        if not self.auto_reply_act.isChecked() or not self._auto_rules:
            return
        self._reply_buf = (self._reply_buf + data)[-512:]
        for rule in self._auto_rules:
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
            if match and match in self._reply_buf:
                if reply and self.worker.is_open():
                    self.worker.send(reply)
                    self.tx_bytes += len(reply)
                    self.update_counts()
                    self._notify(tr("rb.sent", n=len(reply)), ms=3000)
                self._reply_buf = b""
                break

    def _recolor_rx_view(self) -> None:
        """Re-apply theme colours to already-displayed lines (U27).

        Text inserted under one theme keeps the colour it was given, which turns
        black-on-dark (or worse) after a theme switch, so re-colour the document.
        """
        doc = self.rx_view.document()
        cursor = QTextCursor(doc)
        block = doc.begin()
        while block.isValid():
            fallback_tx = "-> " in block.text()[:34]   # older lines carry no kind tag
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    kind = None
                    try:
                        kind = fmt.property(QTextFormat.Property.UserProperty)
                    except (AttributeError, TypeError):
                        kind = None
                    if kind == 2:
                        colour = theme.meta_color()
                    elif kind == 1 or (kind is None and fallback_tx):
                        colour = theme.tx_color()
                    else:
                        colour = theme.text_color()
                    fmt.setForeground(QColor(colour))
                    cursor.setPosition(frag.position())
                    cursor.setPosition(frag.position() + frag.length(),
                                       QTextCursor.MoveMode.KeepAnchor)
                    cursor.setCharFormat(fmt)
                it += 1
            block = block.next()

    # -- modem status lines (T9) ---------------------------------------------

    def _poll_signals(self) -> None:
        """Refresh the CTS/DSR/DCD/RI indicators (50 ms timer)."""
        sig = self.worker.signals()
        self.sig_lbl.setText(self._signals_html(sig if sig.get("open") else {}))

    def _signals_html(self, sig: dict) -> str:
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

    # -- file send (T6) ------------------------------------------------------

    def _baud_value(self) -> int:
        try:
            return int(self.baud_combo.currentText().strip())
        except ValueError:
            return 115200

    def _load_file(self, path: str) -> bytes:
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
                return encode_text(fh.read(), self._encoding(), False)
        with open(path, "rb") as fh:
            return fh.read()

    def on_send_file(self):
        """Start (or cancel) sending a file in chunks with progress feedback."""
        if self._file_timer.isActive():
            self._abort_file_send()
            return
        if not self.worker.is_open():
            self._notify(tr("file.no_port"), ms=5000)
            return
        filters = ";;".join([tr("file.filter.all"), tr("file.filter.hex"),
                             tr("file.filter.text"), tr("file.filter.bin")])
        path, _ = QFileDialog.getOpenFileName(self, tr("file.dialog.title"), "", filters)
        if not path:
            return
        try:
            data = self._load_file(path)
        except (OSError, ValueError) as exc:
            self.on_log_line(tr("file.error", e=exc))
            return
        if not data:
            return
        self._file_data = data
        self._file_pos = 0
        self._file_path = path
        baud = self._baud_value()
        eta = max(1, int(len(data) / max(1.0, baud / 10.0)))
        self.file_progress.setValue(0)
        self.file_progress.show()
        self.file_info_lbl.setText(tr("file.info", size=_human_bytes(len(data)), baud=baud, eta=eta))
        self.send_file_btn.setText(tr("btn.cancel_send"))
        self._file_timer.start(FILE_CHUNK_MS)

    def _send_file_chunk(self):
        if not self.worker.is_open():
            self._abort_file_send()
            return
        chunk = self._file_data[self._file_pos:self._file_pos + FILE_CHUNK_BYTES]
        if not chunk:
            self._finish_file_send()
            return
        self.worker.send(chunk)
        self._file_pos += len(chunk)
        self.tx_bytes += len(chunk)
        self.update_counts()
        total = len(self._file_data)
        pct = int(self._file_pos * 100 / total)
        self.file_progress.setValue(pct)
        self.file_info_lbl.setText(tr("file.progress", sent=_human_bytes(self._file_pos),
                                      total=_human_bytes(total), pct=pct))

    def _finish_file_send(self):
        size = _human_bytes(len(self._file_data))
        name = os.path.basename(self._file_path)
        self._file_timer.stop()
        self.send_file_btn.setText(tr("btn.send_file"))
        self.file_progress.setValue(100)
        self.file_progress.hide()
        self._notify(tr("file.done", name=name, size=size), ms=5000)

    def _abort_file_send(self):
        self._file_timer.stop()
        self.send_file_btn.setText(tr("btn.send_file"))
        self.file_info_lbl.setText("")
        self.file_progress.setValue(0)
        self.file_progress.hide()

    # -- receive log to file (T4) -------------------------------------------

    def _log_open(self) -> None:
        """Open a new log segment under logs/ (auto-save mode)."""
        try:
            os.makedirs(self._log_dir, exist_ok=True)
            name = time.strftime("serial_%Y%m%d_%H%M%S.txt")
            self._log_path = os.path.join(self._log_dir, name)
            self._log_fp = open(self._log_path, "a", encoding="utf-8")
            self._log_started = time.time()
            self._log_bytes = 0
            self._notify(tr("log.autosave.on", path=self._log_path), ms=5000)
        except OSError as exc:
            self._log_fp = None
            self.on_log_line(tr("log.save_fail", e=exc))

    def _log_close(self) -> None:
        if self._log_fp is not None:
            try:
                self._log_fp.close()
            except OSError:
                pass
            self._log_fp = None

    def _log_append(self, text: str) -> None:
        """Append a chunk of received text to the auto-save file, rotating when needed."""
        if self._log_fp is None:
            return
        if (self._log_bytes > self._log_max_bytes
                or time.time() - self._log_started > self._log_max_seconds):
            self._log_close()
            self._log_open()
            if self._log_fp is None:
                return
        try:
            self._log_fp.write(text)
            self._log_fp.flush()
            self._log_bytes += len(text.encode("utf-8"))
        except OSError as exc:
            self._log_close()
            self.on_log_line(tr("log.save_fail", e=exc))

    def on_save_log_quick(self) -> None:
        """One-click save of the receive pane into logs/ (U25-D)."""
        try:
            os.makedirs(self._log_dir, exist_ok=True)
            path = os.path.join(self._log_dir, time.strftime("serial_RX_%Y%m%d_%H%M%S.txt"))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.rx_view.toPlainText())
                fh.write("\n")
            self._notify(tr("log.saved", path=path), ms=5000)
        except OSError as exc:
            self.on_log_line(tr("log.save_fail", e=exc))

    def on_save_log_as(self) -> None:
        """Save the receive pane to a user-chosen path (U25-D)."""
        try:
            os.makedirs(self._log_dir, exist_ok=True)      # U97: the configured log folder
        except OSError:
            pass
        default = os.path.join(self._log_dir, time.strftime("serial_%Y%m%d_%H%M%S.txt"))
        path, _ = QFileDialog.getSaveFileName(self, tr("log.save.title"), default, "Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.rx_view.toPlainText())
                fh.write("\n")
            self._notify(tr("log.saved", path=path), ms=5000)
        except OSError as exc:
            self.on_log_line(tr("log.save_fail", e=exc))

    # -- quick helpers --------------------------------------------------------

    def _emit_rx_text(self, text: str, tx: bool = False, meta: bool = False,
                      log: bool = True) -> None:
        """Insert text into the receive pane and mirror it to the log.

        kind: 0 = RX payload, 1 = TX payload, 2 = timestamp/marker (dimmed, U62).
        The kind is stored on the format so a theme switch can recolour it correctly.
        """
        kind = 2 if meta else (1 if tx else 0)
        cursor = self.rx_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if kind == 2:
            fmt.setForeground(QColor(theme.meta_color()))
        elif kind == 1:
            fmt.setForeground(QColor(theme.tx_color()))
        else:
            fmt.setForeground(QColor(theme.text_color()))
        try:
            fmt.setProperty(QTextFormat.Property.UserProperty, kind)
        except (AttributeError, TypeError):
            pass
        cursor.insertText(text, fmt)
        if log:
            self._log_append(text)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        """Delete the highlighted history entry with the keyboard (U77)."""
        return super().eventFilter(obj, event)

    def _snapshot_rx_fragments(self) -> list:
        """Capture (text, kind) for every fragment so clearing can be undone (U42).

        QPlainTextEdit refuses a cloned document (its layout class differs), so the
        pane is rebuilt from the fragments with our own emitter instead.
        """
        out = []
        block = self.rx_view.document().begin()
        while block.isValid():
            fallback_tx = "-> " in block.text()[:34]
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    try:
                        kind = frag.charFormat().property(QTextFormat.Property.UserProperty)
                    except (AttributeError, TypeError):
                        kind = None
                    if kind is None:
                        kind = 1 if fallback_tx else 0
                    out.append((frag.text(), int(kind)))
                it += 1
            if block.next().isValid():
                out.append(("\n", 0))   # block separators are not fragments
            block = block.next()
        return out

    def _scroll_rx_bottom(self) -> None:
        """Follow the newest line unless the user paused auto-scroll (U43)."""
        if self.autoscroll_check.isChecked():
            bar = self.rx_view.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _pause_autoscroll(self, _action: int = 0) -> None:
        """Manual scrolling means the user is reading: stop following (U43)."""
        if self.autoscroll_check.isChecked():
            self.autoscroll_check.setChecked(False)

    def _rx_separator(self) -> str:
        """Separator used when a HEX group continues an existing line (U59)."""
        return "" if self.rx_fmt_combo.currentIndex() == RX_ASCII else " "

    def _append_rx_group(self, text: str, ts: float, new_line: bool) -> None:
        """Emit one RX group without gluing it onto the previous text (U59).

        - new line requested, or the current line belongs to a TX echo -> open a
          fresh, timestamped line;
        - otherwise append to the running RX line, with a separator in HEX modes
          (previously '39 30' + '31 32' collapsed into '39 3031 32').
        """
        has_text = self.rx_view.document().characterCount() > 1
        if new_line or self._line_is_tx:
            if has_text:
                self._emit_rx_text("\n")
            self._emit_rx_text(self._ts_prefix(ts) + MARK_RX, meta=True)
        elif has_text:
            separator = self._rx_separator()
            if separator:
                self._emit_rx_text(separator)
        self._emit_rx_text(text)
        self._line_is_tx = False
        if not self._cap_warned and self.rx_view.blockCount() >= RECEIVE_MAX_LINES - 5:
            self._cap_warned = True          # U45: one clear warning, not per line
            self._notify(tr("rx.cap", n=RECEIVE_MAX_LINES), "warn", ms=8000)

    def _echo_tx(self, data: bytes) -> None:
        """Mirror sent bytes into the receive pane as a '->' line (U26)."""
        if not self.echo_tx_check.isChecked() or self._file_timer.isActive():
            return
        if self.rx_view.document().characterCount() > 1:
            self._emit_rx_text("\n", tx=True)
        self._emit_rx_text(self._ts_prefix(time.monotonic()) + MARK_TX, tx=True, meta=True)
        self._emit_rx_text(self._format_rx(data), tx=True)
        self._line_is_tx = True
        self._scroll_rx_bottom()          # U43

    def _show_history(self) -> None:
        """Open (or raise) the non-modal history popup (U87)."""
        if self._history_dlg is None:
            self._history_dlg = HistoryDialog(self)
            self._history_dlg.fill_requested.connect(self._on_history_fill)
            self._history_dlg.delete_requested.connect(self._remove_history_entry)
            self._history_dlg.clear_requested.connect(self._clear_history)
        self._history_dlg.set_history(self._send_history, self._history_meta)
        self._history_dlg.show()
        self._history_dlg.raise_()
        self._history_dlg.activateWindow()

    def _on_history_fill(self, text: str) -> None:
        """Recall a stored command into the send box (U87)."""
        self.tx_edit.setPlainText(text)
        self.tx_edit.setFocus()
        self._recall_index = -1
        if self._history_dlg is not None:
            self._history_dlg.close()

    def _recall_history(self, step: int) -> None:
        """Walk the send history with Ctrl+Up / Ctrl+Down (U87).

        step +1 goes further back in time (older), -1 comes towards the newest;
        stepping past the newest restores whatever was typed before browsing.
        """
        if not self._send_history:
            self._notify(tr("tx.history.empty"), "info", ms=2500)
            return
        if self._recall_index < 0:
            self._recall_draft = self.tx_edit.toPlainText()
            self._recall_index = 0
        else:
            self._recall_index += step
        if self._recall_index < 0:
            self._recall_index = -1
            self.tx_edit.setPlainText(self._recall_draft)
            return
        self._recall_index = min(self._recall_index, len(self._send_history) - 1)
        self.tx_edit.setPlainText(self._send_history[self._recall_index])

    def _prune_history_meta(self, raw) -> dict:
        """Keep only the metadata of commands that are still in the history (v0.10.0)."""
        if not isinstance(raw, dict):
            return {}
        allowed = set(self._send_history)
        out = {}
        for text, meta in raw.items():
            if str(text) in allowed and isinstance(meta, dict):
                out[str(text)] = meta
        return out

    def _remember_send(self, text: str, fmt: str = "", nbytes: int | None = None):
        """Push a sent command into the dedup history (max HISTORY_MAX) and persist it."""
        text = text.strip()
        if not text:
            return
        self._send_history = [text] + [h for h in self._send_history if h != text]
        self._send_history = self._send_history[:HISTORY_MAX]
        record = {"fmt": fmt, "ts": time.time()}
        if isinstance(nbytes, int):
            record["b"] = nbytes
        self._history_meta[text] = record
        self._history_meta = self._prune_history_meta(self._history_meta)
        self._update_history_button()
        self._schedule_history_save()

    def _update_history_button(self) -> None:
        """Keep the History button (label, tooltip, enabled state) in sync (U87)."""
        n = len(self._send_history)
        self.history_btn.setText(tr("tx.history.btn", n=n))
        self.history_btn.setToolTip(tr("tx.history.btn.tip", n=n))
        self.history_btn.setEnabled(n > 0)
        if self._history_dlg is not None:
            self._history_dlg.set_history(self._send_history, self._history_meta)

    def _remove_history_entry(self, row: int) -> None:
        """Drop one entry from the send history and persist (U77)."""
        if not (0 <= row < len(self._send_history)):
            return
        removed = self._send_history.pop(row)
        self._history_meta.pop(removed, None)
        self._update_history_button()
        self._schedule_history_save()
        self._notify(tr("tx.history.removed", text=removed), "info", ms=3000)

    def _clear_history(self) -> None:
        """Forget every remembered command (U77)."""
        if not self._send_history:
            return
        self._send_history = []
        self._history_meta = {}
        self._update_history_button()
        self._schedule_history_save()
        self._notify(tr("tx.history.cleared"), "info", ms=3000)

    def _on_repeat_toggled(self, checked: bool):
        if checked and not self._ensure_port():
            self.repeat_btn.blockSignals(True)     # U61: no repeat loop without a port
            self.repeat_btn.setChecked(False)
            self.repeat_btn.blockSignals(False)
            self.repeat_btn.setText(tr("tx.repeat"))
            return
        self.repeat_btn.setText(tr("tx.repeat.stop") if checked else tr("tx.repeat"))
        if checked:
            self._sent_count = 0
            self.sent_lbl.setText(tr("tx.sent_count", n=0))
            self._repeat_timer.start(self._repeat_value())
        else:
            self._repeat_timer.stop()

    def _repeat_value(self) -> int:
        """Parse the repeat interval (10-60000 ms), clamped, defaulting to 1000."""
        try:
            value = int((self.repeat_ms.text() or "").strip())
        except ValueError:
            return 1000
        return max(10, min(60000, value))

    def _on_repeat_interval(self, _text: str):
        if self._repeat_timer.isActive():
            self._repeat_timer.setInterval(self._repeat_value())

    def _stop_repeat(self):
        if self.repeat_btn.isChecked():
            self.repeat_btn.setChecked(False)     # triggers _on_repeat_toggled -> stop
        else:
            self._repeat_timer.stop()

    def _serial_params(self) -> dict:
        """Collect the parameter widgets into pyserial open_port kwargs (T1)."""
        flow = FLOW_KEYS[self.flow_combo.currentIndex()]
        return {
            "bytesize": BYTESIZE_KEYS[self.dbits_combo.currentIndex()],
            "parity": PARITY_KEYS[self.parity_combo.currentIndex()],
            "stopbits": STOPBITS_KEYS[self.stopbits_combo.currentIndex()],
            "rtscts": flow == "rtscts",
            "xonxoff": flow == "xonxoff",
        }

    def _on_tx_fmt_changed(self, index: int):
        # U98: CRLF and escape parsing only mean something for ASCII text (index 1);
        # in HEX mode the group is hidden rather than shown greyed out.
        self._tx_mod_group.setVisible(index == 1)
        self._update_input_placeholder()   # U86: hint follows the send format

    def _update_input_placeholder(self) -> None:
        """Keep the send box and the frame-header box hints in step with the format (U86/U93/U94)."""
        if not hasattr(self, "tx_edit"):
            return          # the format row is built before the input box
        hex_mode = self.tx_fmt_combo.currentIndex() == 0
        self.tx_edit.setPlaceholderText(tr("tx.placeholder.hex" if hex_mode else "tx.placeholder.ascii"))
        if hasattr(self, "header_edit"):
            self.header_edit.setPlaceholderText(
                tr("header.placeholder.hex" if hex_mode else "header.placeholder.ascii"))

    def _on_split_mode_changed(self, index: int):
        self._flush_rx_frames()   # don't lose a half-collected frame (U57)
        if index == SPLIT_MANUAL:
            self.split_slot.setCurrentIndex(1)
            self.split_slot.setVisible(True)
        elif index == SPLIT_HEADER:
            self.split_slot.setCurrentIndex(2)
            self.split_slot.setVisible(True)
        else:
            # U95: in auto/off mode the slot held a hint that repeated the combo's own
            # label and read like stray text, so the slot simply goes away.
            self.split_slot.setCurrentIndex(0)
            self.split_slot.setVisible(False)

    def _on_header_changed(self, text: str):
        # typing a frame header auto-switches to header-split mode
        if text.strip() and self.split_combo.currentIndex() != SPLIT_HEADER:
            self.split_combo.setCurrentIndex(SPLIT_HEADER)

    def _split_threshold_ms(self) -> float | None:
        """Return current split threshold in ms, or None if splitting off."""
        mode = self.split_combo.currentIndex()
        if mode != SPLIT_MANUAL and mode != SPLIT_AUTO:
            return None
        if mode == SPLIT_MANUAL:
            try:
                return max(0.0, float(self.split_ms_edit.text().strip()))
            except ValueError:
                return None
        # auto: 3.5-char rule (Modbus RTU), with 2 ms USB clustering floor
        try:
            baud = int(self.baud_combo.currentText().strip())
        except ValueError:
            return None
        char_ms = 10.0 / baud * 1000.0  # 8N1: one char = 10 bits
        # 10 ms floor: below that, USB chunk delivery (not the wire) decides (U57)
        return max(3.5 * char_ms, 10.0)

    def _encoding(self) -> str:
        """Currently selected text encoding (T7)."""
        idx = self.encoding_combo.currentIndex()
        return TEXT_ENCODINGS[idx] if 0 <= idx < len(TEXT_ENCODINGS) else "ascii"

    def _format_rx(self, data: bytes) -> str:
        mode = self.rx_fmt_combo.currentIndex()
        if mode == RX_HEX:
            return bytes_to_hex_str(data)
        if mode == RX_ASCII:
            return decode_text(data, self._encoding())
        hex_s = bytes_to_hex_str(data)
        text_s = decode_text(data, self._encoding())
        return f"{hex_s} | {text_s}"

    def _ts_prefix(self, ts: float) -> str:
        """'[04:02:10.456] ' when the timestamp switch is on, '' when it is off (U96)."""
        if not self.ts_check.isChecked():
            return ""
        wall = ts + self._clock_offset
        ms = int((wall - int(wall)) * 1000)
        return time.strftime(f"[%H:%M:%S.{ms:03d}] ", time.localtime(wall))

    # -- actions -----------------------------------------------------------------

    def refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for dev, desc in list_serial_ports():
            # U83: the name alone keeps the row narrow and is never truncated; the full
            # description stays reachable from the tooltips and the dropdown entries.
            self.port_combo.addItem(dev, dev)
            if desc:
                self.port_combo.setItemData(self.port_combo.count() - 1,
                                            f"{dev} — {desc}", Qt.ItemDataRole.ToolTipRole)
        if current:
            idx = self.port_combo.findData(current)
            if idx < 0:
                idx = self.port_combo.findText(str(current))
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        self.port_combo.blockSignals(False)
        self._update_port_tooltip()

    def toggle_open(self):
        if self.worker.is_open():
            self.worker.close_port()
            self.open_btn.setText(tr("port.open"))
        else:
            if self.port_combo.count() == 0:
                self._notify(tr("status.no_port"), "warn")
                return
            device = self.port_combo.currentData()
            try:
                baud = int(self.baud_combo.currentText().strip())
            except ValueError:
                self._notify(tr("status.bad_baud"), "error")
                return
            ok = self.worker.open_port(device, baud, **self._serial_params())
            if ok:
                self.refresh_timer.stop()  # keep port list stable while open

    def on_opened_changed(self, opened: bool):
        if opened:
            self.open_btn.setText(tr("port.close"))
            port = self.port_combo.currentData() or ""
            baud = self.baud_combo.currentText().strip()
            self.status_light.setText(tr("status.connected", port=port, baud=baud))
            self.status_light.setStyleSheet(
                f"color: {theme.status_colors()['ok']}; font-weight: bold; padding-right: 8px;")
            self._notify(tr("status.opened"))
            for combo in self._param_combos:
                combo.setEnabled(False)
            self._port_dlg.set_port_open(True)     # U73: explain the lock
        else:
            self.open_btn.setText(tr("port.open"))
            self.status_light.setText(tr("status.disconnected"))
            self.status_light.setStyleSheet(
                f"color: {theme.status_colors()['err']}; font-weight: bold; padding-right: 8px;")
            self._stop_repeat()
            self._abort_file_send()
            self.quick_panel.stop_sequence()
            self._flush_rx_frames()   # flush the tail frame on close (U57)
            self.refresh_timer.start()
            for combo in self._param_combos:
                combo.setEnabled(True)
            self._port_dlg.set_port_open(False)    # U73
            if not self.worker.is_open():
                self._notify(tr("status.closed"))

    def _check_baud(self, text: str) -> None:
        """Mark the baud box invalid (red border) when the typed value is not usable."""
        s = (text or "").strip()
        ok = s.isdigit() and 1 <= int(s) <= 12000000
        if bool(self.baud_combo.property("invalid")) != (not ok):
            self.baud_combo.setProperty("invalid", not ok)
            self.baud_combo.style().unpolish(self.baud_combo)
            self.baud_combo.style().polish(self.baud_combo)

    def _apply_checksum(self, payload: bytes) -> bytes:
        mode = CHECKSUM_KEYS[self.checksum_combo.currentIndex()]
        return append_checksum(payload, mode)

    def on_send(self):
        text = self.tx_edit.toPlainText().strip()
        if not text:
            return
        try:
            if self.tx_fmt_combo.currentIndex() == 0:
                payload = hex_str_to_bytes(text)
            else:
                payload = encode_text(text, self._encoding(), self.escape_check.isChecked())
        except HexFormatError as exc:
            self._notify(hex_error_message(exc), "error")
            return
        except ValueError as exc:
            self._notify(tr("log.send_error", e=exc), "error")
            return
        if not self._ensure_port():
            return
        payload = self._apply_checksum(payload)
        if self.tx_fmt_combo.currentIndex() == 1 and self.crlf_check.isChecked():
            payload += b"\r\n"
        if not self.worker.send(payload):
            return          # U61: never echo or count a frame that was not queued
        self._echo_tx(payload)
        self.tx_bytes += len(payload)
        self._sent_count += 1
        self.sent_lbl.setText(tr("tx.sent_count", n=self._sent_count))
        self._remember_send(
            text,
            "hex" if self.tx_fmt_combo.currentIndex() == 0 else "ascii",
            len(payload))
        self.update_counts()

    def on_quick_send(self, payload: bytes):
        if not self.worker.is_open():     # U61: quick send / sequence obey the same rule
            self.quick_panel.stop_sequence()
            self._notify(tr("err.tx.closed"), "error")
            return
        payload = self._apply_checksum(payload)
        if not self.worker.send(payload):
            self.quick_panel.stop_sequence()
            return
        self._echo_tx(payload)
        # U103: quick send / sequence / repeat go through here, so the send counter
        # has to move too - otherwise "已发送 N 次" stayed at the manual-send count
        # while the TX byte counter kept climbing.
        self.tx_bytes += len(payload)
        self._sent_count += 1
        self.sent_lbl.setText(tr("tx.sent_count", n=self._sent_count))
        self.update_counts()

    def on_received(self, ts: float, data: bytes):
        self._check_auto_reply(data)
        self.rx_bytes += len(data)
        self.update_counts()

        if self.split_combo.currentIndex() == SPLIT_HEADER:
            self._append_header_split(data, ts)
            self._last_ts = ts
            return

        # U57: collect chunks first; the line break is decided when the group settles
        self._frames.set_threshold(self._split_threshold_ms())
        self._frames.feed(ts, data)
        if not self._frame_timer.isActive():
            self._frame_timer.start(int(self._frames.settle_ms))

    def _flush_rx_frames(self) -> None:
        """Emit assembled frames: USB fragments merged, real gaps split (U57)."""
        now = time.monotonic()
        while True:
            got = self._frames.take(now)
            if got is None:
                break
            new_line, ts, data = got
            self._append_rx_group(self._format_rx(data), ts, new_line)
        self._last_ts = now
        self._scroll_rx_bottom()          # U43
        if self._frames.has_pending():
            self._frame_timer.start(int(self._frames.settle_ms))
    def _append_header_split(self, data: bytes, ts: float):
        """Split raw bytes by frame header (e.g. 'fw:'), one line per frame.

        Splitting on the byte level works regardless of HEX/ASCII display mode.
        Leading bytes before the first header belong to the current line.
        """
        header = self.header_edit.text().strip()
        header_b = header.encode("utf-8", errors="replace") if header else b""
        if not header_b:
            return
        segs = data.split(header_b)
        for i, seg in enumerate(segs):
            if i == 0:
                # bytes before the first header: continue the current frame (U59)
                if seg:
                    self._append_rx_group(self._format_rx(seg), ts, False)
                continue
            if not seg:
                continue  # adjacent headers, frame with empty body
            self._append_rx_group(self._format_rx(header_b + seg), ts, True)

        self._scroll_rx_bottom()          # U43

    def on_log_line(self, line: str):
        self._notify(line, ms=5000)

    def on_clear(self):
        """Clear the display and the counters together, with an undo window (U56/U42)."""
        has_text = self.rx_view.document().characterCount() > 1
        offer_undo = has_text and self.rx_view.blockCount() <= CLEAR_UNDO_MAX_LINES
        if offer_undo:
            self._cleared_fragments = self._snapshot_rx_fragments()   # keeps colours
            self._cleared_state = (self._line_is_tx, self.rx_bytes,
                                   self.tx_bytes, self._sent_count)
            self._undo_kind = "clear"
            self._undo_btn.setText(tr("undo.label"))
            self._undo_btn.show()
            self._undo_timer.start(5000)
        self._frame_timer.stop()
        self._frames.reset()
        self._last_ts = None
        self.rx_view.clear()
        self._line_is_tx = False
        self._cap_warned = False
        self.rx_bytes = 0
        self.tx_bytes = 0
        self._sent_count = 0
        self.sent_lbl.setText(tr("tx.sent_count", n=0))
        self.update_counts()
        if offer_undo:
            self._notify(tr("rx.cleared"), "warn", ms=5000)
    def update_counts(self):
        self.rx_count_label.setText(f"RX: {self.rx_bytes} B | TX: {self.tx_bytes} B")

    def showEvent(self, event):  # noqa: N802 - Qt naming
        super().showEvent(event)
        theme.apply_native_dark(self, bool(theme.resolved_dark()))   # U51 (frame exists now)
        if not getattr(self, "_split_room_done", False):
            self._split_room_done = True

            def _first_layout() -> None:
                self._give_data_area_the_room()   # U79
                self._fit_minimum_width()         # U81

            QTimer.singleShot(0, _first_layout)

    def closeEvent(self, event):
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