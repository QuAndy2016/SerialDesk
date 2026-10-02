"""Window regions (refactor step 6 of the main-window split).

Each builder owns one region and receives the window as `win`, so the window
keeps the wiring while construction lives here. The helpers and layout
constants they need moved along and are re-exported for main_window.
"""
from __future__ import annotations


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
from ui.port_delegate import PORT_FULL_ROLE, PortItemDelegate
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.autosave_dialog import AutoSaveDialog
from ui.history_dialog import HistoryDialog
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from app.i18n import hex_error_message, tr
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLayout
    from ui.main_window import MainWindow

BAUDRATES = [
    110, 330, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400,
    56000, 57600, 115200, 128000, 230400, 256000, 460800, 500000,
    512000, 600000, 750000, 921600, 1000000, 1500000, 2000000, 3000000,
]
DATA_FIRST_H = [880, 332]
DATA_FIRST_V = [560, 170]
RECEIVE_MAX_LINES = 20000   # receive-pane display cap (U45)
SPLIT_AUTO = 1
SPLIT_HEADER = 3
SPLIT_MANUAL = 2
SPLIT_FIXED = 4        # B3: byte-stream split modes (params in the U50 slot)
SPLIT_DELIMITED = 5
SPLIT_TLV = 6
def _fixed_row(layout: QLayout) -> QWidget:
    """Wrap a control row so it keeps its natural height (U70).

    A nested layout handed straight to a vertical box absorbs spare space and
    centres its widgets, which made the split row drift downwards whenever the
    receive group grew. A holder with a Fixed vertical policy pins it to the top.
    """
    holder = QWidget()
    layout.setContentsMargins(0, 2, 0, 2)   # U92: drop Qt's default 9 px top/bottom, which
    holder.setLayout(layout)                #      made every control row 18 px taller than
    holder.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return holder                            #      the widgets inside it needed

def build_connection_row(win: MainWindow, root: QWidget) -> None:
    """Connection row: port, baud, open/close, receive format and the panel toggle."""
    bar = QHBoxLayout()
    _build_port_controls(win, bar)
    _build_receive_format_controls(win, bar)
    root.addLayout(bar)
    _mount_parameter_dialog(win)


def _build_port_controls(win: MainWindow, bar: QHBoxLayout) -> None:
    """Port label, port list, refresh, baud rate and the open/close button."""
    win._port_lbl = QLabel(tr("port.label"))     # U100: these two were English-only
    bar.addWidget(win._port_lbl)
    win.port_combo = QComboBox()
    win.port_combo.setMinimumWidth(100)   # U172: the closed box only shows "COMx"
    win.port_combo.view().setItemDelegate(PortItemDelegate(win.port_combo.view()))
    bar.addWidget(win.port_combo)

    win.refresh_btn = QPushButton(tr("port.refresh"))
    win.refresh_btn.clicked.connect(win.refresh_ports)
    bar.addWidget(win.refresh_btn)

    win._baud_lbl = QLabel(tr("baud.label"))
    bar.addWidget(win._baud_lbl)
    win.baud_combo = QComboBox()
    win.baud_combo.addItems([str(b) for b in BAUDRATES])
    win.baud_combo.setEditable(True)
    win.baud_combo.setCurrentText("115200")
    win.baud_combo.setToolTip(tr("baud.tip"))
    win.baud_combo.setMinimumWidth(112)          # U49/U78: 1000000/3000000 still fit
    win.baud_combo.setMinimumContentsLength(7)
    win.baud_combo.lineEdit().textChanged.connect(win._check_baud)
    bar.addWidget(win.baud_combo)

    win.open_btn = QPushButton(tr("port.open"))
    win.open_btn.clicked.connect(win.toggle_open)
    win.open_btn.setToolTip(tr("sc.open.tip"))
    bar.addWidget(win.open_btn)


