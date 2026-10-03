"""Declarative schema (B4-P1): JSON round-trip and validation."""

from __future__ import annotations

import pytest

from app.parserspec import (
    BitField,
    ChecksumSpec,
    FieldSpec,
    FrameSpec,
    checksum_size,
    spec_from_dict,
    spec_from_json,
    spec_to_dict,
    spec_to_json,
    validate_spec,
)


def _rich_spec() -> FrameSpec:
    """A spec that uses every field attribute the plan lists."""
    return FrameSpec(
        name="rich", endian="le", header=b"\xaa\x55", trailer=b"\r\n",
        length_mode="field", length_offset=2, length_width=2, length_endian="be",
        length_adjust=5, min_frame_size=7, max_frame_size=1024,
        checksum=ChecksumSpec(kind="crc16-modbus", cover_start=0, cover_end=None,
                              size=2, endian="le"),
        fields=(
            FieldSpec("kind", "u8", byte_offset=0),
            FieldSpec("size", "u16", byte_offset=1),
            FieldSpec("scale", "f32", endian="be", scale=0.1, bias=-5.0, unit="V"),
            FieldSpec("flags", "bits", byte_offset=5,
                      bits=(BitField("run", 0), BitField("mode", 3, 2))),
            FieldSpec("payload", "bytes", length_field="size", length_scale=1),
            FieldSpec("tail", "ascii", length=4),
        ),
    )


def test_json_round_trip_keeps_every_attribute():
    original = _rich_spec()
    again = spec_from_json(spec_to_json(original))
    assert again == original
    assert again.fields[2].unit == "V"
    assert again.fields[3].bits == (BitField("run", 0), BitField("mode", 3, 2))
    assert again.header == b"\xaa\x55"
    assert again.checksum.kind == "crc16-modbus"


def test_dict_round_trip_is_json_safe():
    raw = spec_to_dict(_rich_spec())
    assert isinstance(raw["header"], str)          # bytes -> latin-1 text for the file
    assert spec_from_dict(raw) == _rich_spec()


def test_checksum_size_is_derived_from_kind_when_not_given():
    assert checksum_size(ChecksumSpec(kind="crc32")) == 4
    assert checksum_size(ChecksumSpec(kind="xor8")) == 1
    assert checksum_size(ChecksumSpec(kind="none")) == 0
    assert checksum_size(ChecksumSpec(kind="none", size=2)) == 2   # explicit wins


def test_validate_accepts_the_rich_spec():
    assert validate_spec(_rich_spec()) == []


@pytest.mark.parametrize("spec, fragment", [
    (FrameSpec(name="a", length_mode="fixed"), "frame_size"),
    (FrameSpec(name="b", length_mode="field"), "length_offset"),
    (FrameSpec(name="c", length_mode="delimiter"), "delimiter"),
    (FrameSpec(name="d", length_mode="fixed", frame_size=4, fields=(FieldSpec("x", "nope"),)),
     "unknown type"),
    (FrameSpec(name="e", length_mode="fixed", frame_size=8,
               fields=(FieldSpec("x", "u8"), FieldSpec("x", "u8"))), "unique"),
    (FrameSpec(name="f", length_mode="fixed", frame_size=8,
               checksum=ChecksumSpec(kind="magic")), "checksum kind"),
    (FrameSpec(name="g", length_mode="fixed", frame_size=8,
               fields=(FieldSpec("payload", "bytes", length_field="missing"),)),
     "length_field"),
    (FrameSpec(name="h", length_mode="field", length_offset=0, length_width=3),
     "length_width"),
    (FrameSpec(name="i", length_mode="fixed", frame_size=2,
               checksum=ChecksumSpec(kind="crc32")), "does not fit"),
])
def test_validate_reports_problems(spec, fragment):
    problems = " | ".join(validate_spec(spec))
    assert fragment in problems


def test_json_text_is_readable_and_stable():
    text = spec_to_json(FrameSpec(name="mini", length_mode="fixed", frame_size=3,
                                 header=b"$", delimiter=b"\r\n"))
    assert '$' in text and "\\r\\n" in text        # latin-1 bytes stay readable
    assert spec_from_json(text).header == b"$"
