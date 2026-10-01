"""Session counters, as plain data (refactor step 1 of the main-window split).

Why this exists: the counters that drive the status bar used to live as three
attributes on the window and were updated from seven places - which is how the
"sent N times" and "TX bytes" numbers drifted apart (U103). One object, one
entry point per counter, and it can be tested without a QApplication.
"""

from __future__ import annotations


class SessionStats:
    """Bytes received, bytes sent and how many send operations happened."""

    __slots__ = ("rx_bytes", "tx_bytes", "sends")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Zero everything (called by the clear action and by restore-defaults)."""
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.sends = 0

    def add_rx(self, count: int) -> int:
        """Count received bytes (fragments included) and return the new total."""
        self.rx_bytes += max(0, int(count))
        return self.rx_bytes

    def add_tx(self, count: int, *, count_send: bool = True) -> int:
        """Every path that puts bytes on the wire adds bytes here.

        `count_send` is False for transfers that are not a user send (file chunks,
        auto-replies) - they still count as traffic, but not as a send (U103).
        """
        self.tx_bytes += max(0, int(count))
        if count_send:
            self.sends += 1
        return self.tx_bytes

    def snapshot(self) -> tuple:
        """(sends, tx_bytes, rx_bytes) - handy for tests and for the status line."""
        return (self.sends, self.tx_bytes, self.rx_bytes)

    def __repr__(self) -> str:                       # pragma: no cover - debug aid
        return "SessionStats(sends=%d, tx=%d, rx=%d)" % self.snapshot()