def _build_receive_format_controls(win: MainWindow, bar: QHBoxLayout) -> None:
    """Receive format, the wire-format summary, the divider and the two icon buttons."""
    bar.addSpacing(12)
    win._rx_fmt_lbl = QLabel(tr("rxfmt.label"))
    bar.addWidget(win._rx_fmt_lbl)
    win.rx_fmt_combo = QComboBox()
    win.rx_fmt_combo.addItems(["ASCII", "HEX", "HEX+ASCII", "HEX cols"])   # U163c: column hexdump
    win.rx_fmt_combo.setCurrentIndex(RX_HEX)
    win.rx_fmt_combo.setToolTip(tr("rxfmt.tip"))
    bar.addWidget(win.rx_fmt_combo)

    bar.addSpacing(12)
    # U84 (revised): the wire-format summary and its dialog opener are one compact
    # control - label plus button cost ~245 px and no label needed shortening.
    win.params_summary = QToolButton()
    win.params_summary.setObjectName("paramsBtn")
    win.params_summary.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    win.params_summary.setToolTip(tr("portset.tip"))
    win.params_summary.clicked.connect(win._show_port_settings)
    win.port_set_btn = win.params_summary   # the open/close lock hint uses this
    bar.addWidget(win.params_summary)

    bar.addSpacing(10)
    conn_div = QFrame()                     # U110: app-level entry, set apart
    conn_div.setObjectName("connDivider")
    conn_div.setFrameShape(QFrame.Shape.VLine)
    conn_div.setFixedWidth(1)
    bar.addWidget(conn_div)
    bar.addWidget(win._settings_btn)   # U72: same line as Port / Baud / Open
    # U120: folding used to leave a 28 px rail on screen. The toggle is a fixed,
    # always-visible control next to Settings now (spatial mapping: it sits on the
    # same edge as the panel it drives), and the rail only appears on hover.
    win._panel_btn = QToolButton()
    win._panel_btn.setObjectName("panelToggle")
    win._panel_btn.setCheckable(True)
    win._panel_btn.setChecked(True)
    win._panel_btn.setMinimumSize(32, 32)
    win._panel_btn.setToolTip(tr("menu.quick_panel.tip"))
    win._panel_btn.clicked.connect(
        lambda: win._on_quick_panel_collapsed(not win._panel_btn.isChecked()))
    bar.addWidget(win._panel_btn)
    win._sync_panel_btn(False)   # U161: initial icon so the button is not blank on first open
    # U114-D4: one control height across the connection row
    for _w in (win.port_combo, win.refresh_btn, win.baud_combo, win.open_btn,
               win.rx_fmt_combo, win.params_summary, win._settings_btn):
        _w.setMinimumHeight(32)

    bar.addStretch(1)


def _mount_parameter_dialog(win: MainWindow) -> None:
    """U35-P3: the parameter widgets now live in their own dialog.

    The main window keeps the same attribute names so the rest of the code needs
    no change.
    """
    win._port_dlg = PortSettingsDialog(win)
    for _name in ("dbits_combo", "parity_combo", "stopbits_combo", "flow_combo",
                  "encoding_combo", "dtr_check", "rts_check", "sig_lbl",
                  "_dbit_lbl", "_parity_lbl", "_stopbit_lbl", "_flow_lbl",
                  "_enc_lbl", "_sig_out_lbl", "_sig_in_lbl"):
        setattr(win, _name, getattr(win._port_dlg, _name))
    win.dtr_check.toggled.connect(win.worker.set_dtr)
    win.rts_check.toggled.connect(win.worker.set_rts)
    win._param_combos = [win.dbits_combo, win.parity_combo,
                         win.stopbits_combo, win.flow_combo]
    for combo in win._param_combos:
        combo.setToolTip(tr("params.tip"))
        combo.currentIndexChanged.connect(win._update_params_summary)
    win.encoding_combo.currentIndexChanged.connect(win._update_params_summary)
    win._update_params_summary()

def build_status_bar(win: MainWindow) -> None:
    """Status bar: connection light, counters and the undo affordance."""
    """Status bar: connection light, counters and the undo affordance."""
    # status bar with connection indicator -------------------------------
    for _sig in (win.tx_edit.textChanged,
                 win.tx_fmt_combo.currentIndexChanged,
                 win.checksum_combo.currentIndexChanged,
                 win.nl_combo.currentIndexChanged,
                 win.escape_check.toggled,
                 win.encoding_combo.currentIndexChanged):
        _sig.connect(win._update_payload_size)      # U74: live payload size
    win._update_payload_size()

    win.status_light = QLabel(tr("status.disconnected"))
    win.status_light.setStyleSheet(
        f"color: {theme.status_colors()['idle']}; font-weight: bold; padding-right: 8px;")
    win.statusBar().addPermanentWidget(win.status_light)
    # U58: 3 s undo affordance for a deleted quick-send row
    win._undo_payload: dict | None = None
    win._undo_kind = ""
    win._cleared_fragments: list | None = None
    win._cleared_state = None
    win._undo_timer = QTimer(win)
    win._undo_timer.setSingleShot(True)
    win._undo_timer.timeout.connect(win._clear_undo)
    win._undo_btn = QPushButton(tr("qs.undo"))
    win._undo_btn.setToolTip(tr("qs.deleted"))
    win._undo_btn.hide()
    win._undo_btn.clicked.connect(win._undo_delete)
    win.statusBar().addPermanentWidget(win._undo_btn)
    win._notify(tr("status.idle"))

def build_send_group(win: MainWindow) -> None:
    """Send group: payload options, the input box and the action toolbar."""
    win._tx_group = QGroupBox(tr("group.tx"))
    tx_layout = QVBoxLayout(win._tx_group)
    tx_layout.setContentsMargins(8, 2, 8, 6)
    tx_layout.setSpacing(4)

    # U74: payload options above, the input owning the middle with the primary
    # Send button beside it, then the repeat controls and the file row. The old
    # layout squeezed the input to ~134 px (a control column ate ~83% of the
    # width) and capped its height at 90 px, so the send area looked like a toy.
    _build_payload_options(win, tx_layout)
    tx_row = _build_input_row(win)
    actions = _build_action_toolbar(win)
    act_row = QHBoxLayout()
    act_row.setContentsMargins(0, 2, 0, 0)
    act_row.setSpacing(10)
    act_row.addWidget(actions)
    act_row.addStretch(1)
    act_row.addWidget(win.tx_size_lbl)     # U121: next to the actions it describes
    tx_layout.addLayout(tx_row, 1)          # U129: the input owns the middle
    tx_layout.addLayout(act_row)


