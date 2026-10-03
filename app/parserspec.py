"""Declarative parse schema (B4-P1): field/frame specs + JSON round-trip.

The kernel is Qt-free on purpose: a spec is data, so it can be stored next to a project,
diffed, and unit-tested without a window (same rule as app/framing.py).

Sources for the protocol-specific parts live in app/parse_templates.py; this module only
describes *how* a frame is laid out, never a particular protocol.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

# Field types: sizes are fixed except ascii/bytes (length comes from the spec) and bits
# (width comes from the bit list).
INT_TYPES = ("u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64")
FLOAT_TYPES = ("f32", "f64")
RAW_TYPES = ("ascii", "bytes")
FIELD_TYPES = INT_TYPES + FLOAT_TYPES + RAW_TYPES + ("bits",)
ENDIANS = ("be", "le")

# none | sum8 (sum of bytes) | xor8 (a.k.a. BCC) | the CRC set already in app/protocol.py
CHECKSUM_KINDS = ("none", "sum8", "xor8", "bcc", "crc16-modbus", "crc16-ccitt", "crc32")
CHECKSUM_SIZES = {"none": 0, "sum8": 1, "xor8": 1, "bcc": 1,
                  "crc16-modbus": 2, "crc16-ccitt": 2, "crc32": 4}

LENGTH_MODES = ("fixed", "field", "delimiter")


@dataclass(frozen=True)
class BitField:
    """One bit range inside a `bits` field. `start` counts from the least significant bit."""

    name: str
    start: int
    width: int = 1


@dataclass(frozen=True)
class FieldSpec:
    """One decoded value.

    Positioning: `byte_offset` when the field sits at a fixed place, otherwise the field
    is read after the previous one (sequential cursor). `length` applies to ascii/bytes;
    when it is None the length comes from the field named `length_field` (variable-length
    frames), multiplied by `length_scale`.
    """

    name: str
    type: str
    byte_offset: int | None = None
    length: int | None = None
    length_field: str | None = None
    length_scale: int = 1
    endian: str | None = None            # None = inherit FrameSpec.endian
    scale: float = 1.0
    bias: float = 0.0
    unit: str = ""
    bits: tuple[BitField, ...] = ()
    text: bool = False                   # text frames: value is decoded as ascii
    optional: bool = False               # text frames: a missing token is not an error
    join_rest: bool = False              # text frames: consume all remaining tokens


@dataclass(frozen=True)
class ChecksumSpec:
    """Checksum kind plus the byte range it covers.

    `cover_end=None` means "up to the checksum itself" (the usual case: the checksum is the
    last `size` bytes and covers everything before it).

    `as_text=True` is for line protocols that spell the checksum in hex digits (NMEA 0183
    writes XOR as two hex characters after '*'), instead of storing it as raw bytes.
    For text frames `cover_start`/`cover_end` are offsets inside the line *after* the
    header and *before* the '*' (so NMEA's default 0..None means "the whole sentence body").
    """

    kind: str = "none"
    cover_start: int = 0
    cover_end: int | None = None
    size: int | None = None              # None = derived from kind
    endian: str = "le"                   # byte order of the checksum inside the frame
    as_text: bool = False                # checksum is hex text (NMEA) not raw bytes


@dataclass(frozen=True)
class FrameSpec:
    """How to cut a byte stream into frames and decode each one."""

    name: str
    fields: tuple[FieldSpec, ...] = ()
    endian: str = "be"                   # default byte order for numeric fields
    header: bytes = b""
    trailer: bytes = b""
    length_mode: str = "fixed"
    frame_size: int | None = None        # length_mode == "fixed"
    length_offset: int | None = None     # length_mode == "field"
    length_width: int = 1
    length_endian: str = "be"
    length_adjust: int = 0               # total frame size = length value + adjust
    min_frame_size: int = 0
    max_frame_size: int = 4096
    delimiter: bytes = b""               # length_mode == "delimiter"
    checksum: ChecksumSpec = field(default_factory=ChecksumSpec)
    text_separator: str = ""             # non-empty: fields are separator-split tokens
    separator_strip: str = "\r\n"        # text frames: characters trimmed at both ends


def checksum_size(spec: ChecksumSpec) -> int:
    """Bytes the checksum occupies (explicit size wins over the kind default)."""
    return spec.size if spec.size is not None else CHECKSUM_SIZES.get(spec.kind, 0)


def effective_endian(frame: FrameSpec, fld: FieldSpec) -> str:
    """Field endian, falling back to the frame default."""
    return fld.endian or frame.endian


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------

def _bits_from_json(raw: list[dict[str, Any]]) -> tuple[BitField, ...]:
    return tuple(BitField(name=str(b["name"]), start=int(b["start"]),
                          width=int(b.get("width", 1))) for b in raw)


def _field_from_json(raw: dict[str, Any]) -> FieldSpec:
    return FieldSpec(
        name=str(raw["name"]),
        type=str(raw["type"]),
        byte_offset=raw.get("byte_offset"),
        length=raw.get("length"),
        length_field=raw.get("length_field"),
        length_scale=int(raw.get("length_scale", 1)),
        endian=raw.get("endian"),
        scale=float(raw.get("scale", 1.0)),
        bias=float(raw.get("bias", 0.0)),
        unit=str(raw.get("unit", "")),
        bits=_bits_from_json(raw.get("bits", [])),
        text=bool(raw.get("text", False)),
        optional=bool(raw.get("optional", False)),
        join_rest=bool(raw.get("join_rest", False)),
    )


def spec_from_dict(raw: dict[str, Any]) -> FrameSpec:
    """Build a FrameSpec from a plain dict (the shape stored in config/JSON files)."""
    chk = raw.get("checksum") or {}
    return FrameSpec(
        name=str(raw.get("name", "unnamed")),
        fields=tuple(_field_from_json(f) for f in raw.get("fields", [])),
        endian=str(raw.get("endian", "be")),
        header=bytes(raw.get("header", b"")) if isinstance(raw.get("header"), (bytes, bytearray))
        else str(raw.get("header", "")).encode("latin-1"),
        trailer=bytes(raw.get("trailer", b"")) if isinstance(raw.get("trailer"), (bytes, bytearray))
        else str(raw.get("trailer", "")).encode("latin-1"),
        length_mode=str(raw.get("length_mode", "fixed")),
        frame_size=raw.get("frame_size"),
        length_offset=raw.get("length_offset"),
        length_width=int(raw.get("length_width", 1)),
        length_endian=str(raw.get("length_endian", "be")),
        length_adjust=int(raw.get("length_adjust", 0)),
        min_frame_size=int(raw.get("min_frame_size", 0)),
        max_frame_size=int(raw.get("max_frame_size", 4096)),
        delimiter=str(raw.get("delimiter", "")).encode("latin-1"),
        checksum=ChecksumSpec(
            kind=str(chk.get("kind", "none")),
            cover_start=int(chk.get("cover_start", 0)),
            cover_end=chk.get("cover_end"),
            size=chk.get("size"),
            endian=str(chk.get("endian", "le")),
            as_text=bool(chk.get("as_text", False)),
        ),
        text_separator=str(raw.get("text_separator", "")),
        separator_strip=str(raw.get("separator_strip", "\r\n")),
    )


def spec_to_dict(spec: FrameSpec) -> dict[str, Any]:
    """Plain dict for JSON storage; bytes become latin-1 strings so the file stays readable."""
    out = asdict(spec)
    out["header"] = spec.header.decode("latin-1")
    out["trailer"] = spec.trailer.decode("latin-1")
    out["delimiter"] = spec.delimiter.decode("latin-1")
    out["checksum"] = asdict(spec.checksum)
    return out


def spec_from_json(text: str) -> FrameSpec:
    """Parse a FrameSpec from its JSON form (see spec_to_json)."""
    return spec_from_dict(json.loads(text))


def spec_to_json(spec: FrameSpec, indent: int = 2) -> str:
    """Serialise a FrameSpec to JSON text; bytes stay readable (latin-1)."""
    return json.dumps(spec_to_dict(spec), indent=indent, ensure_ascii=False)


def with_header(spec: FrameSpec, header: bytes) -> FrameSpec:
    """Convenience for tests/templates: same spec with a different header."""
    return replace(spec, header=header)


# ---------------------------------------------------------------------------
# Validation (never raises: returns the list of problems)
# ---------------------------------------------------------------------------

def validate_spec(spec: FrameSpec) -> list[str]:
    """Return human-readable problems; empty list means the spec is usable."""
    problems: list[str] = []
    if spec.endian not in ENDIANS:
        problems.append("frame endian must be one of %s" % (ENDIANS,))
    if spec.length_mode not in LENGTH_MODES:
        problems.append("length_mode must be one of %s" % (LENGTH_MODES,))
    if spec.length_mode == "fixed" and not spec.frame_size:
        problems.append("length_mode=fixed needs frame_size")
    if spec.length_mode == "field" and spec.length_offset is None:
        problems.append("length_mode=field needs length_offset")
    if spec.length_mode == "field" and spec.length_width not in (1, 2, 4):
        problems.append("length_width must be 1, 2 or 4")
    if spec.length_mode == "delimiter" and not spec.delimiter:
        problems.append("length_mode=delimiter needs delimiter")
    if spec.checksum.kind not in CHECKSUM_KINDS:
        problems.append("checksum kind must be one of %s" % (CHECKSUM_KINDS,))
    if checksum_size(spec.checksum) > 0 and spec.length_mode == "fixed" and spec.frame_size:
        if checksum_size(spec.checksum) >= spec.frame_size:
            problems.append("checksum does not fit in frame_size")
    names = [f.name for f in spec.fields]
    if len(names) != len(set(names)):
        problems.append("field names must be unique")
    for fld in spec.fields:
        if fld.type not in FIELD_TYPES:
            problems.append("field %s: unknown type %r" % (fld.name, fld.type))
        if fld.length_field and fld.length_field not in names:
            problems.append("field %s: length_field %r is not an earlier field"
                            % (fld.name, fld.length_field))
        if fld.type == "bits" and not fld.bits:
            problems.append("field %s: bits type needs at least one bit range" % fld.name)
        if fld.endian is not None and fld.endian not in ENDIANS:
            problems.append("field %s: endian must be be/le" % fld.name)
    return problems
