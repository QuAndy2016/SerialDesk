"""Send-history popup: recall, delete and clear sent commands (U87).

Non-modal on purpose: the main window stays usable while the list is open, and a
double-click (or Enter) puts the entry straight back into the send box.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.i18n import tr


class HistoryDialog(QDialog):
    """List of recently sent commands, newest first."""

    fill_requested = Signal(str)     # put this text back in the send box
    delete_requested = Signal(int)   # drop the entry at this row
    clear_requested = Signal()       # forget everything

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("tx.history.title"))
        self.setModal(False)                 # never block the main window (U87)
        self.setMinimumSize(440, 330)

        layout = QVBoxLayout(self)
        self.hint = QLabel(tr("tx.history.hint"))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._on_activate)
        self.list.itemActivated.connect(self._on_activate)   # Enter key
        self.list.currentRowChanged.connect(lambda _r: self._sync_buttons())
        layout.addWidget(self.list, 1)

        self.empty_lbl = QLabel(tr("tx.history.empty"))
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_lbl)

        row = QHBoxLayout()
        self.fill_btn = QPushButton(tr("tx.history.fill"))
        self.fill_btn.setDefault(True)
        self.fill_btn.clicked.connect(self._fill_current)
        row.addWidget(self.fill_btn)

        self.del_btn = QPushButton(tr("tx.history.delete"))
        self.del_btn.clicked.connect(self._delete_current)
        row.addWidget(self.del_btn)

        self.clear_btn = QPushButton(tr("tx.history.clear"))
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        row.addWidget(self.clear_btn)

        row.addStretch(1)
        self.close_btn = QPushButton(tr("tx.history.close"))
        self.close_btn.clicked.connect(self.close)
        row.addWidget(self.close_btn)
        layout.addLayout(row)

        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._delete_current)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)

    # -- data ----------------------------------------------------------------

    def set_history(self, items: list) -> None:
        """Rebuild the list (newest first, same order as the stored history)."""
        row = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for text in items:
            item = QListWidgetItem(_elide(text))
            item.setToolTip(text)          # the full command is always reachable
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if items:
            self.list.setCurrentRow(max(0, min(row, len(items) - 1)))
        self.empty_lbl.setVisible(not items)
        self.list.setVisible(bool(items))
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        has_rows = self.list.count() > 0
        has_sel = self.list.currentRow() >= 0 and has_rows
        self.fill_btn.setEnabled(has_sel)
        self.del_btn.setEnabled(has_sel)
        self.clear_btn.setEnabled(has_rows)

    # -- actions -------------------------------------------------------------

    def _current_text(self) -> str:
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""

    def _fill_current(self) -> None:
        text = self._current_text()
        if text:
            self.fill_requested.emit(text)

    def _delete_current(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.delete_requested.emit(row)

    def _on_activate(self, item: QListWidgetItem) -> None:
        self.fill_requested.emit(str(item.data(Qt.ItemDataRole.UserRole)))


def _elide(text: str, limit: int = 96) -> str:
    """Keep one row per command - very long commands are cut, tooltip keeps them."""
    flat = " ".join(str(text).split("\n"))
    return flat if len(flat) <= limit else flat[: limit - 1] + "\u2026"