def _build_payload_options(win: MainWindow, tx_layout: QVBoxLayout) -> None:
    """Options row: the format/checksum chip, text decorations and file sending."""
    mod_group = _build_text_decorations(win)
    tx_fmt_row = QHBoxLayout()
    _build_format_chip(win, tx_fmt_row)
    _build_file_send(win, tx_fmt_row)
    tx_fmt_row.addStretch(1)
    tx_fmt_row.addWidget(mod_group)
    tx_layout.addWidget(_fixed_row(tx_fmt_row))
    win.tx_fmt_combo.currentIndexChanged.connect(win._on_tx_fmt_changed)
    win.tx_fmt_combo.currentIndexChanged.connect(win._check_hex_input)
    win._on_tx_fmt_changed(win.tx_fmt_combo.currentIndex())


def _build_format_chip(win: MainWindow, tx_fmt_row: QHBoxLayout) -> None:
    """U121: one "HEX / none" chip opening a popup, instead of two labelled combos."""
    win.tx_settings_btn = QToolButton()
    win.tx_settings_btn.setObjectName("qsChip")
    win.tx_settings_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    win.tx_settings_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    win.tx_settings_btn.setToolTip(tr("tx.settings.tip"))
    _fmt_holder = QWidget()
    _fh = QHBoxLayout(_fmt_holder)
    _fh.setContentsMargins(8, 6, 8, 6)
    _fh.setSpacing(6)
    win._tx_fmt_lbl = QLabel(tr("txfmt.label"))
    _fh.addWidget(win._tx_fmt_lbl)
    win.tx_fmt_combo = QComboBox()
    win.tx_fmt_combo.addItems(["HEX", "ASCII"])
    win.tx_fmt_combo.setToolTip(tr("txfmt.tip"))
    _fh.addWidget(win.tx_fmt_combo)
    win._crc_lbl = QLabel(tr("crc.label"))
    _fh.addWidget(win._crc_lbl)
    win.checksum_combo = QComboBox()
    win.checksum_combo.addItems([tr("crc.none"), "CRC16-Modbus", "CRC16-CCITT", "CRC32", "SUM8"])
    win.checksum_combo.setToolTip(tr("crc.tip"))
    _fh.addWidget(win.checksum_combo)
    _fmt_menu = QMenu(win.tx_settings_btn)
    _fmt_action = QWidgetAction(_fmt_menu)
    _fmt_action.setDefaultWidget(_fmt_holder)
    _fmt_menu.addAction(_fmt_action)
    win.tx_settings_btn.setMenu(_fmt_menu)
    tx_fmt_row.addWidget(win.tx_settings_btn)
    win.tx_fmt_combo.currentIndexChanged.connect(win._refresh_tx_settings_chip)
    win.checksum_combo.currentIndexChanged.connect(win._refresh_tx_settings_chip)
    win._refresh_tx_settings_chip()


def _build_text_decorations(win: MainWindow) -> QWidget:
    """U98/U112: line ending and escape, hidden in HEX mode, in one group widget."""
    group = QWidget()
    win._tx_mod_group = group
    mod_row = QHBoxLayout(group)
    mod_row.setContentsMargins(0, 0, 0, 0)
    mod_row.setSpacing(10)
    # U112: the old "append CRLF" checkbox spoke escape notation. It is now a picker
    # over the actual line endings, named the way the rest of the field names them.
    win._nl_lbl = QLabel(tr("tx.newline.label"))
    mod_row.addWidget(win._nl_lbl)
    win.nl_combo = QComboBox()
    win.nl_combo.addItems([tr("tx.nl.none"), tr("tx.nl.cr"), tr("tx.nl.lf"), tr("tx.nl.crlf")])
    _saved_nl = load_config().get("newline")
    if _saved_nl is None:                      # migrate the old boolean config key
        _saved_nl = "crlf" if load_config().get("crlf") else "none"
    win.nl_combo.setCurrentIndex({"none": 0, "cr": 1, "lf": 2, "crlf": 3}.get(str(_saved_nl), 0))
    win.nl_combo.setToolTip(tr("tx.newline.tip"))
    win.nl_combo.currentIndexChanged.connect(win._persist_newline)
    mod_row.addWidget(win.nl_combo)
    win.escape_check = QCheckBox(tr("tx.escape"))
    win.escape_check.setChecked(True)
    win.escape_check.setToolTip(tr("tx.escape.tip"))
    mod_row.addWidget(win.escape_check)
    # U165: the send box can soft-wrap too (its own switch, default off so a long
    # HEX string still shows as a single line, which is what U130 asked for).
    win.tx_wrap_check = QCheckBox(tr("tx.wrap"))
    win.tx_wrap_check.setChecked(bool(load_config().get("tx_wrap_on", False)))
    win.tx_wrap_check.setToolTip(tr("tx.wrap.tip"))
    win.tx_wrap_check.toggled.connect(win._on_tx_wrap_toggled)
    mod_row.addWidget(win.tx_wrap_check)
    return group


