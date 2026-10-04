"""Declarative parse schema: field/frame specs + JSON round-trip.

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


class SpecFormatError(ValueError):
    """A spec could not be read from JSON/dict form.

    Subclasses ``ValueError`` on purpose: a caller loading a user-supplied spec only has to
    catch one type. Before this existed the same bad input raised ``AttributeError`` (top
    level not an object), ``TypeError`` (a field list that is not a list) or ``ValueError``
    (a number that is not one) depending on which key was wrong - measurably, not by guess.
    """


def _obj(value: Any, what: str) -> dict[str, Any]:
    """``value`` as a dict, or a SpecFormatError naming the shape that arrived."""
    if not isinstance(value, dict):
        raise SpecFormatError("%s must be a JSON object, got %s" % (what, type(value).__name__))
    return value


def _num(value: Any, what: str, cast=int):
    """A number from a number or numeric string; anything else is a SpecFormatError."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SpecFormatError("%s must be a number, got %s" % (what, type(value).__name__))
    try:
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise SpecFormatError("%s must be a number, got %r" % (what, value)) from exc


def _opt_int(value: Any, what: str):
    """An optional integer: ``None`` stays ``None``, anything else must be a number."""
    return None if value is None else _num(value, what)


def _seq(value: Any, what: str) -> list:
    """A list *or* tuple, as a list. ``asdict()`` keeps tuples, so both are legal input."""
    if isinstance(value, (list, tuple)):
        return list(value)
    raise SpecFormatError("%s must be a JSON array, got %s" % (what, type(value).__name__))


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

def _bits_from_json(raw: Any) -> tuple[BitField, ...]:
    if raw is None:
        return ()
    out = []
    for i, item in enumerate(_seq(raw, "bits")):
        item = _obj(item, "bits[%d]" % i)
        if "name" not in item or "start" not in item:
            raise SpecFormatError("bits[%d] needs both 'name' and 'start'" % i)
        out.append(BitField(name=str(item["name"]),
                            start=_num(item["start"], "bits[%d].start" % i),
                            width=_num(item.get("width", 1), "bits[%d].width" % i)))
    return tuple(out)


def _field_from_json(raw: Any) -> FieldSpec:
    raw = _obj(raw, "each entry of 'fields'")
    if not isinstance(raw.get("name"), str) or not isinstance(raw.get("type"), str):
        raise SpecFormatError("every field needs 'name' and 'type' as strings")
    return FieldSpec(
        name=str(raw["name"]),
        type=str(raw["type"]),
        byte_offset=_opt_int(raw.get("byte_offset"), "byte_offset"),
        length=_opt_int(raw.get("length"), "length"),
        length_field=raw.get("length_field"),
        length_scale=_num(raw.get("length_scale", 1), "length_scale"),
        endian=raw.get("endian"),
        scale=_num(raw.get("scale", 1.0), "scale", float),
        bias=_num(raw.get("bias", 0.0), "bias", float),
        unit=str(raw.get("unit", "")),
        bits=_bits_from_json(raw.get("bits", [])),
        text=bool(raw.get("text", False)),
        optional=bool(raw.get("optional", False)),
        join_rest=bool(raw.get("join_rest", False)),
    )


def spec_from_dict(raw: dict[str, Any]) -> FrameSpec:
    """Build a FrameSpec from a plain dict (the shape stored in config/JSON files)."""
    raw = _obj(raw, "spec")
    fields = _seq(raw.get("fields", []), "fields")
    chk = _obj(raw.get("checksum") or {}, "checksum")
    return FrameSpec(
        name=str(raw.get("name", "unnamed")),
        fields=tuple(_field_from_json(f) for f in fields),
        endian=str(raw.get("endian", "be")),
        header=bytes(raw.get("header", b"")) if isinstance(raw.get("header"), (bytes, bytearray))
        else str(raw.get("header", "")).encode("latin-1"),
        trailer=bytes(raw.get("trailer", b"")) if isinstance(raw.get("trailer"), (bytes, bytearray))
        else str(raw.get("trailer", "")).encode("latin-1"),
        length_mode=str(raw.get("length_mode", "fixed")),
        frame_size=_opt_int(raw.get("frame_size"), "frame_size"),
        length_offset=_opt_int(raw.get("length_offset"), "length_offset"),
        length_width=_num(raw.get("length_width", 1), "length_width"),
        length_endian=str(raw.get("length_endian", "be")),
        length_adjust=_num(raw.get("length_adjust", 0), "length_adjust"),
        min_frame_size=_num(raw.get("min_frame_size", 0), "min_frame_size"),
        max_frame_size=_num(raw.get("max_frame_size", 4096), "max_frame_size"),
        delimiter=str(raw.get("delimiter", "")).encode("latin-1"),
        checksum=ChecksumSpec(
            kind=str(chk.get("kind", "none")),
            cover_start=_num(chk.get("cover_start", 0), "checksum.cover_start"),
            cover_end=_opt_int(chk.get("cover_end"), "checksum.cover_end"),
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
    """Parse a FrameSpec from its JSON form (see spec_to_json).

    Every malformed input - invalid JSON, a top-level value that is not an object, wrong
    types inside, even a pathologically nested document - comes back as ``SpecFormatError``
    so a caller has exactly one failure mode to handle.
    """
    try:
        raw = json.loads(text)
    except (ValueError, RecursionError) as exc:      # RecursionError: 深嵌套 JSON
        raise SpecFormatError("spec is not valid JSON: %s" % exc) from exc
    return spec_from_dict(raw)


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
