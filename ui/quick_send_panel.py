"""Quick send panel: editable command shortcuts, up to 99 entries, persisted."""

from __future__ import annotations

import json
import os

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIntValidator, QPainter, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOption,
    QToolButton,
    QVBoxLayout,
    QWidget,
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self.setObjectName("qsRail")
        self.setFixedWidth(RAIL_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_label(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt naming
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

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
from app.config import CONFIG_PATH   # U34: one data dir for the whole app


class QuickSendPanel(QWidget):
    """Right-hand panel: list of editable quick-send commands.

    Each row: text edit + format combo (HEX/ASCII) + send button + delete.
    Persisted to config.json as JSON list; max 99 rows.
    """

    send_payload = Signal(bytes)   # parsed payload, no checksum applied yet
    error = Signal(str)            # user-facing format error text (U36)
    deleted = Signal(dict)         # removed row payload + index (U58: undo)
    log = Signal(str)
    collapsed_changed = Signal(bool)   # U88: fold the panel away

    def __init__(self, parent=None):
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

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        # U106: the panel owns both of its states - the normal column, and a narrow rail
        # that stays on screen while folded (so the way back is always visible).
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._content = QWidget()
        outer.addWidget(self._content, 1)
        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(6, 6, 6, 6)

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
        self.del_btn = QPushButton(tr("qs.del_selected"))   # U68 plan A
        self.del_btn.setToolTip(tr("qs.del_selected.tip"))
        self.del_btn.setEnabled(False)
        self.del_btn.clicked.connect(self.delete_selected)
        seq_row.addWidget(self.del_btn)
        layout.addLayout(seq_row)

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

        self.add_btn = QPushButton(tr("qs.add"))
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.add_btn.clicked.connect(lambda: self.add_row())
        layout.addWidget(self.add_btn)

        self._rail = RailStrip()
        self._rail.set_label(tr("qs.title"))
        self._rail.setToolTip(tr("qs.rail.tip"))
        self._rail.clicked.connect(lambda: self.collapsed_changed.emit(False))
        self._rail.hide()
        outer.addWidget(self._rail)

    # -- rows ----------------------------------------------------------------

    def add_row(self, text: str = "", is_hex: bool = True, delay_ms: int = 500,
                selected: bool = False):
        if len(self._rows) >= MAX_ENTRIES:
            self.log.emit(tr("qs.max", n=MAX_ENTRIES))
            return
        row = QFrame()                     # U68 plan A: a frame paints the selection
        row.setObjectName("qsRow")
        row.setProperty("selected", False)
        row.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        row.setToolTip(tr("qs.row.tip"))
        row.installEventFilter(self)
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 2, 0, 2)
        v.setSpacing(2)

        # U105: the first line is the command itself and gets the whole width - it used
        # to share the row with four other controls and was left with ~105 px.
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)

        # U66: pick which rows the sequence runs, with a small order badge
        sel = QCheckBox()
        sel.setToolTip(tr("qs.sel.tip"))
        sel.toggled.connect(self._renumber_selection)
        h.addWidget(sel)
        # U80: the sequence number is a tiny label pinned to the checkbox corner.
        # It stays out of the layout so it neither widens the row nor eats stretch.
        ord_lbl = QLabel("", row)
        ord_lbl.setObjectName("seqOrd")
        ord_lbl.setToolTip(tr("qs.sel.order.tip"))
        ord_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        ord_lbl.hide()

        edit = QLineEdit(text)
        edit.setPlaceholderText(tr("qs.placeholder"))
        h.addWidget(edit, 1)

        send = QPushButton(tr("qs.send"))
        send.setMinimumWidth(52)
        send.setStyleSheet("padding: 2px 6px;")  # override global QSS padding
        send.clicked.connect(lambda: self._send_row(row))
        h.addWidget(send)
        v.addLayout(h)

        # U105/U104: the second line carries the row's properties, indented under the
        # text box, with the unit written out - "500" explained itself to nobody.
        meta = QHBoxLayout()
        meta.setContentsMargins(24, 0, 0, 0)
        meta.setSpacing(4)
        fmt = QComboBox()
        fmt.addItems(["HEX", "ASCII"])
        fmt.setCurrentIndex(0 if is_hex else 1)
        meta.addWidget(fmt)

        delay = QLineEdit(str(max(0, min(60000, int(delay_ms)))))   # U31: bare number, no arrows
        delay.setValidator(QIntValidator(0, 60000, self))
        delay.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        delay.setStyleSheet("padding: 3px 4px;")   # U80: no room to waste in a tight row
        delay.setFixedWidth(self._delay_width())   # U80: just wide enough for 60000
        delay.setToolTip(tr("qs.delay.tip"))
        meta.addWidget(delay)
        unit = QLabel(tr("qs.delay.unit"))
        unit.setObjectName("qsMeta")
        meta.addWidget(unit)
        meta.addStretch(1)
        v.addLayout(meta)


        self._row_layout.insertWidget(self._row_layout.count() - 1, row)
        edit.installEventFilter(self)      # clicking into the text selects the row
        self._rows.append({"widget": row, "edit": edit, "fmt": fmt, "send": send,
                           "delay": delay, "sel": sel, "ord": ord_lbl, "unit": unit})
        sel.setChecked(bool(selected))
        self._renumber_selection()
        self._update_count()

    # -- folded state (U106) -------------------------------------------------

    def set_folded(self, folded: bool) -> None:
        """Show the rail instead of the panel contents, and let the splitter shrink."""
        self._folded = bool(folded)
        self._content.setVisible(not self._folded)
        self._rail.setVisible(self._folded)
        if self._folded:
            self.setMinimumWidth(RAIL_W)
            self.setMaximumWidth(RAIL_W)
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)      # QWIDGETSIZE_MAX
        self.updateGeometry()

    def is_folded(self) -> bool:
        return self._folded

    # -- row selection + deletion (U68 plan A) -------------------------------

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        """Click selects a row; Delete removes the selection (3 s undo stays)."""
        if event.type() == QEvent.Type.MouseButtonPress:
            for entry in self._rows:
                if entry["widget"] is obj or entry["edit"] is obj:
                    self._select_row(entry)
                    break
        elif event.type() == QEvent.Type.Resize and any(
                entry["widget"] is obj for entry in self._rows):
            self._place_order_badges()
        elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            return True
        return super().eventFilter(obj, event)

    def _select_row(self, entry: dict) -> None:
        """Highlight one row so the toolbar delete knows its target."""
        for other in self._rows:
            want = other is entry
            if bool(other["widget"].property("selected")) != want:
                other["widget"].setProperty("selected", want)
                other["widget"].style().unpolish(other["widget"])
                other["widget"].style().polish(other["widget"])
        self.del_btn.setEnabled(True)

    def selected_entry(self) -> dict | None:
        return next((e for e in self._rows if e["widget"].property("selected")), None)

    def delete_selected(self) -> None:
        """Delete the highlighted row; main window offers a 3 s undo (U68)."""
        entry = self.selected_entry()
        if entry is None:
            return
        self._delete_row(entry["widget"])
        self.del_btn.setEnabled(False)

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
        if not checked:
            self.stop_sequence()

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
        self.seq_label.setText(tr("qs.seq.progress", i=self._seq_index + 1, n=total))
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
        self.del_btn.setEnabled(False)
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