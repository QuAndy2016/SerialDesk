"""Declarative schema: JSON round-trip and validation."""

from __future__ import annotations

import json

import pytest

from app.parserspec import (
    BitField,
    ChecksumSpec,
    FieldSpec,
    FrameSpec,
    SpecFormatError,
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


class TestMalformedSpecIsOneFailureMode:
    """A spec file is user input, so every bad shape must fail the same documented way.

    Measured before the guards existed: the same class of mistake raised ``AttributeError``
    (top level not an object), ``TypeError`` (a field list that is not a list) or
    ``ValueError`` (a number that is not one) depending on which key was wrong. A caller
    could not handle that with one ``except``.
    """

    BAD_JSON = [
        ("invalid json", "{not json"),
        ("truncated json", '{"name": "x", "fields": ['),
        ("top level array", "[1, 2, 3]"),
        ("top level string", '"hello"'),
        ("top level number", "7"),
        ("top level null", "null"),
        ("fields not a list", '{"fields": 7}'),
        ("field entry not an object", '{"fields": [1]}'),
        ("field missing type", '{"fields": [{"name": "a"}]}'),
        ("field name not a string pair", '{"fields": [{"name": [], "type": "u8"}]}'),
        ("length_width is text", '{"length_width": "abc"}'),
        ("length_width is null", '{"length_width": null}'),
        ("frame_size is a list", '{"frame_size": [1]}'),
        ("checksum is a list", '{"checksum": [1]}'),
        ("checksum cover_start is text", '{"checksum": {"cover_start": "x"}}'),
        ("bits not a list", '{"fields": [{"name": "a", "type": "bits", "bits": 3}]}'),
        ("bit missing start", '{"fields": [{"name": "a", "type": "bits", "bits": [{"name": "f"}]}]}'),
    ]

    @pytest.mark.parametrize("what, text", BAD_JSON, ids=[c[0] for c in BAD_JSON])
    def test_bad_json_raises_spec_format_error(self, what, text):
        with pytest.raises(SpecFormatError):
            spec_from_json(text)

    def test_spec_format_error_is_a_value_error(self):
        # One except clause has to cover a spec that cannot be read.
        assert issubclass(SpecFormatError, ValueError)

    @pytest.mark.parametrize("bad", [None, [], "x", 7, ("a",)])
    def test_bad_dict_raises_spec_format_error(self, bad):
        with pytest.raises(SpecFormatError):
            spec_from_dict(bad)

    def test_pathologically_nested_document_is_mapped_to_spec_format_error(self, monkeypatch):
        # Deterministic stand-in for a document deep enough to blow the recursion limit:
        # whatever the parser raises for that, the caller must still see SpecFormatError.
        def too_deep(_text):
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr("app.parserspec.json.loads", too_deep)
        with pytest.raises(SpecFormatError):
            spec_from_json("{}")

    def test_actually_nested_document_never_raises_an_unexpected_type(self):
        text = '{"a": ' + "[" * 3000 + "]" * 3000 + "}"
        try:
            spec_from_json(text)
        except SpecFormatError:
            pass
        except Exception as exc:                     # noqa: BLE001 - that is the assertion
            pytest.fail("unexpected %s: %s" % (type(exc).__name__, exc))

    def test_oversized_field_list_is_loaded_not_refused(self):
        # Growth must stay linear and safe: 5000 fields is a legal, if silly, spec.
        text = json.dumps({"fields": [{"name": "f%d" % i, "type": "u8"} for i in range(5000)]})
        assert len(spec_from_json(text).fields) == 5000