def _build_file_send(win: MainWindow, tx_fmt_row: QHBoxLayout) -> None:
    """U99: file sending moved up beside the checksum box; U121 payload hint."""
    tx_fmt_row.addSpacing(18)
    win.send_file_btn = QPushButton(tr("btn.send_file"))
    win.send_file_btn.setToolTip(tr("btn.send_file"))
    win.send_file_btn.clicked.connect(win.on_send_file)
    tx_fmt_row.addWidget(win.send_file_btn)
    win.file_progress = QProgressBar()
    win.file_progress.setRange(0, 100)
    win.file_progress.setValue(0)
    win.file_progress.setMaximumWidth(120)
    win.file_progress.hide()          # U108: idle progress bar read as a divider
    tx_fmt_row.addWidget(win.file_progress)
    win.file_info_lbl = QLabel("")
    tx_fmt_row.addWidget(win.file_info_lbl, 1)
    # U121: the payload hint sits under the input it describes instead of the far
    # end of the options row, which was ~400 px away from the text it counts.
    win.tx_size_lbl = QLabel("")
    win.tx_size_lbl.setToolTip(tr("tx.payload.tip"))
    # the app stylesheet drives the widget font, so the smaller size is asked for
    # by object name (QLabel#payloadHint) instead of a QFont that QSS would override
    win.tx_size_lbl.setObjectName("payloadHint")


def _build_input_row(win: MainWindow) -> QHBoxLayout:
    """The payload box (one line, horizontal scroll) and the column separator."""
    tx_row = QHBoxLayout()
    win.tx_edit = QPlainTextEdit()
    # U130: data is one line, even when it is 400 characters long - wrapping it
    # mid-token was lying about the payload. Long content scrolls horizontally.
    win.tx_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    win._update_input_placeholder()   # U86: keep the format-specific hint
    win.tx_edit.setToolTip(tr("tx.placeholder"))   # U114-D6: the examples live here
    win.tx_edit.textChanged.connect(win._check_hex_input)
    win.tx_edit.textChanged.connect(win._fit_tx_edit_height)   # U111: compact by default
    win._fit_tx_edit_height()
    tx_row.addWidget(win.tx_edit, 1)
    tx_row.addSpacing(10)
    tx_sep = QFrame()                        # U98: input area | action area
    tx_sep.setObjectName("vSep")
    tx_sep.setFrameShape(QFrame.Shape.VLine)
    tx_sep.setFixedWidth(1)
    tx_row.addWidget(tx_sep)
    tx_row.addSpacing(10)
    return tx_row


def _build_action_toolbar(win: MainWindow) -> QWidget:
    """U99/U129: Send + History on one line, the repeat controls beside them."""
    actions = QWidget()
    act_col = QHBoxLayout(actions)          # U129: a toolbar, not a column
    act_col.setContentsMargins(0, 0, 0, 0)
    act_col.setSpacing(10)
    # U119-P1: no leading/trailing stretch - the actions start on the same baseline
    # as the options row instead of floating in the middle of a tall pane.

    btn_row = QHBoxLayout()
    btn_row.setSpacing(8)
    win.send_btn = QPushButton(tr("btn.send"))
    win.send_btn.clicked.connect(win.on_send)
    win.send_btn.setDefault(True)
    win.send_btn.setMinimumWidth(104)
    win.send_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    win.send_btn.setToolTip(tr("sc.send.tip"))
    btn_row.addWidget(win.send_btn)
    # U87: the history is a popup now, so it costs one compact button beside the
    # primary action instead of a whole row of its own.
    win.history_btn = QPushButton(tr("tx.history.btn", n=0))
    win.history_btn.setToolTip(tr("tx.history.btn.tip", n=0))
    win.history_btn.setMinimumWidth(104)
    win.history_btn.setProperty("secondary", True)   # U98: a reference, not a peer
    win.history_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    win.history_btn.setEnabled(False)
    win.history_btn.clicked.connect(win._show_history)
    btn_row.addWidget(win.history_btn)
    act_col.addLayout(btn_row)

    repeat_row = QHBoxLayout()
    repeat_row.setSpacing(8)
    # U98: "Repeat send" starts and stops a process, so it is a toggle button that
    # reads "Stop repeat" while running - a checkbox stood in for an action before.
    win.repeat_btn = QPushButton(tr("tx.repeat"))
    win.repeat_btn.setCheckable(True)
    win.repeat_btn.setToolTip(tr("tx.repeat.tip"))
    win.repeat_btn.toggled.connect(win._on_repeat_toggled)
    repeat_row.addWidget(win.repeat_btn)
    win._repeat_lbl = QLabel(tr("tx.interval.label"))   # U31: unit lives in the label
    repeat_row.addWidget(win._repeat_lbl)
    win.repeat_ms = QLineEdit("1000")
    win.repeat_ms.setValidator(QIntValidator(10, 60000, win))
    # U113: the label carries "(ms)", so the box only has to fit 60000
    win.repeat_ms.setFixedWidth(win.repeat_ms.fontMetrics().horizontalAdvance("60000") + 22)
    win.repeat_ms.setToolTip(tr("tx.interval.tip"))
    win.repeat_ms.textChanged.connect(win._on_repeat_interval)
    repeat_row.addWidget(win.repeat_ms)
    # U171: how many repeats to send; 0 (shown as the infinity sign) keeps going
    # until stopped - the same "0 = endless" rule as the quick-send sequence.
    win._repeat_cnt_lbl = QLabel(tr("tx.repeat.count"))
    repeat_row.addWidget(win._repeat_cnt_lbl)
    win.repeat_times = QSpinBox()
    win.repeat_times.setRange(0, 9999)
    win.repeat_times.setValue(0)
    win.repeat_times.setSpecialValueText("\u221e")
    win.repeat_times.setToolTip(tr("tx.repeat.count.tip"))
    win.repeat_times.setFixedWidth(
        win.repeat_times.fontMetrics().horizontalAdvance("9999") + 26)
    repeat_row.addWidget(win.repeat_times)
    # U130-fix: the row was built but never attached to the toolbar, so the repeat
    # controls had no parent and stayed invisible from v1.5.1 on (the layout became a
    # single-line toolbar there and this addLayout was lost).
    tx_act_sep = QFrame()
    tx_act_sep.setObjectName("vSep")
    tx_act_sep.setFrameShape(QFrame.Shape.VLine)
    tx_act_sep.setFixedWidth(1)
    act_col.addWidget(tx_act_sep)
    act_col.addLayout(repeat_row)
    return actions

