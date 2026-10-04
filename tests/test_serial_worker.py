"""Unit tests for app.serial_worker (/hang-prevention invariants)."""

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
        """A stuck device must not starve the read/signal path."""
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
        """Closing from the GUI must not block: the worker closes its own port."""
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


class TestFlowControlGuard:
    """never walk into a driver write that can block on CTS."""

    def test_write_skipped_when_cts_is_low(self):
        w = SerialWorker()
        port = FakePort()
        port.cts = False
        w._port = port
        w._rtscts = True
        errors = []
        w.send_error.connect(lambda kind, detail: errors.append(kind))
        w.send(b"\x07")                   # queued frame
        w._drain_tx()
        assert port.writes == []          # the driver was never entered
        assert errors == ["cts"]
        assert w.queued_frames() == 0     # the frame was dropped, not retried

    def test_write_proceeds_when_cts_is_high(self):
        w = SerialWorker()
        port = FakePort()
        port.cts = True
        w._port = port
        w._rtscts = True
        w.send(b"\x01")
        w._drain_tx()
        assert port.writes == [b"\x01"]

    def test_no_cts_check_without_hardware_flow_control(self):
        w = SerialWorker()
        port = FakePort()
        port.cts = False                  # ignored when rtscts is off
        w._port = port
        w._rtscts = False
        w.send(b"\x02")
        w._drain_tx()
        assert port.writes == [b"\x02"]

    def test_timeout_degrades_the_port(self):
        w = SerialWorker()
        w._port = FakePort(timeout=True)
        errors = []
        w.send_error.connect(lambda kind, detail: errors.append(kind))
        w.send(b"\x03")
        w._drain_tx()
        assert errors[0] == "timeout"
        assert w._tx_degraded is True
        errors.clear()
        assert w.send(b"\x04") is False    # no more writes into a stuck driver
        assert errors == ["degraded"]

    def test_reopening_clears_the_degraded_state(self):
        import app.serial_worker as sw

        class StubSerial(FakePort):
            def __init__(self, **kwargs):
                super().__init__()

        real = sw.serial.Serial
        sw.serial.Serial = StubSerial
        try:
            w = SerialWorker()
            w._port = FakePort(timeout=True)
            w.send(b"\x05")
            w._drain_tx()
            assert w._tx_degraded is True
            assert w.open_port("COM_TEST", 115200) is True
            assert w._tx_degraded is False
            w.close_port()                 # never leave a QThread running at exit
            w.wait(2000)
        finally:
            sw.serial.Serial = real


class TestAutoReconnect:
    """T14: reopen after an unexpected loss, never after a manual close."""

    @staticmethod
    def _events(worker):
        seen = []
        worker.reconnecting.connect(seen.append)
        worker.reconnected.connect(lambda: seen.append("ok"))
        worker.disconnected.connect(lambda _r: seen.append("lost"))
        return seen

    def test_manual_close_never_reconnects(self):
        w = SerialWorker()
        w._auto_reconnect = True
        w._user_closed = True
        w._port = FakePort()
        seen = self._events(w)
        w._handle_disconnect("unplugged")
        assert seen == ["lost"]

    def test_disabled_does_not_reconnect(self):
        w = SerialWorker()
        w._auto_reconnect = False
        w._user_closed = False
        w._port = FakePort()
        seen = self._events(w)
        w._handle_disconnect("unplugged")
        assert seen == ["lost"]

    def test_retries_with_bounded_backoff_until_success(self):
        import app.serial_worker as sw

        w = SerialWorker()
        w._auto_reconnect = True
        w._user_closed = False
        w._running = True
        w._port = FakePort()
        seen = self._events(w)
        sleeps: list[float] = []
        real_sleep = sw.time.sleep
        sw.time.sleep = lambda s: sleeps.append(s)      # keep the test instant
        try:
            calls = {"n": 0}

            def fake_reopen() -> bool:
                calls["n"] += 1
                return calls["n"] >= 3                   # up on the third try

            w._try_reopen = fake_reopen
            w._handle_disconnect("driver error")
        finally:
            sw.time.sleep = real_sleep
        assert seen == [1, 2, 3, "ok"]
        assert sleeps == [0.5, 1.0, 1.5]                 # attempt * 0.5 s
        assert w._user_closed is False

    def test_gives_up_when_still_away(self):
        import app.serial_worker as sw

        w = SerialWorker()
        w._auto_reconnect = True
        w._user_closed = False
        w._running = True
        w._port = FakePort()
        seen = self._events(w)
        real_sleep = sw.time.sleep
        sw.time.sleep = lambda s: None
        try:
            calls = {"n": 0}

            def always_fails() -> bool:
                calls["n"] += 1
                if calls["n"] >= 3:
                    w._user_closed = True          # the user gives up / closes the app
                return False

            w._try_reopen = always_fails
            w._handle_disconnect("still away")
        finally:
            sw.time.sleep = real_sleep
        assert seen[-1] == "lost" and seen.count("lost") == 1


class BatchPort:
    """Hands out pre-set chunks and records how the worker read it."""

    is_open = True
    cts = dsr = cd = ri = False

    def __init__(self, chunks):
        self._chunks = [bytes(c) for c in chunks]
        self.read_sizes = []

    @property
    def in_waiting(self):
        return len(self._chunks[0]) if self._chunks else 0

    def read(self, n):
        self.read_sizes.append(n)
        if not self._chunks:
            return b""
        data = self._chunks.pop(0)
        return data[:n] if n > 0 else data

    def write(self, data):
        return len(data)

    def close(self):
        self.is_open = False


class TestReceiveBatching:
    """2026-10-03: fewer cross-thread hops, and no busy sleep."""

    def test_chunks_are_coalesced_into_one_signal(self):
        from app.serial_worker import SerialWorker
        w = SerialWorker()
        w._port = BatchPort([b"\x01\x02", b"\x03\x04"])
        seen = []
        w.received.connect(lambda ts, data: seen.append(data))
        w._pump_rx()                     # first chunk: batch open, under the cap
        assert seen == []
        w._rx_batch_ts -= 1.0            # the stream goes quiet for a while
        w._pump_rx()                     # second chunk still joins the same batch
        assert seen == []
        w._rx_batch_ts -= 1.0
        w._pump_rx()                     # nothing new -> flushed as one signal
        assert seen == [b"\x01\x02\x03\x04"]

    def test_an_idle_port_is_a_blocking_read_not_a_sleep_spin(self):
        from app.serial_worker import SerialWorker
        w = SerialWorker()
        port = BatchPort([])
        w._port = port
        seen = []
        w.received.connect(lambda ts, data: seen.append(data))
        w._pump_rx()
        assert port.read_sizes == [1]     # read(1) with a timeout, not sleep(0.001)
        assert seen == []

    def test_batch_flushes_at_the_size_cap(self):
        from app.serial_worker import RX_BATCH_MAX, SerialWorker
        payload = b"A" * RX_BATCH_MAX
        w = SerialWorker()
        w._port = BatchPort([payload])
        seen = []
        w.received.connect(lambda ts, data: seen.append(data))
        w._pump_rx()
        assert seen == [payload]

    def test_closing_hands_over_what_was_already_read(self):
        from app.serial_worker import SerialWorker
        w = SerialWorker()
        w._port = BatchPort([b"\x07"])
        seen = []
        w.received.connect(lambda ts, data: seen.append(data))
        w._pump_rx()
        w.close_port()                    # nothing already read may be dropped
        assert seen == [b"\x07"]
