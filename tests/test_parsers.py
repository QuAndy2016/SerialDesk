"""Declarative frame kernel: byte-level assertions for the three templates."""

from __future__ import annotations

import os
import random
import struct
import subprocess
import sys
import time

import pytest

from app import parse_templates as tmpl
from app.parsers import (
    ERR_CHECKSUM,
    ERR_FIELD,
    ERR_TRUNCATED,
    ERR_UNKNOWN_FUNCTION,
    checksum_value,
    parse_frame,
    split_stream,
    xor8,
)
from app.parserspec import BitField, ChecksumSpec, FieldSpec, FrameSpec
from app.protocol import append_checksum

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modbus_request_03() -> bytes:
    """01 03 0000 0002 = read 2 holding registers, CRC appended by the app's own helper."""
    return append_checksum(bytes((0x01, 0x03, 0x00, 0x00, 0x00, 0x02)), "crc16-modbus")


def _modbus_response_03(values=(0x1234, 0xABCD)) -> bytes:
    payload = b"".join(v.to_bytes(2, "big") for v in values)
    body = bytes((0x01, 0x03, len(payload))) + payload
    return append_checksum(body, "crc16-modbus")


def _modbus_request_10() -> bytes:
    payload = bytes((0x00, 0x0A, 0x01, 0x02))       # two registers
    body = bytes((0x01, 0x10, 0x00, 0x00, 0x00, 0x02, len(payload))) + payload
    return append_checksum(body, "crc16-modbus")


# --- checksums ------------------------------------------------------------

def test_checksum_vectors_match_published_check_values():
    # The standard check input for a CRC is the ASCII string "123456789".
    assert checksum_value("crc16-modbus", b"123456789") == 0x4B37
    assert checksum_value("crc16-ccitt", b"123456789") == 0x29B1
    assert checksum_value("crc32", b"123456789") == 0xCBF43926
    assert checksum_value("none", b"anything") is None


def test_xor8_bcc_and_sum8():
    assert xor8(b"") == 0
    assert xor8(b"\x01\x02\x03") == 0x00
    assert checksum_value("bcc", b"\x01\x02\x03") == checksum_value("xor8", b"\x01\x02\x03")
    assert checksum_value("sum8", b"\x01\x02\x03") == 6


# --- split_stream ---------------------------------------------------------

def test_split_fixed_frames_keeps_partial_in_rest():
    spec = FrameSpec(name="fixed", length_mode="fixed", frame_size=4)
    frames, rest = split_stream(spec, b"AAAABBBBCC")
    assert frames == [b"AAAA", b"BBBB"]
    assert rest == b"CC"


def test_split_uses_length_field():
    spec = tmpl.modbus_rtu_response(0x03)
    two = _modbus_response_03()
    three = _modbus_response_03((1, 2, 3))
    frames, rest = split_stream(spec, two + three + b"\x01\x03")
    assert frames == [two, three]
    assert rest == b"\x01\x03"


def test_split_delimiter_frames():
    spec = tmpl.nmea_0183()
    a = b"$GPGGA,1,2*00\r\n"
    b = b"$GPRMC,3*00\r\n"
    frames, rest = split_stream(spec, a + b + b"$GP")
    assert frames == [a, b]
    assert rest == b"$GP"


def test_split_resync_drops_junk_but_keeps_partial_header():
    spec = tmpl.nmea_0183()
    frames, rest = split_stream(spec, b"junk$GPGGA,1*00\r\n$")
    assert frames == [b"$GPGGA,1*00\r\n"]
    assert rest == b"$"          # could still become a header


# --- Modbus RTU -----------------------------------------------------------

def test_parse_modbus_read_request():
    values, status = parse_frame(tmpl.modbus_rtu_request(0x03), _modbus_request_03())
    assert status["ok"] and status["errors"] == []
    assert values == {"slave": 1, "function": 3, "start": 0, "quantity": 2}


def test_parse_modbus_read_response_variable_length():
    values, status = parse_frame(tmpl.modbus_rtu_response(0x03), _modbus_response_03())
    assert status["ok"]
    assert values["byte_count"] == 4
    assert values["data"] == b"\x12\x34\xab\xcd"


