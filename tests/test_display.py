"""Payload / timestamp formatting rules (refactor step 1)."""

from app.display import (MARK_RX, MARK_TX, RX_ASCII, RX_HEX, RX_HEX_ASCII,
                         format_payload, hex_separator, line, marker,
                         timestamp_prefix)


def test_hex_mode_shows_bytes_with_spaces():
    assert format_payload(b"\x01\x02", RX_HEX) == "01 02"


def test_ascii_mode_decodes_text():
    assert format_payload(b"AT", RX_ASCII) == "AT"


def test_dual_mode_shows_both_separated():
    assert format_payload(b"\x41\x42", RX_HEX_ASCII) == "41 42 | AB"


def test_markers_are_three_characters_so_columns_line_up():
    assert len(MARK_RX) == len(MARK_TX) == 3
    assert marker(tx=True) == "-> "
    assert marker(tx=False) == "<- "


def test_timestamp_prefix_switch_and_format():
    assert timestamp_prefix(0.0, enabled=False) == ""
    text = timestamp_prefix(1_700_000_000.25, enabled=True)
    assert text.startswith("[") and text.endswith("] ") and ".250] " in text


def test_hex_separator_only_for_hex_modes():
    assert hex_separator(RX_ASCII) == ""
    assert hex_separator(RX_HEX) == " "
    assert hex_separator(RX_HEX_ASCII) == " "


def test_line_composes_timestamp_marker_and_payload():
    assert line("01 02", "[00:00:00.000] ", tx=False) == "[00:00:00.000] <- 01 02"
