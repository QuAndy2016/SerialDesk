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