def test_parse_modbus_write_multiple_request_variable_length():
    values, status = parse_frame(tmpl.modbus_rtu_request(0x10), _modbus_request_10())
    assert status["ok"]
    assert values["quantity"] == 2 and values["byte_count"] == 4
    assert values["data"] == b"\x00\x0a\x01\x02"


def test_parse_modbus_bad_crc_is_structured_error():
    frame = bytearray(_modbus_request_03())
    frame[-1] ^= 0xFF
    values, status = parse_frame(tmpl.modbus_rtu_request(0x03), bytes(frame))
    assert not status["ok"]
    assert status["errors"][0]["code"] == ERR_CHECKSUM


def test_parse_modbus_truncated_is_structured_error():
    values, status = parse_frame(tmpl.modbus_rtu_request(0x03), _modbus_request_03()[:5])
    assert not status["ok"]
    assert status["errors"][0]["code"] == ERR_TRUNCATED


def test_parse_modbus_unknown_function_is_structured_error():
    frame = bytes((0x01, 0x11, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00))
    values, status = tmpl.parse_modbus_frame(frame)
    assert values == {} and not status["ok"]
    assert status["errors"][0]["code"] == ERR_UNKNOWN_FUNCTION
    assert status["errors"][0]["function_code"] == 0x11


def test_modbus_dispatcher_picks_request_and_response():
    v1, s1 = tmpl.parse_modbus_frame(_modbus_request_03())
    v2, s2 = tmpl.parse_modbus_frame(_modbus_response_03())
    assert s1["ok"] and s2["ok"]
    assert "quantity" in v1 and "data" in v2


# --- typed fields ---------------------------------------------------------

def test_bits_field_is_decoded_by_name():
    spec = tmpl.bit_field_example()
    frame = bytes((0b0000_1101, 0x12, 0x34))
    values, status = parse_frame(spec, frame)
    assert status["ok"]
    assert values["status"] == {"run": 1, "fault": 0, "ready": 1, "mode": 1}
    assert values["counter"] == 0x1234


@pytest.mark.parametrize("ftype, endian, value, raw", [
    ("f32", "be", 1.5, struct.pack(">f", 1.5)),
    ("f32", "le", -2.25, struct.pack("<f", -2.25)),
    ("f64", "be", 3.141592653589793, struct.pack(">d", 3.141592653589793)),
    ("f64", "le", -0.5, struct.pack("<d", -0.5)),
    ("u16", "be", 0x1234, b"\x12\x34"),
    ("u16", "le", 0x1234, b"\x34\x12"),
    ("i32", "be", -2, (-2).to_bytes(4, "big", signed=True)),
    ("u64", "le", 0x0102030405060708, (0x0102030405060708).to_bytes(8, "little")),
])
def test_numeric_types_and_endianness(ftype, endian, value, raw):
    spec = FrameSpec(name="one", length_mode="fixed", frame_size=len(raw),
                     checksum=ChecksumSpec(kind="none"),
                     fields=(FieldSpec("v", ftype, endian=endian),))
    values, status = parse_frame(spec, raw)
    assert status["ok"]
    assert values["v"] == pytest.approx(value)


def test_scale_and_bias_are_applied():
    spec = FrameSpec(name="scaled", length_mode="fixed", frame_size=2,
                     checksum=ChecksumSpec(kind="none"),
                     fields=(FieldSpec("t", "u16", scale=0.1, bias=-40.0),))
    values, status = parse_frame(spec, (850).to_bytes(2, "big"))
    assert status["ok"] and values["t"] == pytest.approx(45.0)


# --- text protocols -------------------------------------------------------

def test_parse_at_command_line():
    spec = tmpl.at_line()
    values, status = parse_frame(spec, b"AT+CGMR\r\n")
    assert status["ok"] and values["command"] == "AT+CGMR" and values["args"] == ""


def test_parse_at_response_line_keeps_arguments():
    spec = tmpl.at_line()
    values, status = parse_frame(spec, b"+CSQ: 20,99\r\n")
    assert status["ok"]
    assert values["command"] == "+CSQ:" and values["args"] == "20,99"


