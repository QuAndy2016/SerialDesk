"""Declarative frame kernel (B4-P1): cut a stream, decode fields, verify the checksum.

Qt-free and side-effect free: `split_stream` holds no state (the caller owns the buffer),
`parse_frame` returns a structured status instead of raising, so a truncated or corrupt
frame from a real device can never take the app down.

Checksums reuse app/protocol.py (the app's single source for CRC16/CRC32/SUM8) and add
xor8/BCC, which is just the XOR of the covered bytes.
"""

from __future__ import annotations

import struct

from app.protocol import crc16_ccitt, crc16_modbus, crc32, sum8
from app.parserspec import (
    ChecksumSpec,
    FieldSpec,
    FrameSpec,
    checksum_size,
    effective_endian,
)

# Error codes are part of the contract (UI reads them for i18n), so they are constants.
ERR_TRUNCATED = "truncated"
ERR_CHECKSUM = "checksum_mismatch"
ERR_LENGTH = "bad_length"
ERR_FIELD = "bad_field"
ERR_UNKNOWN_FUNCTION = "unknown_function"
ERR_SPEC = "bad_spec"

_FIXED_SIZES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
                "u64": 8, "i64": 8, "f32": 4, "f64": 8}
_STRUCT_FMT = {("u16", "be"): ">H", ("u16", "le"): "<H",
               ("u32", "be"): ">I", ("u32", "le"): "<I",
               ("u64", "be"): ">Q", ("u64", "le"): "<Q",
               ("i16", "be"): ">h", ("i16", "le"): "<h",
               ("i32", "be"): ">i", ("i32", "le"): "<i",
               ("i64", "be"): ">q", ("i64", "le"): "<q",
               ("f32", "be"): ">f", ("f32", "le"): "<f",
               ("f64", "be"): ">d", ("f64", "le"): "<d"}


def xor8(data: bytes) -> int:
    """XOR of every byte - the BCC used by NMEA 0183 and many binary protocols."""
    value = 0
    for byte in data:
        value ^= byte
    return value & 0xFF


def _byteorder(tag: str) -> str:
    """'be'/'le' -> the words int.from_bytes/to_bytes want."""
    return "little" if tag == "le" else "big"


def checksum_value(kind: str, data: bytes) -> int | None:
    """Compute a checksum; None for kind=none."""
    if kind == "none":
        return None
    if kind == "sum8":
        return sum8(data)
    if kind in ("xor8", "bcc"):
        return xor8(data)
    if kind == "crc16-modbus":
        return crc16_modbus(data)
    if kind == "crc16-ccitt":
        return crc16_ccitt(data)
    if kind == "crc32":
        return crc32(data)
    raise KeyError(kind)


def _frame_size_from_length_field(spec: FrameSpec, buf: bytes) -> int | None:
    """Total frame size when length_mode == "field", else None (not enough bytes yet)."""
    assert spec.length_offset is not None
    need = spec.length_offset + spec.length_width
    if len(buf) < need:
        return None
    value = int.from_bytes(buf[spec.length_offset:need], _byteorder(spec.length_endian))
    return value + spec.length_adjust


def split_stream(spec: FrameSpec, buf: bytes) -> tuple[list[bytes], bytes]:
    """Cut `buf` into complete frames; the trailing partial frame is returned as `rest`.

    Bytes seen before a resync `header` cannot belong to a valid frame and are dropped -
    that is the documented meaning of "resync"; an *incomplete* frame is never dropped, it
    stays in `rest` (see the plan: 不丢字节 applies to partial frames).
    """
    frames: list[bytes] = []
    rest = bytes(buf)

    while True:
        if spec.header:
            at = rest.find(spec.header)
            if at < 0:
                # Keep only a tail that could still be the beginning of a header.
                keep = max(0, len(rest) - (len(spec.header) - 1))
                return frames, rest[keep:]
            rest = rest[at:]

        if spec.length_mode == "delimiter":
            end = rest.find(spec.delimiter)
            if end < 0:
                return frames, rest
            size = end + len(spec.delimiter)
        elif spec.length_mode == "field":
            size = _frame_size_from_length_field(spec, rest)
            if size is None:
                return frames, rest
        else:
            size = spec.frame_size or 0

        if size <= 0 or size > spec.max_frame_size:
            return frames, rest
        if len(rest) < size:
            return frames, rest
        frames.append(rest[:size])
        rest = rest[size:]


