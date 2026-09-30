"""Quick send panel: editable command shortcuts, up to 99 entries, persisted."""

from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import hex_error_message, tr
from app.protocol import HexFormatError, ascii_str_to_bytes, hex_str_to_bytes

MAX_ENTRIES = 99
DEFAULT_ROWS = 10   # blank rows seeded on first run (U15)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")


class QuickSendPanel(QWidget):
    """Right-hand panel: list of editable quick-send commands.

    Each row: text edit + format combo (HEX/ASCII) + send button + delete.
    Persisted to config.json as JSON list; max 99 rows.
    """

    send_payload = Signal(bytes)   # parsed payload, no checksum applied yet
    error = Signal(str)            # user-facing format error text (U36)
    deleted = Signal(dict)         # removed row payload + index (U58: undo)
    log = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []   # [{text, hex, delay}]
        self._seq_timer = QTimer(self)
        self._seq_timer.setSingleShot(True)
        self._seq_timer.timeout.connect(self._seq_advance)
        self._seq_running = False
        self._seq_queue: list[dict] = []
        self._seq_index = 0
        self._build_ui()
        self._load()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        head = QHBoxLayout()
        self._title_lbl = QLabel(tr("qs.title"))
        head.addWidget(self._title_lbl)
        head.addStretch(1)
        self.count_label = QLabel("0/99")
        head.addWidget(self.count_label)
        layout.addLayout(head)

        # sequence mode (T13)
        seq_row = QHBoxLayout()
        self.seq_check = QCheckBox(tr("qs.seq"))
        self.seq_check.setToolTip(tr("qs.seq.tip"))
        self.seq_check.toggled.connect(self._on_seq_toggled)
        seq_row.addWidget(self.seq_check)
        self.seq_btn = QPushButton(tr("qs.run"))
        self.seq_btn.setToolTip(tr("qs.seq.tip"))
        self.seq_btn.setEnabled(False)
        self.seq_btn.clicked.connect(self.toggle_sequence)
        seq_row.addWidget(self.seq_btn)
        self.seq_label = QLabel("")
        seq_row.addWidget(self.seq_label)
        seq_row.addStretch(1)
        layout.addLayout(seq_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(300)   # U47: let the splitter decide the width
        self._container = QWidget()
        self._row_layout = QVBoxLayout(self._container)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(4)
        self._row_layout.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

        self.add_btn = QPushButton(tr("qs.add"))
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.add_btn.clicked.connect(lambda: self.add_row())
        layout.addWidget(self.add_btn)

    # -- rows ----------------------------------------------------------------

    def add_row(self, text: str = "", is_hex: bool = True, delay_ms: int = 500):
        if len(self._rows) >= MAX_ENTRIES:
            self.log.emit(tr("qs.max", n=MAX_ENTRIES))
            return
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)

        edit = QLineEdit(text)
        edit.setPlaceholderText(tr("qs.placeholder"))
        h.addWidget(edit, 1)

        fmt = QComboBox()
        fmt.addItems(["HEX", "ASCII"])
        fmt.setCurrentIndex(0 if is_hex else 1)
        h.addWidget(fmt)

        delay = QLineEdit(str(max(0, min(60000, int(delay_ms)))))   # U31: bare number, no arrows
        delay.setValidator(QIntValidator(0, 60000, self))
        delay.setMaximumWidth(104)
        delay.setToolTip(tr("qs.delay.tip"))
        h.addWidget(delay)

        send = QPushButton(tr("qs.send"))
        send.setMinimumWidth(52)
        send.setStyleSheet("padding: 2px 6px;")  # override global QSS padding
        send.clicked.connect(lambda: self._send_row(row))
        h.addWidget(send)

        h.addSpacing(16)   # U58: keep the destructive action away from "send"
        dele = QPushButton("\u00d7")
        dele.setObjectName("qsDel")           # styled by theme.py (dim -> red on hover)
        dele.setFixedWidth(28)
        dele.setStyleSheet("padding: 0px; background: transparent; border: none;")
        dele.setToolTip(tr("qs.delete.tip"))
        dele.clicked.connect(lambda: self._delete_row(row))
        h.addWidget(dele)

        self._row_layout.insertWidget(self._row_layout.count() - 1, row)
        self._rows.append({"widget": row, "edit": edit, "fmt": fmt, "send": send,
                           "del": dele, "delay": delay})
        self._update_count()

    def _payload_for(self, entry: dict) -> bytes | None:
        """Parse one row into bytes (None + log message when it cannot be parsed)."""
        text = entry["edit"].text().strip()
        if not text:
            self.log.emit(tr("qs.empty"))
            return None
        try:
            if entry["fmt"].currentIndex() == 0:
                return hex_str_to_bytes(text)
            return ascii_str_to_bytes(text)
        except ValueError as exc:
            if isinstance(exc, HexFormatError):
                self.error.emit(hex_error_message(exc))
            else:
                self.error.emit(tr("qs.bad_fmt", e=exc))
            return None

    def _send_row(self, row: QWidget):
        entry = self._find(row)
        if entry is None:
            return
        payload = self._payload_for(entry)
        if payload is not None:
            self.send_payload.emit(payload)

    # -- sequence mode (T13) --------------------------------------------------

    def _on_seq_toggled(self, checked: bool) -> None:
        self.seq_btn.setEnabled(checked)
        if not checked:
            self.stop_sequence()

    def toggle_sequence(self) -> None:
        """Start the row-by-row sequence, or stop it when already running."""
        if self._seq_running:
            self.stop_sequence()
            return
        targets = [e for e in self._rows if e["edit"].text().strip()]
        if not targets:
            self.log.emit(tr("qs.seq.none"))
            return
        self._seq_queue = targets
        self._seq_running = True
        self._seq_index = 0
        self.seq_btn.setText(tr("qs.stop"))
        self._seq_send_current()

    def _seq_send_current(self) -> None:
        """Send the current row, then wait that row's delay before moving on."""
        entry = self._seq_queue[self._seq_index]
        payload = self._payload_for(entry)
        if payload is not None:
            self.send_payload.emit(payload)
        total = len(self._seq_queue)
        self.seq_label.setText(tr("qs.seq.progress", i=self._seq_index + 1, n=total))
        if self._seq_index + 1 >= total:
            delay = self._row_delay(entry)
            self._seq_timer.singleShot(delay, self._finish_sequence)
            return
        self._seq_index += 1
        self._seq_timer.start(self._row_delay(entry))

    def _row_delay(self, entry: dict) -> int:
        """Parse a row's delay in ms (0-60000), defaulting to 500."""
        try:
            value = int((entry["delay"].text() or "").strip())
        except ValueError:
            return 500
        return max(0, min(60000, value))

    def _seq_advance(self) -> None:
        if self._seq_running:
            self._seq_send_current()

    def _finish_sequence(self) -> None:
        self._seq_timer.stop()
        self._seq_running = False
        self.seq_btn.setText(tr("qs.run"))
        self.seq_label.setText(tr("qs.seq.done"))
        self._seq_index = 0
        self._seq_queue = []

    def stop_sequence(self) -> None:
        """Stop the sequence and restore the controls."""
        self._seq_timer.stop()
        self._seq_running = False
        self.seq_btn.setText(tr("qs.run"))
        if self.seq_label.text() != tr("qs.seq.done"):
            self.seq_label.setText("")
        self._seq_index = 0
        self._seq_queue = []

    def _delete_row(self, row: QWidget):
        """Remove a row, but report enough context to undo it (U58)."""
        entry = next((e for e in self._rows if e["widget"] is row), None)
        if entry is None:
            return
        index = self._rows.index(entry)
        payload = {"text": entry["edit"].text(), "hex": entry["fmt"].currentIndex() == 0,
                   "delay": self._row_delay(entry), "index": index}
        self._rows.remove(entry)
        row.setParent(None)
        row.deleteLater()
        self._update_count()
        self.deleted.emit(payload)
        self.save()

    def restore_row(self, payload: dict) -> None:
        """Re-insert a row removed by _delete_row (U58 undo)."""
        index = int(payload.get("index", len(self._rows)))
        before = len(self._rows)
        self.add_row(str(payload.get("text", "")), bool(payload.get("hex", True)),
                     int(payload.get("delay", 500) or 0))
        if len(self._rows) > before and index < len(self._rows) - 1:
            entry = self._rows.pop()
            self._rows.insert(max(0, index), entry)
            self._reorder_rows()
        self.save()

    def _reorder_rows(self) -> None:
        """Re-apply the row order in the layout (U58 undo keeps the position)."""
        for i, entry in enumerate(self._rows):
            self._row_layout.insertWidget(i, entry["widget"])


    def _find(self, row: QWidget) -> dict | None:
        for e in self._rows:
            if e["widget"] is row:
                return e
        return None

    def reload_from_config(self):
        """Drop every row and rebuild the panel from config.json (used after a config import)."""
        for entry in list(self._rows):
            entry["widget"].setParent(None)
            self._rows.remove(entry)
        self._load()
        self._update_count()

    def _update_count(self):
        self.count_label.setText(f"{len(self._rows)}/{MAX_ENTRIES}")

    def retranslate(self):
        """Re-apply translated strings after a language change."""
        self._title_lbl.setText(tr("qs.title"))
        self.add_btn.setText(tr("qs.add"))
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.seq_check.setText(tr("qs.seq"))
        self.seq_check.setToolTip(tr("qs.seq.tip"))
        self.seq_btn.setText(tr("qs.stop") if self._seq_running else tr("qs.run"))
        self.seq_btn.setToolTip(tr("qs.seq.tip"))
        for entry in self._rows:
            entry["edit"].setPlaceholderText(tr("qs.placeholder"))
            entry["send"].setText(tr("qs.send"))
            entry["del"].setToolTip(tr("qs.delete.tip"))
            entry["delay"].setToolTip(tr("qs.delay.tip"))

    # -- persistence -----------------------------------------------------------

    def _load(self):
        data = {}
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        items = data.get("quick_send", []) if isinstance(data, dict) else []
        if not items:
            # first run / empty config: seed the default number of blank rows
            for _ in range(DEFAULT_ROWS):
                self.add_row()
            return
        for item in items:
            self.add_row(str(item.get("text", "")), bool(item.get("hex", True)),
                         int(item.get("delay", 500) or 0))

    def save(self):
        items = [
            {"text": e["edit"].text(), "hex": e["fmt"].currentIndex() == 0,
             "delay": self._row_delay(e)}
            for e in self._rows
        ]
        config = {}
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        config["quick_send"] = items
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.log.emit(tr("qs.save_fail", e=exc))