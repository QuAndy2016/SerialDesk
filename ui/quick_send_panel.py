"""Quick send panel: editable command shortcuts (max 99), persisted and sequenced.

Why this file was rebuilt (2026-10-04, user: "the logic is a mess - delete it and redo")
--------------------------------------------------------------------------------------
A row has exactly two independent flags, each with a single owner:

* ``ticked`` - sequence membership. Only the row's tick box changes it, and the box is
  visible *and enabled* only while sequence mode is on.
* ``armed``  - the delete target. Only the selection gestures change it: click,
  Ctrl+click, Shift+click (from the anchor), Space, Ctrl+A, the arrow keys.

The previous version made a tick *also* mean "armed", so the two states kept overwriting
each other; three of that day's bug reports (R7/R14/R15) came out of that one coupling.

Two more decisions removed a class of bugs each:

* The event filter is installed on the panel's own widgets, never on ``QApplication``.
  Clicks outside the panel cannot reach it, so the "which widget keeps the selection"
  whitelist, the delete snapshot and the leaked-window problem are all gone.
* Delete is immediate and the main window offers its 3 s undo - Microsoft's confirmation
  guide says to prefer a design that does not need a confirmation, and to confirm only
  what cannot easily be undone (``mess-confirm.md:50-51``).

Counters draw through :class:`_GrowingLabel`: a plain QLabel reports its whole text width
as ``minimumSizeHint``, which grows the panel's *minimum* width - and the panel sits in a
splitter at exactly that minimum, so the divider moved whenever a counter changed (R15).
"""
from __future__ import annotations


from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPainter, QPolygonF
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
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
from ui.rounds import ROUNDS_LIMIT, RoundsSpinBox     # the shared rounds wheel

from app.config import load_config, save_config
from app.i18n import hex_error_message, tr
from app.protocol import HexFormatError, ascii_str_to_bytes, hex_str_to_bytes

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QPaintEvent

MAX_ENTRIES = 99
DEFAULT_ROWS = 10                       # blank rows seeded on first run
RAIL_W = 28                             # width of the strip the folded panel keeps
DELAY_DEFAULT = 500                     # ms, when the field is empty or damaged
DELAY_MIN, DELAY_MAX = 0, 60000
#: One-line row budget (measured on the real widgets, 2026-10-04 review): the command owns
#: the left stretch, the label + action cluster on the right.
NAME_W = 96                  # the label column: ~10 half-width chars / 6 CJK
NAME_W_SEQ = 64              # in sequence mode the name yields room to the command
NAME_MAX = 200               # the display is width-capped; typing is only guarded
COMMAND_MIN_W = 80           # the command never collapses; keeps the row floor under 330 px
SEND_SIZE = 24               # WCAG 2.5.8 / project D4 pointer-target floor
CHIP_W = 30                  # the format marker: one letter + the qsChip padding, no more
EXAMPLES = (                            # seeded once so the panel is never a blank wall
    ("AT", False),
    ("AT+VERSION?", False),
    ("01 03 00 00 00 02", True),
)
SELECTED_PROP = "selected"
SENDING_PROP = "sending"


# -- small pure helpers (no Qt: these can be read and tested on their own) -------------

def loop_should_continue(round_no: int, loops: int) -> bool:
    """True when the sequence should start another round (0 = the ∞ switch is on)."""
    return loops == 0 or round_no < loops


def as_int(value: object, default: int) -> int:
    """An int from config, whatever the file holds.

    A damaged value used to abort the whole panel (and with it the window) with
    ``ValueError: invalid literal for int()`` - a broken config must never stop the app.
    """
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def as_text(value: object) -> str:
    """A config string, or "" - never the literal "None"."""
    return "" if value is None else str(value)


def clamp_delay(ms: int) -> int:
    """A delay in the documented 0..60000 ms range."""
    return max(DELAY_MIN, min(DELAY_MAX, ms))


def parse_payload(text: str, is_hex: bool) -> tuple[bytes | None, str | None]:
    """Turn one row's text into bytes.

    Returns ``(payload, error)`` with exactly one of the two set: the panel's signals are
    separate, so the caller decides whether to send or to report.
    """
    text = text.strip()
    if not text:
        return None, tr("qs.empty")
    try:
        return (hex_str_to_bytes(text) if is_hex else ascii_str_to_bytes(text)), None
    except ValueError as exc:
        if isinstance(exc, HexFormatError):
            return None, hex_error_message(exc)
        return None, tr("qs.bad_fmt", e=exc)


# -- widgets ---------------------------------------------------------------------------

class _GrowingLabel(QLabel):
    """A label whose text must never resize the panel it sits in.

    It keeps its natural width while there is room, reports a tiny minimum, and elides
    instead of spilling when the layout has to squeeze it.
    """

    def minimumSizeHint(self):  # noqa: N802 - Qt naming
        """Report no minimum width, so the text width never drives the layout."""
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event: QPaintEvent):  # noqa: N802 - Qt naming
        """Draw the text, elided when the row had to squeeze it."""
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                            self.width())
        painter.drawText(self.rect(), self.alignment(), text)
        painter.end()


