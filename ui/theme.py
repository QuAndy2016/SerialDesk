"""Theme management: dark/light QSS palettes, follow system color scheme."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

DARK_QSS = """
QMainWindow { background: #1e1e2e; }
QWidget { color: #d4d4d4; font-size: 13px; }
QGroupBox {
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
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
"""

LIGHT_QSS = """
QMainWindow { background: #f5f5f7; }
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
    """Default text colour of the receive pane for the effective theme."""
    return "#e0e0e0" if resolved_dark() else "#111111"


def tx_color() -> str:
    """Colour used to highlight echoed TX lines (blue/cyan, never red)."""
    return "#8be9fd" if resolved_dark() else "#1e5aa8"


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