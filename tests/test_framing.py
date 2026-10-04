"""Unit tests for app.framing (USB-fragment aware frame assembly)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.framing import FrameAssembler  # noqa: E402

FRAME = bytes([0x12, 0x34, 0x56, 0x78, 0x90])


class TestFrameAssembler:
    def test_usb_fragments_merge_into_one_line(self):
        """'12 34' + '56 78 90' arriving 5 ms apart is ONE frame, not two."""
        fa = FrameAssembler(settle_ms=10.0, threshold_ms=10.0)
        fa.feed(1.000, FRAME[:2])
        assert fa.has_pending() and fa.pending_bytes() == 2
        assert not fa.due(1.005)            # still inside the settle window
        fa.feed(1.005, FRAME[2:])
        assert fa.due(1.010)
        got = fa.take(1.010)
        assert got is not None
        new_line, _ts, data = got
        assert new_line is True
        assert data == FRAME              # merged, not split
        assert not fa.has_pending()

    def test_chunks_up_to_the_documented_usb_spacing_stay_one_line(self):
        """2026-10-04 user report: the auto rule at 115200 split one 49-byte frame in two.

        The module documents USB chunk spacing of 1-16 ms; with a 10 ms window the first
        8-byte chunk was flushed and the remaining 41 bytes started a new line 13 ms later
        (`[..] <- 12345678` / `[..] <- 90asdfgh...`). The window now clears the documented
        worst case with margin, so every realistic chunk gap stays inside one frame.
        """
        for gap_ms in (1.0, 5.0, 10.0, 13.0, 16.0, 20.0):
            fa = FrameAssembler(settle_ms=25.0, threshold_ms=25.0)
            fa.feed(1.000, b"12345678")
            fa.feed(1.000 + gap_ms / 1000.0, b"90asdfghjkQQQQQQQQQQQQQQKKKKKKKKKKKKKLLLL")
            assert not fa.due(1.000 + (gap_ms + 1.0) / 1000.0), gap_ms
            got = fa.take(1.000 + (gap_ms + 25.0) / 1000.0)
            assert got is not None and got[0] is True, gap_ms
            assert got[2] == (b"12345678"
                              b"90asdfghjkQQQQQQQQQQQQQQKKKKKKKKKKKKKLLLL"), gap_ms

    def test_the_window_is_never_below_the_break_threshold(self):
        """A group can only be complete once the silence that ends a frame has passed."""
        assert FrameAssembler(settle_ms=1.0, threshold_ms=25.0).settle_ms == 25.0
        assert FrameAssembler(settle_ms=120.0, threshold_ms=25.0).settle_ms == 120.0
        assert FrameAssembler(settle_ms=25.0, threshold_ms=None).settle_ms == 25.0

    def test_the_reported_31ms_chunk_gap_stays_one_line(self):
        """The user's adapter again (2026-10-04, second report): FTDI FT232, latency timer 16.

        The driver holds data up to 16 ms and USB scheduling adds more, so one 57-byte frame
        arrived as 44 + 13 bytes 31 ms apart and was displayed as two lines. The window is
        50 ms now: the driver's timer plus a margin, and still far below a real frame gap.
        """
        fa = FrameAssembler(settle_ms=50.0, threshold_ms=50.0)
        first, rest = b"H" * 44, b"F" * 13 + b"DDD"
        fa.feed(1.000, first)
        fa.feed(1.031, rest)                    # 31 ms later, same frame
        # the window is fixed from the first byte (not a debounce), so both chunks are still
        # in hand at 1.040 - the second arrived before the 1.050 deadline
        assert fa.pending_bytes() == len(first) + len(rest)
        assert not fa.due(1.040)
        got = fa.take(1.050)
        assert got[0] is True and got[2] == first + rest

    def test_gap_stats_report_what_the_adapter_delivers(self):
        """The numbers that make the next tuning data-driven instead of another guess."""
        fa = FrameAssembler(settle_ms=50.0, threshold_ms=50.0)
        fa.feed(1.000, b"a")
        fa.feed(1.016, b"b")                    # 16 ms: the FTDI latency timer
        fa.feed(1.047, b"c")                    # 31 ms: scheduling on top of it
        stats = fa.gap_stats()
        assert stats["count"] == 2
        assert round(stats["max"]) == 31
        assert 16 <= round(stats["p95"]) <= 31
        fa.reset()
        # a display clear or a port close must not erase the evidence
        assert fa.gap_stats()["max"] == stats["max"]

    def test_frames_a_hundred_milliseconds_apart_still_split(self):
        """The floor must not glue real frames together (the user sends every 100 ms)."""
        fa = FrameAssembler(settle_ms=25.0, threshold_ms=25.0)
        fa.feed(1.000, b"frame-one")
        fa.take(1.025)
        fa.feed(1.113, b"frame-two")        # 113 ms after the first frame started
        got = fa.take(1.138)
        assert got[0] is True and got[2] == b"frame-two"

    def test_real_inter_frame_gap_still_splits(self):
        fa = FrameAssembler(settle_ms=10.0, threshold_ms=10.0)
        fa.feed(1.000, FRAME)
        fa.take(1.010)
        fa.feed(1.130, FRAME)              # 130 ms later: a new frame
        got = fa.take(1.140)
        assert got[0] is True and got[2] == FRAME

    def test_window_is_fixed_not_debounced(self):
        """A steady stream must keep flushing rather than starving."""
        fa = FrameAssembler(settle_ms=10.0, threshold_ms=10.0)
        fa.feed(1.000, b"ab")
        fa.feed(1.004, b"cd")
        fa.feed(1.008, b"ef")
        assert fa.due(1.010)
        got = fa.take(1.010)
        assert got[2] == b"abcdef"

    def test_no_threshold_merges_across_gaps(self):
        fa = FrameAssembler(settle_ms=5.0, threshold_ms=None)
        fa.feed(1.000, b"a")
        fa.take(1.005)
        fa.feed(2.000, b"b")               # gap ignored when threshold is None
        got = fa.take(2.005)
        assert got[0] is False

    def test_reset_drops_pending_bytes(self):
        fa = FrameAssembler()
        fa.feed(1.0, FRAME)
        fa.reset()
        assert not fa.has_pending() and fa.pending_bytes() == 0
        assert fa.take(2.0) is None

    def test_settle_is_clamped(self):
        assert FrameAssembler(settle_ms=0.1).settle_ms >= 2.0
        assert FrameAssembler(settle_ms=9999).settle_ms <= 200.0

    def test_empty_chunks_ignored(self):
        fa = FrameAssembler()
        fa.feed(1.0, b"")
        assert not fa.has_pending()


def test_split_fixed_cuts_and_keeps_remainder():
    # B3: fixed-length framing keeps the partial tail for the next chunk
    from app.framing import split_fixed
    frames, rest = split_fixed(b"ABCDEFGHIJ", 4)
    assert frames == [b"ABCD", b"EFGH"]
    assert rest == b"IJ"


def test_split_delimited_start_end_and_start_start():
    from app.framing import split_delimited
    frames, rest = split_delimited(b"$A*$B*$C", b"$", b"*")
    assert frames == [b"$A*", b"$B*"]
    assert rest == b"$C"
    frames, rest = split_delimited(b"<1><2><3", b"<", b"")
    assert frames == [b"<1>", b"<2>"]
    assert rest == b"<3"


def test_split_length_prefixed_with_and_without_crc():
    from app.framing import split_length_prefixed, crc16_modbus
    payload = b"HELLO"
    buf = bytes([len(payload)]) + payload + bytes([3]) + b"ABC"
    frames, rest = split_length_prefixed(buf, 1)
    assert frames == [b"HELLO", b"ABC"] and rest == b""
    crc = crc16_modbus(payload)
    buf = bytes([len(payload)]) + payload + crc.to_bytes(2, "big")
    frames, rest = split_length_prefixed(buf, 1, crc_bytes=2)
    assert frames == [b"HELLO"] and rest == b""


def test_split_length_prefixed_drops_bad_crc():
    from app.framing import split_length_prefixed
    buf = bytes([3]) + b"ABC" + b"\x00\x00"      # wrong CRC
    frames, rest = split_length_prefixed(buf, 1, crc_bytes=2)
    assert frames == [] and rest == b""


class TestByteFrameSplitter:
    """B3: the stateful wrapper must keep the tail between serial chunks."""

    def test_fixed_keeps_partial_tail_across_chunks(self):
        from app.framing import ByteFrameSplitter, SPLIT_FIXED
        bs = ByteFrameSplitter(mode=SPLIT_FIXED, size=4)
        assert bs.feed(b"AAAA") == [b"AAAA"]
        assert bs.feed(b"BB") == []            # half a frame, held back
        assert bs.pending() == b"BB"
        assert bs.feed(b"BB") == [b"BBBB"]
        assert bs.pending() == b""

    def test_delimited_across_chunks(self):
        from app.framing import ByteFrameSplitter, SPLIT_DELIMITED
        bs = ByteFrameSplitter(mode=SPLIT_DELIMITED, start=b"\xaa", end=b"\x55")
        assert bs.feed(b"\xaa\x01\x02") == []
        assert bs.pending() == b"\xaa\x01\x02"
        assert bs.feed(b"\x55\xaa\x03\x55") == [b"\xaa\x01\x02\x55", b"\xaa\x03\x55"]

    def test_delimited_without_delimiters_is_a_noop(self):
        from app.framing import ByteFrameSplitter, SPLIT_DELIMITED
        bs = ByteFrameSplitter(mode=SPLIT_DELIMITED, start=b"", end=b"")
        assert bs.feed(b"anything") == []      # would otherwise loop forever
        assert bs.pending() == b"anything"

    def test_length_prefixed_across_chunks(self):
        from app.framing import ByteFrameSplitter, SPLIT_TLV
        bs = ByteFrameSplitter(mode=SPLIT_TLV, prefix_bytes=1)
        assert bs.feed(b"\x03AB") == []
        assert bs.feed(b"C\x02DE") == [b"ABC", b"DE"]

    def test_take_pending_flushes_the_tail(self):
        from app.framing import ByteFrameSplitter, SPLIT_FIXED
        bs = ByteFrameSplitter(mode=SPLIT_FIXED, size=8)
        bs.feed(b"XYZ")
        assert bs.take_pending() == b"XYZ"
        assert bs.pending() == b""

    def test_reconfigure_keeps_the_tail(self):
        from app.framing import ByteFrameSplitter, SPLIT_FIXED
        bs = ByteFrameSplitter(mode=SPLIT_FIXED, size=8)
        bs.feed(b"AB")
        bs.configure(mode=SPLIT_FIXED, size=2)
        assert bs.pending() == b"AB"           # mode switch is the caller's flush
        assert bs.feed(b"CD") == [b"AB", b"CD"]
