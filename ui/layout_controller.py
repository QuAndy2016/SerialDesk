"""Layout controller: measured minimum widths, control-row audit and the size fitting that keeps the window honest."""
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
    QStackedWidget,
    QWidgetAction,
    QVBoxLayout,
    QWidget,
)
from app.framing import DEFAULT_SETTLE_MS, FrameAssembler
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
from ui.receive_controller import append_header_split, append_rx_group, emit_rx_text, flush_rx_frames, on_clear, on_received, recolor_rx_view, snapshot_rx_fragments
from ui.send_controller import abort_file_send, apply_checksum, clear_history, finish_file_send, flush_history_save, on_history_fill, on_quick_send, on_send, on_send_file, prune_history_meta, recall_history, remember_send, remove_history_entry, schedule_history_save, send_file_chunk, show_history, update_history_button, update_payload_size
from ui.connection_controller import ensure_port, notify, on_opened_changed, on_reconnect_toggled, on_worker_error, poll_signals, recolor_status_light, refresh_ports, signals_html, toggle_open, update_port_tooltip
from ui.params_controller import baud_value, check_baud, check_hex_input, encoding, format_rx, newline_bytes, on_header_changed, on_split_mode_changed, on_tx_fmt_changed, persist_newline, refresh_tx_settings_chip, serial_params, split_threshold_ms, ts_prefix, update_input_placeholder
from ui.regions import (BAUDRATES, DATA_FIRST_H, DATA_FIRST_V,
                        RECEIVE_MAX_LINES, SPLIT_AUTO, SPLIT_HEADER,
                        SPLIT_MANUAL, _fixed_row, build_connection_row,
                        build_data_panes, build_send_group, build_status_bar)
from app.i18n import hex_error_message, tr
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLayout
    from ui.main_window import MainWindow
LEGACY_SPLIT_DEFAULTS = {
    "v_split_sizes": ([420, 260], DATA_FIRST_V),
    "split_sizes": ([820, 340], DATA_FIRST_H),
}
QUICK_PANEL_MIN_W = 332   # the quick-send rows need this (U69)
TX_PANE_MIN_H = 120       # 2026-10-02: the send pane is ~2 button rows; data gets the rest
def fit_minimum_width(win: MainWindow) -> None:
    "fit minimum width"
    try:
        need = win._tx_group.layout().minimumSize().height() + 10
        win._tx_group.setMinimumHeight(max(120, need))
    except (AttributeError, TypeError):
        pass
    """Window floor = the connection bar (spans the window) or both panes side by side.

    Derived at start-up and after a language switch, because the needed width
    follows the actual font, DPI scale and translation - a hard-coded value is
    only right for the machine it was measured on.
    """
    win._lock_control_widths()          # U101: before measuring, pin the labels
    # let the layouts recompute with the current font and translation first, or
    # measurements taken right after a language switch use the old label widths
    for lay in win._control_rows():
        lay.activate()
    central = win.centralWidget().layout()
    if central is not None:
        central.activate()
    win._fit_pane_minimums()
    # U101: the left column (both panes, stacked vertically) must be able to hold
    # its own rows, or dragging the horizontal divider clips them. A vertical
    # splitter's width floor is the widest pane, not the sum - and neither pane's
    # cached hint is reliable at this point, so take the measured floors directly.
    pane_need = max(win._rx_group.minimumWidth(), win._tx_group.minimumWidth())
    pad = max(0, win._left_column.width() - win._v_splitter.width())
    win._left_column.setMinimumWidth(max(360, pane_need + pad))
    rows = win._control_rows()
    connect_need = win._row_need(rows[0]) if rows else 0
    # U120: a folded panel costs nothing now - the rail only exists on hover
    panel_min = (0 if win.quick_panel.is_folded() else
                 max(QUICK_PANEL_MIN_W, win.quick_panel.minimumSizeHint().width()))
    pair_need = (win._rx_group.minimumWidth() + panel_min + win._splitter.handleWidth()
                 + max(0, win.width() - win._splitter.width()))
    win.setMinimumWidth(max(980, connect_need, pair_need))

