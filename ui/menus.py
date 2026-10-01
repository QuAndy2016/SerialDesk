"""Settings menu construction (theme, language, config, panel, update, about, shortcuts)."""
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
from ui.regions import (BAUDRATES, DATA_FIRST_H, DATA_FIRST_V,
                        RECEIVE_MAX_LINES, SPLIT_AUTO, SPLIT_HEADER,
                        SPLIT_MANUAL, _fixed_row, build_connection_row,
                        build_data_panes, build_send_group, build_status_bar)
from app import i18n
from app.i18n import hex_error_message, tr
from app.config import log_dir
from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII)  # refactor step 1
from app.shortcuts import HELP_ROWS as SHORTCUT_ROWS
from app.stats import SessionStats

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.main_window import MainWindow

def build_menu(win: MainWindow) -> None:
    """Settings menu construction (theme, language, config, panel, update, about, shortcuts)."""
    _build_panel_entry(win)
    _build_theme_menu(win)
    _build_language_menu(win)
    _build_config_menu(win)
    _build_io_section(win)
    _build_danger_section(win)


def _build_panel_entry(win: MainWindow) -> None:
    """U88: the panel can be folded away, so it needs an entry outside itself."""
    menu = win._settings_menu
    win._quick_panel_act = QAction(tr("menu.quick_panel"), win)
    win._quick_panel_act.setCheckable(True)
    win._quick_panel_act.setChecked(True)
    win._quick_panel_act.triggered.connect(
        lambda: win._on_quick_panel_collapsed(not win._quick_panel_act.isChecked()))
    menu.addAction(win._quick_panel_act)
    menu.addSeparator()
    menu.addSection(tr("menu.sec.appearance"))    # U110: give the menu structure


def _build_theme_menu(win: MainWindow) -> None:
    """Theme submenu with an exclusive system/dark/light group."""
    menu = win._settings_menu.addMenu(tr("theme.menu"))
    win._theme_menu = menu
    win._theme_group = QActionGroup(win)
    win._theme_group.setExclusive(True)

    choice = load_config().get("theme", "system")

    win._theme_system = QAction(tr("theme.system"), win, checkable=True)
    win._theme_dark = QAction(tr("theme.dark"), win, checkable=True)
    win._theme_light = QAction(tr("theme.light"), win, checkable=True)

    for act in (win._theme_system, win._theme_dark, win._theme_light):
        win._theme_group.addAction(act)
        menu.addAction(act)

    if choice == "dark":
        win._theme_dark.setChecked(True)
    elif choice == "light":
        win._theme_light.setChecked(True)
    else:
        win._theme_system.setChecked(True)

    win._theme_system.triggered.connect(win._set_theme_system)
    win._theme_dark.triggered.connect(win._set_theme_dark)
    win._theme_light.triggered.connect(win._set_theme_light)


def _build_language_menu(win: MainWindow) -> None:
    """Language submenu (U19) - sibling of the theme submenu inside Settings."""
    win._lang_menu = win._settings_menu.addMenu(tr("menu.language"))
    win._lang_group = QActionGroup(win)
    win._lang_group.setExclusive(True)
    win._lang_system = QAction(tr("lang.system"), win, checkable=True)
    win._lang_zh = QAction(tr("lang.zh"), win, checkable=True)
    win._lang_en = QAction(tr("lang.en"), win, checkable=True)
    for act in (win._lang_system, win._lang_zh, win._lang_en):
        win._lang_group.addAction(act)
        win._lang_menu.addAction(act)
    lang_now = i18n.get_language()
    {"zh": win._lang_zh, "en": win._lang_en}.get(lang_now, win._lang_system).setChecked(True)
    win._lang_system.triggered.connect(lambda: win._set_language("system"))
    win._lang_zh.triggered.connect(lambda: win._set_language("zh"))
    win._lang_en.triggered.connect(lambda: win._set_language("en"))


def _build_config_menu(win: MainWindow) -> None:
    """Config import / export (T15)."""
    win._settings_menu.addSection(tr("menu.sec.config"))
    win._cfg_menu = win._settings_menu.addMenu(tr("cfg.menu"))

    win._cfg_export_act = QAction(tr("cfg.export"), win)
    win._cfg_import_act = QAction(tr("cfg.import"), win)
    win._cfg_export_act.triggered.connect(win.on_export_config)
    win._cfg_import_act.triggered.connect(win.on_import_config)
    win._cfg_menu.addAction(win._cfg_export_act)
    win._cfg_menu.addAction(win._cfg_import_act)


def _build_io_section(win: MainWindow) -> None:
    """Auto-save, auto-reply rules, auto-reconnect, shortcuts and the about box."""
    menu = win._settings_menu
    menu.addSection(tr("menu.sec.io"))
    win._autosave_act = QAction(tr("as.menu"), win)
    win._autosave_act.setToolTip(tr("as.note"))
    win._autosave_act.triggered.connect(win._show_autosave_settings)
    menu.addAction(win._autosave_act)

    # U98: the auto-reply switch and its rules belong with the settings, not in
    # the middle of the send row next to the file button where they used to sit.
    win.auto_reply_act = QAction(tr("rb.enable"), win, checkable=True)
    win.auto_reply_act.setToolTip(tr("rb.enable.tip"))
    win.auto_reply_act.setChecked(bool(load_config().get("auto_reply_enabled", False)))
    win.auto_reply_act.toggled.connect(win._on_auto_reply_toggled)
    menu.addAction(win.auto_reply_act)

    win.rules_act = QAction(tr("rb.rules.menu"), win)
    win.rules_act.triggered.connect(win._edit_rules)
    menu.addAction(win.rules_act)

    menu.addSeparator()
    win._reconnect_act = QAction(tr("conn.auto"), win, checkable=True)
    win._reconnect_act.setToolTip(tr("conn.auto.tip"))
    win._reconnect_act.setChecked(bool(load_config().get("auto_reconnect", False)))
    win._reconnect_act.toggled.connect(win._on_reconnect_toggled)
    menu.addAction(win._reconnect_act)

    win._shortcuts_act = QAction(tr("menu.shortcuts"), win)   # U123
    win._shortcuts_act.triggered.connect(win._show_shortcuts)
    menu.addAction(win._shortcuts_act)

    win._about_act = QAction(tr("about.menu"), win)
    win._about_act.triggered.connect(win._show_about)
    menu.addAction(win._about_act)


def _build_danger_section(win: MainWindow) -> None:
    """U110/D: the destructive entry lives at the very bottom, under its own heading."""
    win._settings_menu.addSeparator()
    win._settings_menu.addSection(tr("menu.sec.danger"))
    win._reset_act = QAction(tr("cfg.reset"), win)
    win._reset_act.triggered.connect(win._reset_settings)
    win._settings_menu.addAction(win._reset_act)
