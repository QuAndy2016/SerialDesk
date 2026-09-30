"""Unit tests for app.serial_worker (U52/U64 hang-prevention invariants)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import serial  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.serial_worker import MAX_TX_PER_TICK, MAX_TX_QUEUE, SerialWorker  # noqa: E402

app = QApplication.instance() or QApplication([])


class FakePort:
    """Records writes; optionally behaves like a device that stopped reading."""

    def __init__(self, timeout: bool = False):
        self.is_open = True
        self.in_waiting = 0
        self.cts = self.dsr = self.cd = self.ri = False
        self.timeout = timeout
        self.writes: list[bytes] = []

    def write(self, data):
        self.writes.append(bytes(data))
        if self.timeout:
            raise serial.SerialTimeoutException("write timeout")
        return len(data)

    def read(self, n):
        return b""

    def close(self):
        self.is_open = False


class TestSendQueue:
    def test_send_without_port_reports_closed(self):
        w = SerialWorker()
        errors = []
        w.send_error.connect(lambda kind, detail: errors.append(kind))
        assert w.send(b"\x01") is False
        assert errors == ["closed"]

    def test_send_enqueues_and_reports_queue_full(self):
        w = SerialWorker()
        w._port = FakePort()
        errors = []
        w.send_error.connect(lambda kind, detail: errors.append(kind))
        for i in range(MAX_TX_QUEUE):
            assert w.send(bytes([i % 256])) is True
        assert w.send(b"\xff") is False and errors == ["queue"]
        assert w.queued_frames() == MAX_TX_QUEUE


class TestDrainIsBounded:
    def test_drain_writes_at_most_max_per_tick(self):
        """A stuck device must not starve the read/signal path (U64)."""
        w = SerialWorker()
        port = FakePort()
        w._port = port
        for _ in range(5):
            w.send(b"\x01\x02")
        w._drain_tx()
        assert len(port.writes) == MAX_TX_PER_TICK

    def test_timeout_clears_the_stale_backlog(self):
        w = SerialWorker()
        port = FakePort(timeout=True)
        w._port = port
        errors = []
        w.send_error.connect(lambda kind, detail: errors.append(kind))
        for _ in range(4):
            w.send(b"\x03")
        w._drain_tx()
        assert errors[0] == "timeout"
        assert w.queued_frames() == 0          # dropped, not retried forever


class TestCloseNeverBlocks:
    def test_close_port_does_not_touch_the_handle_when_thread_runs(self):
        """Closing from the GUI must not block: the worker closes its own port (U64)."""
        w = SerialWorker()
        port = FakePort()
        w._port = port
        w._running = True
        w.start()                              # the thread now owns the handle
        w.close_port()
        assert w._running is False
        assert port.is_open is True            # the GUI thread did not close it inline
        assert w.wait(3000)
        assert port.is_open is False           # the worker closed it on the way out
