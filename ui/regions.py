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
)
from PySide6.QtGui import (
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
from app import __version__
from app import update as update_check
from app.config import CONFIG_PATH, data_dir, load_config, log_dir, save_config
from app.log_sink import LogSink
from app.serial_worker import SerialWorker, list_serial_ports
from ui import theme
from ui.auto_reply_dialog import AutoReplyDialog
from ui.autosave_dialog import AutoSaveDialog
from ui.history_dialog import HistoryDialog
from ui.port_settings_dialog import PortSettingsDialog
from ui.quick_send_panel import RAIL_W, QuickSendPanel
from ui.retranslate import retranslate_ui
from app import i18n
from app.i18n import hex_error_message, tr
from app.config import log_dir
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

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
def _fixed_row(layout) -> QWidget:
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

def build_connection_row(win, root) -> None:
    """Connection row: port, baud, open/close, receive format, panel toggle."""
    """Connection row: port, baud, open/close, receive format and the panel toggle."""
    bar = QHBoxLayout()
    win._port_lbl = QLabel(tr("port.label"))     # U100: these two were English-only
    bar.addWidget(win._port_lbl)
    win.port_combo = QComboBox()
    win.port_combo.setMinimumWidth(170)   # U78: keep the whole row under 1040 px
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

    bar.addSpacing(12)
    win._rx_fmt_lbl = QLabel(tr("rxfmt.label"))
    bar.addWidget(win._rx_fmt_lbl)
    win.rx_fmt_combo = QComboBox()
    win.rx_fmt_combo.addItems(["ASCII", "HEX", "HEX+ASCII"])
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
    # U114-D4: one control height across the connection row
    for _w in (win.port_combo, win.refresh_btn, win.baud_combo, win.open_btn,
               win.rx_fmt_combo, win.params_summary, win._settings_btn):
        _w.setMinimumHeight(32)

    bar.addStretch(1)
    root.addLayout(bar)

    # U35-P3: the parameter widgets now live in their own dialog; the main
    # window keeps the same attribute names so the rest of the code is unchanged.
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

def build_status_bar(win) -> None:
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

def build_send_group(win) -> None:
    """Send group: payload options, the input box and the action toolbar."""
    """Send group: payload options, the input box and the action toolbar."""
    # send group ----------------------------------------------------------
    win._tx_group = QGroupBox(tr("group.tx"))
    tx_group = win._tx_group
    tx_layout = QVBoxLayout(tx_group)
    tx_layout.setContentsMargins(8, 2, 8, 6)
    tx_layout.setSpacing(4)

    # U74: payload options above, the input owning the middle with the primary
    # Send button beside it, then the repeat controls and the file row. The old
    # layout squeezed the input to ~134 px (a control column ate ~83% of the
    # width) and capped its height at 90 px, so the send area looked like a toy.
    tx_fmt_row = QHBoxLayout()
    # U121: "格式: HEX" + "校验: 无" and their two labels used ~200 px of a row that
    # had nothing else in it, leaving half the row empty. They live in one chip
    # ("HEX · 无") pointing at a small popup, and the width goes back to the input.
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

    # U98: the text decorations only mean something for ASCII, so they live in one
    # group that disappears in HEX mode (same rule as U50). U99: measured in English
    # they pushed the minimum window width up, so they sit in the action column now
    # instead of the option row - the fallback recorded in the U99 plan.
    win._tx_mod_group = QWidget()
    mod_row = QHBoxLayout(win._tx_mod_group)
    mod_row.setContentsMargins(0, 0, 0, 0)
    mod_row.setSpacing(10)
    # U112: the old "追加 \r\n" checkbox spoke escape notation. It is now a picker
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

    # U99: file sending moved up beside the checksum box, so the row below only
    # carries the input box and the actions.
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
    # U129: the line-ending and escape controls belong with the other payload
    # options; the action column that used to hold them was eating the height the
    # input needs.
    tx_fmt_row.addStretch(1)
    tx_fmt_row.addWidget(win._tx_mod_group)
    tx_layout.addWidget(_fixed_row(tx_fmt_row))
    win.tx_fmt_combo.currentIndexChanged.connect(win._on_tx_fmt_changed)
    win.tx_fmt_combo.currentIndexChanged.connect(win._check_hex_input)
    win._on_tx_fmt_changed(win.tx_fmt_combo.currentIndex())

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

    # U99: every action lives in the right-hand column - Send/History on the first
    # line and the repeat controls right below them - so the left side of the row
    # is nothing but the input box.
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
    # U130-fix: the row was built but never attached to the toolbar, so the repeat
    # controls had no parent and stayed invisible from v1.5.1 on (the layout became a
    # single-line toolbar there and this addLayout was lost).
    tx_act_sep = QFrame()
    tx_act_sep.setObjectName("vSep")
    tx_act_sep.setFrameShape(QFrame.Shape.VLine)
    tx_act_sep.setFixedWidth(1)
    act_col.addWidget(tx_act_sep)
    act_col.addLayout(repeat_row)
    act_row = QHBoxLayout()
    act_row.setContentsMargins(0, 2, 0, 0)
    act_row.setSpacing(10)
    act_row.addWidget(actions)
    act_row.addStretch(1)
    act_row.addWidget(win.tx_size_lbl)     # U121: next to the actions it describes
    tx_layout.addLayout(tx_row, 1)          # U129: the input owns the middle
    tx_layout.addLayout(act_row)

def build_data_panes(win, root) -> None:
    """Data panes: receive group, splitter wiring, send group, quick-send panel."""
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

    rx_opts = QHBoxLayout()
    win._split_lbl = QLabel(tr("split.label"))
    rx_opts.addWidget(win._split_lbl)
    win.split_combo = QComboBox()
    win.split_combo.addItems([tr("split.off"), tr("split.auto"), tr("split.manual"), tr("split.header")])
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

    win.split_slot = QStackedWidget()
    win.split_slot.setMinimumWidth(132)   # the mode hint must not clip
    win.split_slot.addWidget(win.split_hint_lbl)   # 0 auto / off
    win.split_slot.addWidget(win.split_ms_edit)    # 1 manual
    win.split_slot.addWidget(win.header_edit)      # 2 by header
    rx_opts.addWidget(win.split_slot)

    # U96: one row, not two. The stream settings come first, then the display
    # switches, then the log actions; Clear stays alone at the far right (U95's
    # rule for destructive actions), which is what the stretch is there for.
    # The in-row Auto-save switch is gone (U97) - the settings dialog owns it.
    rx_opts.addSpacing(12)
    win.ts_check = QCheckBox(tr("ts.label"))                   # U96: on/off only
    win.ts_check.setChecked(bool(load_config().get("timestamp_on", True)))
    win.ts_check.setToolTip(tr("ts.tip"))
    win.ts_check.toggled.connect(win._on_timestamp_toggled)
    rx_opts.addWidget(win.ts_check)

    rx_opts.addSpacing(12)
    win.echo_tx_check = QCheckBox(tr("rx.echo_tx"))
    win.echo_tx_check.setChecked(True)          # echo sent data by default (U26)
    win.echo_tx_check.setToolTip(tr("rx.echo_tx.tip"))
    rx_opts.addWidget(win.echo_tx_check)
    rx_opts.addSpacing(12)
    win.autoscroll_check = QCheckBox(tr("rx.autoscroll"))   # U43
    win.autoscroll_check.setChecked(bool(load_config().get("autoscroll", True)))   # U75: default on
    win.autoscroll_check.setToolTip(tr("rx.autoscroll.tip"))
    win.autoscroll_check.toggled.connect(win._on_autoscroll_toggled)
    rx_opts.addWidget(win.autoscroll_check)

    rx_opts.addSpacing(18)
    win.save_log_btn = QPushButton(tr("btn.save_log_quick"))
    win.save_log_btn.setToolTip(tr("log.quick.tip"))
    win.save_log_btn.clicked.connect(win.on_save_log_quick)
    rx_opts.addWidget(win.save_log_btn)

    win.save_log_as_btn = QPushButton(tr("btn.save_log_as"))
    win.save_log_as_btn.clicked.connect(win.on_save_log_as)
    rx_opts.addWidget(win.save_log_as_btn)

    rx_opts.addStretch(1)
    win.clear_btn = QPushButton(tr("btn.clear"))
    win.clear_btn.clicked.connect(win.on_clear)
    win.clear_btn.setToolTip(tr("sc.clear.tip"))
    rx_opts.addWidget(win.clear_btn)
    rx_layout.addWidget(_fixed_row(rx_opts))
    # U95: the slot only exists for manual/header mode; set that before the log view
    # is created, so the initial state must not run the full change handler.
    win.split_slot.setVisible(win.split_combo.currentIndex() in (SPLIT_MANUAL, SPLIT_HEADER))

    # RX/TX counters live in the status bar (Z4): global state, and it frees
    # ~140 px of horizontal room for the single receive row (U35-P2).
    # U124: one counter for the whole session - "TX 12 次 · 39 B | RX 39 B" - in a
    # monospace face so the numbers cannot shift the layout as they change.
    win.sent_lbl = QLabel(tr("tx.counter", n=0, tx=0, rx=0))
    win.sent_lbl.setObjectName("statusCounters")
    win.statusBar().addPermanentWidget(win.sent_lbl)

    # U41: find bar, hidden until Ctrl+F
    win._find_bar = QWidget()
    find_row = QHBoxLayout(win._find_bar)
    find_row.setContentsMargins(0, 0, 0, 0)
    win._find_lbl = QLabel(tr("find.label"))
    find_row.addWidget(win._find_lbl)
    win.find_edit = QLineEdit()
    win.find_edit.setPlaceholderText(tr("find.placeholder"))
    win.find_edit.returnPressed.connect(lambda: win._find_next(True))
    find_row.addWidget(win.find_edit, 1)
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
    win._find_bar.hide()
    rx_layout.addWidget(win._find_bar)

    win.rx_view = QPlainTextEdit()
    win.rx_view.setReadOnly(True)
    win.rx_view.verticalScrollBar().actionTriggered.connect(win._pause_autoscroll)   # U43
    win.rx_view.setMaximumBlockCount(RECEIVE_MAX_LINES)   # U45
    win.rx_view.setPlaceholderText(tr("rx.empty.hint"))    # U123: an empty pane says why
    rx_layout.addWidget(win.rx_view, 1)   # U70: the view absorbs all spare height
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

    splitter.addWidget(left)

    # right: quick send panel ---------------------------------------------
    win.quick_panel = QuickSendPanel()
    win.quick_panel.send_payload.connect(win.on_quick_send)
    win.quick_panel.log.connect(win.on_log_line)
    win.quick_panel.error.connect(lambda m: win._notify(m, "error"))
    win.quick_panel.deleted.connect(win._on_row_deleted)
    splitter.addWidget(win.quick_panel)
    win.quick_panel.collapsed_changed.connect(win._on_quick_panel_collapsed)   # U88
    splitter.setCollapsible(0, False)           # U63: same, after the panes exist
    splitter.setCollapsible(1, False)
    win._splitter = splitter
    splitter.setChildrenCollapsible(False)                  # U63: no zero-width panes
    left.setMinimumWidth(360)   # U63 floor; _fit_minimum_width() raises it to fit the rows
    splitter.setSizes(win._saved_sizes("split_sizes", DATA_FIRST_H))

    root.addWidget(splitter, 1)
