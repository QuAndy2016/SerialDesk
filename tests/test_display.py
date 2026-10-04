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


def test_long_line_tooltip_only_for_very_long_lines():
    from app.display import LONG_LINE_CHARS, long_line_tooltip
    assert long_line_tooltip("short") is None
    assert long_line_tooltip("x" * LONG_LINE_CHARS) is None   # at the limit: no tip
    full = "x" * (LONG_LINE_CHARS + 1)
    assert long_line_tooltip(full) == full


def test_fragment_filter_keeps_the_markers_of_the_shown_side():
    # /0=RX payload, 1=TX payload, 2=RX mark, 3=TX mark
    from app.display import fragment_visible, kind_is_meta, kind_is_tx
    assert [kind_is_tx(k) for k in (0, 1, 2, 3)] == [False, True, False, True]
    assert [kind_is_meta(k) for k in (0, 1, 2, 3)] == [False, False, True, True]
    for mode, keep in ((0, {0, 1, 2, 3}), (1, {0, 2}), (2, {1, 3})):
        for kind in (0, 1, 2, 3):
            assert fragment_visible(kind, mode) is (kind in keep), (kind, mode)


def test_embedded_newlines_become_explicit_line_breaks():
    """2026-10-03: a payload that carries its own \n must not stay one store entry.

    The document always rendered the break; the store did not know about it, so
    the two disagreed about where a line ends (the source of the phantom line
    break / glued rows after a view rebuild).
    """
    from app.display import split_fragments
    assert split_fragments("AA", 0) == [("AA", 0)]
    assert split_fragments("AA\nBB", 0) == [("AA", 0), ("\n", 0), ("BB", 0)]
    assert split_fragments("A\n", 1) == [("A", 1), ("\n", 1)]
    assert split_fragments("\n", 2) == [("\n", 2)]
    assert split_fragments("A\n\nB", 0) == [("A", 0), ("\n", 0), ("\n", 0), ("B", 0)]


def test_row_model_matches_the_document_for_plain_and_embedded_lines():
    from app.display import rows_from_fragments
    store = [("<- ", 0), ("hello", 0), ("\n", 0), ("<- ", 0), ("AA\nBB", 0)]
    rows = rows_from_fragments(store)
    assert len(rows) == 3                       # <-1, <-2, and the BB tail
    assert [t for t, _ in rows[1]] == ["<- ", "AA"]
    assert [t for t, _ in rows[2]] == ["BB"]
    # a blank line stays a blank line (no shifting of the rows below it)
    assert len(rows_from_fragments([("A", 0), ("\n", 0), ("\n", 0), ("B", 0)])) == 3
    # a trailing separator keeps the empty last row the pane also shows
    assert len(rows_from_fragments([("A", 0), ("\n", 0)])) == 2