def build_data_panes(win: MainWindow, root: QWidget) -> None:
    """Data panes: receive group, splitter wiring, send group and the quick-send panel."""
    # --- main splitter: left (rx/tx) + right (quick send) ---------------
    splitter = QSplitter()

    left = QWidget()
    win._left_column = left      # U101: its floor is measured, not hard-coded
    left_layout = QVBoxLayout(left)

    # receive group -----------------------------------------------------
    win._rx_group = QGroupBox(tr("group.rx"))
    rx_group = win._rx_group
    rx_layout = QVBoxLayout(rx_group)
    rx_layout.setContentsMargins(8, 2, 8, 6)   # controls hug the top of the group
    rx_layout.setSpacing(4)

    _build_options_row(win, rx_layout)
    _build_status_counters(win)
    _build_find_bar(win, rx_layout)
    _build_receive_view(win, rx_layout)
    _build_vertical_splitter(win, rx_group, left_layout)

    splitter.addWidget(left)
    _build_quick_panel(win, splitter)
    splitter.setCollapsible(0, False)           # U63: same, after the panes exist
    splitter.setCollapsible(1, False)
    win._splitter = splitter
    splitter.setChildrenCollapsible(False)                  # U63: no zero-width panes
    left.setMinimumWidth(360)   # U63 floor; _fit_minimum_width() raises it to fit the rows
    splitter.setSizes(win._saved_sizes("split_sizes", DATA_FIRST_H))

    root.addWidget(splitter, 1)


def _build_options_row(win: MainWindow, rx_layout: QVBoxLayout) -> None:
    """Receive control row: split mode, display switches and the log actions."""
    rx_opts = QHBoxLayout()
    _build_split_controls(win, rx_opts)
    _build_display_switches(win, rx_opts)
    rx_layout.addWidget(_fixed_row(rx_opts))
    # U95: the slot only exists for manual/header mode; set that before the log view
    # is created, so the initial state must not run the full change handler.
    win.split_slot.setVisible(win.split_combo.currentIndex() >= SPLIT_MANUAL)


def _build_byte_split_pages(win: MainWindow) -> tuple[QWidget, QWidget, QWidget]:
    """The three B3 byte-stream parameter pages that live in the split slot."""
    win.split_size_spin = QSpinBox()
    win.split_size_spin.setRange(1, 65535)
    win.split_size_spin.setValue(8)
    win.split_size_spin.setMaximumWidth(88)
    win.split_size_spin.setToolTip(tr("split.fixed.tip"))

    win.split_start_edit = QLineEdit()
    win.split_start_edit.setPlaceholderText(tr("split.delim.start"))
    win.split_start_edit.setMaximumWidth(64)
    win.split_start_edit.setToolTip(tr("split.delim.tip"))
    win.split_end_edit = QLineEdit()
    win.split_end_edit.setPlaceholderText(tr("split.delim.end"))
    win.split_end_edit.setMaximumWidth(64)
    win.split_end_edit.setToolTip(tr("split.delim.tip"))
    delim_page = QWidget()
    delim_row = QHBoxLayout(delim_page)
    delim_row.setContentsMargins(0, 0, 0, 0)
    delim_row.setSpacing(4)
    delim_row.addWidget(win.split_start_edit)
    delim_row.addWidget(win.split_end_edit)

    win.split_prefix_spin = QSpinBox()
    win.split_prefix_spin.setRange(1, 4)
    win.split_prefix_spin.setValue(1)
    win.split_prefix_spin.setMaximumWidth(64)
    win.split_prefix_spin.setToolTip(tr("split.tlv.tip"))
    win.split_little_check = QCheckBox(tr("split.tlv.le"))
    win.split_little_check.setToolTip(tr("split.tlv.le.tip"))
    win.split_crc_check = QCheckBox(tr("split.tlv.crc"))
    win.split_crc_check.setToolTip(tr("split.tlv.crc.tip"))
    tlv_page = QWidget()
    tlv_row = QHBoxLayout(tlv_page)
    tlv_row.setContentsMargins(0, 0, 0, 0)
    tlv_row.setSpacing(6)
    tlv_row.addWidget(win.split_prefix_spin)
    tlv_row.addWidget(win.split_little_check)
    tlv_row.addWidget(win.split_crc_check)
    return win.split_size_spin, delim_page, tlv_page


