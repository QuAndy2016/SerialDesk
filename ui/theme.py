"""Theme management: dark/light QSS palettes, follow system color scheme."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

DARK_QSS = """
QMainWindow { background: #1e1e2e; }
QDialog { background: #1e1e2e; }
QWidget { color: #d4d4d4; font-size: 13px; }
QGroupBox {
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 2px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #8be9fd;
    font-weight: bold;
}
QPushButton {
    background: #3a3a4a;
    border: 1px solid #4a4a5a;
    border-radius: 4px;
    padding: 5px 14px;
}
QPushButton:hover { background: #4a4a5a; }
QPushButton:pressed { background: #2a2a3a; }
QPushButton:disabled { color: #666; background: #2a2a35; }
QPushButton[secondary="true"] { background: #2d2d3d; border: 1px solid #4a4a5a; color: #cfcfcf; }
QPushButton[secondary="true"]:hover { background: #3a3a4a; border-color: #6a6a7a; }
QComboBox, QLineEdit {
    background: #2d2d3d;
    border: 1px solid #4a4a5a;
    border-radius: 4px;
    padding: 3px 8px;
}
QComboBox:hover, QLineEdit:hover { border-color: #8be9fd; }
QComboBox::drop-down { border: none; border-left: 1px solid #4a4a5a; width: 22px; }
QComboBox::down-arrow { image: url(__ASSETS__/arrow_down_dark.png); width: 10px; height: 6px; }
QComboBox[invalid="true"] { border: 1px solid #ff4136; }
QComboBox QAbstractItemView {
    background: #2d2d3d;
    color: #d4d4d4;
    selection-background-color: #4a6a9a;
}
QSpinBox {
    background: #2d2d3d;
    border: 1px solid #4a4a5a;
    border-radius: 4px;
    padding: 3px 6px;
}
QSpinBox:hover { border-color: #8be9fd; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url(__ASSETS__/arrow_up_dark.png); width: 8px; height: 5px; }
QSpinBox::down-arrow { image: url(__ASSETS__/arrow_down_dark.png); width: 8px; height: 5px; }
QPlainTextEdit {
    background: #16161f;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    color: #e0e0e0;
    font-family: Consolas, "Courier New", monospace;
    font-size: 13px;
}
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; }
QStatusBar { background: #2d2d3d; }
QStatusBar::item { border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMenuBar { background: #1e1e2e; color: #d4d4d4; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: #3a3a4a; }
QMenu { background: #2d2d3d; color: #d4d4d4; border: 1px solid #4a4a5a; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 28px; border-radius: 4px; }
QMenu::item:selected { background: #4a6a9a; color: #ffffff; }
QMenu::separator { height: 1px; background: #4a4a5a; margin: 4px 8px; }
QSplitter::handle { background: #3a3a4a; }
QPushButton#qsDel { color: #8a8a8a; background: transparent; border: none; font-size: 15px; }
QPushButton#qsDel:hover { color: #ff7b72; background: #3a3a4a; border-radius: 4px; }
QToolButton#paramsBtn { color: #d4d4d4; background: transparent; border: 1px solid #4a4a5a; border-radius: 4px; padding: 3px 8px; }
QToolButton#paramsBtn:hover { border-color: #8be9fd; }
QToolButton#settingsBtn { color: #d4d4d4; background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 4px 12px; margin: 2px 4px 2px 0; }
QToolButton#settingsBtn:hover { background: #3a3a4a; border-color: #4a4a5a; }
QToolButton#settingsBtn::menu-indicator { image: none; width: 0px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #5a5a6a; border-radius: 3px; background: #16161f; }
QCheckBox::indicator:hover { border-color: #8be9fd; }
QCheckBox::indicator:checked { background: #1f3a44; border-color: #4b8fa3; image: url(__ASSETS__/check_accent.png); }
QCheckBox::indicator:checked:hover { background: #27495a; border-color: #63aec4; }
QCheckBox::indicator:disabled { border-color: #3a3a4a; background: #2a2a35; }
QCheckBox::indicator:checked:disabled { background: #24343c; border-color: #3a545e; }
QScrollBar:vertical { background: #23232f; width: 13px; margin: 0px; }
QScrollBar::handle:vertical { background: #4a4a5c; min-height: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #6a6a80; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: #23232f; height: 13px; margin: 0px; }
QScrollBar::handle:horizontal { background: #4a4a5c; min-width: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #6a6a80; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QLabel#seqOrd { color: #8be9fd; font-size: 9px; font-weight: bold; background: transparent; }   /* U80: corner badge */
QFrame#qsRow { border: 1px solid transparent; border-radius: 4px; }
QFrame#qsRow[selected="true"] { background: rgba(139, 233, 253, 0.16); border: 1px solid rgba(139, 233, 253, 0.16); }
"""

LIGHT_QSS = """
QMainWindow { background: #f5f5f7; }
QDialog { background: #f5f5f7; }
QWidget { color: #1f1f1f; font-size: 13px; }
QGroupBox {
    border: 1px solid #d0d0d8;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #1e5aa8;
    font-weight: bold;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #c8c8d0;
    border-radius: 4px;
    padding: 5px 14px;
}
QPushButton:hover { background: #ececf2; }
QPushButton:pressed { background: #dcdce4; }
QPushButton:disabled { color: #aaa; background: #e8e8ee; }
QPushButton[secondary="true"] { background: #f4f4f6; border: 1px solid #c9c9d1; color: #44444c; }
QPushButton[secondary="true"]:hover { background: #e9e9ee; border-color: #a9a9b4; }
QComboBox, QLineEdit {
    background: #ffffff;
    border: 1px solid #c8c8d0;
    border-radius: 4px;
    padding: 3px 8px;
}
QComboBox:hover, QLineEdit:hover { border-color: #1e5aa8; }
QComboBox::drop-down { border: none; border-left: 1px solid #c8c8d0; width: 22px; }
QComboBox::down-arrow { image: url(__ASSETS__/arrow_down_light.png); width: 10px; height: 6px; }
QComboBox[invalid="true"] { border: 1px solid #ff4136; }
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1f1f1f;
    selection-background-color: #cfe0f5;
}
QSpinBox {
    background: #ffffff;
    border: 1px solid #c8c8d0;
    border-radius: 4px;
    padding: 3px 6px;
}
QSpinBox:hover { border-color: #1e5aa8; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url(__ASSETS__/arrow_up_light.png); width: 8px; height: 5px; }
QSpinBox::down-arrow { image: url(__ASSETS__/arrow_down_light.png); width: 8px; height: 5px; }
QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #d0d0d8;
    border-radius: 4px;
    color: #111111;
    font-family: Consolas, "Courier New", monospace;
    font-size: 13px;
}
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; }
QStatusBar { background: #e8e8ee; }
QStatusBar::item { border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMenuBar { background: #f5f5f7; color: #1f1f1f; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: #e0e0e8; }
QMenu { background: #ffffff; color: #1f1f1f; border: 1px solid #c8c8d0; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 28px; border-radius: 4px; }
QMenu::item:selected { background: #cfe0f5; color: #111111; }
QMenu::separator { height: 1px; background: #d0d0d8; margin: 4px 8px; }
QSplitter::handle { background: #d0d0d8; }
QPushButton#qsDel { color: #9a9a9a; background: transparent; border: none; font-size: 15px; }
QPushButton#qsDel:hover { color: #c62828; background: #ececf2; border-radius: 4px; }
QToolButton#paramsBtn { color: #1f1f1f; background: transparent; border: 1px solid #c8c8d0; border-radius: 4px; padding: 3px 8px; }
QToolButton#paramsBtn:hover { border-color: #1e5aa8; }
QToolButton#settingsBtn { color: #1f1f1f; background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 4px 12px; margin: 2px 4px 2px 0; }
QToolButton#settingsBtn:hover { background: #e0e0e8; border-color: #c8c8d0; }
QToolButton#settingsBtn::menu-indicator { image: none; width: 0px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #b0b0bc; border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:hover { border-color: #1e5aa8; }
QCheckBox::indicator:checked { background: #1e5aa8; border-color: #1e5aa8; image: url(__ASSETS__/check_light.png); }
QCheckBox::indicator:checked:hover { background: #2a6fc4; border-color: #2a6fc4; }
QCheckBox::indicator:disabled { border-color: #d0d0d8; background: #ececf2; }
QCheckBox::indicator:checked:disabled { background: #9db4cf; border-color: #9db4cf; }
QScrollBar:vertical { background: #ececf2; width: 13px; margin: 0px; }
QScrollBar::handle:vertical { background: #b8b8c4; min-height: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #9090a0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: #ececf2; height: 13px; margin: 0px; }
QScrollBar::handle:horizontal { background: #b8b8c4; min-width: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #9090a0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QLabel#seqOrd { color: #1e5aa8; font-size: 9px; font-weight: bold; background: transparent; }   /* U80: corner badge */
QFrame#qsRow { border: 1px solid transparent; border-radius: 4px; }
QFrame#qsRow[selected="true"] { background: rgba(30, 90, 168, 0.14); border: 1px solid rgba(30, 90, 168, 0.14); }
"""


def asset_dir() -> str:
    """Absolute path of the assets dir, works from source and PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets").replace("\\", "/")


def qss(text: str) -> str:
    """Substitute __ASSETS__ placeholder with the resolved assets dir."""
    return text.replace("__ASSETS__", asset_dir())

# manual override state: None = follow system, True = dark, False = light
_override: bool | None = None


def set_override(dark: bool | None) -> None:
    """Set manual theme override. None = follow system again."""
    global _override
    _override = dark


def get_override() -> bool | None:
    """Return current override (None = follow system)."""
    return _override


def is_system_dark() -> bool:
    """Detect current OS color scheme (Qt 6.5+)."""
    scheme = QGuiApplication.styleHints().colorScheme()
    return scheme == Qt.ColorScheme.Dark


def resolved_dark(dark: bool | None = None) -> bool:
    """Resolve effective dark flag: override > argument > system."""
    if _override is not None:
        return _override
    if dark is None:
        return is_system_dark()
    return dark


def apply_theme(app: QApplication, dark: bool | None = None) -> bool:
    """Apply dark/light QSS (override-aware). Returns the effective dark flag."""
    dark = resolved_dark(dark)
    app.setStyleSheet(qss(DARK_QSS if dark else LIGHT_QSS))
    return dark


def text_color() -> str:
    """Receive-pane text colour (U62: dark theme softened from #e0e0e0, which glared)."""
    return "#c0c0c0" if resolved_dark() else "#111111"


def tx_color() -> str:
    """Colour used to highlight echoed TX data (calm blue, never red)."""
    return "#7fb3d5" if resolved_dark() else "#1e5aa8"


def meta_color() -> str:
    """Timestamp + direction marker colour: dimmer than the payload (U62)."""
    return "#7d8590" if resolved_dark() else "#6d6d78"


def history_list_colors() -> dict:
    """Colours for the send-history list (v0.10.0 P0/P1).

    Selected rows keep >=4.5:1 text contrast in both themes (measured):
    dark  #ffffff on #33506e = 8.3:1, meta #c9d6e8 = 5.7:1;
    light #111111 on #cfe0f5 = 15.4:1, meta #3d5e84 = 5.5:1.
    """
    if resolved_dark():
        return {"sel_bg": "#33506e", "sel_text": "#ffffff", "sel_meta": "#c9d6e8",
                "text": "#c0c0c0", "meta": "#9aa4b1"}
    return {"sel_bg": "#cfe0f5", "sel_text": "#111111", "sel_meta": "#3d5e84",
            "text": "#111111", "meta": "#6d6d78"}


def watch_system_theme(app: QApplication, callback) -> None:
    """Notify callback(dark: bool) when OS theme changes, unless overridden.

    When a manual override is active, system changes are ignored so the
    manual choice stays fixed. Clearing override (None) resumes following.
    """
    hints = QGuiApplication.styleHints()
    try:
        def _on_system_change(scheme):
            if get_override() is None:
                callback(scheme == Qt.ColorScheme.Dark)
        hints.colorSchemeChanged.connect(_on_system_change)
    except (AttributeError, RuntimeError):
        pass  # older Qt without live theme switching


def status_colors() -> dict:
    """State-light colours per theme (U38; all values WCAG AA >= 4.5:1 measured).

    Keys: ok (connected) / err (not connected) / idle (port not open).
    """
    if resolved_dark():
        return {"ok": "#7ee787", "err": "#ff7b72", "idle": "#9a9a9a"}
    return {"ok": "#176c2c", "err": "#c62828", "idle": "#5f5f5f"}


def level_color(level: str) -> str:
    """Status-bar message colour for a notification level (U30/U36).

    error -> red, warn -> amber, anything else -> current theme text colour.
    """
    dark = resolved_dark()
    if level == "error":
        return "#ff7b72" if dark else "#c62828"
    if level == "warn":
        return "#ffb74d" if dark else "#9c5300"
    return text_color()


def apply_native_dark(widget, dark: bool) -> None:
    """Match the OS window frame to the app theme (U51).

    Windows: DWMWA_USE_IMMERSIVE_DARK_MODE (attribute 20 on Win10 1809+, 19 on
    earlier builds) turns the native title bar dark. Qt 6.8+: setColorScheme
    keeps other native surfaces in sync. No-op elsewhere; never raises.
    """
    try:
        setter = getattr(QGuiApplication.styleHints(), "setColorScheme", None)
        if setter is not None:
            setter(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
    except Exception:  # noqa: BLE001 - older Qt / headless
        pass
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            try:
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
            except Exception:  # noqa: BLE001 - try the next attribute id
                continue
    except Exception:  # noqa: BLE001 - never break theming
        pass
