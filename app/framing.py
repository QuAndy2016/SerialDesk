"""Frame assembly for received bytes (U57).

USB serial adapters do not deliver one frame per read: the driver and the OS
scheduler hand over a frame in several chunks (1-16 ms apart). Deciding a line
break from the gap *between chunks* therefore splits frames in the middle.

This module merges chunks inside a short "settle" window and only then decides
whether the group starts a new line, comparing timestamps between *flushes*.
Qt-free on purpose so the timing rules can be unit-tested with synthetic clocks.
"""

from __future__ import annotations

DEFAULT_SETTLE_MS = 10.0     # chunks closer than this are the same frame
MIN_SETTLE_MS = 2.0
MAX_SETTLE_MS = 200.0


class FrameAssembler:
    """Collect chunks into a frame, then report when it is ready to display."""

    def __init__(self, settle_ms: float = DEFAULT_SETTLE_MS,
                 threshold_ms: float | None = None) -> None:
        self.settle_ms = min(MAX_SETTLE_MS, max(MIN_SETTLE_MS, float(settle_ms)))
        self.threshold_ms = threshold_ms
        self._buf = bytearray()
        self._first_ts: float | None = None
        self._last_flush_ts: float | None = None
        self._start_new_line = True

    # -- input (called from the GUI thread on every received chunk) ----------

    def feed(self, ts: float, data: bytes) -> None:
        """Add a chunk; the line-break decision is taken once per group."""
        if not data:
            return
        if self._first_ts is None:
            self._first_ts = ts
            self._start_new_line = self._decide_break(ts)
        self._buf.extend(data)

    def _decide_break(self, ts: float) -> bool:
        if self._last_flush_ts is None:
            return True
        if self.threshold_ms is None:
            return False
        return (ts - self._last_flush_ts) * 1000.0 > self.threshold_ms

    # -- output --------------------------------------------------------------

    def has_pending(self) -> bool:
        return self._first_ts is not None

    def pending_bytes(self) -> int:
        return len(self._buf)

    def due(self, now: float) -> bool:
        """True when the group has been quiet for `settle_ms`."""
        if self._first_ts is None:
            return False
        return (now - self._first_ts) * 1000.0 >= self.settle_ms

    def take(self, now: float) -> tuple[bool, float, bytes] | None:
        """Remove and return (start_new_line, timestamp, data), or None."""
        if self._first_ts is None:
            return None
        out = (self._start_new_line, self._first_ts, bytes(self._buf))
        self._last_flush_ts = self._first_ts
        self._buf.clear()
        self._first_ts = None
        self._start_new_line = True
        return out

    def add_bytes(self, data: bytes) -> None:
        """ASCII helper for tests: queue raw bytes without touching state."""
        self._buf.extend(data)

    def set_threshold(self, threshold_ms: float | None) -> None:
        """Update the split threshold (mode or baud rate changes)."""
        self.threshold_ms = threshold_ms

    def reset(self) -> None:
        """Drop any pending bytes (port closed / display cleared)."""
        self._buf.clear()
        self._first_ts = None
        self._start_new_line = True
