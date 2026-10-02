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
RX_COLUMN_HEX = 3     # U163c: classic hexdump columns (offset + 16 bytes + ASCII)

COL_WIDTH = 16
LONG_LINE_CHARS = 240     # U129-A4: above this, hovering shows the whole line


def long_line_tooltip(text: str, limit: int = LONG_LINE_CHARS) -> str | None:
    """Full line for a hover tooltip when it is very long (U129-A4).

    Long frames are read by scrolling horizontally (wrap off); the tooltip gives
    the whole line at once without touching the text that is displayed, so the
    copy semantics (U162) stay exactly as they are.
    """
    if len(text) <= limit:
        return None
    return text


def column_hex(data: bytes, offset: int = 0, width: int = COL_WIDTH):
    """Hexdump rows: offset, spaced hex bytes, ASCII gutter.

    Returns (text, next_offset) so a caller can keep the offset running across
    chunks (U163c). Pads the hex column so the ASCII gutter stays aligned.
    """
    rows = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join("%02X" % b for b in chunk).ljust(width * 3 - 1)
        gutter = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        rows.append("%08X  %s  |%s|" % (offset + i, hex_part, gutter))
    return "\n".join(rows), offset + len(data)


def format_payload(data: bytes, mode: int, encoding: str = "ascii") -> str:
    """Render bytes the way the receive pane shows them for the given mode."""
    if mode == RX_HEX:
        return bytes_to_hex_str(data)
    if mode == RX_ASCII:
        return decode_text(data, encoding)
    if mode == RX_COLUMN_HEX:
        return column_hex(data, 0)[0]
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