def _build_split_controls(win: MainWindow, rx_opts: QHBoxLayout) -> None:
    """Split-mode combo and the fixed-width slot that follows the mode (U50)."""
    win._split_lbl = QLabel(tr("split.label"))
    rx_opts.addWidget(win._split_lbl)
    win.split_combo = QComboBox()
    win.split_combo.addItems([
        tr("split.off"), tr("split.auto"), tr("split.manual"), tr("split.header"),
        tr("split.fixed"), tr("split.delimited"), tr("split.tlv")])
    win.split_combo.setCurrentIndex(SPLIT_AUTO)
    win.split_combo.setToolTip(tr("split.tip"))
    win.split_combo.currentIndexChanged.connect(win._on_split_mode_changed)
    rx_opts.addWidget(win.split_combo)

    # U50: one fixed-width slot whose content follows the split mode
    win.split_ms_edit = QLineEdit("10")
    win.split_ms_edit.setValidator(QIntValidator(0, 60000, win))
    win.split_ms_edit.setMaximumWidth(104)
    win.split_ms_edit.setToolTip(tr("split.ms.tip"))

    win.header_edit = QLineEdit()      # U94: never pre-fill a value the user did not type
    win.header_edit.setPlaceholderText(tr("header.placeholder.hex"))
    win.header_edit.setToolTip(tr("header.tip"))
    win.header_edit.textChanged.connect(win._on_header_changed)
    win._update_input_placeholder()   # U94: hint follows the send format

    win.split_hint_lbl = QLabel(tr("split.auto.hint"))
    win.split_hint_lbl.setEnabled(False)

    # B3: each byte-stream mode carries its own compact parameter page
    fixed_page, delim_page, tlv_page = _build_byte_split_pages(win)

    win.split_slot = QStackedWidget()
    win.split_slot.setMinimumWidth(140)   # the mode hint must not clip
    win.split_slot.addWidget(win.split_hint_lbl)   # 0 auto / off
    win.split_slot.addWidget(win.split_ms_edit)    # 1 manual
    win.split_slot.addWidget(win.header_edit)      # 2 by header
    win.split_slot.addWidget(fixed_page)           # 3 fixed length (B3)
    win.split_slot.addWidget(delim_page)           # 4 start/end delimiters (B3)
    win.split_slot.addWidget(tlv_page)             # 5 length-prefixed / TLV (B3)
    rx_opts.addWidget(win.split_slot)


def _link_checkbox(box: QCheckBox, action: QAction) -> None:
    """Mirror a checkbox's state onto a menu action, in both directions (U164)."""
    action.setChecked(box.isChecked())      # set before wiring: no startup signal
    action.toggled.connect(box.setChecked)
    box.toggled.connect(action.setChecked)


def _build_more_controls(win: MainWindow) -> QToolButton:
    """The hidden switches and the More menu that mirrors them (U164/U179).

    U179: auto-scroll is high-frequency (toggled while reading the data), so it is
    a normal row control again; only pause, wrap and the log "save as" stay here.
    """
    win.autoscroll_check = QCheckBox(tr("rx.autoscroll"), win)   # U43
    win.autoscroll_check.setChecked(bool(load_config().get("autoscroll", True)))   # U75: default on
    win.autoscroll_check.setToolTip(tr("rx.autoscroll.tip"))
    win.autoscroll_check.toggled.connect(win._on_autoscroll_toggled)

    win.pause_check = QCheckBox(tr("rx.pause"), win)
    win.pause_check.setToolTip(tr("rx.pause.tip"))
    win.pause_check.toggled.connect(win._on_pause_toggled)
    win.pause_check.hide()

    win.wrap_check = QCheckBox(tr("rx.wrap"), win)            # U162: soft-wrap toggle
    win.wrap_check.setToolTip(tr("rx.wrap.tip"))
    win.wrap_check.setChecked(bool(load_config().get("wrap_on", False)))
    win.wrap_check.toggled.connect(win._on_wrap_toggled)
    win.wrap_check.hide()

    win.save_log_as_btn = QPushButton(tr("btn.save_log_as"), win)
    win.save_log_as_btn.clicked.connect(win.on_save_log_as)
    win.save_log_as_btn.hide()

    win.more_btn = QToolButton()
    win.more_btn.setText(tr("btn.more"))
    win.more_btn.setToolTip(tr("btn.more.tip"))
    win.more_btn.setAccessibleName(tr("btn.more"))
    win.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    win.more_menu = QMenu(win.more_btn)
    win.act_pause = win.more_menu.addAction(tr("rx.pause"))
    win.act_pause.setToolTip(tr("rx.pause.tip"))
    win.act_wrap = win.more_menu.addAction(tr("rx.wrap"))
    win.act_wrap.setToolTip(tr("rx.wrap.tip"))
    win.more_menu.addSeparator()
    win.act_save_as = win.more_menu.addAction(tr("btn.save_log_as"))
    win.act_save_as.triggered.connect(win.on_save_log_as)
    for action in (win.act_pause, win.act_wrap):
        action.setCheckable(True)
    _link_checkbox(win.pause_check, win.act_pause)
    _link_checkbox(win.wrap_check, win.act_wrap)
    win.more_btn.setMenu(win.more_menu)
    return win.more_btn