class RailStrip(QWidget):
    """The folded state of the panel: a labelled, clickable strip on screen.

    Folding used to hide the panel completely, leaving a menu entry and Ctrl+B as the
    only way back. The rail keeps something visible to click instead.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None=None):
        super().__init__(parent)
        self._text = ""
        self.setObjectName("qsRail")
        self.setFixedWidth(RAIL_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_label(self, text: str) -> None:
        """Set the visible label."""
        self._text = text
        self.update()

    def paintEvent(self, event: QPaintEvent):  # noqa: N802 - Qt naming
        """Paint the chevron and the rotated label."""
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        # the stylesheet paints the background/border (QWidget#qsRail, incl. :hover)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        colour = QColor(theme.text_color())
        center = self.width() / 2.0
        metrics = self.fontMetrics()            # geometry follows the font, so it scales
        half = max(3.0, metrics.height() / 4.0)
        top = max(6.0, metrics.height() * 0.55)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPolygon(QPolygonF([QPointF(center - half, top),
                                       QPointF(center + half, top + half),
                                       QPointF(center - half, top + 2 * half)]))
        painter.setPen(colour)
        painter.save()
        painter.translate(center + metrics.height() / 3.0, self.height() - metrics.height())
        painter.rotate(-90)
        painter.drawText(0, 0, self._text)
        painter.restore()
        painter.end()

    def mouseReleaseEvent(self, event: QMouseEvent):  # noqa: N802 - Qt naming
        """Reopen the panel when the collapsed rail is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class RowItem(QFrame):
    """One command row.

    The row owns its widgets and exposes *meaning* (``text()``, ``is_hex()``,
    ``delay_ms()``, ``ticked()``/``set_ticked()``, ``armed()``/``set_armed()``). Mouse,
    context-menu and key events are reported to the panel, which owns the selection.
    """

    tickChanged = Signal()
    sendRequested = Signal()

    def __init__(self, text: str = "", is_hex: bool = True, delay_ms: int = DELAY_DEFAULT,
                 name: str = "", note: str = "", ticked: bool = False,
                 parent: QWidget | None=None):
        super().__init__(parent)
        self.note = str(note)
        self.setObjectName("qsRow")
        self.setProperty(SELECTED_PROP, False)
        self.setProperty(SENDING_PROP, False)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setToolTip(tr("qs.row.tip"))
        self._build()
        self.text_edit.setText(text)
        self.name_edit.setText(name)
        self.fmt.setCurrentIndex(0 if is_hex else 1)
        self.delay.setText(str(clamp_delay(delay_ms)))
        self.tick.setChecked(bool(ticked))
        self.refresh_chip()
        self.refresh_tip()

    # -- construction ---------------------------------------------------------------

    def _build(self) -> None:
        """Build the one-line row: ``[tick] command delay? format name [send]``.

        The 2026-10-04 review fixed this order: the command owns the left stretch so every
        command starts on the same x and the list scans vertically, while the label and the
        action cluster on the right. Measured at the panel's real 344 px: command 162 px,
        format marker 30 px, name 96 px, send 24x24 (the offscreen font here is ~1.5x wider
        than the real mono face, where those 162 px read as ~20 characters).
        """
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)
        self._build_leading(row)
        self._build_command(row)
        self._build_trailing(row)

    def _build_leading(self, row: QHBoxLayout) -> None:
        """The sequence tick (only visible in sequence mode) and its order badge."""
        self.tick = QCheckBox(self)
        self.tick.setToolTip(tr("qs.sel.tip"))
        self.tick.setAccessibleName(tr("qs.sel.tip"))
        self.tick.toggled.connect(self._on_tick)
        row.addWidget(self.tick)
        # the sequence number is a tiny label pinned to the tick's corner; it stays out of
        # the layout so it neither widens the row nor eats the stretch
        self.badge = QLabel("", self)
        self.badge.setObjectName("seqOrd")
        self.badge.setToolTip(tr("qs.sel.order.tip"))
        self.badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.badge.hide()

    def _build_command(self, row: QHBoxLayout) -> None:
        """The command box - the row's primary content, and the only stretch item."""
        self.text_edit = QLineEdit(self)
        self.text_edit.setPlaceholderText(tr("qs.empty_row"))
        self.text_edit.setAccessibleName(tr("qs.row.tip"))
        self.text_edit.setMinimumWidth(COMMAND_MIN_W)
        row.addWidget(self.text_edit, 1)

    def _build_trailing(self, row: QHBoxLayout) -> None:
        """The right cluster: the delay (sequence only), the format, the label, the send."""
        # the delay is sequence material, so it is only on screen in sequence mode
        self.delay = QLineEdit(self)
        self.delay.setValidator(QIntValidator(DELAY_MIN, DELAY_MAX, self))
        self.delay.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.delay.setStyleSheet("padding: 3px 4px;")
        self.delay.setFixedWidth(self._delay_width())
        self.delay.setToolTip(tr("qs.delay.tip"))
        self.delay.setAccessibleName(tr("qs.delay.tip"))
        self.delay.textChanged.connect(self.refresh_chip)
        row.addWidget(self.delay)

        # the row's format: one letter on the row, the combo in its popup - a format change
        # reinterprets the text, so it must not be a one-click toggle
        self.chip = QToolButton(self)
        self.chip.setObjectName("qsChip")
        self.chip.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.chip.setToolTip(tr("qs.chip.tip"))
        self.chip.setAccessibleName(tr("qs.chip.tip"))
        self.chip.setFixedWidth(CHIP_W)     # one letter: Qt's default hint is 44 px, too wide
        row.addWidget(self.chip)
        self._build_chip_menu()

        self.name_edit = QLineEdit(self)
        self.name_edit.setObjectName("qsName")
        self.name_edit.setPlaceholderText(tr("qs.name.ph"))
        self.name_edit.setToolTip(tr("qs.name.tip"))
        self.name_edit.setAccessibleName(tr("qs.name.ph"))
        self.name_edit.setMaxLength(NAME_MAX)          # typing is free, the column is capped
        self.name_edit.setFixedWidth(NAME_W)
        self.name_edit.textChanged.connect(self.refresh_tip)
        row.addWidget(self.name_edit)

        self.send_btn = QToolButton(self)
        self.send_btn.setObjectName("qsSend")
        self.send_btn.setToolTip(tr("qs.send.row.tip"))
        self.send_btn.setAccessibleName(tr("qs.send"))
        self.send_btn.setFixedSize(SEND_SIZE, SEND_SIZE)
        self.send_btn.setIconSize(QSize(16, 16))
        self.refresh_send_icon()
        self.send_btn.clicked.connect(self.sendRequested)
        row.addWidget(self.send_btn)

    def set_sequence_mode(self, on: bool) -> None:
        """Sequence mode shows the tick and the delay, and narrows the name column."""
        on = bool(on)
        self.tick.setVisible(on)
        self.tick.setEnabled(on)
        self.delay.setVisible(on)
        self.delay.setEnabled(on)
        self.name_edit.setFixedWidth(NAME_W_SEQ if on else NAME_W)

    def refresh_send_icon(self) -> None:
        """The paper-plane glyph follows the theme (the dark sheet draws a light glyph)."""
        suffix = "dark" if theme.resolved_dark() else "light"
        self.send_btn.setIcon(QIcon("%s/send_%s.png" % (theme.asset_dir(), suffix)))

    def _build_chip_menu(self) -> None:
        """The format lives in the marker's popup; the row itself shows one letter."""
        holder_widget = QWidget()
        holder_layout = QHBoxLayout(holder_widget)
        holder_layout.setContentsMargins(8, 6, 8, 6)
        holder_layout.setSpacing(6)
        self.fmt = QComboBox(holder_widget)
        self.fmt.addItems(["HEX", "ASCII"])
        self.fmt.setAccessibleName(tr("qs.chip.tip"))
        self.fmt.currentIndexChanged.connect(self.refresh_chip)
        holder_layout.addWidget(self.fmt)
        menu = QMenu(self.chip)
        holder = QWidgetAction(menu)
        holder.setDefaultWidget(holder_widget)
        menu.addAction(holder)
        self.chip.setMenu(menu)

    def _delay_width(self) -> int:
        """Width that just fits the longest delay value."""
        return max(34, self.fontMetrics().horizontalAdvance(str(DELAY_MAX)) + 12)

    # -- meaning --------------------------------------------------------------------

    def watched(self) -> tuple:
        """The widgets whose events the panel needs (presses, focus, context menu)."""
        return (self, self.text_edit, self.delay, self.name_edit)

    def text(self) -> str:
        """The command as typed."""
        return self.text_edit.text()

    def name(self) -> str:
        """The optional display name."""
        return self.name_edit.text()

    def is_hex(self) -> bool:
        """True when the chip says HEX (the bytes are exact)."""
        return self.fmt.currentIndex() == 0

    def delay_ms(self) -> int:
        """This row's delay in ms (0..60000, default when the field is empty/damaged)."""
        return clamp_delay(as_int(self.delay.text() or DELAY_DEFAULT, DELAY_DEFAULT))

    def ticked(self) -> bool:
        """True when the row belongs to the sequence."""
        return self.tick.isChecked()

    def set_ticked(self, on: bool) -> None:
        """Set sequence membership (the tick box emits ``tickChanged``)."""
        self.tick.setChecked(bool(on))

    def armed(self) -> bool:
        """True when this row is a delete target."""
        return bool(self.property(SELECTED_PROP))

    def set_armed(self, on: bool) -> None:
        """Paint/unpaint the delete highlight."""
        on = bool(on)
        if self.armed() != on:
            self.setProperty(SELECTED_PROP, on)
            self.style().unpolish(self)
            self.style().polish(self)

    def set_sending(self, on: bool) -> None:
        """Highlight the row the sequence is sending right now."""
        on = bool(on)
        if bool(self.property(SENDING_PROP)) != on:
            self.setProperty(SENDING_PROP, on)
            self.style().unpolish(self)
            self.style().polish(self)

    def payload(self) -> tuple[bytes | None, str | None]:
        """``(bytes, None)`` or ``(None, message)`` for this row's text."""
        return parse_payload(self.text(), self.is_hex())

    def undo_payload(self, index: int) -> dict:
        """What the undo needs to put this row back exactly where it was."""
        return {"text": self.text(), "hex": self.is_hex(), "delay": self.delay_ms(),
                "index": index, "name": self.name(), "note": str(self.note)}

    # -- presentation ---------------------------------------------------------------

    def refresh_chip(self) -> None:
        """The marker shows the row's format; its tooltip spells out format + delay."""
        fmt = "HEX" if self.is_hex() else "ASCII"
        self.chip.setText("H" if self.is_hex() else "A")
        self.chip.setToolTip(tr("qs.chip.tip", fmt=fmt,
                                ms=(self.delay.text().strip() or "0")))

    def refresh_tip(self) -> None:
        """The row tooltip carries the name and the note; the name field shows its full text.

        The name column is width-capped, and an editable field clips instead of drawing an
        ellipsis, so hovering the field is how the whole name stays reachable
        (the "full name infotip" pattern, uxguide/ctrl-tooltips-and-infotips.md:126).
        """
        name, note = self.name().strip(), str(self.note).strip()
        parts = [part for part in (name, note) if part]
        self.setToolTip("\n".join(parts) if parts else tr("qs.row.tip"))
        self.name_edit.setToolTip(name or tr("qs.name.tip"))

    def set_badge(self, order: int | None) -> None:
        """Show (or hide) the sequence position badge."""
        if order is None:
            self.badge.setText("")
            self.badge.hide()
            return
        self.badge.setText(str(order))
        self.badge.setVisible(self.tick.isVisible())

    def place_badge(self) -> None:
        """Pin the badge to the top-right corner of the tick box."""
        if not self.badge.isVisible():
            return
        corner = self.tick.mapTo(self, QPoint(self.tick.width(), 0))
        self.badge.adjustSize()
        self.badge.move(max(0, corner.x() - self.badge.width() + 4), max(0, corner.y() - 4))

    def _on_tick(self, _checked: bool = False) -> None:
        self.tickChanged.emit()

    def retranslate(self) -> None:
        """Re-apply translated strings after a language change."""
        self.text_edit.setPlaceholderText(tr("qs.empty_row"))
        self.name_edit.setPlaceholderText(tr("qs.name.ph"))
        self.name_edit.setToolTip(tr("qs.name.tip"))
        self.tick.setToolTip(tr("qs.sel.tip"))
        self.badge.setToolTip(tr("qs.sel.order.tip"))
        self.send_btn.setToolTip(tr("qs.send.row.tip"))
        self.send_btn.setAccessibleName(tr("qs.send"))
        self.refresh_send_icon()
        self.delay.setToolTip(tr("qs.delay.tip"))
        self.delay.setAccessibleName(tr("qs.delay.tip"))
        self.refresh_chip()
        self.refresh_tip()


