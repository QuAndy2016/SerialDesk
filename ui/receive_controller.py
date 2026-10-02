"""Receive/view controller: frame flush, text emission into the display, colourising and clear."""
from __future__ import annotations


import json
import os
import shutil
import sys
import time
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
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
    QToolTip,
    QStackedWidget,
    QWidgetAction,
    QVBoxLayout,
    QWidget,
)
from app.framing import DEFAULT_SETTLE_MS, ByteFrameSplitter, FrameAssembler
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
from app import (
    __version__,
    update as update_check,
    i18n,
)
from app.config import (
    CONFIG_PATH,
    data_dir,
    load_config,
    log_dir,
    save_config,
)
from app.log_sink import LogSink
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.autosave_dialog import AutoSaveDialog
from ui.history_dialog import HistoryDialog
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from ui.menus import build_menu
from ui.log_controller import apply_autosave_settings, log_append, log_close, log_header_text, log_open, on_log_line, on_save_log_as, on_save_log_quick, show_autosave_settings
from ui.regions import (BAUDRATES, DATA_FIRST_H, DATA_FIRST_V,
                        RECEIVE_MAX_LINES, SPLIT_AUTO, SPLIT_DELIMITED,
                        SPLIT_FIXED, SPLIT_HEADER, SPLIT_MANUAL, SPLIT_TLV,
                        _fixed_row, build_connection_row,
                        build_data_panes, build_send_group, build_status_bar)
from app.i18n import hex_error_message, tr
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII, RX_COLUMN_HEX, frag_kind, fragment_visible, kind_is_meta, kind_is_tx, long_line_tooltip)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.main_window import MainWindow
CLEAR_UNDO_MAX_LINES = 60000  # above this, clearing is not snapshotted (U42)
def _byte_splitter(win: MainWindow) -> ByteFrameSplitter:
    "byte splitter"
    """The lazy per-window byte-stream splitter for the B3 modes (U50 slot)."""
    splitter = getattr(win, "_byte_splitter", None)
    if splitter is None:
        splitter = ByteFrameSplitter()
        win._byte_splitter = splitter
    return splitter

def flush_byte_frames(win: MainWindow) -> None:
    "flush byte frames"
    """Emit the unfinished tail when the split rule changes or the port closes."""
    splitter = getattr(win, "_byte_splitter", None)
    if splitter is None:
        return
    tail = splitter.take_pending()
    if not tail:
        return
    win._append_rx_group(win._format_rx(tail), time.monotonic(), True)
    win._scroll_rx_bottom()

def on_received(win: MainWindow, ts: float, data: bytes):
    "on received"
    win._check_auto_reply(data)
    win.rx_bytes += len(data)
    win.update_counts()

    mode = win.split_combo.currentIndex()
    if mode == SPLIT_HEADER:
        win._append_header_split(data, ts)
        win._last_ts = ts
        return

    if mode >= SPLIT_FIXED:
        # B3: byte-stream modes cut frames from the bytes themselves, not timers
        splitter = _byte_splitter(win)
        splitter.configure(**win._split_byte_params())
        for frame in splitter.feed(data):
            if frame:
                win._append_rx_group(win._format_rx(frame), ts, True)
        win._scroll_rx_bottom()
        win._last_ts = ts
        return

    # U57: collect chunks first; the line break is decided when the group settles
    win._frames.set_threshold(win._split_threshold_ms())
    win._frames.feed(ts, data)
    if not win._frame_timer.isActive():
        win._frame_timer.start(int(win._frames.settle_ms))

def flush_rx_frames(win: MainWindow) -> None:
    "flush rx frames"
    """Emit assembled frames: USB fragments merged, real gaps split (U57)."""
    now = time.monotonic()
    while True:
        got = win._frames.take(now)
        if got is None:
            break
        new_line, ts, data = got
        win._append_rx_group(win._format_rx(data), ts, new_line)
    win._last_ts = now
    win._scroll_rx_bottom()          # U43
    if win._frames.has_pending():
        win._frame_timer.start(int(win._frames.settle_ms))

RX_STORE_MAX = 40000   # U163b: fragments kept so the RX/TX view filter can rebuild


def _rx_store(win: MainWindow) -> list:
    """The bounded (text, kind) stream that backs view filtering (U163b)."""
    store = getattr(win, "_rx_store", None)
    if store is None:
        store = []
        win._rx_store = store
    return store


