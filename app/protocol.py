"""Protocol helpers: HEX/ASCII conversion, CRC16/CRC32/SUM8 checksums, Modbus RTU frames."""

from __future__ import annotations

import binascii
import zlib
from typing import Tuple

# ---------------------------------------------------------------------------
# HEX / ASCII
# ---------------------------------------------------------------------------

class HexFormatError(ValueError):
    """Malformed HEX text, with the exact offending position.

    kind: "empty" | "odd" | "bad_char" | "fullwidth" | "prefix"
    pos:  1-based position in the original text (None when kind == "empty")
    ch:   offending character (for bad_char / fullwidth / prefix)
    """

    def __init__(self, kind: str, pos: int | None = None, ch: str = ""):
        self.kind = kind
        self.pos = pos
        self.ch = ch
        super().__init__(f"hex format error: kind={kind} pos={pos} ch={ch!r}")


# Separators accepted between hex bytes: whitespace, comma, dash.
_HEX_SEPARATORS = " \t\r\n,;-"
_HEX_DIGITS = "0123456789abcdefABCDEF"


def _is_fullwidth_hex(ch: str) -> bool:
    """True for full-width forms like ０-９ / ａ-ｆ / ｘ (common with CN IME)."""
    o = ord(ch)
    return (
        0xFF10 <= o <= 0xFF19  # ０-９
        or 0xFF21 <= o <= 0xFF26  # Ａ-Ｆ
        or 0xFF41 <= o <= 0xFF46  # ａ-ｆ
        or ch in ("\uff58", "\uff38")  # ｘ Ｘ
    )


def hex_str_to_bytes(s: str) -> bytes:
    """Convert HEX text to bytes.

    Accepted forms: "01 03", "0103", "0x01 0x02", "0x0103", "01,03", "01-03",
    tab/newline separated, any letter case.

    Raises HexFormatError (a ValueError subclass) carrying the offending
    position, so the UI can point at the exact character.
    """
    if not s or not s.strip():
        return b""
    digits: list[str] = []
    positions: list[int] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in _HEX_SEPARATORS or ch.isspace():
            i += 1
            continue
        at_token_start = i == 0 or s[i - 1] in _HEX_SEPARATORS or s[i - 1].isspace()
        if ch == "0" and at_token_start and i + 1 < n and s[i + 1] in "xX":
            j = i + 2
            if j >= n or s[j] in _HEX_SEPARATORS or s[j].isspace() or not s[j] in _HEX_DIGITS:
                raise HexFormatError("prefix", i + 1, "0x")
            i = j
            continue
        if ch in _HEX_DIGITS:
            digits.append(ch)
            positions.append(i + 1)
            i += 1
            continue
        if _is_fullwidth_hex(ch):
            raise HexFormatError("fullwidth", i + 1, ch)
        raise HexFormatError("bad_char", i + 1, ch)
    if not digits:
        raise HexFormatError("empty")
    if len(digits) % 2:
        raise HexFormatError("odd", positions[-1])
    return binascii.unhexlify("".join(digits))


def bytes_to_hex_str(data: bytes, sep: str = " ") -> str:
    """Convert bytes to '01 03 00 00' style string."""
    return sep.join(f"{b:02X}" for b in data)


def bytes_to_ascii_str(data: bytes) -> str:
    """Decode bytes as ASCII for display; the line structure survives, the rest is '.'.

    2026-10-03 (data-path pass): tab / newline / carriage return used to be replaced by
    '.' along with every other control byte, which erased the line structure of every
    text protocol - a device sending "T=24.6C\\nVIN=12.12V\\n" showed as one glued
    line ("T=24.6C.VIN=12.12V."), and a 100 KB log became a single line for the pane to
    lay out. Those three are kept now (a 0x0A from the device *is* a line break); only
    the remaining non-printables become '.', which is what serial tools conventionally do.
    """
    return "".join(chr(b) if 32 <= b < 127 or b in (9, 10, 13) else "." for b in data)


def ascii_str_to_bytes(s: str) -> bytes:
    """Encode string to bytes, supporting \\xNN and \\r\\n escapes.

    Example: 'AT\\r\\n\\x01\\x02' -> b'AT\\r\\n\\x01\\x02'
    """
    return s.encode("utf-8").decode("unicode_escape").encode("latin-1")


# Text encodings offered for send/receive. "ascii" keeps the legacy
# byte-per-character view; the others decode/encode Chinese text properly.
TEXT_ENCODINGS = ("ascii", "utf-8", "gbk", "gb2312")

_ENCODING_ALIASES = {"ascii": "latin-1", "utf-8": "utf-8", "gbk": "gbk", "gb2312": "gb2312"}


