"""Unit tests for app.protocol."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.protocol import (  # noqa: E402
    append_checksum,
    append_crc16_modbus,
    ascii_str_to_bytes,
    bytes_to_ascii_str,
    bytes_to_hex_str,
    crc16_ccitt,
    crc16_modbus,
    crc32,
    hex_str_to_bytes,
    modbus_read_holding_registers,
    parse_modbus_response,
    sum8,
    validate_crc,
)


class TestHexAscii:
    def test_hex_str_to_bytes_spaced(self):
        assert hex_str_to_bytes("01 03 00 00") == bytes([0x01, 0x03, 0x00, 0x00])

    def test_hex_str_to_bytes_compact(self):
        assert hex_str_to_bytes("01030000") == bytes([0x01, 0x03, 0x00, 0x00])

    def test_hex_str_to_bytes_empty(self):
        assert hex_str_to_bytes("") == b""

    def test_hex_str_to_bytes_odd_length_raises(self):
        try:
            hex_str_to_bytes("010")
        except ValueError:
            return
        raise AssertionError("expected ValueError")

    def test_bytes_to_hex_str(self):
        assert bytes_to_hex_str(b"\x01\x03\x0a") == "01 03 0A"

    def test_bytes_to_ascii_str_replaces_nonprintable(self):
        assert bytes_to_ascii_str(b"OK\x01") == "OK."

    def test_ascii_str_to_bytes_escapes(self):
        assert ascii_str_to_bytes(r"AT\r\n") == b"AT\r\n"


class TestCrc16Modbus:
    # Standard check value: CRC16-Modbus of "123456789" == 0x4B37
    def test_check_value(self):
        assert crc16_modbus(b"123456789") == 0x4B37

    def test_append_and_validate(self):
        frame = append_crc16_modbus(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x02]))
        assert len(frame) == 8
        assert validate_crc(frame)

    def test_validate_rejects_corrupted(self):
        frame = append_crc16_modbus(bytes([0x01, 0x03, 0x00]))
        bad = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        assert not validate_crc(bad)

    def test_validate_short_frame(self):
        assert not validate_crc(b"\x01\x03")


class TestChecksums:
    """Check value tests for the extra checksum modes (CRC16-CCITT, CRC32, SUM8)."""

    def test_crc16_ccitt_check_value(self):
        # Standard CRC16-CCITT (poly 0x1021, init 0xFFFF) of "123456789" == 0x29B1
        assert crc16_ccitt(b"123456789") == 0x29B1

    def test_crc32_check_value(self):
        # Standard CRC32 (IEEE 802.3) of "123456789" == 0xCBF43926
        assert crc32(b"123456789") == 0xCBF43926

    def test_sum8(self):
        # SUM8 of b"\x01\x02\x03" == 6
        assert sum8(b"\x01\x02\x03") == 6

    def test_sum8_wraps(self):
        # 0xFF + 0x01 -> 0x00 (mask to 8 bits)
        assert sum8(b"\xff\x01") == 0x00

    def test_append_checksum_modbus_low_first(self):
        frame = append_checksum(b"\x01\x03\x00\x00", "crc16-modbus")
        crc = crc16_modbus(b"\x01\x03\x00\x00")
        assert frame[-2:] == bytes((crc & 0xFF, (crc >> 8) & 0xFF))

    def test_append_checksum_ccitt_high_first(self):
        frame = append_checksum(b"\x01\x03\x00\x00", "crc16-ccitt")
        crc = crc16_ccitt(b"\x01\x03\x00\x00")
        assert frame[-2:] == bytes(((crc >> 8) & 0xFF, crc & 0xFF))

    def test_append_checksum_crc32_four_bytes(self):
        frame = append_checksum(b"hello", "crc32")
        assert len(frame) == len(b"hello") + 4
        assert frame[-4:] == crc32(b"hello").to_bytes(4, "big")

    def test_append_checksum_sum8_one_byte(self):
        frame = append_checksum(b"\x01\x02\x03", "sum8")
        assert frame[-1:] == b"\x06"

    def test_append_checksum_none_unchanged(self):
        assert append_checksum(b"\x01\x02", "none") == b"\x01\x02"


class TestModbusFrames:
    def test_read_holding_registers_layout(self):
        frame = modbus_read_holding_registers(1, 0, 2)
        # 01 03 00 00 00 02 + CRC(2)
        assert frame[:6] == bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x02])
        assert len(frame) == 8
        assert validate_crc(frame)

    def test_read_holding_registers_range(self):
        try:
            modbus_read_holding_registers(0, 0, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for addr 0")

        try:
            modbus_read_holding_registers(1, 0, 126)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for qty 126")

    def test_parse_response_ok(self):
        ok, desc, regs = parse_modbus_response(bytes([0x01, 0x03, 0x04, 0x00, 0x0A, 0x01, 0x2C, 0x00, 0x00]))
        assert ok
        assert regs == [10, 300]

    def test_parse_response_exception(self):
        ok, desc, regs = parse_modbus_response(bytes([0x01, 0x83, 0x02, 0xC0, 0xF1]))
        assert not ok
        assert "illegal data address" in desc
        assert regs == []

    def test_parse_response_short(self):
        ok, _, _ = parse_modbus_response(b"\x01\x03")
        assert not ok