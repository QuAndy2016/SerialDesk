"""Quick send panel: editable command shortcuts, up to 99 entries, persisted."""
from __future__ import annotations


import json
import os

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIntValidator, QPainter, QPolygonF
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOption,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

import ui.theme as theme

from app.i18n import hex_error_message, tr
from app.protocol import HexFormatError, ascii_str_to_bytes, hex_str_to_bytes

MAX_ENTRIES = 99
DEFAULT_ROWS = 10   # blank rows seeded on first run (U15)
RAIL_W = 28         # U106: width of the rail that stays visible while the panel is folded


class RailStrip(QWidget):
    """U106: the folded state of the quick-send panel.

    Folding used to hide the panel completely, leaving a menu entry and Ctrl+B as the
    only way back. The rail keeps a labelled, clickable strip on screen instead, so the
    panel is never "gone" - you can always see what is folded away and click it open.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None=None):
        super().__init__(parent)
        self._text = ""
        self.setObjectName("qsRail")
        self.setFixedWidth(RAIL_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_label(self, text: str) -> None:
        """Set the visible label (compact and icon states)."""
        self._text = text
        self.update()

    def paintEvent(self, event: QPaintEvent):  # noqa: N802 - Qt naming
        """Paint the collapsed rail's chevron."""
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        # let the stylesheet paint the background/border (#qsRail, incl. :hover)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        colour = QColor(theme.text_color())
        cx = self.width() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPolygon(QPolygonF([QPointF(cx - 3, 10), QPointF(cx + 3, 15),
                                       QPointF(cx - 3, 20)]))
        painter.setPen(colour)
        painter.save()
        painter.translate(cx + 5, self.height() - 14)
        painter.rotate(-90)
        painter.drawText(0, 0, self._text)
        painter.restore()
        painter.end()

    def mouseReleaseEvent(self, event: QMouseEvent):  # noqa: N802 - Qt naming
        """Reopen the panel when the collapsed rail is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
from app.config import CONFIG_PATH   # U34: one data dir for the whole app

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QMouseEvent, QPaintEvent


class QuickSendPanel(QWidget):
    """Right-hand panel: list of editable quick-send commands.

    Each row: text edit + format combo (HEX/ASCII) + send button + delete.
    Persisted to config.json as JSON list; max 99 rows.
    """

    send_payload = Signal(bytes)   # parsed payload, no checksum applied yet
    error = Signal(str)            # user-facing format error text (U36)
    deleted = Signal(list)         # removed row payloads (U58/U118: batch undo)
    log = Signal(str)
    collapsed_changed = Signal(bool)   # U88: fold the panel away

    def __init__(self, parent: QWidget | None=None):
        super().__init__(parent)
        self._rows: list[dict] = []   # [{text, hex, delay}]
        self._seq_timer = QTimer(self)
        self._seq_timer.setSingleShot(True)
        self._seq_timer.timeout.connect(self._seq_advance)
        self._seq_running = False
        self._seq_queue: list[dict] = []
        self._seq_index = 0
        self._folded = False
        self._build_ui()
        self._load()
        self.set_rows_selectable(self.seq_check.isChecked())
        # U115: watch clicks anywhere in the app so a selection cannot go stale
        QApplication.instance().installEventFilter(self)

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        """U106: the panel owns both of its states - the normal column and a rail."""
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._content = QWidget()
        outer.addWidget(self._content, 1)
        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(6, 6, 6, 6)
        self._build_head(layout)
        self._build_sequence_row(layout)
        self._build_row_area(layout)
        self._build_rail(outer)

    def _build_head(self, layout: QVBoxLayout) -> None:
        """Title row with the entry count and the fold button"""
        head = QHBoxLayout()
        self._title_lbl = QLabel(tr("qs.title"))
        head.addWidget(self._title_lbl)
        head.addStretch(1)
        self.count_label = QLabel("0/99")
        head.addWidget(self.count_label)
        # U106: the fold control sits at the trailing edge (matching the side it folds
        # towards), is a themed icon button instead of a text glyph, has a 24x24 hit
        # target, and toggles both ways.
        self._collapse_btn = QToolButton()
        self._collapse_btn.setObjectName("qsCollapse")
        self._collapse_btn.setAutoRaise(True)
        self._collapse_btn.setMinimumSize(24, 24)
        self._collapse_btn.setToolTip(tr("qs.collapse.tip"))
        self._collapse_btn.clicked.connect(lambda: self.collapsed_changed.emit(True))
        head.addWidget(self._collapse_btn)
        layout.addLayout(head)

    def _build_sequence_row(self, layout: QVBoxLayout) -> None:
        """Sequence-mode toggle, Run and the delete-selected action"""
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
        seq_row.addStretch(1)
        seq_row.addSpacing(16)      # U114-D10: keep a destructive action away from Run
        self.del_btn = QPushButton(tr("qs.del_selected"))   # U68 plan A
        self.del_btn.setToolTip(tr("qs.del_selected.tip"))
        self.del_btn.setEnabled(False)
        self.del_btn.clicked.connect(self.delete_selected)
        seq_row.addWidget(self.del_btn)
        layout.addLayout(seq_row)

    def _build_row_area(self, layout: QVBoxLayout) -> None:
        """Scrollable row container and the add-row button"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(332)   # U69: rows need ~318px or the buttons clip
        self._container = QWidget()
        self._row_layout = QVBoxLayout(self._container)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(4)
        self._row_layout.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

        self.add_btn = QPushButton(tr("qs.add"))   # U114-D3: secondary weight, not a hero
        self.add_btn.setProperty("secondary", True)
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.add_btn.clicked.connect(lambda: self.add_row())
        layout.addWidget(self.add_btn)

    def _build_rail(self, outer: QHBoxLayout) -> None:
        """The narrow strip that stays on screen while the panel is folded"""
        self._rail = RailStrip()
        self._rail.set_label(tr("qs.title"))
        self._rail.setToolTip(tr("qs.rail.tip"))
        self._rail.clicked.connect(lambda: self.collapsed_changed.emit(False))
        self._rail.hide()
        outer.addWidget(self._rail)

    # -- rows ----------------------------------------------------------------

    def add_row(self, text: str = "", is_hex: bool = True, delay_ms: int = 500,
                selected: bool = False):
        """Append one quick-send row together with its property chip."""
        if len(self._rows) >= MAX_ENTRIES:
            self.log.emit(tr("qs.max", n=MAX_ENTRIES))
            return
        row = self._make_row_frame()
        # U118: one line per row again - the command keeps the whole width and the
        # row's properties moved into a small chip at the trailing edge.
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(6)
        sel, ord_lbl = self._build_row_select(h, row)
        edit = self._build_row_edit(h, text)
        chip, fmt, delay, unit = self._build_row_chip(h, is_hex, delay_ms)
        send = self._build_row_send(h, row)

        self._row_layout.insertWidget(self._row_layout.count() - 1, row)
        edit.installEventFilter(self)      # clicking into the text selects the row
        entry = {"widget": row, "edit": edit, "fmt": fmt, "send": send, "delay": delay,
                 "sel": sel, "ord": ord_lbl, "unit": unit, "chip": chip}
        self._rows.append(entry)
        fmt.currentIndexChanged.connect(lambda *_: self._refresh_chip(entry))
        delay.textChanged.connect(lambda *_: self._refresh_chip(entry))
        self._refresh_chip(entry)
        sel.setChecked(bool(selected))
        sel.setEnabled(self.seq_check.isChecked())   # U114-D9
        self._renumber_selection()
        self._update_count()

    def _make_row_frame(self) -> QFrame:
        """U68 plan A: a frame paints the selection; the row owns the mouse filter."""
        row = QFrame()
        row.setObjectName("qsRow")
        row.setProperty("selected", False)
        row.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        row.setToolTip(tr("qs.row.tip"))
        row.installEventFilter(self)
        return row

    def _build_row_select(self, h: QHBoxLayout, row: QFrame) -> tuple:
        """U66/U80: the sequence checkbox plus the tiny order badge pinned to it."""
        sel = QCheckBox()
        sel.setToolTip(tr("qs.sel.tip"))
        sel.setAccessibleName(tr("qs.sel.tip"))     # U122
        sel.toggled.connect(self._renumber_selection)
        h.addWidget(sel)
        # U80: the sequence number is a tiny label pinned to the checkbox corner.
        # It stays out of the layout so it neither widens the row nor eats stretch.
        ord_lbl = QLabel("", row)
        ord_lbl.setObjectName("seqOrd")
        ord_lbl.setToolTip(tr("qs.sel.order.tip"))
        ord_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        ord_lbl.hide()
        return sel, ord_lbl

    def _build_row_edit(self, h: QHBoxLayout, text: str) -> QLineEdit:
        """The command text; clicking into it selects the row (see eventFilter)."""
        edit = QLineEdit(text)
        edit.setPlaceholderText(tr("qs.placeholder"))
        edit.setAccessibleName(tr("qs.row.tip"))    # U122
        h.addWidget(edit, 1)
        return edit

    def _build_row_chip(self, h: QHBoxLayout, is_hex: bool, delay_ms: int) -> tuple:
        """U118: format + delay live in this chip's popup ("HEX / 500 ms" at a glance)."""
        chip = QToolButton()
        chip.setObjectName("qsChip")
        chip.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        chip.setToolTip(tr("qs.chip.tip"))
        chip.setAccessibleName(tr("qs.chip.tip"))   # U122
        props = QWidget()
        pl = QHBoxLayout(props)
        pl.setContentsMargins(8, 6, 8, 6)
        pl.setSpacing(6)

        fmt = QComboBox()
        fmt.addItems(["HEX", "ASCII"])
        fmt.setCurrentIndex(0 if is_hex else 1)
        pl.addWidget(fmt)

        delay = QLineEdit(str(max(0, min(60000, int(delay_ms)))))   # U31: bare number
        delay.setValidator(QIntValidator(0, 60000, self))
        delay.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        delay.setStyleSheet("padding: 3px 4px;")
        delay.setFixedWidth(self._delay_width())
        delay.setToolTip(tr("qs.delay.tip"))
        pl.addWidget(delay)
        unit = QLabel(tr("qs.delay.unit"))
        unit.setObjectName("qsMeta")
        pl.addWidget(unit)

        chip_menu = QMenu(chip)
        holder = QWidgetAction(chip_menu)
        holder.setDefaultWidget(props)
        chip_menu.addAction(holder)
        chip.setMenu(chip_menu)
        h.addWidget(chip)
        return chip, fmt, delay, unit

    def _build_row_send(self, h: QHBoxLayout, row: QFrame) -> QPushButton:
        """The per-row Send button."""
        send = QPushButton(tr("qs.send"))
        send.setAccessibleName(tr("qs.send"))       # U122
        send.setMinimumWidth(52)
        send.setStyleSheet("padding: 2px 6px;")  # override global QSS padding
        send.clicked.connect(lambda: self._send_row(row))
        h.addWidget(send)
        return send

    # -- folded state (U106) -------------------------------------------------

    def set_folded(self, folded: bool) -> None:
        """Show the rail instead of the panel contents, and let the splitter shrink."""
        self._folded = bool(folded)
        if self._folded:
            self.clear_selection()
        self._content.setVisible(not self._folded)
        if self._folded:
            # U120: folded costs nothing at rest - the rail is brought back by hovering
            # the window's right edge (or the toolbar button / Ctrl+B).
            self._rail.hide()
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
        else:
            self._rail.hide()
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)      # QWIDGETSIZE_MAX
        self.updateGeometry()

    def set_rail_visible(self, on: bool) -> None:
        """U120: show the folded-state rail while the pointer is near the right edge."""
        if not self._folded or bool(on) == self._rail.isVisible():
            return
        if on:
            self.setMinimumWidth(RAIL_W)
            self.setMaximumWidth(RAIL_W)
            self._rail.show()
        else:
            self._rail.hide()
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)

    def is_folded(self) -> bool:
        """True while the panel is collapsed."""
        return self._folded

    # -- row selection + deletion (U68 plan A) -------------------------------

    def eventFilter(self, obj: QObject, event: QEvent):  # noqa: N802 - Qt naming
        """Click selects a row; Delete removes the selection (3 s undo stays)."""
        if event.type() == QEvent.Type.MouseButtonPress:
            # U115: a click outside the panel (or on its empty area) drops the selection;
            # clicking the toolbar controls that act on the selection keeps it.
            if self.selected_entries() and not self._click_keeps_selection(obj, event):
                self.clear_selection()
            # U118: the row is the selection unit - a press anywhere inside its rect
            # selects it (Ctrl toggles, Shift extends), the widgets keep working.
            hit = self._row_at(event)
            if hit is not None:
                mods = event.modifiers()
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self._select_row(hit, "toggle")
                elif mods & Qt.KeyboardModifier.ShiftModifier:
                    self._select_row(hit, "range")
                else:
                    self._select_row(hit, "replace")
        elif event.type() == QEvent.Type.Resize and any(
                entry["widget"] is obj for entry in self._rows):
            self._place_order_badges()
        elif event.type() == QEvent.Type.KeyPress and self._owns_keyboard():
            # U129: these shortcuts belong to the panel only - they used to be app-wide,
            # which meant Ctrl+A in the send box selected quick-send rows, and Delete in
            # any text field deleted rows.
            key, mods = event.key(), event.modifiers()
            if key == Qt.Key.Key_Delete:
                self.delete_selected()
                return True
            if key == Qt.Key.Key_Escape and self.clear_selection():
                return True
            if key == Qt.Key.Key_A and mods & Qt.KeyboardModifier.ControlModifier:
                for entry in self._rows:
                    self._paint_row(entry, True)
                self._update_del_btn()
                return True
        return super().eventFilter(obj, event)

    def _paint_row(self, entry: dict, on: bool) -> None:
        widget = entry["widget"]
        if bool(widget.property("selected")) != bool(on):
            widget.setProperty("selected", bool(on))
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _select_row(self, entry: dict, mode: str = "replace") -> None:
        """U118: replace / toggle / range - the usual list semantics."""
        if mode == "toggle":
            self._paint_row(entry, not bool(entry["widget"].property("selected")))
            self._anchor = entry
        elif mode == "range" and self._anchor in self._rows:
            lo, hi = sorted((self._rows.index(self._anchor), self._rows.index(entry)))
            for i, other in enumerate(self._rows):
                self._paint_row(other, lo <= i <= hi)
        else:
            for other in self._rows:
                self._paint_row(other, other is entry)
            self._anchor = entry
        self._update_del_btn()

    def _owns_keyboard(self) -> bool:
        """U129: True only when the focus is inside the panel and not in a text field."""
        focus = QApplication.focusWidget()
        if focus is None or isinstance(focus, (QLineEdit, QPlainTextEdit, QAbstractSpinBox)):
            return False
        return focus is self or self.isAncestorOf(focus)

    def _row_at(self, event: QMouseEvent):
        """The row under the press, if any (U118: the whole row is the hit target)."""
        point = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else None
        if point is None:
            return None
        for entry in self._rows:
            row = entry["widget"]
            if row.isVisible() and row.rect().contains(row.mapFromGlobal(point)):
                return entry
        return None

    def _update_del_btn(self) -> None:
        count = len(self.selected_entries())
        self.del_btn.setEnabled(count > 0)
        self.del_btn.setText(tr("qs.del_selected.n", n=count) if count
                             else tr("qs.del_selected"))
        self.del_btn.setToolTip(tr("qs.del_selected.tip"))

    def selected_entries(self) -> list:
        """Payloads of every selected row, in list order."""
        return [e for e in self._rows if bool(e["widget"].property("selected"))]

    def selected_entry(self) -> dict | None:
        """Payload of the single selected row, or None."""
        got = self.selected_entries()
        return got[0] if got else None

    def _chip_text(self, entry: dict) -> str:
        fmt = "HEX" if entry["fmt"].currentIndex() == 0 else "ASCII"
        return "%s · %s %s" % (fmt, entry["delay"].text().strip() or "0",
                               tr("qs.delay.unit"))

    def _refresh_chip(self, entry: dict) -> None:
        chip = entry.get("chip")
        if chip is not None:
            chip.setText(self._chip_text(entry))

    def clear_selection(self) -> bool:
        """U115: drop the highlight (outside click, Esc, folding, starting a sequence)."""
        changed = False
        for entry in self._rows:
            if bool(entry["widget"].property("selected")):
                self._paint_row(entry, False)
                changed = True
        self._update_del_btn()
        return changed

    def _click_keeps_selection(self, obj: QObject, event: QEvent) -> bool:
        """True when the press should not clear the selection."""
        widget = obj if isinstance(obj, QWidget) else None
        if widget is None:
            return False
        for keeper in (self.del_btn, self.add_btn, self.seq_btn, self.seq_check):
            if widget is keeper or keeper.isAncestorOf(widget):
                return True
        if widget is self or self.isAncestorOf(widget):
            point = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else None
            if point is None:
                return False
            for entry in self._rows:
                row = entry["widget"]
                if row.isVisible() and row.rect().contains(row.mapFromGlobal(point)):
                    return True
        return False

    def delete_selected(self) -> None:
        """U118: delete every selected row; the main window offers a 3 s batch undo."""
        entries = self.selected_entries()
        if entries:
            self.delete_entries(entries)

    def _row_payload(self, entry: dict) -> dict:
        return {"text": entry["edit"].text(), "hex": entry["fmt"].currentIndex() == 0,
                "delay": self._row_delay(entry), "index": self._rows.index(entry)}

    def delete_entries(self, entries: list) -> None:
        """Remove the given rows and report them as one batch (U118)."""
        payloads = sorted((self._row_payload(e) for e in entries),
                          key=lambda item: item["index"])
        for entry in entries:
            row = entry["widget"]
            if entry in self._rows:
                self._rows.remove(entry)
            row.setParent(None)
            row.deleteLater()
        self._update_del_btn()
        self._update_count()
        if payloads:
            self.deleted.emit(payloads)
        self.save()

    def _renumber_selection(self) -> None:
        """Show 1..n on the ticked rows so the run order is obvious (U66)."""
        order = 0
        for entry in self._rows:
            widget = entry.get("ord")
            if widget is None:
                continue
            if entry["sel"].isChecked():
                order += 1
                widget.setText(str(order))
                widget.show()
            else:
                widget.setText("")
                widget.hide()
        self._place_order_badges()

    def _sequence_targets(self) -> list:
        """Rows the sequence should run: the ticked ones, or all filled rows (U66)."""
        ticked = [e for e in self._rows if e["sel"].isChecked()]
        if ticked:
            return ticked
        return [e for e in self._rows if e["edit"].text().strip()]

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
        self.set_rows_selectable(checked)       # U114-D9: the ticks only mean something here
        if not checked:
            self.stop_sequence()
            self.clear_selection()

    def set_rows_selectable(self, enabled: bool) -> None:
        """U114-D9: outside sequence mode a row tick does nothing, so grey it out."""
        for entry in self._rows:
            entry["sel"].setEnabled(bool(enabled))

    def toggle_sequence(self) -> None:
        """Start the row-by-row sequence, or stop it when already running."""
        if self._seq_running:
            self.stop_sequence()
            return
        targets = self._sequence_targets()          # U66: ticked rows only
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
        self.log.emit(tr("qs.seq.progress", i=self._seq_index + 1, n=total))
        if self._seq_index + 1 >= total:
            delay = self._row_delay(entry)
            self._seq_timer.singleShot(delay, self._finish_sequence)
            return
        self._seq_index += 1
        self._seq_timer.start(self._row_delay(entry))

    def _delay_width(self) -> int:
        """Width that just fits the longest delay value (U80)."""
        return max(34, self.fontMetrics().horizontalAdvance("60000") + 12)

    def _place_order_badges(self) -> None:
        """Pin each sequence number to the top-right corner of its checkbox (U80)."""
        for entry in self._rows:
            badge = entry["ord"]
            if not badge.isVisible():
                continue
            box, row = entry["sel"], entry["widget"]
            corner = box.mapTo(row, QPoint(box.width(), 0))
            badge.adjustSize()
            badge.move(max(0, corner.x() - badge.width() + 4), max(0, corner.y() - 4))

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
        self.log.emit(tr("qs.seq.done"))
        self._seq_index = 0
        self._seq_queue = []

    def stop_sequence(self) -> None:
        """Stop the sequence and restore the controls."""
        self._seq_timer.stop()
        self._seq_running = False
        self.seq_btn.setText(tr("qs.run"))
        self._seq_index = 0
        self._seq_queue = []

    def _delete_row(self, row: QWidget):
        """Remove a single row (kept for the row-level callers)."""
        entry = next((e for e in self._rows if e["widget"] is row), None)
        if entry is not None:
            self.delete_entries([entry])

    def restore_rows(self, payloads: list) -> None:
        """Re-insert rows removed by delete_entries, in their original order (U118)."""
        for payload in sorted(payloads, key=lambda item: int(item.get("index", 0))):
            self.restore_row(payload)

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
        self.del_btn.setText(tr("qs.del_selected"))
        self.del_btn.setToolTip(tr("qs.del_selected.tip"))
        self.add_btn.setText(tr("qs.add"))
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.seq_check.setText(tr("qs.seq"))
        self.seq_check.setToolTip(tr("qs.seq.tip"))
        self.seq_btn.setText(tr("qs.stop") if self._seq_running else tr("qs.run"))
        self.seq_btn.setToolTip(tr("qs.seq.tip"))
        self._collapse_btn.setToolTip(tr("qs.collapse.tip"))
        self._rail.set_label(tr("qs.title"))
        self._rail.setToolTip(tr("qs.rail.tip"))
        for entry in self._rows:
            entry["edit"].setPlaceholderText(tr("qs.placeholder"))
            entry["send"].setText(tr("qs.send"))
            entry["widget"].setToolTip(tr("qs.row.tip"))
            entry["delay"].setToolTip(tr("qs.delay.tip"))
            entry["unit"].setText(tr("qs.delay.unit"))
            if entry.get("sel") is not None:
                entry["sel"].setToolTip(tr("qs.sel.tip"))
                entry["ord"].setToolTip(tr("qs.sel.order.tip"))

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
                         int(item.get("delay", 500) or 0), bool(item.get("sel", False)))

    def save(self):
        """Persist the quick-send rows into the config file."""
        items = [
            {"text": e["edit"].text(), "hex": e["fmt"].currentIndex() == 0,
             "delay": self._row_delay(e), "sel": bool(e["sel"].isChecked())}
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