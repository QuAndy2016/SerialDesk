"""Theme management: dark/light QSS palettes, follow system color scheme."""
from __future__ import annotations


from string import Template

from ui.tokens import DARK_TOKENS, FONT_TOKENS, LIGHT_TOKENS, TEXT_COLOURS

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from typing import Callable

_DARK_QSS_TEMPLATE = """
QMainWindow { background: $bg_base; }
QDialog { background: $bg_base; }
QLabel#payloadHint { font-size: $fs_small; }
QFrame#vSep { background: $border_muted; }
QWidget { color: $text_primary; font-size: $fs_body; }
QGroupBox {
    border: 1px solid $border_muted;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 2px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: $accent;
    font-weight: $fw_title;
}
QPushButton {
    background: $border_muted;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 5px 14px;
}
QPushButton:hover { background: $border_strong; }
QPushButton:pressed { background: $surface_pressed_alt; }
QPushButton:disabled { color: $text_disabled; background: $surface_disabled; }
QPushButton[secondary="true"] { background: $surface_1; border: 1px solid $border_strong; color: $text_secondary; }
QPushButton[secondary="true"]:hover { background: $border_muted; border-color: $border_hover_soft; }
QComboBox, QLineEdit {
    background: $surface_1;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 3px 8px;
}
QComboBox:hover, QLineEdit:hover { border-color: $accent; }
/* U122: a visible keyboard focus ring (WCAG 2.4.7) - a tint plus the accent border,
   which is distinguishable from :hover on the same controls */
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus { border: 1px solid $accent; background: $focus_border; }
QPushButton:focus, QToolButton:focus { border: 1px solid $accent; }
QCheckBox:focus { color: $accent; }
QLabel#statusCounters { font-family: $ff_mono; }
QComboBox::drop-down { border: none; border-left: 1px solid $border_strong; width: 22px; }
QComboBox::down-arrow { image: url(__ASSETS__/arrow_down_dark.png); width: 10px; height: 6px; }
QComboBox[invalid="true"] { border: 1px solid $invalid; }
QComboBox QAbstractItemView {
    background: $surface_1;
    color: $text_primary;
    selection-background-color: $selection_bg;
}
QSpinBox {
    background: $surface_1;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 3px 6px;
}
QSpinBox:hover { border-color: $accent; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url(__ASSETS__/arrow_up_dark.png); width: 8px; height: 5px; }
QSpinBox::down-arrow { image: url(__ASSETS__/arrow_down_dark.png); width: 8px; height: 5px; }
QPlainTextEdit {
    background: $surface_input;
    border: 1px solid $border_muted;
    border-radius: 4px;
    color: $text_strong;
    font-family: $ff_mono;
    font-size: $fs_body;
}
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; }
QStatusBar { background: $surface_1; }
QStatusBar::item { border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMenuBar { background: $bg_base; color: $text_primary; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: $border_muted; }
QMenu { background: $surface_1; color: $text_primary; border: 1px solid $border_strong; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 28px; border-radius: 4px; }
QMenu::item:selected { background: $selection_bg; color: $selection_text; }
QMenu::separator { height: 1px; background: $border_strong; margin: 4px 8px; }
QSplitter::handle { background: $border_muted; }
QPushButton#qsDel { color: $danger_disabled; background: transparent; border: none; font-size: $fs_action; }
QPushButton#qsDel:hover { color: $danger_hover; background: $border_muted; border-radius: 4px; }
QToolButton#paramsBtn { color: $text_primary; background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 3px 8px; }
QToolButton#paramsBtn:hover { border-color: $accent; }
/* U110: the settings entry is an app-level control - icon + text, a real border,
   a 32 px hit target and three states, separated from the connection parameters */
QToolButton#settingsBtn { color: $text_primary; background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 3px 10px; margin: 0 0 0 8px; qproperty-icon: url(__ASSETS__/gear_dark.png); qproperty-iconSize: 14px 14px; }
QToolButton#settingsBtn:hover { background: $border_muted; border-color: $border_hover; }
QToolButton#settingsBtn:pressed, QToolButton#settingsBtn:checked { background: $surface_pressed; border-color: $accent; }
QFrame#connDivider { background: $border_strong; max-width: 1px; border: none; }
/* U106: quick-send panel fold/unfold - a themed icon button, both directions */
QToolButton#qsCollapse { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 3px 4px; qproperty-icon: url(__ASSETS__/arrow_left_dark.png); qproperty-iconSize: 8px 12px; }
QToolButton#qsCollapse:hover { background: $border_muted; border-color: $border_hover_rail; }
/* U118/U121: the property chip (row properties, send options) */
QToolButton#qsChip { color: $chip_text; background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 2px 8px; font-size: $fs_small; }
QToolButton#qsChip:hover { color: $text_primary; border-color: $border_hover; background: $border_muted; }
QToolButton#qsChip::menu-indicator { image: none; width: 0px; }
/* U120: the quick-send panel toggle beside Settings */
QToolButton#panelToggle { background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 3px 6px; margin: 0 4px 0 0; qproperty-iconSize: 8px 12px; }
QToolButton#panelToggle:hover { background: $border_muted; border-color: $border_hover; }
QToolButton#panelToggle:checked { background: $surface_pressed; border-color: $accent; }
QToolButton#qsRail { background: transparent; border: 1px solid transparent; border-left: 1px solid $border_strong; border-radius: 0px; padding: 6px 2px; qproperty-icon: url(__ASSETS__/arrow_right_dark.png); qproperty-iconSize: 8px 12px; }
QToolButton#qsRail:hover { background: $border_muted; border-color: $border_hover_rail; border-left-color: $border_hover; }
QToolButton#settingsBtn::menu-indicator { image: none; width: 0px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid $check_border_off; border-radius: 3px; background: $surface_input; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $check_bg; border-color: $check_border; image: url(__ASSETS__/check_accent.png); }
QCheckBox::indicator:checked:hover { background: $check_bg_hover; border-color: $check_border_hover; }
QCheckBox::indicator:disabled { border-color: $check_border_off_disabled; background: $surface_disabled; }
QCheckBox::indicator:checked:disabled { background: $check_bg_disabled; border-color: $check_border_disabled; }
QScrollBar:vertical { background: $scroll_track; width: 13px; margin: 0px; }
QScrollBar::handle:vertical { background: $scroll_handle; min-height: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: $border_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: $scroll_track; height: 13px; margin: 0px; }
QScrollBar::handle:horizontal { background: $scroll_handle; min-width: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: $border_hover; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QLabel#seqOrd { color: $accent; font-size: $fs_badge; font-weight: $fw_title; background: transparent; }   /* U80: corner badge */
QFrame#qsRow { border: 1px solid transparent; border-radius: 4px; }
QFrame#qsRow[selected="true"] { background: rgba(210, 210, 225, 0.10); border: 1px solid rgba(210, 210, 225, 0.28); }   /* U114-D7: neutral, not the TX blue */
"""