class QuickSendPanel(QWidget):
    """Right-hand pane: the quick-send rows, their selection, sequence and persistence.

    State owners - nothing outside this list may write these:

    ======================  =====================================================
    ``self._rows``          the rows, in list order
    ``self._anchor``        where a Shift+click range starts (set from the start)
    ``self._running``       the sequence is stepping
    ``self._finishing``     the pending timer finishes the round instead of sending
    ``self._queue``         the rows this run walks, snapshotted when it starts
    ``self._index``         position in ``_queue``
    ``self._round``         the round being sent right now
    ``self._rounds_sent``   completed rounds (header counter)
    ``self._folded``        the panel shows its rail instead of its contents
    ======================  =====================================================
    """

    send_payload = Signal(bytes, bool)     # parsed payload + whether the row is HEX
    error = Signal(str)                    # user-facing format error text
    deleted = Signal(list)                 # removed row payloads (main window: 3 s undo)
    log = Signal(str)                      # one-line progress / explanation
    collapsed_changed = Signal(bool)       # fold the panel away

    def __init__(self, parent: QWidget | None=None):
        super().__init__(parent)
        self._rows: list[RowItem] = []
        self._anchor: RowItem | None = None
        self._running = False
        self._finishing = False
        self._queue: list[RowItem] = []
        self._index = 0
        self._round = 1
        self._rounds_sent = 0
        self._folded = False
        self._sending: RowItem | None = None
        self._step_timer = QTimer(self)
        self._step_timer.setSingleShot(True)
        self._step_timer.timeout.connect(self._advance)
        self._build_ui()
        self._load()
        self.set_rows_selectable(self.seq_check.isChecked())

    # -- construction ---------------------------------------------------------------

    def _build_ui(self) -> None:
        """The panel owns both of its states: the normal column and the rail."""
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._content = QWidget(self)
        outer.addWidget(self._content, 1)
        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(6, 6, 6, 6)
        self._build_head(layout)
        self._build_controls(layout)
        self._build_rows(layout)
        self._build_rail(outer)

    def _build_head(self, layout: QVBoxLayout) -> None:
        """Title, the two counters and the row count.

        The counters live here on purpose: this row has spare room, while the control row
        below already sits at its minimum width - anything that grows there drags the
        splitter with it (a tick used to change the panel's width).
        """
        head = QHBoxLayout()
        head.setSpacing(6)
        accent = QFrame(self._content)
        accent.setObjectName("qsTitleBar")
        accent.setFixedSize(3, 14)
        head.addWidget(accent)
        self._title_lbl = QLabel(tr("qs.title"), self._content)
        self._title_lbl.setObjectName("qsTitle")
        head.addWidget(self._title_lbl)
        head.addStretch(1)
        self.rounds_lbl = _GrowingLabel("", self._content)
        self.rounds_lbl.setObjectName("qsSeqSent")
        self.rounds_lbl.setToolTip(tr("qs.seq.sent.tip"))
        head.addWidget(self.rounds_lbl)
        self.armed_lbl = _GrowingLabel("", self._content)
        self.armed_lbl.setObjectName("qsArmed")
        self.armed_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(self.armed_lbl)
        self.count_lbl = _GrowingLabel("0/%d" % MAX_ENTRIES, self._content)
        head.addWidget(self.count_lbl)
        layout.addLayout(head)

    def _build_controls(self, layout: QVBoxLayout) -> None:
        """Sequence mode, Run, the round controls and Delete."""
        controls = QHBoxLayout()
        self.seq_check = QCheckBox(tr("qs.seq"), self._content)
        self.seq_check.setToolTip(tr("qs.seq.tip"))
        self.seq_check.toggled.connect(self._on_seq_toggled)
        controls.addWidget(self.seq_check)
        self.seq_btn = QPushButton(tr("qs.run"), self._content)
        self.seq_btn.setToolTip(tr("qs.seq.tip"))
        self.seq_btn.setEnabled(False)
        self.seq_btn.clicked.connect(self.toggle_sequence)
        controls.addWidget(self.seq_btn)
        self.rounds = RoundsSpinBox(self._content, tip=tr("qs.rounds.tip"),
                                    name=tr("qs.rounds.label"))
        controls.addWidget(self.rounds)
        controls.addStretch(1)
        controls.addSpacing(16)          # keep a destructive action away from Run
        self.del_btn = QPushButton(tr("qs.del"), self._content)
        self.del_btn.setEnabled(False)
        self.del_btn.clicked.connect(self.delete_armed)
        controls.addWidget(self.del_btn)
        layout.addLayout(controls)

    def _build_rows(self, layout: QVBoxLayout) -> None:
        """Scrollable row container and the add-row button."""
        scroll = QScrollArea(self._content)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(332)      # rows need ~318 px or the buttons clip
        self._container = QWidget()
        self._row_layout = QVBoxLayout(self._container)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(4)
        self._row_layout.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)
        self.add_btn = QPushButton(tr("qs.add"), self._content)
        self.add_btn.setProperty("secondary", True)
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.add_btn.clicked.connect(lambda: self.add_row())
        layout.addWidget(self.add_btn)

    def _build_rail(self, outer: QHBoxLayout) -> None:
        """The narrow strip that stays on screen while the panel is folded."""
        self._rail = RailStrip(self)
        self._rail.set_label(tr("qs.title"))
        self._rail.setToolTip(tr("qs.rail.tip"))
        self._rail.clicked.connect(lambda: self.collapsed_changed.emit(False))
        self._rail.hide()
        outer.addWidget(self._rail)

    # -- rows -----------------------------------------------------------------------

    def add_row(self, text: str = "", is_hex: bool = True, delay_ms: int = DELAY_DEFAULT,
                selected: bool = False, name: str = "", note: str = "") -> RowItem | None:
        """Append one command row (and return it, or None when the limit is reached)."""
        if len(self._rows) >= MAX_ENTRIES:
            self.log.emit(tr("qs.max", n=MAX_ENTRIES))
            return None
        row = RowItem(text=text, is_hex=is_hex, delay_ms=delay_ms, name=name, note=note,
                      ticked=selected, parent=self._container)
        self._row_layout.insertWidget(self._row_layout.count() - 1, row)
        for widget in row.watched():
            widget.installEventFilter(self)
        row.tickChanged.connect(lambda item=row: self._on_tick_changed(item))
        row.sendRequested.connect(lambda item=row: self._send_one(item))
        self._rows.append(row)
        row.set_sequence_mode(self.seq_check.isChecked())
        self._refresh_badges()
        self._refresh_controls()
        return row

    def reload_from_config(self) -> None:
        """Drop every row and rebuild the panel from config.json (after a config import)."""
        for row in list(self._rows):
            row.setParent(None)
            self._rows.remove(row)
        self._load()
        self._refresh_badges()
        self._refresh_controls()

    def _row_of(self, obj: QObject) -> RowItem | None:
        """The row that owns a widget, or None."""
        for row in self._rows:
            if obj is row or (isinstance(obj, QWidget) and row.isAncestorOf(obj)):
                return row
        return None

    def _index_of(self, row: RowItem) -> int:
        """Index of a row by identity, or -1."""
        for index, other in enumerate(self._rows):
            if other is row:
                return index
        return -1

    # -- selection (the delete target) ----------------------------------------------

    def arm_row(self, row: RowItem, mode: str = "replace") -> None:
        """replace / toggle / range - the platform's extended-selection semantics.

        Shift+click extends from the anchor (UI-03); with no anchor yet - the very first
        interaction may be a Shift+click - it falls back to a plain selection.
        """
        if mode == "toggle":
            row.set_armed(not row.armed())
            self._anchor = row
        elif mode == "range" and self._anchor in self._rows:
            lo, hi = sorted((self._index_of(self._anchor), self._index_of(row)))
            for index, other in enumerate(self._rows):
                other.set_armed(lo <= index <= hi)
        else:
            for other in self._rows:
                other.set_armed(other is row)
            self._anchor = row
        self._refresh_controls()

    def clear_selection(self) -> bool:
        """Drop the delete highlight; True when something was highlighted."""
        changed = False
        for row in self._rows:
            if row.armed():
                row.set_armed(False)
                changed = True
        self._refresh_controls()
        return changed

    def armed_rows(self) -> list[RowItem]:
        """The rows a delete would remove, in list order."""
        return [row for row in self._rows if row.armed()]

    def selected_entries(self) -> list[RowItem]:
        """Alias kept for older callers: the armed rows."""
        return self.armed_rows()

    def selected_row(self) -> RowItem | None:
        """The first armed row, or None."""
        rows = self.armed_rows()
        return rows[0] if rows else None

    def _move_arm(self, step: int, extend: bool = False) -> bool:
        """Move the armed row by ``step`` rows and give that row the focus.

        The row is the selection unit, so the arrow keys move *rows* (UI-09); they only
        reach here when no text field owns the focus.
        """
        if not self._rows:
            return False
        current = self._row_of(QApplication.focusWidget())
        if current is None:
            current = self.selected_row()
        index = self._index_of(current) if current is not None else -1
        target = (0 if step > 0 else len(self._rows) - 1) if index < 0 else index + step
        if not 0 <= target < len(self._rows):
            return False
        row = self._rows[target]
        self.arm_row(row, "range" if extend else "replace")
        row.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def _owns_keyboard(self) -> bool:
        """True only when the focus is inside the panel and not in a text field."""
        focus = QApplication.focusWidget()
        if focus is None or isinstance(focus, (QLineEdit, QPlainTextEdit, QAbstractSpinBox)):
            return False
        return focus is self or self.isAncestorOf(focus)

    # -- events (panel widgets only: nothing is installed on QApplication) -----------

    def eventFilter(self, obj: QObject, event: QEvent):  # noqa: N802 - Qt naming
        """Press selects; FocusIn selects; ContextMenu shows the standard menu; keys act."""
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            row = self._row_of(obj)
            if row is not None and obj is not row.tick:
                # the tick box is a sequence control, not a selection: pressing it must
                # not arm the row (the old code coupled the two and they fought)
                mods = event.modifiers()
                if mods & Qt.KeyboardModifier.ControlModifier:
                    self.arm_row(row, "toggle")
                elif mods & Qt.KeyboardModifier.ShiftModifier:
                    self.arm_row(row, "range")
                else:
                    self.arm_row(row, "replace")
            elif row is None and (obj is self or obj is self._content):
                self.clear_selection()          # a click on the panel's own empty area
        elif kind == QEvent.Type.FocusIn:
            row = self._row_of(obj)
            if row is not None and not row.armed():
                self.arm_row(row, "replace")
        elif kind == QEvent.Type.Resize:
            if self._row_of(obj) is not None:
                self._place_badges()
        elif kind == QEvent.Type.ContextMenu:
            row = self._row_of(obj)
            if row is not None:
                menu = self.row_context_menu(obj)
                menu.exec(event.globalPos())
                menu.deleteLater()      # createStandardContextMenu hands the menu over
                return True
        elif kind == QEvent.Type.KeyPress:
            # Enter inside a row's command box sends that row: the box owns the key, so the
            # panel's own key path (which ignores text fields) would never see it. Same rule
            # as the send box - Enter runs the default command (inter-keyboard.md:78).
            if self._is_row_send_key(obj, event):
                row = self._row_of(obj)
                if row is not None:
                    self._send_one(row)
                    return True
            if self._owns_keyboard():
                return self._on_key(event)
        return super().eventFilter(obj, event)

    def _is_row_send_key(self, obj: QObject, event: QKeyEvent) -> bool:
        """True when this key means "send the row that owns ``obj``"."""
        row = self._row_of(obj)
        if row is None or obj is not row.text_edit:
            return False                       # the name box is a label, not a command box
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False
        return event.modifiers() in (Qt.KeyboardModifier.NoModifier,
                                     Qt.KeyboardModifier.KeypadModifier)

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802 - Qt naming
        """Panel-level keys when the panel itself (not a row) has the focus."""
        if not self._on_key(event):
            super().keyPressEvent(event)

    def _on_key(self, event: QKeyEvent) -> bool:
        """The panel's own keys: Delete, Enter, the arrows, Space, Ctrl+A and Esc."""
        key, mods = event.key(), event.modifiers()
        if key == Qt.Key.Key_Delete:
            self.delete_armed()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not mods:
            # the list's default command is "send": Enter runs the row the click selected
            armed = self.armed_rows()
            if len(armed) == 1:
                self._send_one(armed[0])
                return True
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            step = 1 if key == Qt.Key.Key_Down else -1
            if self._move_arm(step, bool(mods & Qt.KeyboardModifier.ShiftModifier)):
                return True
        if key == Qt.Key.Key_Space:
            row = self._row_of(QApplication.focusWidget())
            if row is not None and row is not row.tick:
                self.arm_row(row, "toggle")
                return True
        if key == Qt.Key.Key_Escape and self.clear_selection():
            return True
        if key == Qt.Key.Key_A and mods & Qt.KeyboardModifier.ControlModifier:
            for row in self._rows:
                row.set_armed(True)
            self._anchor = self._rows[-1] if self._rows else None
            self._refresh_controls()
            return True
        return False

    def row_context_menu(self, obj: QObject) -> QMenu:
        """The row's context menu: the widget's own standard menu, plus "edit note".

        A text box keeps Cut/Copy/Paste (the platform rule is "always have the relevant
        standard context menu commands"); the row's own command is appended, not swapped.
        """
        row = self._row_of(obj)
        menu = None
        if isinstance(obj, (QLineEdit, QPlainTextEdit)):
            menu = obj.createStandardContextMenu()
        if menu is None:
            menu = QMenu(self)
        if not menu.isEmpty():
            menu.addSeparator()
        note = menu.addAction(tr("qs.note.menu"))
        if row is not None:
            note.triggered.connect(lambda _checked=False, item=row: self.edit_note(item))
        return menu

    def edit_note(self, row: RowItem) -> None:
        """Edit the free-text note for one command (row context menu)."""
        text, ok = QInputDialog.getMultiLineText(
            self, tr("qs.note.title"), tr("qs.note.label"), str(row.note))
        if ok:
            row.note = text
            row.refresh_tip()
            self.save()

    # -- sending --------------------------------------------------------------------

    def _send_one(self, row: RowItem) -> None:
        """Send one row's payload (the row's Send button)."""
        payload, error = row.payload()
        if error is not None:
            # an empty row is a reminder, a malformed one is an error - the panel made
            # the same distinction before ("指令内容为空" was a log line, not an error)
            (self.log if not row.text().strip() else self.error).emit(error)
            return
        self.send_payload.emit(payload, row.is_hex())

    # -- sequence mode --------------------------------------------------------------

    def _on_seq_toggled(self, checked: bool) -> None:
        self.seq_btn.setEnabled(checked)
        self.set_rows_selectable(checked)
        if not checked:
            self.stop_sequence()
            self.clear_selection()

    def set_rows_selectable(self, enabled: bool = True) -> None:
        """The tick box belongs to sequence mode, and only there.

        Visibility and enabled state change together: the boxes are built while the mode
        is off, so restoring only their visibility left them disabled and every click was
        swallowed (the row highlighted, the tick never took).
        """
        for row in self._rows:
            row.set_sequence_mode(bool(enabled))
        self._refresh_badges()

    def sequence_rows(self) -> list[RowItem]:
        """The rows the sequence runs: the ticked ones, or all non-empty rows."""
        ticked = [row for row in self._rows if row.ticked()]
        if ticked:
            return ticked
        return [row for row in self._rows if row.text().strip()]

    def toggle_sequence(self) -> None:
        """Start the row-by-row sequence, or stop it when already running."""
        if self._running:
            self.stop_sequence()
            return
        rows = self.sequence_rows()
        if not rows:
            self.log.emit(tr("qs.seq.none"))
            return
        self._queue = list(rows)
        self._index = 0
        self._round = 1
        self._rounds_sent = 0
        self._running = True
        self._finishing = False
        self._refresh_rounds()
        self.seq_btn.setText(tr("qs.stop"))
        self._send_current()

    def stop_sequence(self) -> None:
        """Stop the sequence and restore the controls (cancels the pending step)."""
        self._reset_sequence()

    def _reset_sequence(self) -> None:
        self._step_timer.stop()
        self._running = False
        self._finishing = False
        self._queue = []
        self._index = 0
        self._round = 1
        self.seq_btn.setText(tr("qs.run"))
        self._mark_sending(None)

    def _send_current(self) -> None:
        """Send the row at ``_index``, then wait that row's delay."""
        row = self._queue[self._index]
        self._mark_sending(row)
        self._send_one(row)
        self.log.emit(tr("qs.seq.progress", i=self._index + 1, n=len(self._queue)))
        if self._index + 1 >= len(self._queue):
            self._finishing = True
        else:
            self._index += 1
        # the *instance* timer, never QTimer.singleShot(): a static timer cannot be
        # cancelled, so Stop used to leave a callback that inflated the round counter
        self._step_timer.start(row.delay_ms())

    def _advance(self) -> None:
        """The step timer fired; a stopped sequence must do nothing at all."""
        if not self._running:
            return
        if self._finishing:
            self._finishing = False
            self._finish_round()
            return
        self._send_current()

    def _finish_round(self) -> None:
        """One full round went out: another one, or done."""
        if not self._running:
            return
        self._rounds_sent += 1
        self._refresh_rounds()
        if loop_should_continue(self._round, self._loops_value()):
            self._round += 1
            self._index = 0
            self._send_current()
            return
        self.log.emit(tr("qs.seq.done.n", n=max(1, self._round)))
        self._reset_sequence()

    def _loops_value(self) -> int:
        """Rounds to run; 0 means the ∞ state of the rounds wheel."""
        return max(0, min(ROUNDS_LIMIT, self.rounds.value()))

    def _mark_sending(self, row: RowItem | None) -> None:
        """Highlight exactly one row as "being sent right now" (or none)."""
        self._sending = row
        for other in self._rows:
            other.set_sending(other is row)

    def _refresh_rounds(self) -> None:
        """Show the completed-round counter (empty before the first round)."""
        self.rounds_lbl.setText(tr("qs.seq.sent", n=self._rounds_sent)
                                if self._rounds_sent else "")

    # -- deletion -------------------------------------------------------------------

    def delete_armed(self) -> None:
        """Delete the selected rows immediately; the main window offers the 3 s undo.

        No modal confirmation on purpose: the action is undoable (Microsoft's guidance is
        to confirm only what "cannot be easily undone"), and a modal box that owns the
        mouse while the user looks elsewhere is indistinguishable from a dead button.
        """
        rows = self.armed_rows()
        if not rows:
            self.log.emit(tr("qs.del.none"))
            return
        self.delete_entries(rows)

    def delete_entries(self, rows: list[RowItem]) -> None:
        """Remove the given rows and report them as one batch (the undo payloads)."""
        payloads = sorted((row.undo_payload(self._index_of(row)) for row in rows),
                          key=lambda item: item["index"])
        for row in rows:
            if row in self._rows:
                self._rows.remove(row)
            row.setParent(None)
            row.deleteLater()
        if self._anchor in (None,) or self._anchor not in self._rows:
            self._anchor = self._rows[-1] if self._rows else None
        self._refresh_badges()
        self._refresh_controls()
        if payloads:
            self.deleted.emit(payloads)
        self.save()

    def restore_rows(self, payloads: list) -> None:
        """Re-insert rows removed by ``delete_entries``, in their original order."""
        for payload in sorted(payloads, key=lambda item: as_int(item.get("index", 0), 0)):
            self.restore_row(payload)

    def restore_row(self, payload: dict) -> None:
        """Re-insert one row removed by a delete (undo)."""
        index = as_int(payload.get("index", len(self._rows)), len(self._rows))
        row = self.add_row(as_text(payload.get("text", "")), bool(payload.get("hex", True)),
                           clamp_delay(as_int(payload.get("delay", DELAY_DEFAULT),
                                              DELAY_DEFAULT)),
                           False, as_text(payload.get("name", "")),
                           as_text(payload.get("note", "")))
        if row is None:
            return
        if 0 <= index < len(self._rows) - 1:
            self._rows.remove(row)
            self._rows.insert(index, row)
            self._reorder_rows()
        self.save()

    def _reorder_rows(self) -> None:
        """Re-apply the row order in the layout (undo keeps the position)."""
        for index, row in enumerate(self._rows):
            self._row_layout.insertWidget(index, row)

    # -- chrome ---------------------------------------------------------------------

    def _refresh_controls(self) -> None:
        """The armed counter, the delete button and the row counter."""
        count = len(self.armed_rows())
        self.del_btn.setEnabled(count > 0)
        self.del_btn.setToolTip(tr("qs.del.tip") if count else tr("qs.del.none.tip"))
        self.armed_lbl.setText(tr("qs.armed", n=count) if count else "")
        self.armed_lbl.setToolTip(tr("qs.del.tip") if count else tr("qs.del.none.tip"))
        self.count_lbl.setText("%d/%d" % (len(self._rows), MAX_ENTRIES))

    def _refresh_badges(self) -> None:
        """Number the ticked rows 1..n so the run order is obvious."""
        order = 0
        for row in self._rows:
            if row.ticked():
                order += 1
                row.set_badge(order)
            else:
                row.set_badge(None)
        self._place_badges()

    def _place_badges(self) -> None:
        """Pin every badge to its tick box (called on resize and after renumbering)."""
        for row in self._rows:
            row.place_badge()

    def _on_tick_changed(self, _row: RowItem) -> None:
        """A tick only changes sequence membership - never the delete selection."""
        self._refresh_badges()

    def set_folded(self, folded: bool) -> None:
        """Show the rail instead of the panel contents, and let the splitter shrink."""
        self._folded = bool(folded)
        if self._folded:
            self.clear_selection()
        self._content.setVisible(not self._folded)
        # folded costs nothing at rest - the rail is brought back by hovering the window's
        # right edge, or by the toolbar button / Ctrl+B
        self._rail.hide()
        if self._folded:
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)      # QWIDGETSIZE_MAX
        self.updateGeometry()

    def set_rail_visible(self, on: bool) -> None:
        """Show the folded-state rail while the pointer is near the window's right edge."""
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

    def detach_app_filter(self) -> None:
        """Kept for the window's close path.

        The panel installs its event filter on its own widgets now (never on the
        application), so there is nothing to detach - the old app-wide filter kept closed
        windows alive and made the audit grow quadratically.
        """

    def retranslate(self) -> None:
        """Re-apply translated strings after a language change."""
        self._title_lbl.setText(tr("qs.title"))
        self.add_btn.setText(tr("qs.add"))
        self.add_btn.setToolTip(tr("qs.add.tip", n=MAX_ENTRIES))
        self.seq_check.setText(tr("qs.seq"))
        self.seq_check.setToolTip(tr("qs.seq.tip"))
        self.seq_btn.setText(tr("qs.stop") if self._running else tr("qs.run"))
        self.seq_btn.setToolTip(tr("qs.seq.tip"))
        self.rounds.setToolTip(tr("qs.rounds.tip"))
        self.rounds.setAccessibleName(tr("qs.rounds.label"))
        self.del_btn.setText(tr("qs.del"))
        self.rounds_lbl.setToolTip(tr("qs.seq.sent.tip"))
        self._rail.set_label(tr("qs.title"))
        self._rail.setToolTip(tr("qs.rail.tip"))
        for row in self._rows:
            row.retranslate()
        self._refresh_controls()

    # -- persistence ----------------------------------------------------------------

    def _load(self) -> None:
        """Build the rows from config.json; missing or damaged values fall back."""
        data = load_config()
        items = data.get("quick_send", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []
        items = [item for item in items if isinstance(item, dict)]
        if len(items) > MAX_ENTRIES:
            self.log.emit(tr("qs.max", n=MAX_ENTRIES))
            items = items[:MAX_ENTRIES]
        if not items:
            for text, is_hex in EXAMPLES:
                row = self.add_row(text, is_hex)
                if row is not None:
                    row.text_edit.setToolTip(tr("qs.example.tip"))
            for _ in range(max(0, DEFAULT_ROWS - len(EXAMPLES))):
                self.add_row()
            return
        for item in items:
            self.add_row(as_text(item.get("text", "")), bool(item.get("hex", True)),
                         clamp_delay(as_int(item.get("delay", DELAY_DEFAULT), DELAY_DEFAULT)),
                         bool(item.get("sel", False)), as_text(item.get("name", "")),
                         as_text(item.get("note", "")))

    def save(self) -> None:
        """Persist the rows through the shared atomic writer.

        ``app.config.save_config`` merges into the file and swaps it in with
        ``os.replace``; the hand-rolled ``open(path, "w")`` this used to do could truncate
        the whole config and never wrote ``config_version``.
        """
        items = [{"text": row.text(), "hex": row.is_hex(), "delay": row.delay_ms(),
                  "sel": row.ticked(), "name": row.name(), "note": str(row.note)}
                 for row in self._rows]
        if not save_config({"quick_send": items}):
            self.log.emit(tr("qs.save_fail", e="config.json"))
