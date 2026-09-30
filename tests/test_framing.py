"""Unit tests for app.framing (U57: USB-fragment aware frame assembly)."""

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
