"""Serial worker: background QThread doing read loop, emits (timestamp, data).

U52/U64 design notes - the GUI thread never performs serial I/O:
- Outgoing frames are handed over through a bounded queue (`send()` only enqueues).
- Writes carry a `write_timeout`, so a driver that never completes the transfer
  (e.g. hardware flow control waiting for CTS) raises instead of blocking forever.
- The queue is drained a few frames per loop turn so the receive path and the
  modem-status polling keep running even when a device stopped accepting data.
- The worker thread closes its own port: closing a handle while the driver is
  still completing a write can block for seconds, which used to freeze the window
  and prevent the app from exiting.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from PySide6.QtCore import QThread, Signal

import serial
from serial.tools import list_ports

WRITE_TIMEOUT = 0.3         # seconds; a stuck write must not hang the app
READ_TIMEOUT = 0.1          # seconds
SIGNAL_POLL_INTERVAL = 0.2  # seconds between modem-status reads
MAX_TX_QUEUE = 64           # frames; protects memory if the port stops draining
MAX_TX_PER_TICK = 2         # frames written per loop turn (keeps RX alive, U64)


def list_serial_ports() -> list:
    """Return list of (port, description) tuples."""
    return [(p.device, p.description) for p in list_ports.comports()]


class SerialWorker(QThread):
    """Owns the serial port; safe to open/close/send from UI thread.

    received carries (monotonic_timestamp, raw_bytes) so the UI layer can
    implement time-gap frame splitting (packet segmentation by baud rate).
    """

    received = Signal(float, bytes)   # (time.monotonic(), raw bytes)
    log = Signal(str)                 # info/error lines
    opened = Signal(bool)             # True when opened, False when closed/error
    error = Signal(str)               # user-facing open/IO failure text (U37)
    send_error = Signal(str, str)     # (kind, detail) - kind: timeout/closed/queue/io (U52)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port: serial.Serial | None = None
        self._running = False
        self._tx_queue: deque[bytes] = deque()
        self._tx_lock = threading.Lock()
        self._sig_cache = {"open": False, "cts": False, "dsr": False,
                           "dcd": False, "ri": False}
        self._sig_lock = threading.Lock()

    # -- control (UI thread; never blocks on serial I/O) ---------------------

    def open_port(self, device: str, baudrate: int, **kwargs) -> bool:
        try:
            self._port = serial.Serial(
                port=device,
                baudrate=baudrate,
                bytesize=kwargs.get("bytesize", serial.EIGHTBITS),
                parity=kwargs.get("parity", serial.PARITY_NONE),
                stopbits=kwargs.get("stopbits", serial.STOPBITS_ONE),
                rtscts=kwargs.get("rtscts", False),
                xonxoff=kwargs.get("xonxoff", False),
                timeout=READ_TIMEOUT,
                write_timeout=WRITE_TIMEOUT,   # U52: never block forever on write
            )
        except Exception as exc:  # noqa: BLE001 - surface any serial error
            self.log.emit(f"open failed: {exc}")
            self.error.emit(str(exc))
            self.opened.emit(False)
            return False
        self._running = True
        if not self.isRunning():
            self.start()
        self.opened.emit(True)
        self.log.emit(f"opened {device} @ {baudrate}")
        return True

    def close_port(self):
        """Ask the worker to stop. Never touches the port from this thread (U64)."""
        self._running = False
        with self._tx_lock:
            self._tx_queue.clear()
        # The worker owns the handle: if it is not running we may close directly,
        # otherwise it closes on the way out (closing inside a pending write can
        # block the caller for seconds and used to freeze the whole window).
        if not self.isRunning():
            self._close_port_safely()
        with self._sig_lock:
            self._sig_cache = {"open": False, "cts": False, "dsr": False,
                               "dcd": False, "ri": False}
        self.opened.emit(False)

    def send(self, data: bytes) -> bool:
        """Enqueue a frame for the worker thread (returns False when dropped)."""
        if self._port is None or not self._port.is_open:
            self.send_error.emit("closed", "")
            return False
        with self._tx_lock:
            if len(self._tx_queue) >= MAX_TX_QUEUE:
                self.send_error.emit("queue", str(len(self._tx_queue)))
                return False
            self._tx_queue.append(bytes(data))
        return True

    def queued_frames(self) -> int:
        """Number of frames waiting to be written (diagnostics, U52)."""
        with self._tx_lock:
            return len(self._tx_queue)

    def is_open(self) -> bool:
        return self._port is not None and self._port.is_open

    # -- modem control lines (T9) -------------------------------------------

    def set_dtr(self, value: bool) -> None:
        """Drive the DTR output line."""
        if self._port is not None and self._port.is_open:
            try:
                self._port.dtr = bool(value)
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"dtr failed: {exc}")

    def set_rts(self, value: bool) -> None:
        """Drive the RTS output line."""
        if self._port is not None and self._port.is_open:
            try:
                self._port.rts = bool(value)
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"rts failed: {exc}")

    def signals(self) -> dict:
        """Cached modem status lines (U52: no serial I/O on the calling thread)."""
        with self._sig_lock:
            return dict(self._sig_cache)

    # -- internals (worker thread) ------------------------------------------

    def _close_port_safely(self) -> None:
        """Close the port handle (worker thread, or when no thread is running)."""
        if self._port is not None:
            try:
                self._port.close()
            except Exception:  # noqa: BLE001
                pass
            self._port = None

    def _poll_signals(self) -> None:
        """Refresh the modem-status cache (worker thread only)."""
        port = self._port
        if port is None or not port.is_open:
            state = {"open": False, "cts": False, "dsr": False, "dcd": False, "ri": False}
        else:
            def read(name: str) -> bool:
                try:
                    return bool(getattr(port, name))
                except Exception:  # noqa: BLE001
                    return False

            state = {"open": True, "cts": read("cts"), "dsr": read("dsr"),
                     "dcd": read("cd"), "ri": read("ri")}
        with self._sig_lock:
            self._sig_cache = state

    def _drain_tx(self) -> None:
        """Write at most MAX_TX_PER_TICK frames, then let the read loop run (U64).

        Draining without a limit starves the receive path (RX stays 0) whenever a
        device stops accepting writes.
        """
        for _ in range(MAX_TX_PER_TICK):
            with self._tx_lock:
                if not self._tx_queue:
                    return
                data = self._tx_queue.popleft()
            self._write_one(data)

    def _write_one(self, data: bytes) -> None:
        """Write a single frame (worker thread only)."""
        port = self._port
        if port is None or not port.is_open:
            self.send_error.emit("closed", "")
            return
        try:
            port.write(data)
            self.log.emit(f"TX {len(data)} bytes")
        except serial.SerialTimeoutException as exc:
            # driver never accepted the bytes (buffer full / CTS never asserted)
            with self._tx_lock:
                self._tx_queue.clear()      # U64: drop the stale backlog
            self.log.emit(f"send timeout: {exc}")
            self.send_error.emit("timeout", str(exc))
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"send failed: {exc}")
            self.send_error.emit("io", str(exc))

    # -- thread body ----------------------------------------------------------

    def run(self):
        last_sig = 0.0
        while self._running:
            if self._port is None or not self._port.is_open:
                time.sleep(0.05)
                continue
            try:
                self._drain_tx()
                now = time.monotonic()
                if now - last_sig >= SIGNAL_POLL_INTERVAL:
                    last_sig = now
                    self._poll_signals()
                waiting = self._port.in_waiting
                if waiting:
                    data = self._port.read(waiting)
                    if data:
                        self.received.emit(time.monotonic(), data)
                else:
                    time.sleep(0.001)
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"read error: {exc}")
                self.opened.emit(False)
                break
        # the worker closes its own handle on the way out (U64)
        self._close_port_safely()
        with self._sig_lock:
            self._sig_cache = {"open": False, "cts": False, "dsr": False,
                               "dcd": False, "ri": False}