def _field_size(spec: FrameSpec, fld: FieldSpec, values: dict) -> int | None:
    """Bytes this field occupies, or None when a referenced length is not known yet."""
    if fld.type in _FIXED_SIZES:
        return _FIXED_SIZES[fld.type]
    if fld.type == "bits":
        width = sum(b.width for b in fld.bits)
        return max(1, (width + 7) // 8)
    # ascii / bytes
    if fld.length is not None:
        return fld.length
    if fld.length_field and fld.length_field in values:
        return int(values[fld.length_field]) * fld.length_scale
    return None


def _decode_value(spec: FrameSpec, fld: FieldSpec, raw: bytes) -> object:
    if fld.type == "ascii":
        return raw.decode("latin-1")
    if fld.type == "bytes":
        return raw
    if fld.type == "bits":
        value = int.from_bytes(raw, "little")   # bit ranges are defined LSB-first
        return {b.name: (value >> b.start) & ((1 << b.width) - 1) for b in fld.bits}
    if fld.type in ("u8", "i8"):
        value = int.from_bytes(raw, "little", signed=fld.type.startswith("i"))
    else:
        fmt = _STRUCT_FMT.get((fld.type, effective_endian(spec, fld)))
        if fmt is None:
            raise KeyError(fld.type)
        value = struct.unpack(fmt, raw)[0]
    if fld.scale != 1.0 or fld.bias != 0.0:
        value = value * fld.scale + fld.bias
    return value


def verify_checksum(spec: FrameSpec, frame: bytes) -> tuple[bool, bytes]:
    """(ok, expected-bytes-as-they-should-appear-in-the-frame)."""
    cs = spec.checksum
    size = checksum_size(cs)
    if cs.kind == "none" or size == 0:
        return True, b""
    if len(frame) < size:
        return False, b""
    end = len(frame) - size if cs.cover_end is None else cs.cover_end
    covered = frame[cs.cover_start:end]
    value = checksum_value(cs.kind, covered)
    if value is None:
        return True, b""
    expected = value.to_bytes(size, _byteorder(cs.endian))
    return frame[len(frame) - size:] == expected, expected


def parse_frame(spec: FrameSpec, frame: bytes) -> tuple[dict, dict]:
    """Decode one frame.

    Returns (values, status) where status is {"ok": bool, "errors": [ {...}, ... ]}.
    The function never raises: a short frame, a bad checksum, an unparsable field or an
    unknown Modbus function code all come back as structured errors.
    """
    errors: list[dict] = []
    values: dict = {}

    if spec.text_separator:
        return _parse_text_frame(spec, frame)

    size = checksum_size(spec.checksum)
    body_end = len(frame) - size if size else len(frame)
    min_needed = spec.min_frame_size
    if len(frame) < min_needed:
        errors.append({"code": ERR_TRUNCATED, "detail": "frame %d < min %d"
                       % (len(frame), min_needed)})
        return values, {"ok": False, "errors": errors}

    ok, expected = verify_checksum(spec, frame)
    if not ok:
        errors.append({"code": ERR_CHECKSUM, "kind": spec.checksum.kind,
                       "detail": "expected %s" % expected.hex(" ")})

    cursor = 0
    for fld in spec.fields:
        where = fld.byte_offset if fld.byte_offset is not None else cursor
        fsize = _field_size(spec, fld, values)
        if fsize is None:
            errors.append({"code": ERR_LENGTH, "field": fld.name,
                           "detail": "length source %r not decoded" % fld.length_field})
            return values, {"ok": False, "errors": errors}
        if where < 0 or where + fsize > body_end:
            errors.append({"code": ERR_TRUNCATED, "field": fld.name,
                           "detail": "field needs bytes %d..%d, body ends at %d"
                                     % (where, where + fsize, body_end)})
            return values, {"ok": False, "errors": errors}
        try:
            values[fld.name] = _decode_value(spec, fld, frame[where:where + fsize])
        except (KeyError, struct.error) as exc:
            errors.append({"code": ERR_FIELD, "field": fld.name, "detail": str(exc)})
            return values, {"ok": False, "errors": errors}
        cursor = where + fsize

    return values, {"ok": not errors, "errors": errors}


def _parse_text_frame(spec: FrameSpec, frame: bytes) -> tuple[dict, dict]:
    """Separator-split frames (AT / NMEA): fields are tokens of one line.

    The line keeps its header and delimiter here (they are the frame's own bytes); with
    `checksum.as_text` the value is written in hex after '*' (NMEA 0183) and covers the
    characters between '$' and '*', which is exactly `checksum.cover_start..cover_end`.
    """
    errors: list[dict] = []
    text = frame.decode("latin-1").strip(spec.separator_strip)
    cs = spec.checksum
    size = checksum_size(cs)

    # Drop the frame's own header ("$" for NMEA) before anything else: the checksum and
    # the field tokens both describe what comes *after* it.
    if spec.header:
        header_text = spec.header.decode("latin-1")
        if text.startswith(header_text):
            text = text[len(header_text):]

    if size and cs.as_text:
        text = _check_text_checksum(cs, size, text, errors)
    values = _split_text_fields(spec, text, errors)
    return values, {"ok": not errors, "errors": errors}


def _check_text_checksum(cs: ChecksumSpec, size: int, text: str,
                         errors: list[dict]) -> str:
    """Verify an NMEA-style "*HH" tail; returns the body without it.

    Appends its findings to `errors` (so the caller keeps one error list) and never raises.
    """
    if "*" not in text:
        errors.append({"code": ERR_TRUNCATED, "detail": "no '*' checksum separator"})
        return text
    body, _, tail = text.rpartition("*")
    digits = 2 * size
    if len(tail) < digits:
        errors.append({"code": ERR_TRUNCATED, "detail": "checksum tail %r" % tail})
        return body
    expected = checksum_value(cs.kind, body[cs.cover_start:cs.cover_end].encode("latin-1"))
    try:
        got = int(tail[:digits], 16)
    except ValueError:
        errors.append({"code": ERR_CHECKSUM, "detail": "checksum %r is not hex" % tail})
    else:
        if got != expected:
            errors.append({"code": ERR_CHECKSUM, "kind": cs.kind,
                           "detail": "expected %0*X, got %0*X" % (digits, expected, digits, got)})
    return body


def _split_text_fields(spec: FrameSpec, text: str, errors: list[dict]) -> dict:
    """Assign the line's tokens to the spec's fields (see FieldSpec.optional/join_rest).

    Appends missing-token problems to the caller's `errors` list and returns the values.
    """
    values: dict = {}

    tokens = text.split(spec.text_separator) if spec.text_separator else [text]
    for index, fld in enumerate(spec.fields):
        first = index
        if fld.join_rest:
            # A "the rest of the line" field (AT parameter list): re-join what is left.
            if first >= len(tokens):
                if fld.optional:
                    values[fld.name] = ""
                else:
                    errors.append({"code": ERR_TRUNCATED, "field": fld.name,
                                   "detail": "token %d missing" % first})
                break
            values[fld.name] = spec.text_separator.join(tokens[first:])
            break
        if first >= len(tokens):
            if fld.optional:
                continue
            errors.append({"code": ERR_TRUNCATED, "field": fld.name,
                           "detail": "token %d missing" % first})
            break
        values[fld.name] = tokens[first]
    return values