def _insert_rx_fragment(win: MainWindow, text: str, kind: int) -> None:
    """Insert one fragment with the colour its class calls for (U62/U163b)."""
    cursor = win.rx_view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    fmt = QTextCharFormat()
    if kind_is_meta(kind):
        fmt.setForeground(QColor(theme.meta_color()))
    elif kind_is_tx(kind):
        fmt.setForeground(QColor(theme.tx_color()))
    else:
        fmt.setForeground(QColor(theme.text_color()))
    try:
        fmt.setProperty(QTextFormat.Property.UserProperty, kind)
    except (AttributeError, TypeError):
        pass
    cursor.insertText(text, fmt)


def _frag_visible(win: MainWindow, kind: int) -> bool:
    """Whether a fragment survives the active view filter (U163b/U176)."""
    return fragment_visible(kind, getattr(win, "_rx_filter", 0))


def emit_rx_text(win: MainWindow, text: str, tx: bool = False, meta: bool = False, log: bool = True) -> None:
    "emit rx text"
    """Insert text into the receive pane and mirror it to the log.

    kind: RX/TX payload or RX/TX timestamp marker (see app.display.frag_kind).
    The kind is stored on the format so a theme switch can recolour it correctly.

    While the display is paused (U160) the text is buffered instead of inserted,
    so it can be replayed when the user resumes; the log keeps receiving it.
    """
    kind = frag_kind(tx, meta)
    if getattr(win, "_rx_paused", False):
        buf = getattr(win, "_rx_pause_buf", None)
        if buf is None:
            buf = []
            win._rx_pause_buf = buf
        if len(buf) < 20000:
            buf.append((text, kind))
        if log:
            win._log_append(text)
        return
    store = _rx_store(win)
    store.append((text, kind))
    if len(store) > RX_STORE_MAX:
        del store[:len(store) - RX_STORE_MAX]
    if text == "\n" or kind:
        win._cur_line_tx = kind_is_tx(kind)
    else:
        win._cur_line_tx = False
    if _frag_visible(win, kind):
        _insert_rx_fragment(win, text, kind)
    if log:
        win._log_append(text)


def rebuild_rx_view(win: MainWindow) -> None:
    "rebuild rx view"
    """Re-render the pane from the fragment store under the active filter (U163b)."""
    if not hasattr(win, "rx_view"):
        return
    store = _rx_store(win)
    lines = [[]]
    for text, kind in store:
        if text == "\n":
            lines.append([(text, kind)])
        else:
            lines[-1].append((text, kind))
    mode = getattr(win, "_rx_filter", 0)
    win.rx_view.clear()
    for line in lines:
        tx_line = any(kind_is_tx(k) for _, k in line)
        if (mode == 1 and tx_line) or (mode == 2 and not tx_line):
            continue
        for text, kind in line:
            _insert_rx_fragment(win, text, kind)


def on_filter_changed(win: MainWindow, index: int) -> None:
    "on filter changed"
    """Switch the RX/TX view filter and rebuild the pane (U163b)."""
    win._rx_filter = int(index)
    rebuild_rx_view(win)

def append_rx_group(win: MainWindow, text: str, ts: float, new_line: bool) -> None:
    "append rx group"
    """Emit one RX group without gluing it onto the previous text (U59).

    - new line requested, or the current line belongs to a TX echo -> open a
      fresh, timestamped line;
    - otherwise append to the running RX line, with a separator in HEX modes
      (previously '39 30' + '31 32' collapsed into '39 3031 32').
    """
    if win.rx_fmt_combo.currentIndex() == RX_COLUMN_HEX:
        new_line = True      # U163c: every hexdump row set starts on its own line
    has_text = win.rx_view.document().characterCount() > 1
    if new_line or win._line_is_tx:
        if has_text:
            win._emit_rx_text("\n")
        win._emit_rx_text(win._ts_prefix(ts) + MARK_RX, meta=True)
    elif has_text:
        separator = win._rx_separator()
        if separator:
            win._emit_rx_text(separator)
    win._emit_rx_text(text)
    win._line_is_tx = False
    if not win._cap_warned and win.rx_view.blockCount() >= RECEIVE_MAX_LINES - 5:
        win._cap_warned = True          # U45: one clear warning, not per line
        win._notify(tr("rx.cap", n=RECEIVE_MAX_LINES), "warn", ms=8000)

def append_header_split(win: MainWindow, data: bytes, ts: float):
    "append header split"
    """Split raw bytes by frame header (e.g. 'fw:'), one line per frame.

    Splitting on the byte level works regardless of HEX/ASCII display mode.
    Leading bytes before the first header belong to the current line.
    """
    header = win.header_edit.text().strip()
    header_b = header.encode("utf-8", errors="replace") if header else b""
    if not header_b:
        return
    segs = data.split(header_b)
    for i, seg in enumerate(segs):
        if i == 0:
            # bytes before the first header: continue the current frame (U59)
            if seg:
                win._append_rx_group(win._format_rx(seg), ts, False)
            continue
        if not seg:
            continue  # adjacent headers, frame with empty body
        win._append_rx_group(win._format_rx(header_b + seg), ts, True)

    win._scroll_rx_bottom()          # U43