def fit_pane_minimums(win: MainWindow) -> None:
    "fit pane minimums"
    """Hard width floor per pane so a divider drag can never squeeze its rows (U81).

    Pushing the constraint onto the panes (instead of only computing one global
    window minimum) means every splitter position stays safe: the splitter cannot
    compress a pane below the width its widest control row actually needs.
    """
    for group in (win._rx_group, win._tx_group):
        lay = group.layout()
        if lay is None:
            continue
        widest, holder = 0, None
        for i in range(lay.count()):
            wid = lay.itemAt(i).widget()
            if wid is not None and wid.layout() is not None:
                need = win._row_need(wid.layout())
                if need > widest:
                    widest, holder = need, wid
        if holder is None:
            continue
        pad = max(0, group.width() - holder.width())   # group frame + margins
        group.setMinimumWidth(widest + pad)

def lock_control_widths(win: MainWindow) -> None:
    "lock control widths"
    """Text controls never shrink below their label (U101).

    Qt already refuses to go under minimumSizeHint for most widgets, but an
    explicit minimum or a nested layout can still squeeze one; locking the width to
    the current sizeHint - recomputed on every language switch - keeps every label
    readable at every splitter position without ever touching the font.
    """
    controls = (win._port_lbl, win._baud_lbl, win.refresh_btn, win.open_btn,
                win._settings_btn, win._crc_lbl, win._repeat_lbl,
                win.tx_fmt_combo, win.checksum_combo,
                win.ts_check, win.autoscroll_check,
                win.nl_combo, win.escape_check,
                win.save_log_btn, win.save_log_as_btn, win.clear_btn,
                win.send_file_btn, win.repeat_btn, win.send_btn, win.history_btn)
    for wdg in controls:
        if wdg is None:
            continue
        wdg.setMinimumWidth(max(wdg.minimumWidth(), wdg.sizeHint().width()))
        if isinstance(wdg, (QPushButton, QCheckBox)):
            # U101: height stays put as well - a button must not grow with the row
            wdg.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    # U189 (Andy): the More menu is a plain QToolButton, whose own sizeHint is a few
    # pixels taller than the QPushButtons beside it; pin it to the row's button height.
    more = getattr(win, "more_btn", None)
    ref = getattr(win, "save_log_btn", None)
    if more is not None and ref is not None:
        more.setFixedHeight(ref.sizeHint().height())
    # Standard clause 16b / WCAG 2.5.8: a pointer target is at least 24x24 px. Row-level
    # controls (quick-send buttons and ticks, option chips) came out 18-23 px tall. Raise
    # the *hit* height, not the glyph: pad the control so the visual density is unchanged.
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit, QSpinBox
    for wdg in win.findChildren(QAbstractButton):
        if wdg.isVisible():
            wdg.setMinimumHeight(max(24, wdg.minimumHeight()))
    for cls in (QComboBox, QSpinBox, QLineEdit):
        for wdg in win.findChildren(cls):
            # the internal editor of a spin box / combo is not itself the target
            if isinstance(wdg.parentWidget(), (QComboBox, QSpinBox)):
                continue
            if wdg.isVisible():
                # 2026-10-03: inputs keep a 28 px floor - 24 px squeezes a spin box's arrows
                # until the number is clipped and the steppers stop responding (Andy).
                floor = 28 if isinstance(wdg, (QSpinBox, QComboBox)) else 24
                wdg.setMinimumHeight(max(floor, wdg.minimumHeight()))
                if 24 < wdg.height() < 28 and floor == 24:
                    wdg.setFixedHeight(24)