def decode_text(data: bytes, encoding: str = "ascii") -> str:
    """Decode received bytes for display; non-printables become '.' in ascii mode."""
    if encoding == "ascii":
        return bytes_to_ascii_str(data)
    try:
        return data.decode(_ENCODING_ALIASES.get(encoding, encoding), errors="replace")
    except LookupError:
        return bytes_to_ascii_str(data)


def encode_text(s: str, encoding: str = "ascii", escapes: bool = True) -> bytes:
    """Encode typed text for sending.

    escapes=True keeps the historical behaviour (control escapes are interpreted);
    escapes=False sends the literal characters instead.
    """
    text = s.encode("utf-8").decode("unicode_escape") if escapes else s
    try:
        return text.encode(_ENCODING_ALIASES.get(encoding, encoding))
    except (UnicodeEncodeError, LookupError):
        return text.encode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Checksums: CRC16-Modbus / CRC16-CCITT / CRC32 / SUM8
# ---------------------------------------------------------------------------

def crc16_modbus(data: bytes, init: int = 0xFFFF) -> int:
    """Standard Modbus RTU CRC16 (poly 0x8005, reflected in/out)."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    """CRC16-CCITT (poly 0x1021, init 0xFFFF, non-reflected)."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def crc32(data: bytes) -> int:
    """Standard CRC-32 (IEEE 802.3), as zlib.crc32."""
    return zlib.crc32(data) & 0xFFFFFFFF


def sum8(data: bytes) -> int:
    """Simple 8-bit checksum: sum of all bytes masked to 0xFF."""
    return sum(data) & 0xFF


CHECKSUM_MODES = {
    "none": None,
    "crc16-modbus": crc16_modbus,
    "crc16-ccitt": crc16_ccitt,
    "crc32": crc32,
    "sum8": sum8,
}


def append_checksum(frame: bytes, mode: str) -> bytes:
    """Append checksum bytes to frame according to mode.

    Modes: none / crc16-modbus (low-first) / crc16-ccitt (high-first)
           / crc32 (big-endian, 4B) / sum8 (1B).
    Unknown mode raises ValueError.
    """
    fn = CHECKSUM_MODES.get(mode)
    if mode == "none" or fn is None:
        return frame
    value = fn(frame)
    if mode == "crc16-modbus":
        return frame + bytes((value & 0xFF, (value >> 8) & 0xFF))
    if mode == "crc16-ccitt":
        return frame + bytes(((value >> 8) & 0xFF, value & 0xFF))
    if mode == "crc32":
        return frame + value.to_bytes(4, "big")
    if mode == "sum8":
        return frame + bytes((value,))
    raise ValueError(f"unknown checksum mode: {mode}")


def append_crc16_modbus(frame: bytes) -> bytes:
    """Append CRC16-Modbus to a byte frame (low byte first)."""
    return append_checksum(frame, "crc16-modbus")


# ---------------------------------------------------------------------------
# Modbus RTU frames
# ---------------------------------------------------------------------------

def modbus_read_holding_registers(
    slave_addr: int, start_reg: int, qty: int
) -> bytes:
    """Build Modbus RTU frame: 01 03 0000 0002 CRCLO CRCHI."""
    if not (1 <= slave_addr <= 247):
        raise ValueError("slave address must be 1..247")
    if qty < 1 or qty > 125:
        raise ValueError("quantity must be 1..125")
    frame = bytes((slave_addr, 0x03)) + start_reg.to_bytes(2, "big") + qty.to_bytes(2, "big")
    return append_checksum(frame, "crc16-modbus")


def parse_modbus_response(data: bytes) -> Tuple[bool, str, list]:
    """Parse a Modbus RTU response.

    Returns (ok, description, registers_or_errors).
    For exception responses, returns codes 0x80|fn.
    """
    if len(data) < 5:
        return False, "short frame", []
    fn = data[1]
    if fn & 0x80:
        exc = data[2]
        desc = {
            0x01: "illegal function",
            0x02: "illegal data address",
            0x03: "illegal data value",
            0x04: "server device failure",
        }.get(exc, f"unknown exception {exc}")
        return False, f"exception 0x{exc:02X}: {desc}", []
    if fn == 0x03:
        byte_count = data[2]
        if len(data) < 3 + byte_count + 2:
            return False, "truncated data", []
        payload = data[3 : 3 + byte_count]
        registers = [
            (payload[i] << 8) | payload[i + 1] for i in range(0, byte_count, 2)
        ]
        return True, f"read {len(registers)} regs", registers
    return False, f"unsupported fn 0x{fn:02X}", []


def validate_crc(frame: bytes) -> bool:
    """Check that the last two bytes of frame match CRC16-Modbus."""
    if len(frame) < 4:
        return False
    body, crc_bytes = frame[:-2], frame[-2:]
    expected = crc16_modbus(body)
    return crc_bytes == bytes((expected & 0xFF, (expected >> 8) & 0xFF))