def _render(template: str, tokens: dict[str, str]) -> str:
    """Fill $token placeholders in a QSS template."""
    return Template(template).substitute(tokens)


_LIGHT_QSS_TEMPLATE = """
QMainWindow { background: $bg_base; }
QDialog { background: $bg_base; }
QLabel#payloadHint { font-size: $fs_small; }
QFrame#vSep { background: $border_sep; }
QWidget { color: $text_primary; font-size: $fs_body; }
QGroupBox {
    border: 1px solid $border_muted;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: $accent;
    font-weight: $fw_title;
}
QPushButton {
    background: $surface_1;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 5px 14px;
}
QPushButton:hover { background: $surface_soft; }
QPushButton:pressed { background: $surface_pressed_alt; }
QPushButton:disabled { color: $text_disabled; background: $surface_disabled; }
QPushButton[secondary="true"] { background: $surface_secondary; border: 1px solid $border_secondary; color: $text_secondary; }
QPushButton[secondary="true"]:hover { background: $surface_secondary_hover; border-color: $border_hover; }
QComboBox, QLineEdit {
    background: $surface_1;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 3px 8px;
}
QComboBox:hover, QLineEdit:hover { border-color: $accent; }
/* U122: see the dark theme */
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus { border: 1px solid $accent; background: $focus_bg; }
QPushButton:focus, QToolButton:focus { border: 1px solid $accent; }
QCheckBox:focus { color: $accent; }
QLabel#statusCounters { font-family: $ff_mono; }
QComboBox::drop-down { border: none; border-left: 1px solid $border_strong; width: 22px; }
QComboBox::down-arrow { image: url(__ASSETS__/arrow_down_light.png); width: 10px; height: 6px; }
QComboBox[invalid="true"] { border: 1px solid $invalid; }
QComboBox QAbstractItemView {
    background: $surface_1;
    color: $text_primary;
    selection-background-color: $selection_bg;
}
QSpinBox {
    background: $surface_1;
    border: 1px solid $border_strong;
    border-radius: 4px;
    padding: 3px 6px;
}
QSpinBox:hover { border-color: $accent; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url(__ASSETS__/arrow_up_light.png); width: 8px; height: 5px; }
QSpinBox::down-arrow { image: url(__ASSETS__/arrow_down_light.png); width: 8px; height: 5px; }
QPlainTextEdit {
    background: $surface_1;
    border: 1px solid $border_muted;
    border-radius: 4px;
    color: $text_strong;
    font-family: $ff_mono;
    font-size: $fs_body;
}
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; }
QStatusBar { background: $surface_disabled; }
QStatusBar::item { border: none; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMenuBar { background: $bg_base; color: $text_primary; }
QMenuBar::item { background: transparent; padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: $surface_hover; }
QMenu { background: $surface_1; color: $text_primary; border: 1px solid $border_strong; padding: 4px; }
QMenu::item { padding: 5px 24px 5px 28px; border-radius: 4px; }
QMenu::item:selected { background: $selection_bg; color: $text_strong; }
QMenu::separator { height: 1px; background: $border_muted; margin: 4px 8px; }
QSplitter::handle { background: $border_muted; }
QPushButton#qsDel { color: $danger_disabled; background: transparent; border: none; font-size: $fs_action; }
QPushButton#qsDel:hover { color: $danger_hover; background: $surface_soft; border-radius: 4px; }
QToolButton#paramsBtn { color: $text_primary; background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 3px 8px; }
QToolButton#paramsBtn:hover { border-color: $accent; }
/* U110: see the dark theme */
QToolButton#settingsBtn { color: $text_primary; background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 3px 10px; margin: 0 0 0 8px; qproperty-icon: url(__ASSETS__/gear_light.png); qproperty-iconSize: 14px 14px; }
QToolButton#settingsBtn:hover { background: $surface_hover; border-color: $border_hover; }
QToolButton#settingsBtn:pressed, QToolButton#settingsBtn:checked { background: $surface_pressed; border-color: $accent; }
QFrame#connDivider { background: $border_strong; max-width: 1px; border: none; }
/* U106: quick-send panel fold/unfold - a themed icon button, both directions */
QToolButton#qsCollapse { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 3px 4px; qproperty-icon: url(__ASSETS__/arrow_left_light.png); qproperty-iconSize: 8px 12px; }
QToolButton#qsCollapse:hover { background: $surface_hover; border-color: $border_hover_rail; }
/* U118/U121: the property chip (row properties, send options) */
QToolButton#qsChip { color: $chip_text; background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 2px 8px; font-size: $fs_small; }
QToolButton#qsChip:hover { color: $text_primary; border-color: $border_hover; background: $surface_hover; }
QToolButton#qsChip::menu-indicator { image: none; width: 0px; }
/* U120: the quick-send panel toggle beside Settings */
QToolButton#panelToggle { background: transparent; border: 1px solid $border_strong; border-radius: 4px; padding: 3px 6px; margin: 0 4px 0 0; qproperty-iconSize: 8px 12px; }
QToolButton#panelToggle:hover { background: $surface_hover; border-color: $border_hover; }
QToolButton#panelToggle:checked { background: $surface_pressed; border-color: $accent; }
QToolButton#qsRail { background: transparent; border: 1px solid transparent; border-left: 1px solid $border_strong; border-radius: 0px; padding: 6px 2px; qproperty-icon: url(__ASSETS__/arrow_right_light.png); qproperty-iconSize: 8px 12px; }
QToolButton#qsRail:hover { background: $surface_hover; border-color: $border_hover_rail; border-left-color: $border_hover; }
QToolButton#settingsBtn::menu-indicator { image: none; width: 0px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid $check_border_off; border-radius: 3px; background: $surface_1; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $check_border; image: url(__ASSETS__/check_light.png); }
QCheckBox::indicator:checked:hover { background: $check_fill_hover; border-color: $check_border_hover; }
QCheckBox::indicator:disabled { border-color: $check_border_off_disabled; background: $surface_soft; }
QCheckBox::indicator:checked:disabled { background: $check_fill_disabled; border-color: $check_border_disabled; }
QScrollBar:vertical { background: $surface_soft; width: 13px; margin: 0px; }
QScrollBar::handle:vertical { background: $scroll_handle; min-height: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: $scroll_handle_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: $surface_soft; height: 13px; margin: 0px; }
QScrollBar::handle:horizontal { background: $scroll_handle; min-width: 30px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: $scroll_handle_hover; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QLabel#seqOrd { color: $accent; font-size: $fs_badge; font-weight: $fw_title; background: transparent; }   /* U80: corner badge */
QFrame#qsRow { border: 1px solid transparent; border-radius: 4px; }
QFrame#qsRow[selected="true"] { background: rgba(70, 70, 100, 0.08); border: 1px solid rgba(70, 70, 100, 0.20); }   /* U114-D7: neutral, not the TX blue */
"""