def recolor_rx_view(win: MainWindow) -> None:
    "recolor rx view"
    """Re-apply theme colours to already-displayed lines (U27).

    Text inserted under one theme keeps the colour it was given, which turns
    black-on-dark (or worse) after a theme switch, so re-colour the document.
    """
    doc = win.rx_view.document()
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
                if kind is not None and kind_is_meta(kind):
                    colour = theme.meta_color()
                elif (kind is not None and kind_is_tx(kind)) or (kind is None and fallback_tx):
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

def snapshot_rx_fragments(win: MainWindow) -> list:
    "snapshot rx fragments"
    """Capture (text, kind) for every fragment so clearing can be undone (U42).

    QPlainTextEdit refuses a cloned document (its layout class differs), so the
    pane is rebuilt from the fragments with our own emitter instead.
    """
    out = []
    block = win.rx_view.document().begin()
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

def rx_tooltip(win: MainWindow, obj: QObject, event) -> bool:
    "rx tooltip"
    """Show the whole line when hovering a very long receive line (U129-A4).

    Returns True when the tooltip was ours, so the window's event filter stops
    there; the displayed text is never altered, so copy keeps the full data.
    """
    if event.type() != QEvent.Type.ToolTip or obj is not win.rx_view.viewport():
        return False
    try:
        cursor = win.rx_view.cursorForPosition(event.pos())
        tip = long_line_tooltip(cursor.block().text())
        if tip is None:
            return False
        QToolTip.showText(event.globalPos(), tip, win.rx_view)
    except (AttributeError, TypeError):
        return False
    return True

def on_clear(win: MainWindow):
    "on clear"
    """Clear the display only (U169); the session counters keep counting.

    (The old docstring said "and the counters"; the code never zeroed them, so the
    label was wrong - the counter actions now live in the split button's menu.)
    """
    has_text = win.rx_view.document().characterCount() > 1
    offer_undo = has_text and win.rx_view.blockCount() <= CLEAR_UNDO_MAX_LINES
    if offer_undo:
        win._cleared_fragments = win._snapshot_rx_fragments()   # keeps colours
        win._cleared_state = (win._line_is_tx, win.rx_bytes,
                               win.tx_bytes, win._sent_count)
        win._undo_kind = "clear"
        win._undo_btn.setText(tr("undo.label"))
        win._undo_btn.show()
        win._undo_timer.start(5000)
    win._frame_timer.stop()
    win._frames.reset()
    _bsplit = getattr(win, "_byte_splitter", None)   # B3: the byte tail goes too
    if _bsplit is not None:
        _bsplit.reset()
    win._last_ts = None
    win._rx_pause_buf = []      # U160: a pause buffer must not survive a clear
    win._rx_store = []          # U163b: the filter store goes with the display
    win._cur_line_tx = False
    win._col_off = 0            # U163c: the hexdump offset starts over with the pane
    win.rx_view.clear()
    win._line_is_tx = False
    win._cap_warned = False
    win.update_counts()
    if offer_undo:
        win._notify(tr("rx.cleared"), "warn", ms=5000)


def on_reset_counters(win: MainWindow) -> None:
    "on reset counters"
    """Zero the RX/TX byte and send counters, leaving the display alone (N2/U163)."""
    win.rx_bytes = 0
    win.tx_bytes = 0
    win._sent_count = 0
    win.update_counts()
    win._notify(tr("rx.counters_reset"), "info", ms=3000)


def on_clear_and_counters(win: MainWindow) -> None:
    "on clear and counters"
    """U169: clear the pane and zero the counters in one step (menu item).

    on_clear runs first, so the undo snapshot still holds the pre-clear counters
    and undoing brings both the text and the numbers back.
    """
    on_clear(win)
    win.rx_bytes = 0
    win.tx_bytes = 0
    win._sent_count = 0
    win.update_counts()


def resume_rx_display(win: MainWindow) -> None:
    """Replay the buffered lines after the user resumes display (U160)."""
    win._rx_paused = False   # replay must go to the view, not back into the buffer
    buf = getattr(win, "_rx_pause_buf", None) or []
    win._rx_pause_buf = []
    for text, kind in buf:
        win._emit_rx_text(text, tx=kind_is_tx(kind), meta=kind_is_meta(kind), log=False)
    win._scroll_rx_bottom()
    win._notify(tr("rx.pause.resumed"), "info", ms=3000)
