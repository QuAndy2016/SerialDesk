"""Rolling throughput metrics for the receive path (data-path P2).

Pure logic, no Qt: the receive controller feeds it one record per received batch
and the status bar reads a snapshot. Keeping the maths here means the numbers can
be unit-tested without a window (and the bench can reuse the same class).
"""

from __future__ import annotations

METER_WINDOW_S = 1.0        # the rolling window the read-out averages over


class ThroughputMeter:
    """Rolling window over (bytes, fragments, batch cost) received samples."""

    def __init__(self, window_s: float = METER_WINDOW_S) -> None:
        self.window_s = float(window_s)
        self._samples: list[tuple[float, int, int, float]] = []
        self.max_batch_ms = 0.0      # worst batch since the last reset
        self.dropped = 0             # fragments discarded because the pane was paused

    def record(self, now: float, nbytes: int, frags: int, cost_ms: float) -> None:
        """Add one received batch."""
        self._samples.append((now, int(nbytes), int(frags), float(cost_ms)))
        if cost_ms > self.max_batch_ms:
            self.max_batch_ms = float(cost_ms)
        cutoff = now - self.window_s
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.pop(0)

    def note_dropped(self, n: int = 1) -> None:
        self.dropped += int(n)

    def reset_peak(self) -> None:
        self.max_batch_ms = 0.0

    def snapshot(self, now: float) -> dict:
        """Averages over the live window; zeroed when nothing arrived lately."""
        cutoff = now - self.window_s
        live = [s for s in self._samples if s[0] >= cutoff]
        if not live:
            return {"bps": 0.0, "batches": 0.0, "merge": 0.0,
                    "max_ms": self.max_batch_ms, "dropped": self.dropped}
        span = max(1e-3, min(self.window_s, now - live[0][0] + 1e-3))
        nbytes = sum(s[1] for s in live)
        frags = sum(s[2] for s in live)
        return {
            "bps": nbytes / span,
            "batches": len(live) / span,
            "merge": frags / len(live),
            "max_ms": self.max_batch_ms,
            "dropped": self.dropped,
        }


def human_rate(bps: float) -> str:
    """Bytes per second as a short human string (B/s, KB/s, MB/s)."""
    if bps >= 1024 * 1024:
        return "%.1f MB/s" % (bps / (1024 * 1024))
    if bps >= 1024:
        return "%.1f KB/s" % (bps / 1024)
    return "%.0f B/s" % bps
