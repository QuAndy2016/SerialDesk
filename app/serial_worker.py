"""Serial worker: background QThread doing read loop, emits (timestamp, data).

U52 (hang fix): *all* blocking serial I/O happens on this thread.
- Outgoing frames are handed over through a bounded queue (`send()` only enqueues),
  so a stalled write can never freeze the GUI.
- Writes carry a `write_timeout`, so a driver that never completes the transfer
  (e.g. hardware flow control waiting for CTS) raises instead of blocking forever.
- Modem status lines are polled here and cached; `signals()` is a plain dict read.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from PySide6.QtCore import QThread, Signal

import serial
from serial.tools import list_ports

WRITE_TIMEOUT = 0.3        # seconds; a stuck write must not hang the app
READ_TIMEOUT = 0.1         # seconds
SIGNAL_POLL_INTERVAL = 0.2  # seconds between modem-status reads (was 50 ms in the GUI)
MAX_TX_QUEUE = 64          # frames; protects memory if the port stops draining


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
        self._running = False
        with self._tx_lock:
            self._tx_queue.clear()
        if self._port is not None:
            try:
                self._port.close()
            except Exception:  # noqa: BLE001
                pass
            self._port = None
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
        """Write queued frames with a bounded timeout (worker thread only)."""
        while True:
            with self._tx_lock:
                if not self._tx_queue:
                    return
                data = self._tx_queue.popleft()
            port = self._port
            if port is None or not port.is_open:
                self.send_error.emit("closed", "")
                return
            try:
                port.write(data)
                self.log.emit(f"TX {len(data)} bytes")
            except serial.SerialTimeoutException as exc:
                # driver never accepted the bytes (buffer full / CTS never asserted)
                self.log.emit(f"send timeout: {exc}")
                self.send_error.emit("timeout", str(exc))
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"send failed: {exc}")
                self.send_error.emit("io", str(exc))
                return

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
        # drain anything left before exit
        if self._port is not None and self._port.is_open:
            try:
                self._port.close()
            except Exception:  # noqa: BLE001
                pass
            self._port = None
        with self._sig_lock:
            self._sig_cache = {"open": False, "cts": False, "dsr": False,
                               "dcd": False, "ri": False}
