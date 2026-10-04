"""Display formatting for the panes, as pure functions (no Qt).

Extracted from the window so the rules "what does a frame look like" can be
tested directly instead of through an offscreen QPlainTextEdit.
"""

from __future__ import annotations

import time

from app.protocol import bytes_to_hex_str, decode_text

MARK_RX = "<- "      # ASCII markers keep the monospace columns aligned
MARK_TX = "-> "

# Fragment kinds stamped on the receive document (and kept in the b store).
# Side (RX/TX) and meta (timestamp/direction marker) are separate bits, so the
# view filter can tell a TX marker from an RX one. The old 3-kind
# encoding conflated "meta" with "RX side", which let TX markers leak into
# "RX only" and hid TX timestamps in "TX only".
RX_PAYLOAD = 0
TX_PAYLOAD = 1
RX_MARK = 2
TX_MARK = 3


def frag_kind(tx: bool, meta: bool) -> int:
    """The fragment kind: side bit (TX=1) plus meta bit (timestamp/marker=2)."""
    return (1 if tx else 0) + (2 if meta else 0)


def kind_is_tx(kind: int) -> bool:
    """True when the fragment belongs to a sent (TX) line."""
    return bool(int(kind) & 1)


def kind_is_meta(kind: int) -> bool:
    """True for the dimmed timestamp/direction fragments."""
    return int(kind) >= 2


def fragment_visible(kind: int, mode: int) -> bool:
    """Whether a fragment survives the view filter (b: 0=all, 1=RX, 2=TX).

    The pane is filtered by line side, so a filter must keep the marker of the
    side it shows and drop the other side's marker - markers are not side-neutral.
    """
    if mode == 0:
        return True
    return kind_is_tx(kind) == (mode == 2)

def split_fragments(text: str, kind: int) -> list[tuple[str, int]]:
    """Store entries for one display fragment, with the newlines made explicit.

    A payload can carry '\n' of its own: an ASCII 0x0A byte, or the row breaks a
    hexdump adds. Keeping that inside one entry made the *document* show more
    lines than the *store* knew about, so the two disagreed about where a line
    ends - which is how "a line break that should not be there" (and rows glued
    together after a view rebuild) appeared. Splitting it here gives the store
    exactly the shape the pane renders.
    """
    if "\n" not in text:
        return [(text, kind)]
    out: list[tuple[str, int]] = []
    for i, part in enumerate(text.split("\n")):
        if i:
            out.append(("\n", kind))     # exactly where the pane breaks the line
        if part:
            out.append((part, kind))
    return out


def rows_from_fragments(store) -> list[list[tuple[str, int]]]:
    """Group the fragment stream into display rows - the single row model.

    The live pane and the view rebuild both walk this, so a "row" cannot mean
    two different things in the two places. Empty rows are kept: a blank line in
    the store is a blank line in the pane, and dropping it would shift every row
    below it. (Raised by the 2026-10-03 data-path pass.)
    """
    rows: list[list[tuple[str, int]]] = [[]]
    for text, kind in store:
        for piece, piece_kind in split_fragments(text, kind):
            if piece == "\n":
                rows.append([])
            else:
                rows[-1].append((piece, piece_kind))
    return rows


RX_ASCII = 0
RX_HEX = 1
RX_HEX_ASCII = 2
RX_COLUMN_HEX = 3     # c: classic hexdump columns (offset + 16 bytes + ASCII)

COL_WIDTH = 16
LONG_LINE_CHARS = 240     # above this, hovering shows the whole line


def long_line_tooltip(text: str, limit: int = LONG_LINE_CHARS) -> str | None:
    """Full line for a hover tooltip when it is very long.

    Long frames are read by scrolling horizontally (wrap off); the tooltip gives
    the whole line at once without touching the text that is displayed, so the
    copy semantics stay exactly as they are.
    """
    if len(text) <= limit:
        return None
    return text


def column_hex(data: bytes, offset: int = 0, width: int = COL_WIDTH):
    """Hexdump rows: offset, spaced hex bytes, ASCII gutter.

    Returns (text, next_offset) so a caller can keep the offset running across
    chunks (c). Pads the hex column so the ASCII gutter stays aligned.
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