def fit_tx_edit_height(win: MainWindow) -> None:
    "fit tx edit height"
    """U111/U119/U121: the input owns the send pane's vertical space.

    At the default pane height that is one line; when the user drags the divider,
    when the window grows, or when HEX mode hides the line-ending row, the freed
    pixels go to the input box instead of turning into blank space.
    """
    if getattr(win, "_fitting_tx", False):
        return
    chip = getattr(win, "tx_settings_btn", None)
    actions = getattr(win, "send_btn", None)
    if chip is None or actions is None:
        return          # still building the send group
    win._fitting_tx = True
    try:
        fm = win.tx_edit.fontMetrics()
        line = max(1, fm.lineSpacing())
        chrome = 2 * win.tx_edit.frameWidth() + 10
        # the tallest fixed row beside the input (options row / action column);
        # neither depends on the input's own height, so this cannot oscillate
        # measure the bottom of the fixed rows themselves - the action column's
        # container stretches, so its own geometry would report the row's bottom
        # U129: the options row sits above the input, the action toolbar below it
        # U192: send_file_btn lives inside the settings chip now (its own window), so
        # the probes stay on widgets that are actually in this row.
        above_probes = [win.tx_settings_btn, win.inc_chip, win.nl_combo]
        bottoms = [w.mapTo(win._tx_group, w.rect().bottomLeft()).y()
                   for w in above_probes if w.isVisible()]
        above = (max(bottoms) if bottoms else 0) + 6
        # 2026-10-02 (Andy): the actions sit BESIDE the input now (a column on the
        # right), so nothing sits below it - only the caption above the box and the
        # group margins come off the height.
        cap_lbl = getattr(win, "_tx_content_lbl", None)
        caption = (cap_lbl.sizeHint().height() + 2) if cap_lbl is not None \
            and cap_lbl.isVisible() else 0
        avail = win._tx_group.height() - above - caption - 8
        cap = 26 * line + chrome
        # 2026-10-02 (Andy): the pane is compact, so the box must never demand more
        # height than its row has. A minimum derived from the pane's current height goes
        # stale the moment the divider moves (the audit's squeezed state caught a 7 px
        # overhang). The floor is therefore constant - one line - and the box fills the
        # rest of its row through the layout (Expanding/Ignored policy, stretch 1).
        _ = min(avail, cap)      # kept for the size hint bookkeeping below
        win.tx_edit.setMinimumHeight(int(line + chrome))
    finally:
        win._fitting_tx = False

def give_data_area_the_room(win: MainWindow) -> None:
    "give data area the room"
    """First run: hand every spare pixel to the receive pane (U79).

    The send pane and the quick-send column start at their minimum sizes, so
    the data display area gets the maximum room by default. Once the user
    drags a divider, their proportions are stored and honoured instead.
    """
    if win._custom_split_sizes:
        return
    h = win._v_splitter.height()
    w = win._splitter.width()
    if h > TX_PANE_MIN_H + 40:
        win._v_splitter.setSizes([h - TX_PANE_MIN_H, TX_PANE_MIN_H])
    if w > QUICK_PANEL_MIN_W + 80:
        win._splitter.setSizes([w - QUICK_PANEL_MIN_W, QUICK_PANEL_MIN_W])

def control_rows(win: MainWindow) -> list:
    "control rows"
    """Every horizontal control row whose width must fit (U81)."""
    rows = []
    central = win.centralWidget()
    top = central.layout().itemAt(0)
    if top is not None and top.layout() is not None:
        rows.append(top.layout())
    for group in (win._rx_group, win._tx_group):
        lay = group.layout()
        if lay is None:
            continue
        for i in range(lay.count()):
            wid = lay.itemAt(i).widget()
            if wid is not None and wid.layout() is not None:
                rows.append(wid.layout())
    return rows

def row_need(win: MainWindow, layout: QLayout) -> int:
    "row need"
    """Minimum width one row needs.

    Qt's own layout minimum accounts for the items' minimums, the layout's
    internal spacing and its contents margins; adding them up by hand missed a
    few pixels per combo box and left rows slightly too narrow (U81).
    """
    return int(layout.minimumSize().width())

def widest_row(win: MainWindow) -> tuple:
    "widest row"
    """(need, row widget) of the widest control row (U81)."""
    best = (0, None)
    for lay in win._control_rows():
        wid = lay.parentWidget()
        need = win._row_need(lay)
        if need > best[0]:
            best = (need, wid)
    return best

def saved_sizes(win: MainWindow, key: str, default: list) -> list:
    "saved sizes"
    """Restore a persisted splitter size list, falling back to the default (U35)."""
    value = load_config().get(key)
    legacy, upgraded = LEGACY_SPLIT_DEFAULTS.get(key, (None, default))
    if isinstance(value, list) and len(value) == len(default):
        try:
            sizes = [int(v) for v in value]
        except (TypeError, ValueError):
            return list(default)
        # a stored list that is exactly the old default was never dragged by
        # the user, so upgrading it to the new default is safe (U79)
        if legacy is not None and sizes == list(legacy):
            return list(upgraded)
        return sizes
    return list(default)

def fit_settings_btn(win: MainWindow) -> None:
    "fit settings btn"
    """Size the Settings control (U188: icon-only, so it is the gear plus padding)."""
    win._settings_btn.setMinimumWidth(max(30, win._settings_btn.iconSize().width() + 16))
    win._settings_btn.setMinimumHeight(28)
