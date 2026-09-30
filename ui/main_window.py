"""Main window: port selection, baudrate, format dropdowns, quick send panel."""

from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.protocol import (
    append_checksum,
    ascii_str_to_bytes,
    bytes_to_ascii_str,
    bytes_to_hex_str,
    hex_str_to_bytes,
)
from app import __version__
from app.config import load_config, save_config
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.quick_send_panel import QuickSendPanel

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

        self._build_ui()
        self._build_menu()

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
        view_menu = self.menuBar().addMenu("视图")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)

        choice = load_config().get("theme", "system")

        self._theme_system = QAction("跟随系统", self, checkable=True)
        self._theme_dark = QAction("深色", self, checkable=True)
        self._theme_light = QAction("浅色", self, checkable=True)

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

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        bar.addWidget(self.refresh_btn)

        bar.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([str(b) for b in BAUDRATES])
        self.baud_combo.setEditable(True)
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setToolTip("可直接输入自定义波特率（如 1000000），或点右侧箭头选择 26 档预设")
        self.baud_combo.lineEdit().textChanged.connect(self._check_baud)
        bar.addWidget(self.baud_combo)

        self.open_btn = QPushButton("打开")
        self.open_btn.clicked.connect(self.toggle_open)
        bar.addWidget(self.open_btn)

        bar.addSpacing(12)
        bar.addWidget(QLabel("接收格式:"))
        self.rx_fmt_combo = QComboBox()
        self.rx_fmt_combo.addItems(["ASCII", "HEX", "HEX+ASCII"])
        self.rx_fmt_combo.setCurrentIndex(RX_HEX)
        self.rx_fmt_combo.setToolTip("接收显示格式\nASCII：字符显示\nHEX：十六进制显示\nHEX+ASCII：两者对照")
        bar.addWidget(self.rx_fmt_combo)

        bar.addStretch(1)
        root.addLayout(bar)

        # --- main splitter: left (rx/tx) + right (quick send) ---------------
        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)

        # receive group -----------------------------------------------------
        rx_group = QGroupBox("接收")
        rx_layout = QVBoxLayout(rx_group)

        rx_opts = QHBoxLayout()
        rx_opts.addWidget(QLabel("分包:"))
        self.split_combo = QComboBox()
        self.split_combo.addItems(["不分包", "自动(按波特率)", "手动(ms)", "按帧头"])
        self.split_combo.setCurrentIndex(SPLIT_AUTO)
        self.split_combo.setToolTip("分包分行方式\n自动：按波特率 3.5 字符时间\n手动：指定毫秒间隔\n按帧头：识别帧头字符串分行")
        self.split_combo.currentIndexChanged.connect(self._on_split_mode_changed)
        rx_opts.addWidget(self.split_combo)

        self.split_ms_edit = QLineEdit("10")
        self.split_ms_edit.setMaximumWidth(52)
        self.split_ms_edit.setToolTip("手动分包间隔（毫秒）")
        self.split_ms_edit.setEnabled(False)
        rx_opts.addWidget(self.split_ms_edit)

        self.header_edit = QLineEdit("fw:")
        self.header_edit.setMaximumWidth(90)
        self.header_edit.setPlaceholderText("帧头如 fw:")
        self.header_edit.setToolTip("按帧头分包的帧头字符串\n填写后自动切换为按帧头模式")
        self.header_edit.setEnabled(False)
        self.header_edit.textChanged.connect(self._on_header_changed)
        rx_opts.addWidget(self.header_edit)

        rx_opts.addWidget(QLabel("时间戳:"))
        self.ts_combo = QComboBox()
        self.ts_combo.addItems(["不显示", "HH:MM:SS", "HH:MM:SS.mmm", "yyyy-MM-dd HH:MM:SS.mmm"])
        self.ts_combo.setCurrentIndex(TS_HMS_MS)
        self.ts_combo.setToolTip("行首时间戳格式\n建议 SHELL 调试用 HH:MM:SS.mmm")
        rx_opts.addWidget(self.ts_combo)

        rx_opts.addStretch(1)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.on_clear)
        rx_opts.addWidget(self.clear_btn)
        self.rx_count_label = QLabel("RX: 0 B | TX: 0 B")
        rx_opts.addWidget(self.rx_count_label)
        rx_layout.addLayout(rx_opts)

        self.rx_view = QPlainTextEdit()
        self.rx_view.setReadOnly(True)
        self.rx_view.setMaximumBlockCount(20000)
        rx_layout.addWidget(self.rx_view)
        left_layout.addWidget(rx_group, 3)

        # send group ----------------------------------------------------------
        tx_group = QGroupBox("发送")
        tx_layout = QVBoxLayout(tx_group)
        tx_row = QHBoxLayout()
        self.tx_edit = QPlainTextEdit()
        self.tx_edit.setMaximumHeight(90)
        tx_row.addWidget(self.tx_edit, 1)

        tx_col = QVBoxLayout()
        tx_fmt_row = QHBoxLayout()
        tx_fmt_row.addWidget(QLabel("格式:"))
        self.tx_fmt_combo = QComboBox()
        self.tx_fmt_combo.addItems(["HEX", "ASCII"])
        self.tx_fmt_combo.setToolTip("发送格式\nHEX：十六进制数据\nASCII：文本（支持 \r\n 转义）")
        tx_fmt_row.addWidget(self.tx_fmt_combo)
        tx_col.addLayout(tx_fmt_row)

        crc_row = QHBoxLayout()
        crc_row.addWidget(QLabel("校验:"))
        self.checksum_combo = QComboBox()
        self.checksum_combo.addItems(["无", "CRC16-Modbus", "CRC16-CCITT", "CRC32", "SUM8"])
        self.checksum_combo.setToolTip("发送时自动追加的校验\nCRC16-Modbus：低字节在前（Modbus RTU）\nCRC16-CCITT：高字节在前\nCRC32：4 字节大端\nSUM8：单字节累加和")
        crc_row.addWidget(self.checksum_combo)
        tx_col.addLayout(crc_row)

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.on_send)
        self.send_btn.setDefault(True)
        tx_col.addWidget(self.send_btn)
        tx_col.addStretch(1)
        tx_row.addLayout(tx_col)
        tx_layout.addLayout(tx_row)
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
        self.status_light = QLabel("● 未连接")
        self.status_light.setStyleSheet("color: #999999; font-weight: bold; padding-right: 8px;")
        self.statusBar().addPermanentWidget(self.status_light)
        self.statusBar().showMessage("未打开串口")
        self.setCentralWidget(central)

    # -- helpers ---------------------------------------------------------------

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

    def _format_rx(self, data: bytes) -> str:
        mode = self.rx_fmt_combo.currentIndex()
        if mode == RX_HEX:
            return bytes_to_hex_str(data)
        if mode == RX_ASCII:
            return bytes_to_ascii_str(data)
        hex_s = bytes_to_hex_str(data)
        ascii_s = bytes_to_ascii_str(data)
        return f"{hex_s} | {ascii_s}"

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
            self.open_btn.setText("打开")
        else:
            if self.port_combo.count() == 0:
                self.statusBar().showMessage("未发现串口")
                return
            device = self.port_combo.currentData()
            try:
                baud = int(self.baud_combo.currentText().strip())
            except ValueError:
                self.statusBar().showMessage("波特率格式错误", 5000)
                return
            ok = self.worker.open_port(device, baud)
            if ok:
                self.refresh_timer.stop()  # keep port list stable while open

    def on_opened_changed(self, opened: bool):
        if opened:
            self.open_btn.setText("关闭")
            port = self.port_combo.currentData() or ""
            baud = self.baud_combo.currentText().strip()
            self.status_light.setText(f"● 已连接 {port} @ {baud}")
            self.status_light.setStyleSheet("color: #2ecc40; font-weight: bold; padding-right: 8px;")
            self.statusBar().showMessage("串口已打开")
        else:
            self.open_btn.setText("打开")
            self.status_light.setText("● 未连接")
            self.status_light.setStyleSheet("color: #ff4136; font-weight: bold; padding-right: 8px;")
            self.refresh_timer.start()
            if not self.worker.is_open():
                self.statusBar().showMessage("串口已关闭")

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
                payload = ascii_str_to_bytes(text)
        except ValueError as exc:
            self.on_log_line(f"发送内容错误: {exc}")
            return
        payload = self._apply_checksum(payload)
        self.worker.send(payload)
        self.tx_bytes += len(payload)
        self.update_counts()

    def on_quick_send(self, payload: bytes):
        payload = self._apply_checksum(payload)
        self.worker.send(payload)
        self.tx_bytes += len(payload)
        self.update_counts()

    def on_received(self, ts: float, data: bytes):
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
                self.rx_view.insertPlainText("\n")
            if prefix:
                self.rx_view.insertPlainText(prefix)
        self.rx_view.insertPlainText(text)

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
                    self.rx_view.insertPlainText(self._format_rx(seg))
                continue
            if not seg:
                continue  # adjacent headers, frame with empty body
            if self.rx_view.document().characterCount() > 1:
                self.rx_view.insertPlainText("\n")
            self.rx_view.insertPlainText(self._ts_prefix(ts))
            self.rx_view.insertPlainText(self._format_rx(header_b + seg))

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
        self.refresh_timer.stop()
        self.quick_panel.save()
        self.worker.close_port()
        super().closeEvent(event)