def test_parse_nmea_sentence_pinned_vector():
    """$GPGGA,...*47 - the checksum 0x47 of this widely used example is the XOR of the
    characters between '$' and '*' (recomputed here as an independent check)."""
    body = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,"
    assert xor8(body.encode("latin-1")) == 0x47
    frame = ("$%s*47\r\n" % body).encode("latin-1")
    values, status = parse_frame(tmpl.nmea_0183(), frame)
    assert status["ok"], status
    assert values["type"] == "GPGGA"
    assert values["f1"] == "123519"
    # token 0 is the sentence type, so body field n sits at f<n>: "0.9" is f8 and the
    # altitude 545.4 is f9 (13 Sept 2000 GGA layout).
    assert values["f8"] == "0.9"
    assert values["f9"] == "545.4"


def test_parse_nmea_bad_checksum_is_reported():
    frame = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*48\r\n"
    values, status = parse_frame(tmpl.nmea_0183(), frame)
    assert not status["ok"]
    assert status["errors"][0]["code"] == ERR_CHECKSUM


def test_parse_nmea_missing_checksum_is_reported():
    frame = b"$GPGGA,123519\r\n"
    values, status = parse_frame(tmpl.nmea_0183(), frame)
    assert not status["ok"]
    assert status["errors"][0]["code"] == ERR_TRUNCATED


def test_short_nmea_sentence_parses_without_optional_fields():
    body = b"GPRMC,123519,A"
    frame = b"$" + body + ("*%02X\r\n" % xor8(body)).encode("ascii")
    values, status = parse_frame(tmpl.nmea_0183(), frame)
    assert status["ok"]
    assert values["type"] == "GPRMC" and "f4" not in values


# --- contract: purity, robustness, budget ---------------------------------

def test_parsers_never_raise_on_garbage():
    specs = [tmpl.modbus_rtu_request(0x03), tmpl.modbus_rtu_response(0x03),
             tmpl.modbus_rtu_request(0x10), tmpl.nmea_0183(), tmpl.at_line(),
             tmpl.bit_field_example()]
    rng = random.Random(20261003)
    for _ in range(200):
        blob = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 40)))
        for spec in specs:
            values, status = parse_frame(spec, blob)
            assert isinstance(values, dict) and isinstance(status["ok"], bool)
        values, status = tmpl.parse_modbus_frame(blob)
        assert isinstance(status["errors"], list)


def test_parsers_do_not_pull_in_pyside6():
    code = ("import sys, app.parsers, app.parserspec, app.parse_templates; "
            "bad = [m for m in sys.modules if m.split('.')[0] == 'PySide6']; "
            "print('BAD:' + ','.join(bad) if bad else 'CLEAN')")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "CLEAN", out.stdout


def test_parse_throughput_budget():
    """A 256-byte frame must decode well inside the plan's 50 us budget (2x tolerance)."""
    spec = FrameSpec(
        name="bench", endian="be", length_mode="fixed", frame_size=256,
        min_frame_size=256, checksum=ChecksumSpec(kind="crc32", size=4, endian="be"),
        fields=tuple([FieldSpec("w%d" % i, "u32") for i in range(63)]),
    )
    payload = b"".join(i.to_bytes(4, "big") for i in range(63))
    frame = append_checksum(payload, "crc32")
    assert len(frame) == 256
    values, status = parse_frame(spec, frame)
    assert status["ok"] and len(values) == 63

    runs = 2000
    start = time.perf_counter()
    for _ in range(runs):
        parse_frame(spec, frame)
    per_frame_us = (time.perf_counter() - start) / runs * 1e6
    assert per_frame_us <= 100.0, "%0.1f us per 256-byte frame" % per_frame_us


def test_parse_reports_bad_length_reference():
    spec = FrameSpec(name="needs-length", length_mode="fixed", frame_size=4,
                     checksum=ChecksumSpec(kind="none"),
                     fields=(FieldSpec("body", "bytes", length_field="missing"),))
    values, status = parse_frame(spec, b"\x01\x02\x03\x04")
    assert not status["ok"]
    assert status["errors"][0]["code"] in (ERR_TRUNCATED, "bad_length")