DARK_QSS = _render(_DARK_QSS_TEMPLATE, {**DARK_TOKENS, **FONT_TOKENS})
LIGHT_QSS = _render(_LIGHT_QSS_TEMPLATE, {**LIGHT_TOKENS, **FONT_TOKENS})


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
    return TEXT_COLOURS["dark" if resolved_dark() else "light"]["rx"]


def tx_color() -> str:
    """Colour used to highlight echoed TX data (calm blue, never red, never the accent)."""
    return TEXT_COLOURS["dark" if resolved_dark() else "light"]["echo"]


def meta_color() -> str:
    """Timestamp + direction marker colour: dimmer than the payload (U62)."""
    return TEXT_COLOURS["dark" if resolved_dark() else "light"]["meta"]


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


def find_colors() -> dict:
    """Find-bar highlight colours for the receive pane (runtime, not QSS).

    Current hit uses the same measured selection pair as the history list
    (dark #ffffff on #4a6a9a = 8.3:1, light #111111 on #cfe0f5 = 15.4:1).
    Other hits use a dimmed variant of the same hue, still >= 4.5:1 on text.
    """
    if resolved_dark():
        return {"current_bg": "#4a6a9a", "current_fg": "#ffffff",
                "other_bg": "#3a4a6a", "other_fg": "#d4d4d4"}
    return {"current_bg": "#cfe0f5", "current_fg": "#111111",
            "other_bg": "#dde6f2", "other_fg": "#111111"}


def watch_system_theme(app: QApplication, callback: Callable[[str], None]) -> None:
    """Notify callback(dark: bool) when OS theme changes, unless overridden.

    When a manual override is active, system changes are ignored so the
    manual choice stays fixed. Clearing override (None) resumes following.
    """
    hints = QGuiApplication.styleHints()
    try:
        def _on_system_change(scheme: str):
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


def apply_native_dark(widget: QWidget, dark: bool) -> None:
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
