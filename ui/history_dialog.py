"""Send-history popup: recall, delete and clear sent commands (U87; v0.10.0 P0+P1).

Non-modal on purpose: the main window stays usable while the list is open, and a
double-click (or Enter) puts the entry straight back into the send box.

v0.10.0 P0+P1 (2026-10-01): monospace rows, live count line, a filter box,
per-entry meta (format / byte count / relative time), clear needs a second click,
the destructive button is set apart, and the dialog remembers its size.
"""
from __future__ import annotations


import time

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
)

from app.config import load_config, save_config
from app.i18n import tr
from ui import theme

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QCloseEvent, QPainter
    from PySide6.QtWidgets import QWidget

TEXT_ROLE = Qt.ItemDataRole.UserRole
META_ROLE = Qt.ItemDataRole.UserRole + 1

MONO_FAMILIES = "Consolas, 'Cascadia Mono', 'DejaVu Sans Mono', 'Courier New', monospace"


class _HistoryDelegate(QStyledItemDelegate):
    """Row painter: monospace command on the left, dim meta text on the right.

    Colours are taken from theme.history_list_colors() so the selected row keeps
    a measured contrast (>4.5:1) in both themes (plan D5).
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: D102 - Qt override
        """Draw one history row with the selection and alternating background."""
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""                                  # background only, we draw text
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        colors = theme.history_list_colors()
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.fillRect(option.rect, QColor(colors["sel_bg"]))

        rect = option.rect.adjusted(8, 0, -8, 0)
        text = str(index.data(TEXT_ROLE) or "")
        meta = str(index.data(META_ROLE) or "")

        meta_font = QFont(option.font)
        meta_font.setFamily(MONO_FAMILIES)
        meta_font.setPointSizeF(max(7.5, option.font.pointSizeF() - 1.0))
        meta_w = self._meta_width(meta_font, meta)
        gap = 16 if meta else 0

        painter.save()
        painter.setFont(option.font)
        painter.setPen(QColor(colors["sel_text"] if selected else colors["text"]))
        avail = max(0, rect.width() - meta_w - gap)
        elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, avail)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided)
        if meta:
            painter.setFont(meta_font)
            painter.setPen(QColor(colors["sel_meta"] if selected else colors["meta"]))
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), meta)
        painter.restore()

    @staticmethod
    def _meta_width(font: QFont, meta: str) -> int:
        if not meta:
            return 0
        return QFontMetrics(font).horizontalAdvance(meta)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):  # noqa: D102 - Qt override
        """Row size that keeps the full command text readable."""
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 26))
        return size


class HistoryDialog(QDialog):
    """List of recently sent commands, newest first."""

    fill_requested = Signal(str)     # put this text back in the send box
    delete_requested = Signal(int)   # drop the entry at this row
    clear_requested = Signal()       # forget everything

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("tx.history.title"))
        self.setModal(False)                 # never block the main window (U87)
        self.setMinimumSize(440, 330)

        self._meta: dict = {}
        self._clear_armed = False
        self._arm_timer = QTimer(self)
        self._arm_timer.setSingleShot(True)
        self._arm_timer.timeout.connect(self._disarm_clear)

        layout = QVBoxLayout(self)
        self._build_header(layout)
        self._build_list(layout)
        self._build_buttons(layout)

        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self._delete_current)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close)

        self._restore_size()
        self._apply_filter()

    def _build_header(self, layout: QVBoxLayout) -> None:
        """Explanatory hint plus the filter box and the match counter."""
        self.hint = QLabel(tr("tx.history.hint"))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        head = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(tr("tx.history.filter.ph"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        head.addWidget(self.filter_edit, 1)
        self.count_lbl = QLabel("")
        head.addWidget(self.count_lbl)
        layout.addLayout(head)

    def _build_list(self, layout: QVBoxLayout) -> None:
        """The monospace history list and the empty-state label."""
        self.list = QListWidget()
        mono = QFont()
        mono.setFamily(MONO_FAMILIES)
        self.list.setFont(mono)
        self.list.setItemDelegate(_HistoryDelegate(self.list))
        self.list.setUniformItemSizes(True)
        self.list.itemDoubleClicked.connect(self._on_activate)
        self.list.itemActivated.connect(self._on_activate)   # Enter key
        self.list.currentRowChanged.connect(lambda _r: self._sync_buttons())
        layout.addWidget(self.list, 1)

        self.empty_lbl = QLabel(tr("tx.history.empty"))
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_lbl)

    def _build_buttons(self, layout: QVBoxLayout) -> None:
        """Fill / delete on the left, the destructive clear set apart on the right."""
        row = QHBoxLayout()
        self.fill_btn = QPushButton(tr("tx.history.fill"))
        self.fill_btn.setDefault(True)                 # primary action (P0.3)
        self.fill_btn.clicked.connect(self._fill_current)
        row.addWidget(self.fill_btn)

        row.addSpacing(8)
        self.del_btn = QPushButton(tr("tx.history.delete"))
        self.del_btn.setProperty("secondary", True)    # quieter, sits next to fill
        self.del_btn.clicked.connect(self._delete_current)
        row.addWidget(self.del_btn)

        row.addStretch(1)                              # keep the destructive pair apart
        self.clear_btn = QPushButton(tr("tx.history.clear"))
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.setToolTip(tr("tx.history.clear.tip"))
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        row.addWidget(self.clear_btn)

        row.addSpacing(12)
        self.close_btn = QPushButton(tr("tx.history.close"))
        self.close_btn.clicked.connect(self.close)
        row.addWidget(self.close_btn)
        layout.addLayout(row)

    # -- geometry ------------------------------------------------------------

    def _restore_size(self) -> None:
        size = load_config().get("history_dlg_size")
        if isinstance(size, list) and len(size) == 2:
            try:
                w, h = int(size[0]), int(size[1])
            except (TypeError, ValueError):
                return
            if w >= 440 and h >= 330:
                self.resize(w, h)

    def _remember_size(self) -> None:
        try:
            config = load_config()
            config["history_dlg_size"] = [self.width(), self.height()]
            save_config(config)
        except (OSError, TypeError, ValueError):
            pass

    def closeEvent(self, event: QCloseEvent):  # noqa: N802 - Qt naming
        """Remember the column widths before the dialog closes."""
        self._remember_size()
        self._disarm_clear()
        super().closeEvent(event)

    # -- data ----------------------------------------------------------------

    def set_history(self, items: list, meta: dict | None = None) -> None:
        """Rebuild the list (newest first, same order as the stored history)."""
        row = self.list.currentRow()
        self._meta = meta if isinstance(meta, dict) else {}
        self.list.blockSignals(True)
        self.list.clear()
        for text in items:
            text = str(text)
            item = QListWidgetItem(text)          # delegate elides; keeps filtering simple
            item.setToolTip(text)                 # the full command is always reachable
            item.setData(TEXT_ROLE, text)
            item.setData(META_ROLE, _meta_text(self._meta.get(text)))
            self.list.addItem(item)
        self.list.blockSignals(False)
        if items:
            self.list.setCurrentRow(max(0, min(row, len(items) - 1)))
        self._apply_filter()

    def _apply_filter(self) -> None:
        term = self.filter_edit.text().strip().lower()
        total = self.list.count()
        shown = 0
        for i in range(total):
            item = self.list.item(i)
            hit = (term in item.text().lower()) if term else True
            item.setHidden(not hit)
            shown += int(hit)
        if term:
            self.count_lbl.setText(tr("tx.history.count.filtered", m=shown, n=total))
        else:
            self.count_lbl.setText(tr("tx.history.count", n=total))

        if total == 0:
            self.empty_lbl.setText(tr("tx.history.empty"))
        else:
            self.empty_lbl.setText(tr("tx.history.empty.filtered"))
        self.empty_lbl.setVisible(shown == 0)
        self.list.setVisible(shown > 0)

        if shown and self.list.currentItem() is not None and self.list.currentItem().isHidden():
            for i in range(total):
                if not self.list.item(i).isHidden():
                    self.list.setCurrentRow(i)
                    break
        if shown == 0 and total:
            self.list.setCurrentRow(-1)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        has_rows = self.list.count() > 0
        has_sel = self.list.currentRow() >= 0 and has_rows and not self.list.currentItem().isHidden()
        self.fill_btn.setEnabled(bool(has_sel))
        self.del_btn.setEnabled(bool(has_sel))
        self.clear_btn.setEnabled(has_rows)

    # -- actions -------------------------------------------------------------

    def _current_text(self) -> str:
        item = self.list.currentItem()
        return str(item.data(TEXT_ROLE)) if item is not None else ""

    def _fill_current(self) -> None:
        text = self._current_text()
        if text:
            self.fill_requested.emit(text)
            self.close()                        # match the double-click behaviour (P1.8)

    def _delete_current(self) -> None:
        row = self.list.currentRow()
        if row >= 0 and not self.list.item(row).isHidden():
            self.delete_requested.emit(row)
            self._disarm_clear()

    def _on_activate(self, item: QListWidgetItem) -> None:
        self.fill_requested.emit(str(item.data(TEXT_ROLE)))
        self.close()

    def _on_clear_clicked(self) -> None:
        """Two-click confirmation: arm first, wipe on the second click (P0.3)."""
        if not self._clear_armed:
            self._clear_armed = True
            self.clear_btn.setText(tr("tx.history.clear.arm"))
            self._arm_timer.start(5000)
            return
        self._disarm_clear()
        self.clear_requested.emit()

    def _disarm_clear(self) -> None:
        self._arm_timer.stop()
        if self._clear_armed:
            self._clear_armed = False
        self.clear_btn.setText(tr("tx.history.clear"))


def _meta_text(meta: dict | None) -> str:
    """'HEX · 5B · 3 分钟前' - whatever parts the record actually has."""
    if not isinstance(meta, dict):
        return ""
    parts = []
    fmt = str(meta.get("fmt") or "")
    if fmt == "hex":
        parts.append("HEX")
    elif fmt == "ascii":
        parts.append("ASCII")
    count = meta.get("b")
    if isinstance(count, int) and count >= 0:
        parts.append(f"{count}B")
    stamp = meta.get("ts")
    if isinstance(stamp, (int, float)) and stamp > 0:
        parts.append(_ago_text(float(stamp)))
    return " · ".join(parts)


def _ago_text(stamp: float) -> str:
    delta = max(0.0, time.time() - stamp)
    if delta < 60:
        return tr("tx.history.ago.now")
    if delta < 3600:
        return tr("tx.history.ago.min", n=int(delta // 60))
    if delta < 86400:
        return tr("tx.history.ago.hour", n=int(delta // 3600))
    return tr("tx.history.ago.day", n=int(delta // 86400))
