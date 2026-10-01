"""Colour tokens for the QSS themes (U132 batch 1: value-preserving extraction).

Batch 1 keeps every rendered colour exactly as it was: one token per literal, named
after the role it plays today. Role splits (for example separating "disabled text"
from "surface") belong to the contrast batch, where the numbers actually change.

The QSS in ui/theme.py references these as ``$token`` and is rendered with
``string.Template.substitute`` — plain ``str.format`` cannot be used because QSS is
full of ``{`` / ``}``.
"""

from __future__ import annotations

#: Dark theme (the default look).
DARK_TOKENS: dict[str, str] = {
    "bg_base": "#1e1e2e",
    "surface_1": "#2d2d3d",
    "surface_input": "#16161f",
    "surface_disabled": "#2a2a35",
    "surface_pressed": "#2f2f3d",
    "surface_pressed_alt": "#2a2a3a",
    "scroll_track": "#23232f",
    "scroll_handle": "#4a4a5c",
    "border_muted": "#3a3a4a",
    "border_strong": "#4a4a5a",
    "border_hover": "#83839f",
    "border_hover_soft": "#838397",
    "border_hover_rail": "#83839f",
    "focus_border": "#33404f",
    "text_primary": "#d4d4d4",
    "text_strong": "#e0e0e0",
    "text_secondary": "#cfcfcf",
    "text_disabled": "#989898",
    "chip_text": "#a9a9bd",
    "accent": "#8be9fd",
    "selection_bg": "#4a6a9a",
    "selection_text": "#ffffff",
    "invalid": "#ff4136",
    "danger_disabled": "#8a8a8a",
    "danger_hover": "#ff938c",
    "check_bg": "#1f3a44",
    "check_border": "#4b8fa3",
    "check_bg_hover": "#27495a",
    "check_border_hover": "#63aec4",
    "check_bg_disabled": "#24343c",
    "check_border_disabled": "#598090",
    "check_border_off": "#5a5a6a",
    "check_border_off_disabled": "#717190",
}

#: Light theme.
LIGHT_TOKENS: dict[str, str] = {
    "bg_base": "#f5f5f7",
    "surface_1": "#ffffff",
    "surface_soft": "#ececf2",
    "surface_hover": "#e0e0e8",
    "surface_disabled": "#e8e8ee",
    "surface_pressed": "#d5d5e0",
    "surface_pressed_alt": "#dcdce4",
    "surface_secondary": "#f4f4f6",
    "surface_secondary_hover": "#e9e9ee",
    "scroll_handle": "#b8b8c4",
    "scroll_handle_hover": "#9090a0",
    "border_muted": "#d0d0d8",
    "border_strong": "#c8c8d0",
    "border_sep": "#d8d8e0",
    "border_hover": "#7f7f87",
    "border_hover_rail": "#7a7a80",
    "border_secondary": "#c9c9d1",
    "focus_bg": "#eaf2fb",
    "text_primary": "#1f1f1f",
    "text_strong": "#111111",
    "text_secondary": "#44444c",
    "text_disabled": "#636363",
    "chip_text": "#55556a",
    "accent": "#1e5aa8",
    "selection_bg": "#cfe0f5",
    "invalid": "#ff4136",
    "danger_disabled": "#707070",
    "danger_hover": "#c62828",
    "check_border": "#9dbfe8",
    "check_fill_hover": "#2a6fc4",
    "check_border_hover": "#b4d3f5",
    "check_fill_disabled": "#9db4cf",
    "check_border_disabled": "#54606e",
    "check_border_off": "#b0b0bc",
    "check_border_off_disabled": "#82828a",
}
