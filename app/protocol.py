"""Protocol helpers: HEX/ASCII conversion, CRC16/CRC32/SUM8 checksums, Modbus RTU frames."""

from __future__ import annotations

import binascii
import zlib
from typing import Tuple

# ---------------------------------------------------------------------------
# HEX / ASCII
# ---------------------------------------------------------------------------

def hex_str_to_bytes(s: str) -> bytes:
    """Convert '01 03 00 00 00 02' or '010300000002' to bytes.

    Raises ValueError on malformed input.
    """
    cleaned = "".join(s.split())
    if not cleaned:
        return b""
    if len(cleaned) % 2 != 0:
        raise ValueError("HEX string length must be even")
    return binascii.unhexlify(cleaned)


def bytes_to_hex_str(data: bytes, sep: str = " ") -> str:
    """Convert bytes to '01 03 00 00' style string."""
    return sep.join(f"{b:02X}" for b in data)


def bytes_to_ascii_str(data: bytes) -> str:
    """Decode bytes as ASCII, replacing non-printable chars with '.'."""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def ascii_str_to_bytes(s: str) -> bytes:
    """Encode string to bytes, supporting \\xNN and \\r\\n escapes.

    Example: 'AT\\r\\n\\x01\\x02' -> b'AT\\r\\n\\x01\\x02'
    """
    return s.encode("utf-8").decode("unicode_escape").encode("latin-1")


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