def _build_display_switches(win: MainWindow, rx_opts: QHBoxLayout) -> None:
    """Timestamp / echo switches, the More menu and the log + clear actions (U96/U164)."""
    # U96: one row, not two. U164: the row must still fit a 1366x768 laptop, so the
    # low-frequency controls (auto-scroll, pause, wrap, "Save as") keep their state
    # but move into a "More" menu. Their widgets stay alive (hidden) so every piece
    # of code that addresses them - retranslate, tests, config - keeps working.
    win.rx_filter_combo = QComboBox()                          # U163b: all / RX only / TX only
    win.rx_filter_combo.addItems([tr("rx.filter.all"), tr("rx.filter.rx"), tr("rx.filter.tx")])
    win.rx_filter_combo.setCurrentIndex(0)
    win.rx_filter_combo.setToolTip(tr("rx.filter.tip"))
    win.rx_filter_combo.currentIndexChanged.connect(win._on_rx_filter_changed)
    rx_opts.addWidget(win.rx_filter_combo)

    rx_opts.addSpacing(12)
    win.ts_check = QCheckBox(tr("ts.label"))                   # U96: on/off only
    win.ts_check.setChecked(bool(load_config().get("timestamp_on", True)))
    win.ts_check.setToolTip(tr("ts.tip"))
    win.ts_check.toggled.connect(win._on_timestamp_toggled)
    rx_opts.addWidget(win.ts_check)

    more = _build_more_controls(win)        # creates the hidden switches + the menu
    rx_opts.addSpacing(12)
    rx_opts.addWidget(win.autoscroll_check)   # U179: high-frequency -> back in the row
    rx_opts.addSpacing(12)
    rx_opts.addWidget(more)

    rx_opts.addSpacing(18)
    win.save_log_btn = QPushButton(tr("btn.save_log_quick"))
    win.save_log_btn.setToolTip(tr("log.quick.tip"))
    win.save_log_btn.clicked.connect(win.on_save_log_quick)
    rx_opts.addWidget(win.save_log_btn)

    rx_opts.addStretch(1)
    # U169: 清空 is a split button - one click clears the display (unchanged), and
    # the menu exposes the counter actions, which used to be buried in Settings.
    win.clear_btn = QToolButton()
    win.clear_btn.setObjectName("clearBtn")
    win.clear_btn.setText(tr("btn.clear"))
    win.clear_btn.setToolTip(tr("sc.clear.tip"))
    win.clear_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    win.clear_btn.clicked.connect(win.on_clear)
    win._clear_menu = QMenu(win.clear_btn)
    win._act_clear_all = win._clear_menu.addAction(tr("btn.clear.all"))
    win._act_clear_all.triggered.connect(win._on_clear_and_counters)
    win._act_reset_counters = win._clear_menu.addAction(tr("menu.reset_counters"))
    win._act_reset_counters.triggered.connect(win._reset_counters)
    win.clear_btn.setMenu(win._clear_menu)
    rx_opts.addWidget(win.clear_btn)

def _build_status_counters(win: MainWindow) -> None:
    """Session counters in the status bar (Z4/U124), away from the receive row."""
    # RX/TX counters live in the status bar (Z4): global state, and it frees
    # ~140 px of horizontal room for the single receive row (U35-P2).
    # U124: one counter for the whole session - "TX 12 次 · 39 B | RX 39 B" - in a
    # monospace face so the numbers cannot shift the layout as they change.
    win.sent_lbl = QLabel(tr("tx.counter", n=0, tx=0, rx=0))
    win.sent_lbl.setObjectName("statusCounters")
    win.statusBar().addPermanentWidget(win.sent_lbl)


