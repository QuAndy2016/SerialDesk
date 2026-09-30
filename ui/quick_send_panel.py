"""Quick send panel: editable command shortcuts, up to 99 entries, persisted."""

from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.protocol import ascii_str_to_bytes, hex_str_to_bytes

MAX_ENTRIES = 99
DEFAULT_ROWS = 10   # blank rows seeded on first run (U15)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")


class QuickSendPanel(QWidget):
    """Right-hand panel: list of editable quick-send commands.

    Each row: text edit + format combo (HEX/ASCII) + send button + delete.
    Persisted to config.json as JSON list; max 99 rows.
    """

    send_payload = Signal(bytes)   # parsed payload, no checksum applied yet
    log = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []   # [{text, hex}]
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(380)
        scroll.setMaximumWidth(420)
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

    def add_row(self, text: str = "", is_hex: bool = True):
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

        send = QPushButton(tr("qs.send"))
        send.setMinimumWidth(52)
        send.setStyleSheet("padding: 2px 6px;")  # override global QSS padding
        send.clicked.connect(lambda: self._send_row(row))
        h.addWidget(send)

        dele = QPushButton("×")
        dele.setFixedWidth(28)
        dele.setStyleSheet("padding: 0px;")  # key fix: global padding 5px 14px ate the 28px width
        dele.setToolTip(tr("qs.delete.tip"))
        dele.clicked.connect(lambda: self._delete_row(row))
        h.addWidget(dele)

        self._row_layout.insertWidget(self._row_layout.count() - 1, row)
        self._rows.append({"widget": row, "edit": edit, "fmt": fmt, "send": send, "del": dele})
        self._update_count()

    def _send_row(self, row: QWidget):
        entry = self._find(row)
        if entry is None:
            return
        text = entry["edit"].text().strip()
        if not text:
            self.log.emit(tr("qs.empty"))
            return
        try:
            if entry["fmt"].currentIndex() == 0:
                payload = hex_str_to_bytes(text)
            else:
                payload = ascii_str_to_bytes(text)
        except ValueError as exc:
            self.log.emit(tr("qs.bad_fmt", e=exc))
            return
        self.send_payload.emit(payload)

    def _delete_row(self, row: QWidget):
        entry = self._find(row)
        if entry is None:
            return
        self._row_layout.removeWidget(row)
        row.deleteLater()
        self._rows.remove(entry)

    def _find(self, row: QWidget) -> dict | None:
        for e in self._rows:
            if e["widget"] is row:
                return e
        return None

    def _update_count(self):
        self.count_label.setText(f"{len(self._rows)}/{MAX_ENTRIES}")

    def retranslate(self):
        """Re-apply translated strings after a language change."""
        self._title_lbl.setText(tr("qs.title"))
        self.add_btn.setText(tr("qs.add"))
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        for entry in self._rows:
            entry["edit"].setPlaceholderText(tr("qs.placeholder"))
            entry["send"].setText(tr("qs.send"))
            entry["del"].setToolTip(tr("qs.delete.tip"))

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
            self.add_row(str(item.get("text", "")), bool(item.get("hex", True)))

    def save(self):
        items = [
            {"text": e["edit"].text(), "hex": e["fmt"].currentIndex() == 0}
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