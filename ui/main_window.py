"""Main window: port selection, baudrate, format dropdowns, quick send panel."""

from __future__ import annotations

import json
import os
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.protocol import (
    TEXT_ENCODINGS,
    append_checksum,
    ascii_str_to_bytes,
    bytes_to_ascii_str,
    bytes_to_hex_str,
    decode_text,
    encode_text,
    hex_str_to_bytes,
)
from app import __version__
from app.config import load_config, save_config
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.quick_send_panel import QuickSendPanel
from app import i18n
from app.i18n import tr

def resource_path(rel: str) -> str:
    """Resolve resource path; works in source and PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if os.path.dirname(base).endswith("ui") or base.endswith("ui"):
        base = os.path.dirname(base)
    return os.path.join(base, rel)


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

# -- timestamp formats ---------------------------------------------------------
TS_OFF = 0
TS_HMS = 1
TS_HMS_MS = 2
TS_FULL_MS = 3

CHECKSUM_KEYS = ["none", "crc16-modbus", "crc16-ccitt", "crc32", "sum8"]

# -- serial parameters (T1); plain values accepted by pyserial ---------------
BYTESIZE_KEYS = [5, 6, 7, 8]
PARITY_KEYS = ["N", "O", "E", "M", "S"]
STOPBITS_KEYS = [1, 1.5, 2]
FLOW_KEYS = ["none", "xonxoff", "rtscts"]
HISTORY_MAX = 50
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_MAX_SECONDS = 30 * 60
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

        self.worker = SerialWorker(self)
        self.worker.received.connect(self.on_received)
        self.worker.log.connect(self.on_log_line)
        self.worker.opened.connect(self.on_opened_changed)

        self.rx_bytes = 0
        self.tx_bytes = 0
        self._last_ts: float | None = None
        self._clock_offset = time.time() - time.monotonic()

        # initial language from config (default: follow system)
        i18n.set_language(str(load_config().get("language", "system")))

        self._log_fp = None
        self._log_started = 0.0
        self._log_bytes = 0
        self._send_history: list[str] = []
        self._sent_count = 0
        self._repeat_timer = QTimer(self)
        self._repeat_timer.timeout.connect(self.on_send)
        self._file_timer = QTimer(self)
        self._file_timer.timeout.connect(self._send_file_chunk)
        self._sig_timer = QTimer(self)
        self._sig_timer.timeout.connect(self._poll_signals)
        self._sig_timer.start(50)
        self._file_data = b""
        self._file_pos = 0
        self._file_path = ""

        self._build_ui()
        self._build_menu()

        # send history (T5) from config
        self._send_history = [str(h) for h in load_config().get("send_history", [])
                              if str(h).strip()][:HISTORY_MAX]
        self.history_combo.addItems(self._send_history)

        # auto-reply rules (T10) from config
        cfg = load_config()
        self._auto_rules = [r for r in cfg.get("auto_reply", []) if isinstance(r, dict)]
        self._reply_buf = b""
        self.auto_reply_check.setChecked(bool(cfg.get("auto_reply_enabled", False)))

        # initial theme from config (default: follow system)
        choice = load_config().get("theme", "system")
        if choice == "dark":
            theme.set_override(True)
        elif choice == "light":
            theme.set_override(False)
        else:
            theme.set_override(None)
        theme.apply_theme(QApplication.instance())

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_ports)
        self.refresh_timer.start(3000)

    # -- UI -----------------------------------------------------------------

    def _build_menu(self):
        self._view_menu = self.menuBar().addMenu(tr("menu.view"))
        view_menu = self._view_menu
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

        # language submenu (U19)
        view_menu.addSeparator()
        self._lang_menu = view_menu.addMenu(tr("menu.language"))
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
        view_menu.addSeparator()
        self._cfg_menu = view_menu.addMenu(tr("cfg.menu"))
        self._cfg_export_act = QAction(tr("cfg.export"), self)
        self._cfg_import_act = QAction(tr("cfg.import"), self)
        self._cfg_export_act.triggered.connect(self.on_export_config)
        self._cfg_import_act.triggered.connect(self.on_import_config)
        self._cfg_menu.addAction(self._cfg_export_act)
        self._cfg_menu.addAction(self._cfg_import_act)

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
        """Re-apply every translated string (called after a language change)."""
        self._view_menu.setTitle(tr("menu.view"))
        self._lang_menu.setTitle(tr("menu.language"))
        self._cfg_menu.setTitle(tr("cfg.menu"))
        self._cfg_export_act.setText(tr("cfg.export"))
        self._cfg_import_act.setText(tr("cfg.import"))
        self._theme_system.setText(tr("theme.system"))
        self._theme_dark.setText(tr("theme.dark"))
        self._theme_light.setText(tr("theme.light"))
        self._lang_system.setText(tr("lang.system"))
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
        self.header_edit.setPlaceholderText(tr("header.placeholder"))
        self.header_edit.setToolTip(tr("header.tip"))
        self._ts_lbl.setText(tr("ts.label"))
        self._reload_combo(self.ts_combo, [
            tr("ts.off"), "HH:MM:SS", "HH:MM:SS.mmm", "yyyy-MM-dd HH:MM:SS.mmm"])
        self.ts_combo.setToolTip(tr("ts.tip"))
        self.clear_btn.setText(tr("btn.clear"))
        self.save_log_btn.setText(tr("btn.save_log_quick"))
        self.save_log_btn.setToolTip(tr("log.quick.tip"))
        self.save_log_as_btn.setText(tr("btn.save_log_as"))
        self.dtr_check.setToolTip(tr("sig.tip"))
        self.rts_check.setToolTip(tr("sig.tip"))
        self.sig_lbl.setToolTip(tr("sig.tip"))
        self.auto_reply_check.setText(tr("rb.enable"))
        self.auto_reply_check.setToolTip(tr("rb.enable.tip"))
        self.rules_btn.setText(tr("rb.rules_btn"))
        self.send_file_btn.setText(tr("btn.cancel_send") if self._file_timer.isActive()
                                    else tr("btn.send_file"))
        self.send_file_btn.setToolTip(tr("btn.send_file"))
        self.autosave_check.setText(tr("log.autosave"))
        self.autosave_check.setToolTip(tr("log.autosave.tip"))
        self._dbit_lbl.setText(tr("params.databits"))
        self._parity_lbl.setText(tr("params.parity"))
        self._stopbit_lbl.setText(tr("params.stopbits"))
        self._flow_lbl.setText(tr("params.flow"))
        self._reload_combo(self.parity_combo, [tr("parity.none"), tr("parity.odd"), tr("parity.even"),
                                               "Mark", "Space"])
        self._reload_combo(self.flow_combo, [tr("flow.none"), tr("flow.sw"), tr("flow.hw")])
        for combo in self._param_combos:
            combo.setToolTip(tr("params.tip"))
        self._hist_lbl.setText(tr("tx.history"))
        self.history_combo.setToolTip(tr("tx.history.tip", n=HISTORY_MAX))
        self.repeat_check.setText(tr("tx.repeat"))
        self.repeat_check.setToolTip(tr("tx.repeat.tip"))
        self.repeat_ms.setToolTip(tr("tx.interval.tip"))
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
        self.statusBar().showMessage(tr("status.opened") if self.worker.is_open() else tr("status.idle"))
        if self.worker.is_open():
            port = self.port_combo.currentData() or ""
            baud = self.baud_combo.currentText().strip()
            self.status_light.setText(tr("status.connected", port=port, baud=baud))
        else:
            self.status_light.setText(tr("status.disconnected"))

    def _set_theme_system(self):
        theme.set_override(None)
        theme.apply_theme(QApplication.instance())
        self._persist_theme("system")

    def _set_theme_dark(self):
        theme.set_override(True)
        theme.apply_theme(QApplication.instance())
        self._persist_theme("dark")

    def _set_theme_light(self):
        theme.set_override(False)
        theme.apply_theme(QApplication.instance())
        self._persist_theme("light")

    def _persist_theme(self, choice: str):
        config = load_config()
        config["theme"] = choice
        save_config(config)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        # --- connection bar -------------------------------------------------
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(220)
        bar.addWidget(self.port_combo)

        self.refresh_btn = QPushButton(tr("port.refresh"))
        self.refresh_btn.clicked.connect(self.refresh_ports)
        bar.addWidget(self.refresh_btn)

        bar.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([str(b) for b in BAUDRATES])
        self.baud_combo.setEditable(True)
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setToolTip(tr("baud.tip"))
        self.baud_combo.lineEdit().textChanged.connect(self._check_baud)
        bar.addWidget(self.baud_combo)

        self.open_btn = QPushButton(tr("port.open"))
        self.open_btn.clicked.connect(self.toggle_open)
        bar.addWidget(self.open_btn)

        bar.addSpacing(12)
        self._rx_fmt_lbl = QLabel(tr("rxfmt.label"))
        bar.addWidget(self._rx_fmt_lbl)
        self.rx_fmt_combo = QComboBox()
        self.rx_fmt_combo.addItems(["ASCII", "HEX", "HEX+ASCII"])
        self.rx_fmt_combo.setCurrentIndex(RX_HEX)
        self.rx_fmt_combo.setToolTip(tr("rxfmt.tip"))
        bar.addWidget(self.rx_fmt_combo)

        bar.addStretch(1)
        root.addLayout(bar)

        # --- serial parameters row (T1) --------------------------------------
        self._param_combos = []
        params = QHBoxLayout()
        self._dbit_lbl = QLabel(tr("params.databits"))
        params.addWidget(self._dbit_lbl)
        self.dbits_combo = QComboBox()
        self.dbits_combo.addItems([str(b) for b in BYTESIZE_KEYS])
        self.dbits_combo.setCurrentIndex(len(BYTESIZE_KEYS) - 1)     # 8
        params.addWidget(self.dbits_combo)

        self._parity_lbl = QLabel(tr("params.parity"))
        params.addWidget(self._parity_lbl)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems([tr("parity.none"), tr("parity.odd"), tr("parity.even"),
                                    "Mark", "Space"])
        params.addWidget(self.parity_combo)

        self._stopbit_lbl = QLabel(tr("params.stopbits"))
        params.addWidget(self._stopbit_lbl)
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems([str(b) for b in STOPBITS_KEYS])
        params.addWidget(self.stopbits_combo)

        self._flow_lbl = QLabel(tr("params.flow"))
        params.addWidget(self._flow_lbl)
        self.flow_combo = QComboBox()
        self.flow_combo.addItems([tr("flow.none"), tr("flow.sw"), tr("flow.hw")])
        params.addWidget(self.flow_combo)

        self._enc_lbl = QLabel(tr("params.encoding"))
        params.addWidget(self._enc_lbl)
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["ASCII", "UTF-8", "GBK", "GB2312"])
        self.encoding_combo.setToolTip(tr("params.encoding.tip"))
        params.addWidget(self.encoding_combo)

        params.addSpacing(12)
        self.dtr_check = QCheckBox("DTR")
        self.dtr_check.setToolTip(tr("sig.tip"))
        self.dtr_check.toggled.connect(self.worker.set_dtr)
        params.addWidget(self.dtr_check)
        self.rts_check = QCheckBox("RTS")
        self.rts_check.setToolTip(tr("sig.tip"))
        self.rts_check.toggled.connect(self.worker.set_rts)
        params.addWidget(self.rts_check)
        self.sig_lbl = QLabel("CTS ○  DSR ○  DCD ○  RI ○")
        self.sig_lbl.setToolTip(tr("sig.tip"))
        params.addWidget(self.sig_lbl)

        self._param_combos = [self.dbits_combo, self.parity_combo, self.stopbits_combo, self.flow_combo]
        for combo in self._param_combos:
            combo.setToolTip(tr("params.tip"))
        params.addStretch(1)
        root.addLayout(params)

        # --- main splitter: left (rx/tx) + right (quick send) ---------------
        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)

        # receive group -----------------------------------------------------
        self._rx_group = QGroupBox(tr("group.rx"))
        rx_group = self._rx_group
        rx_layout = QVBoxLayout(rx_group)

        rx_opts = QHBoxLayout()
        self._split_lbl = QLabel(tr("split.label"))
        rx_opts.addWidget(self._split_lbl)
        self.split_combo = QComboBox()
        self.split_combo.addItems([tr("split.off"), tr("split.auto"), tr("split.manual"), tr("split.header")])
        self.split_combo.setCurrentIndex(SPLIT_AUTO)
        self.split_combo.setToolTip(tr("split.tip"))
        self.split_combo.currentIndexChanged.connect(self._on_split_mode_changed)
        rx_opts.addWidget(self.split_combo)

        self.split_ms_edit = QLineEdit("10")
        self.split_ms_edit.setMaximumWidth(52)
        self.split_ms_edit.setToolTip(tr("split.ms.tip"))
        self.split_ms_edit.setEnabled(False)
        rx_opts.addWidget(self.split_ms_edit)

        self.header_edit = QLineEdit("fw:")
        self.header_edit.setMaximumWidth(90)
        self.header_edit.setPlaceholderText(tr("header.placeholder"))
        self.header_edit.setToolTip(tr("header.tip"))
        self.header_edit.setEnabled(False)
        self.header_edit.textChanged.connect(self._on_header_changed)
        rx_opts.addWidget(self.header_edit)

        self._ts_lbl = QLabel(tr("ts.label"))
        rx_opts.addWidget(self._ts_lbl)
        self.ts_combo = QComboBox()
        self.ts_combo.addItems([tr("ts.off"), "HH:MM:SS", "HH:MM:SS.mmm", "yyyy-MM-dd HH:MM:SS.mmm"])
        self.ts_combo.setCurrentIndex(TS_HMS_MS)
        self.ts_combo.setToolTip(tr("ts.tip"))
        rx_opts.addWidget(self.ts_combo)

        rx_opts.addStretch(1)
        rx_layout.addLayout(rx_opts)

        # receive toolbar (U25): its own row so the log buttons are easy to spot
        toolbar = QHBoxLayout()
        self.save_log_btn = QPushButton(tr("btn.save_log_quick"))
        self.save_log_btn.setToolTip(tr("log.quick.tip"))
        self.save_log_btn.clicked.connect(self.on_save_log_quick)
        toolbar.addWidget(self.save_log_btn)

        self.save_log_as_btn = QPushButton(tr("btn.save_log_as"))
        self.save_log_as_btn.clicked.connect(self.on_save_log_as)
        toolbar.addWidget(self.save_log_as_btn)

        self.autosave_check = QCheckBox(tr("log.autosave"))
        self.autosave_check.setToolTip(tr("log.autosave.tip"))
        self.autosave_check.toggled.connect(self._on_autosave_toggled)
        toolbar.addWidget(self.autosave_check)

        self.clear_btn = QPushButton(tr("btn.clear"))
        self.clear_btn.clicked.connect(self.on_clear)
        toolbar.addWidget(self.clear_btn)

        toolbar.addStretch(1)
        self.rx_count_label = QLabel("RX: 0 B | TX: 0 B")
        toolbar.addWidget(self.rx_count_label)
        rx_layout.addLayout(toolbar)

        self.rx_view = QPlainTextEdit()
        self.rx_view.setReadOnly(True)
        self.rx_view.setMaximumBlockCount(20000)
        rx_layout.addWidget(self.rx_view)
        left_layout.addWidget(rx_group, 3)

        # send group ----------------------------------------------------------
        self._tx_group = QGroupBox(tr("group.tx"))
        tx_group = self._tx_group
        tx_layout = QVBoxLayout(tx_group)

        hist_row = QHBoxLayout()
        self._hist_lbl = QLabel(tr("tx.history"))
        hist_row.addWidget(self._hist_lbl)
        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(200)
        self.history_combo.setToolTip(tr("tx.history.tip", n=HISTORY_MAX))
        self.history_combo.activated.connect(self._on_history_pick)
        hist_row.addWidget(self.history_combo, 1)
        tx_layout.addLayout(hist_row)

        tx_row = QHBoxLayout()
        self.tx_edit = QPlainTextEdit()
        self.tx_edit.setMaximumHeight(90)
        tx_row.addWidget(self.tx_edit, 1)

        tx_col = QVBoxLayout()
        tx_fmt_row = QHBoxLayout()
        self._tx_fmt_lbl = QLabel(tr("txfmt.label"))
        tx_fmt_row.addWidget(self._tx_fmt_lbl)
        self.tx_fmt_combo = QComboBox()
        self.tx_fmt_combo.addItems(["HEX", "ASCII"])
        self.tx_fmt_combo.setToolTip(tr("txfmt.tip"))
        tx_fmt_row.addWidget(self.tx_fmt_combo)
        self.crlf_check = QCheckBox(tr("tx.crlf"))
        self.crlf_check.setToolTip(tr("tx.crlf.tip"))
        tx_fmt_row.addWidget(self.crlf_check)
        self.escape_check = QCheckBox(tr("tx.escape"))
        self.escape_check.setChecked(True)
        self.escape_check.setToolTip(tr("tx.escape.tip"))
        tx_fmt_row.addWidget(self.escape_check)
        self.tx_fmt_combo.currentIndexChanged.connect(self._on_tx_fmt_changed)
        self._on_tx_fmt_changed(self.tx_fmt_combo.currentIndex())
        tx_col.addLayout(tx_fmt_row)

        crc_row = QHBoxLayout()
        self._crc_lbl = QLabel(tr("crc.label"))
        crc_row.addWidget(self._crc_lbl)
        self.checksum_combo = QComboBox()
        self.checksum_combo.addItems([tr("crc.none"), "CRC16-Modbus", "CRC16-CCITT", "CRC32", "SUM8"])
        self.checksum_combo.setToolTip(tr("crc.tip"))
        crc_row.addWidget(self.checksum_combo)
        tx_col.addLayout(crc_row)

        repeat_row = QHBoxLayout()
        self.repeat_check = QCheckBox(tr("tx.repeat"))
        self.repeat_check.setToolTip(tr("tx.repeat.tip"))
        self.repeat_check.toggled.connect(self._on_repeat_toggled)
        repeat_row.addWidget(self.repeat_check)
        self.repeat_ms = QSpinBox()
        self.repeat_ms.setRange(10, 60000)
        self.repeat_ms.setValue(1000)
        self.repeat_ms.setSingleStep(100)
        self.repeat_ms.setSuffix(" ms")
        self.repeat_ms.setMaximumWidth(96)
        self.repeat_ms.setToolTip(tr("tx.interval.tip"))
        self.repeat_ms.valueChanged.connect(self._on_repeat_interval)
        repeat_row.addWidget(self.repeat_ms)
        self.sent_lbl = QLabel(tr("tx.sent_count", n=0))
        repeat_row.addWidget(self.sent_lbl)
        tx_col.addLayout(repeat_row)

        self.send_btn = QPushButton(tr("btn.send"))
        self.send_btn.clicked.connect(self.on_send)
        self.send_btn.setDefault(True)
        tx_col.addWidget(self.send_btn)
        tx_col.addStretch(1)
        tx_row.addLayout(tx_col)
        tx_layout.addLayout(tx_row)

        file_row = QHBoxLayout()
        self.send_file_btn = QPushButton(tr("btn.send_file"))
        self.send_file_btn.setToolTip(tr("btn.send_file"))
        self.send_file_btn.clicked.connect(self.on_send_file)
        file_row.addWidget(self.send_file_btn)
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.file_progress.setMaximumWidth(220)
        file_row.addWidget(self.file_progress)
        self.file_info_lbl = QLabel("")
        file_row.addWidget(self.file_info_lbl, 1)

        self.auto_reply_check = QCheckBox(tr("rb.enable"))
        self.auto_reply_check.setToolTip(tr("rb.enable.tip"))
        self.auto_reply_check.toggled.connect(self._on_auto_reply_toggled)
        file_row.addWidget(self.auto_reply_check)
        self.rules_btn = QPushButton(tr("rb.rules_btn"))
        self.rules_btn.clicked.connect(self._edit_rules)
        file_row.addWidget(self.rules_btn)
        tx_layout.addLayout(file_row)
        left_layout.addWidget(tx_group, 1)

        splitter.addWidget(left)

        # right: quick send panel ---------------------------------------------
        self.quick_panel = QuickSendPanel()
        self.quick_panel.send_payload.connect(self.on_quick_send)
        self.quick_panel.log.connect(self.on_log_line)
        splitter.addWidget(self.quick_panel)
        splitter.setSizes([820, 340])

        root.addWidget(splitter, 1)

        # status bar with connection indicator -------------------------------
        self.status_light = QLabel(tr("status.disconnected"))
        self.status_light.setStyleSheet("color: #999999; font-weight: bold; padding-right: 8px;")
        self.statusBar().addPermanentWidget(self.status_light)
        self.statusBar().showMessage(tr("status.idle"))
        self.setCentralWidget(central)

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
            self.statusBar().showMessage(tr("cfg.exported", path=path), 5000)
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
        for key in ("theme", "language", "quick_send", "send_history",
                    "auto_reply", "auto_reply_enabled"):
            if key in incoming:
                config[key] = incoming[key]
        if not save_config(config):
            self.on_log_line(tr("cfg.import_fail", e="config.json"))
            return
        self._apply_config()
        self.statusBar().showMessage(tr("cfg.imported", path=path), 5000)

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
        {"dark": self._theme_dark, "light": self._theme_light}.get(
            choice, self._theme_system).setChecked(True)

        i18n.set_language(str(cfg.get("language", "system")))
        self.retranslate()

        self.quick_panel.reload_from_config()

        self._send_history = [str(h) for h in cfg.get("send_history", []) if str(h).strip()][:HISTORY_MAX]
        self.history_combo.clear()
        self.history_combo.addItems(self._send_history)

        self._auto_rules = [r for r in cfg.get("auto_reply", []) if isinstance(r, dict)]
        self.auto_reply_check.setChecked(bool(cfg.get("auto_reply_enabled", False)))
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
        self.statusBar().showMessage(tr("rb.saved", n=len(self._auto_rules)), 5000)

    def _check_auto_reply(self, data: bytes) -> None:
        """Send the configured reply when a match string shows up in the stream."""
        if not self.auto_reply_check.isChecked() or not self._auto_rules:
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
                    self.statusBar().showMessage(tr("rb.sent", n=len(reply)), 3000)
                self._reply_buf = b""
                break

    # -- modem status lines (T9) ---------------------------------------------

    def _poll_signals(self) -> None:
        """Refresh the CTS/DSR/DCD/RI indicators (50 ms timer)."""
        sig = self.worker.signals()
        if not sig.get("open"):
            self.sig_lbl.setText("CTS ○  DSR ○  DCD ○  RI ○")
            return
        mark = lambda on: "●" if on else "○"
        self.sig_lbl.setText(
            f"CTS {mark(sig['cts'])}  DSR {mark(sig['dsr'])}  "
            f"DCD {mark(sig['dcd'])}  RI {mark(sig['ri'])}")

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
            self.statusBar().showMessage(tr("file.no_port"), 5000)
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
        self.statusBar().showMessage(tr("file.done", name=name, size=size), 5000)

    def _abort_file_send(self):
        self._file_timer.stop()
        self.send_file_btn.setText(tr("btn.send_file"))
        self.file_info_lbl.setText("")
        self.file_progress.setValue(0)

    # -- receive log to file (T4) -------------------------------------------

    def _log_open(self) -> None:
        """Open a new log segment under logs/ (auto-save mode)."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            name = time.strftime("serial_%Y%m%d_%H%M%S.txt")
            self._log_path = os.path.join(LOG_DIR, name)
            self._log_fp = open(self._log_path, "a", encoding="utf-8")
            self._log_started = time.time()
            self._log_bytes = 0
            self.statusBar().showMessage(tr("log.autosave.on", path=self._log_path), 5000)
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
        if (self._log_bytes > LOG_MAX_BYTES
                or time.time() - self._log_started > LOG_MAX_SECONDS):
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

    def _on_autosave_toggled(self, checked: bool) -> None:
        if checked:
            self._log_open()
            if self._log_fp is None:
                self.autosave_check.setChecked(False)
        else:
            self._log_close()

    def on_save_log_quick(self) -> None:
        """One-click save of the receive pane into logs/ (U25-D)."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            path = os.path.join(LOG_DIR, time.strftime("serial_RX_%Y%m%d_%H%M%S.txt"))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.rx_view.toPlainText())
                fh.write("\n")
            self.statusBar().showMessage(tr("log.saved", path=path), 5000)
        except OSError as exc:
            self.on_log_line(tr("log.save_fail", e=exc))

    def on_save_log_as(self) -> None:
        """Save the receive pane to a user-chosen path (U25-D)."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except OSError:
            pass
        default = os.path.join(LOG_DIR, time.strftime("serial_%Y%m%d_%H%M%S.txt"))
        path, _ = QFileDialog.getSaveFileName(self, tr("log.save.title"), default, "Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.rx_view.toPlainText())
                fh.write("\n")
            self.statusBar().showMessage(tr("log.saved", path=path), 5000)
        except OSError as exc:
            self.on_log_line(tr("log.save_fail", e=exc))

    # -- quick helpers --------------------------------------------------------

    def _emit_rx_text(self, text: str) -> None:
        """Insert text into the receive pane and mirror it to the auto-save log."""
        self.rx_view.insertPlainText(text)
        self._log_append(text)

    def _on_history_pick(self, index: int):
        text = self.history_combo.itemText(index)
        if text:
            self.tx_edit.setPlainText(text)

    def _remember_send(self, text: str):
        """Push a sent command into the dedup history (max HISTORY_MAX) and persist it."""
        text = text.strip()
        if not text:
            return
        self._send_history = [text] + [h for h in self._send_history if h != text]
        self._send_history = self._send_history[:HISTORY_MAX]
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        self.history_combo.addItems(self._send_history)
        self.history_combo.blockSignals(False)
        config = load_config()
        config["send_history"] = self._send_history
        save_config(config)

    def _on_repeat_toggled(self, checked: bool):
        if checked:
            self._sent_count = 0
            self.sent_lbl.setText(tr("tx.sent_count", n=0))
            self._repeat_timer.start(self.repeat_ms.value())
        else:
            self._repeat_timer.stop()

    def _on_repeat_interval(self, value: int):
        if self._repeat_timer.isActive():
            self._repeat_timer.setInterval(value)

    def _stop_repeat(self):
        if self.repeat_check.isChecked():
            self.repeat_check.setChecked(False)   # triggers _on_repeat_toggled -> stop
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
        # appending CRLF only makes sense for ASCII (index 1)
        self.crlf_check.setEnabled(index == 1)

    def _on_split_mode_changed(self, index: int):
        self.split_ms_edit.setEnabled(index == SPLIT_MANUAL)
        self.header_edit.setEnabled(index == SPLIT_HEADER)

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
        return max(3.5 * char_ms, 2.0)

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
        mode = self.ts_combo.currentIndex()
        if mode == TS_OFF:
            return ""
        wall = ts + self._clock_offset
        t = time.localtime(wall)
        ms = int((wall - int(wall)) * 1000)
        if mode == TS_HMS:
            return time.strftime("[%H:%M:%S] ", t)
        if mode == TS_HMS_MS:
            return time.strftime(f"[%H:%M:%S.{ms:03d}] ", t)
        return time.strftime(f"[%Y-%m-%d %H:%M:%S.{ms:03d}] ", t)

    # -- actions -----------------------------------------------------------------

    def refresh_ports(self):
        current = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        for dev, desc in list_serial_ports():
            self.port_combo.addItem(f"{dev}  [{desc}]" if desc else dev, dev)
        if current:
            idx = self.port_combo.findText(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        self.port_combo.blockSignals(False)

    def toggle_open(self):
        if self.worker.is_open():
            self.worker.close_port()
            self.open_btn.setText(tr("port.open"))
        else:
            if self.port_combo.count() == 0:
                self.statusBar().showMessage(tr("status.no_port"))
                return
            device = self.port_combo.currentData()
            try:
                baud = int(self.baud_combo.currentText().strip())
            except ValueError:
                self.statusBar().showMessage(tr("status.bad_baud"), 5000)
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
            self.status_light.setStyleSheet("color: #2ecc40; font-weight: bold; padding-right: 8px;")
            self.statusBar().showMessage(tr("status.opened"))
            for combo in self._param_combos:
                combo.setEnabled(False)
        else:
            self.open_btn.setText(tr("port.open"))
            self.status_light.setText(tr("status.disconnected"))
            self.status_light.setStyleSheet("color: #ff4136; font-weight: bold; padding-right: 8px;")
            self._stop_repeat()
            self._abort_file_send()
            self.refresh_timer.start()
            for combo in self._param_combos:
                combo.setEnabled(True)
            if not self.worker.is_open():
                self.statusBar().showMessage(tr("status.closed"))

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
        except ValueError as exc:
            self.on_log_line(tr("log.send_error", e=exc))
            return
        payload = self._apply_checksum(payload)
        if self.tx_fmt_combo.currentIndex() == 1 and self.crlf_check.isChecked():
            payload += b"\r\n"
        self.worker.send(payload)
        self.tx_bytes += len(payload)
        self._sent_count += 1
        self.sent_lbl.setText(tr("tx.sent_count", n=self._sent_count))
        self._remember_send(text)
        self.update_counts()

    def on_quick_send(self, payload: bytes):
        payload = self._apply_checksum(payload)
        self.worker.send(payload)
        self.tx_bytes += len(payload)
        self.update_counts()

    def on_received(self, ts: float, data: bytes):
        self._check_auto_reply(data)
        self.rx_bytes += len(data)
        self.update_counts()

        mode = self.split_combo.currentIndex()

        if mode == SPLIT_HEADER:
            self._append_header_split(data, ts)
            self._last_ts = ts
            return

        text = self._format_rx(data)

        threshold = self._split_threshold_ms()
        new_line = False
        if self._last_ts is None:
            new_line = True
        elif threshold is not None:
            gap_ms = (ts - self._last_ts) * 1000.0
            new_line = gap_ms > threshold
        self._last_ts = ts

        has_text = self.rx_view.document().characterCount() > 1
        if new_line:
            prefix = self._ts_prefix(ts)
            if has_text:
                self._emit_rx_text("\n")
            if prefix:
                self._emit_rx_text(prefix)
        self._emit_rx_text(text)

        sb = self.rx_view.verticalScrollBar()
        sb.setValue(sb.maximum())

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
                # bytes before the first header: continue current line
                if seg:
                    self._emit_rx_text(self._format_rx(seg))
                continue
            if not seg:
                continue  # adjacent headers, frame with empty body
            if self.rx_view.document().characterCount() > 1:
                self._emit_rx_text("\n")
            self._emit_rx_text(self._ts_prefix(ts))
            self._emit_rx_text(self._format_rx(header_b + seg))

        sb = self.rx_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_log_line(self, line: str):
        self.statusBar().showMessage(line, 5000)

    def on_clear(self):
        self.rx_view.clear()
        self.rx_bytes = 0
        self.update_counts()

    def update_counts(self):
        self.rx_count_label.setText(f"RX: {self.rx_bytes} B | TX: {self.tx_bytes} B")

    def closeEvent(self, event):
        self._sig_timer.stop()
        self._log_close()
        self.refresh_timer.stop()
        self.quick_panel.save()
        self.worker.close_port()
        super().closeEvent(event)