def _build_find_bar(win: MainWindow, rx_layout: QVBoxLayout) -> None:
    """U41: find bar, hidden until Ctrl+F."""
    win._find_bar = QWidget()
    find_row = QHBoxLayout(win._find_bar)
    find_row.setContentsMargins(0, 0, 0, 0)
    win._find_lbl = QLabel(tr("find.label"))
    find_row.addWidget(win._find_lbl)
    win.find_edit = QLineEdit()
    win.find_edit.setPlaceholderText(tr("find.placeholder"))
    win.find_edit.returnPressed.connect(lambda: win._find_next(True))
    win.find_edit.textChanged.connect(win._on_find_text_changed)
    find_row.addWidget(win.find_edit, 1)
    win.find_count_lbl = QLabel("")
    win.find_count_lbl.setToolTip(tr("find.count.tip"))
    find_row.addWidget(win.find_count_lbl)
    win.find_case_check = QCheckBox(tr("find.case"))     # U181
    win.find_case_check.setChecked(bool(load_config().get("find_case", False)))
    win.find_case_check.setToolTip(tr("find.case.tip"))
    win.find_case_check.toggled.connect(win._on_find_case_toggled)
    find_row.addWidget(win.find_case_check)
    win.find_prev_btn = QPushButton(tr("find.prev"))
    win.find_prev_btn.clicked.connect(lambda: win._find_next(False))
    find_row.addWidget(win.find_prev_btn)
    win.find_next_btn = QPushButton(tr("find.next"))
    win.find_next_btn.clicked.connect(lambda: win._find_next(True))
    find_row.addWidget(win.find_next_btn)
    win.find_close_btn = QPushButton("\u00d7")
    win.find_close_btn.setObjectName("qsDel")
    win.find_close_btn.setFixedWidth(28)
    win.find_close_btn.setToolTip(tr("find.close.tip"))
    win.find_close_btn.clicked.connect(lambda: win._toggle_find_bar(False))
    find_row.addWidget(win.find_close_btn)
    win._find_bar.setSizePolicy(QSizePolicy.Policy.Preferred,
                                QSizePolicy.Policy.Fixed)   # U70
    # U181: the bar is a persistent highlight box now (default on, remembered)
    win._find_bar.setVisible(bool(load_config().get("find_bar_on", True)))
    rx_layout.addWidget(win._find_bar)


def _build_receive_view(win: MainWindow, rx_layout: QVBoxLayout) -> None:
    """The read-only receive view; it absorbs all spare height (U70)."""
    win.rx_view = QPlainTextEdit()
    win.rx_view.setReadOnly(True)
    win.rx_view.setLineWrapMode(
        QPlainTextEdit.LineWrapMode.WidgetWidth if load_config().get("wrap_on", False)
        else QPlainTextEdit.LineWrapMode.NoWrap)   # U162: follows the wrap switch (default off = U160-A5)
    win.rx_view.verticalScrollBar().actionTriggered.connect(win._pause_autoscroll)   # U43
    win.rx_view.setMaximumBlockCount(RECEIVE_MAX_LINES)   # U45
    win.rx_view.setPlaceholderText(tr("rx.empty.hint"))    # U123: an empty pane says why
    win.rx_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    win.rx_view.customContextMenuRequested.connect(win._open_rx_context_menu)
    win.rx_view.viewport().installEventFilter(win)   # U129-A4: long-line hover tooltip
    rx_layout.addWidget(win.rx_view, 1)   # U70: the view absorbs all spare height


def _build_vertical_splitter(win: MainWindow, rx_group: QGroupBox, left_layout: QVBoxLayout) -> None:
    """Draggable splitter holding the receive group above the send group."""
    win._v_splitter = QSplitter(Qt.Orientation.Vertical)   # U35-P0: draggable
    win._v_splitter.setChildrenCollapsible(False)          # U63: never collapse a pane
    win._v_splitter.addWidget(rx_group)
    win._v_splitter.setStretchFactor(0, 3)
    rx_group.setMinimumHeight(170)                          # U63: keep both panes usable

    win._build_send_group()
    win._v_splitter.addWidget(win._tx_group)
    win._v_splitter.setStretchFactor(1, 0)   # U111: data first
    win._v_splitter.splitterMoved.connect(   # U119: the input takes the extra room
        lambda *_: QTimer.singleShot(0, win._fit_tx_edit_height))
    win._tx_group.setMinimumHeight(120)                    # U63/U98/U99/U111
    win._v_splitter.setCollapsible(0, False)   # U63: flags must be set after
    win._v_splitter.setCollapsible(1, False)   #      the panes are added
    _stored_v = load_config().get("v_split_sizes")
    _stored_h = load_config().get("split_sizes")
    win._custom_split_sizes = bool(
        (isinstance(_stored_v, list) and _stored_v not in (DATA_FIRST_V, [420, 260]))
        or (isinstance(_stored_h, list) and _stored_h not in (DATA_FIRST_H, [820, 340])))
    win._v_splitter.setSizes(win._saved_sizes("v_split_sizes", DATA_FIRST_V))
    left_layout.addWidget(win._v_splitter, 1)


def _build_quick_panel(win: MainWindow, splitter: QSplitter) -> None:
    """Right pane: the quick-send panel and its signal wiring."""
    win.quick_panel = QuickSendPanel()
    win.quick_panel.send_payload.connect(win.on_quick_send)
    win.quick_panel.log.connect(win.on_log_line)
    win.quick_panel.error.connect(lambda m: win._notify(m, "error"))
    win.quick_panel.deleted.connect(win._on_row_deleted)
    splitter.addWidget(win.quick_panel)
    win.quick_panel.collapsed_changed.connect(win._on_quick_panel_collapsed)   # U88
