"""Colour tokens for the QSS themes (batch 1: value-preserving extraction).

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
    "border_hover_rail": "#83839f",
    "focus_border": "#33404f",
    #: Keyboard-focus ring. Deliberately quiet: the data panes are where the eye has to
    #: stay, and the brand accent measured 12.98:1 against #16161f - brighter than every
    #: other element in that area (normal border 1.61:1, focus tint 1.70:1, selection
    #: 1.76:1). This value keeps the >=3:1 non-text contrast the standard asks for at
    #: 4.30:1, i.e. the quietest colour that still counts as a visible indicator.
    "focus_ring": "#5f7f9f",
    "text_primary": "#d4d4d4",
    "text_strong": "#e0e0e0",
    "text_secondary": "#cfcfcf",
    "text_disabled": "#989898",
    "chip_text": "#a9a9bd",
    "accent": "#8be9fd",
    "selection_bg": "#4a6a9a",
    "selection_bg_text": "#33415c",     # text panes want a much quieter selection
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

    "scroll_handle": "#b8b8c4",
    "scroll_handle_hover": "#9090a0",
    "border_muted": "#d0d0d8",
    "border_strong": "#c8c8d0",
    "border_sep": "#d8d8e0",
    "border_hover": "#7f7f87",
    "border_hover_rail": "#7a7a80",
    "border_secondary": "#c9c9d1",
    "focus_bg": "#eaf2fb",
    #: Keyboard-focus ring, the light twin of the dark token. Deliberately NOT the accent:
    #: the accent measured 6.20:1 against #f5f5f7, and the parameter chip's hover border is
    #: the accent itself - using it for focus would make "focused" and "hovered" the same
    #: picture (rule D5). This value measures 4.73:1 on the base and 3.42:1 on the filled
    #: "More" button, i.e. the >=3:1 a non-text indicator needs, and stays quiet.
    "focus_ring": "#4a6f9c",
    "text_primary": "#1f1f1f",
    "text_strong": "#111111",
    "text_secondary": "#44444c",
    "text_disabled": "#636363",
    "chip_text": "#55556a",
    "accent": "#1e5aa8",
    "selection_bg": "#cfe0f5",
    "selection_bg_text": "#cfe0f5",     # same quiet blue on white
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

#: Type scale. Batch 3 extracts the values that were typed inline; nothing changes yet,
#: which is why the rendered sheets stay byte-identical to the snapshot.
#: Colours painted at runtime into the receive view (they are character formats, not
#: QSS rules): the received payload, the echo of a sent payload and the meta line.
#: The echo is deliberately NOT the brand accent - in the light theme they used to be
#: the same literal #1e5aa8, so "what I sent" and "the product colour" were identical.
#: Measured (tests/test_text_colours.py): hue distance to the accent >= 18 deg,
#: saturation below the accent's, contrast on the pane >= 4.5:1.
TEXT_COLOURS: dict[str, dict[str, str]] = {
    # colour convergence: the echo is a NEUTRAL cool gray-blue, not a second
    # brand colour - the accent (interaction) and the data colours (rx/echo/meta)
    # must not compete. Verified by tests/test_text_colours.py (hue >= 18 deg from
    # the accent, saturation <= the accent's, contrast on the pane >= 4.5:1).
    "dark": {"rx": "#c0c0c0", "echo": "#8f9fb2", "meta": "#7d8590"},
    "light": {"rx": "#111111", "echo": "#4f6a70", "meta": "#6d6d78"},
}

#: The background those runtime colours are painted on (QPlainTextEdit).
PANE_BG: dict[str, str] = {"dark": "#16161f", "light": "#ffffff"}

FONT_TOKENS: dict[str, str] = {
    "fs_badge": "9px",      # corner index on a quick-send row
    "fs_small": "12px",     # hints, property chips
    "fs_body": "13px",      # default text
    "fs_title": "15px",     # a pane's own name (one step above body, see #qsTitle)
    "fs_action": "15px",    # the round delete glyph
    "ff_mono": 'Consolas, "Courier New", monospace',
    "fw_title": "bold",
    "fw_medium": "500",     # e/T2: group titles sit between body (400) and bold
}
