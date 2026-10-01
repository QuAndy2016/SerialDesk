"""Display formatting for the panes, as pure functions (no Qt).

Extracted from the window so the rules "what does a frame look like" can be
tested directly instead of through an offscreen QPlainTextEdit.
"""

from __future__ import annotations

import time

from app.protocol import bytes_to_hex_str, decode_text

MARK_RX = "<- "      # ASCII markers keep the monospace columns aligned (U26)
MARK_TX = "-> "

RX_ASCII = 0
RX_HEX = 1
RX_HEX_ASCII = 2


def format_payload(data: bytes, mode: int, encoding: str = "ascii") -> str:
    """Render bytes the way the receive pane shows them for the given mode."""
    if mode == RX_HEX:
        return bytes_to_hex_str(data)
    if mode == RX_ASCII:
        return decode_text(data, encoding)
    return "%s | %s" % (bytes_to_hex_str(data), decode_text(data, encoding))


def hex_separator(mode: int) -> str:
    """HEX needs a separator between appended fragments; plain ASCII does not."""
    return "" if mode == RX_ASCII else " "


def marker(tx: bool) -> str:
    """The three-character direction marker, so both columns share one baseline."""
    return MARK_TX if tx else MARK_RX


def timestamp_prefix(wall_ts: float, enabled: bool = True) -> str:
    """'[04:02:10.456] ' - fixed to milliseconds, or '' when the switch is off."""
    if not enabled:
        return ""
    ms = int((wall_ts - int(wall_ts)) * 1000)
    return time.strftime(f"[%H:%M:%S.{ms:03d}] ", time.localtime(wall_ts))


def line(text: str, ts_prefix: str = "", tx: bool = False) -> str:
    """One display line: optional timestamp, then the direction marker, then data."""
    return "%s%s%s" % (ts_prefix, marker(tx), text)
