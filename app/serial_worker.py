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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

WRITE_TIMEOUT = 0.3         # seconds; a stuck write must not hang the app
READ_TIMEOUT = 0.005        # seconds; a real wait, not a spin (see _read_chunk)
RX_BATCH_MAX = 4096         # bytes; push a batch to the UI at this size
RX_BATCH_MS = 10.0          # ms; or once the stream has been quiet this long
SIGNAL_POLL_INTERVAL = 0.2  # seconds between modem-status reads
MAX_TX_QUEUE = 64           # frames; protects memory if the port stops draining
MAX_TX_PER_TICK = 2         # frames written per loop turn (keeps RX alive, U64)
MAX_RECONNECT_ATTEMPTS = 60  # give up after ~2 minutes of retries (T14)


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
    disconnected = Signal(str)        # unexpected loss, no reconnect possible (T14)
    reconnecting = Signal(int)        # attempt number (T14)
    reconnected = Signal()            # came back on its own (T14)

    def __init__(self, parent: QWidget | None=None):
        super().__init__(parent)
        self._port: serial.Serial | None = None
        self._running = False
        self._tx_queue: deque[bytes] = deque()
        self._tx_lock = threading.Lock()
        self._sig_cache = {"open": False, "cts": False, "dsr": False,
                           "dcd": False, "ri": False}
        self._sig_lock = threading.Lock()
        self._rtscts = False        # hardware flow control enabled? (U65)
        self._tx_degraded = False   # a write timed out: refuse more sends until reopen (U65)
        self._auto_reconnect = False   # T14
        self._user_closed = True       # True = the user closed it; never auto-reopen
        self._device, self._baud, self._open_kwargs = "", 115200, {}
        self._rx_batch = bytearray()   # 2026-10-03: coalesced read buffer
        self._rx_batch_ts = 0.0        # when the current batch started

    # -- control (UI thread; never blocks on serial I/O) ---------------------

    def open_port(self, device: str, baudrate: int, **kwargs) -> bool:
        """Open the port (UI thread; never blocks on serial I/O)."""
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
        except (serial.SerialException, OSError, ValueError, TypeError) as exc:  # surface any serial error
            self.log.emit(f"open failed: {exc}")
            self.error.emit(str(exc))
            self.opened.emit(False)
            return False
        self._rtscts = bool(kwargs.get("rtscts", False))
        self._tx_degraded = False          # a fresh open clears the degraded state (U65)
        self._device, self._baud, self._open_kwargs = device, baudrate, dict(kwargs)
        self._user_closed = False          # T14: an open is a user action
        self._running = True
        if not self.isRunning():
            self.start()
        self.opened.emit(True)
        self.log.emit(f"opened {device} @ {baudrate}")
        return True

    def close_port(self):
        """Ask the worker to stop. Never touches the port from this thread (U64)."""
        self._running = False
        self._user_closed = True           # T14: stop any reconnect loop
        with self._tx_lock:
            self._tx_queue.clear()
        self._flush_rx_batch()             # 2026-10-03: nothing already read is dropped
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
        if self._tx_degraded:
            # U65: a write already timed out - do not walk back into the driver
            self.send_error.emit("degraded", "")
            return False
        with self._tx_lock:
            if len(self._tx_queue) >= MAX_TX_QUEUE:
                self.send_error.emit("queue", str(len(self._tx_queue)))
                return False
            self._tx_queue.append(bytes(data))
        return True

    def set_auto_reconnect(self, enabled: bool) -> None:
        """Enable/disable automatic reopening after an unexpected loss (T14)."""
        self._auto_reconnect = bool(enabled)

    def queued_frames(self) -> int:
        """Number of frames waiting to be written (diagnostics, U52)."""
        with self._tx_lock:
            return len(self._tx_queue)

    def is_open(self) -> bool:
        """True while the serial port is open."""
        return self._port is not None and self._port.is_open

    # -- modem control lines (T9) -------------------------------------------

    def set_dtr(self, value: bool) -> None:
        """Drive the DTR output line."""
        if self._port is not None and self._port.is_open:
            try:
                self._port.dtr = bool(value)
            except (serial.SerialException, OSError, ValueError, TypeError) as exc:  # a control line
                # must never take the UI down, the failure is reported instead
                self.log.emit(f"dtr failed: {exc}")

    def set_rts(self, value: bool) -> None:
        """Drive the RTS output line."""
        if self._port is not None and self._port.is_open:
            try:
                self._port.rts = bool(value)
            except (serial.SerialException, OSError, ValueError, TypeError) as exc:  # same as DTR: report, never raise
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
            except (serial.SerialException, OSError):  # closing a half-dead handle can raise
                # anything; swallowing it guarantees close() always completes
                pass
            self._port = None

    def _poll_signals(self) -> None:
        """Refresh the modem-status cache (worker thread only)."""
        port = self._port
        if port is None or not port.is_open:
            state = {"open": False, "cts": False, "dsr": False, "dcd": False, "ri": False}
        else:
            def read(name: str) -> bool:
                """Read one modem-status line, treating a missing line as not asserted."""
                try:
                    return bool(getattr(port, name))
                except (serial.SerialException, OSError, AttributeError):  # some USB-serial chips do not expose
                    # every modem line; "not asserted" is the truthful reading
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
        if self._rtscts:
            # U65: with hardware flow control, a low CTS means the driver would
            # block inside WriteFile until the peer raises it - drop instead.
            try:
                if not port.cts:
                    self.log.emit("send skipped: CTS not asserted")
                    self.send_error.emit("cts", "")
                    return
            except (serial.SerialException, OSError):  # a wedged driver reports nothing
                self.log.emit("send skipped: CTS unreadable")
                self.send_error.emit("cts", "")
                return
        try:
            port.write(data)
            self.log.emit(f"TX {len(data)} bytes")
        except serial.SerialTimeoutException as exc:
            # driver never accepted the bytes (buffer full / CTS never asserted)
            with self._tx_lock:
                self._tx_queue.clear()      # U64: drop the stale backlog
            self._tx_degraded = True        # U65: stop feeding a stuck driver
            self.log.emit(f"send timeout: {exc}")
            self.send_error.emit("timeout", str(exc))
        except (serial.SerialException, OSError) as exc:  # any other write failure is surfaced
            # to the user with the driver's own text, then the caller decides
            self.log.emit(f"send failed: {exc}")
            self.send_error.emit("io", str(exc))

    # -- reconnect (T14) -------------------------------------------------------

    def _try_reopen(self) -> bool:
        """Re-create the port with the original settings (worker thread only)."""
        if not self._device:
            return False
        try:
            self._port = serial.Serial(
                port=self._device,
                baudrate=self._baud,
                bytesize=self._open_kwargs.get("bytesize", serial.EIGHTBITS),
                parity=self._open_kwargs.get("parity", serial.PARITY_NONE),
                stopbits=self._open_kwargs.get("stopbits", serial.STOPBITS_ONE),
                rtscts=self._open_kwargs.get("rtscts", False),
                xonxoff=self._open_kwargs.get("xonxoff", False),
                timeout=READ_TIMEOUT,
                write_timeout=WRITE_TIMEOUT,
            )
        except (serial.SerialException, OSError) as exc:  # device still away
            self.log.emit(f"reconnect failed: {exc}")
            return False
        self._tx_degraded = False
        self.log.emit(f"reconnected {self._device} @ {self._baud}")
        return True

    def _handle_disconnect(self, reason: str) -> None:
        """Lost the port: report it, then reconnect if the user asked for it (T14)."""
        self._flush_rx_batch()             # 2026-10-03: hand over what was already read
        with self._tx_lock:
            self._tx_queue.clear()
        self._close_port_safely()
        with self._sig_lock:
            self._sig_cache = {"open": False, "cts": False, "dsr": False,
                               "dcd": False, "ri": False}
        self.log.emit(f"disconnected: {reason}")
        self.opened.emit(False)
        if self._user_closed or not self._auto_reconnect:
            self.disconnected.emit(reason)
            return
        attempt = 0
        while self._running and not self._user_closed and attempt < MAX_RECONNECT_ATTEMPTS:
            attempt += 1
            self.reconnecting.emit(attempt)
            time.sleep(min(5.0, 0.5 * attempt))     # bounded backoff
            if not self._running or self._user_closed:
                return
            if self._try_reopen():
                self.reconnected.emit()
                self.opened.emit(True)
                return
        self.disconnected.emit(reason)

    # -- receive path (worker thread) ----------------------------------------

    def _read_chunk(self) -> bytes:
        """One read, without ever busy-sleeping.

        The loop used to `time.sleep(0.001)` when nothing was waiting, but 1 ms is
        unreachable on Windows (default timer granularity is 15.6 ms), so at high
        baud rates the driver buffer could overflow between turns and bytes were
        lost mid-frame. A read with a short timeout is a real wait the OS
        implements, and it returns immediately when data is already buffered.
        """
        port = self._port
        if port is None or not port.is_open:
            return b""
        waiting = port.in_waiting
        return port.read(waiting if waiting else 1)

    def _pump_rx(self) -> None:
        """Read into the batch and hand it to the UI when it is worth a signal."""
        data = self._read_chunk()
        if data:
            if not self._rx_batch:
                self._rx_batch_ts = time.monotonic()
            self._rx_batch.extend(data)
            if len(self._rx_batch) >= RX_BATCH_MAX:
                self._flush_rx_batch()
            return
        if self._rx_batch and (time.monotonic() - self._rx_batch_ts) * 1000.0 >= RX_BATCH_MS:
            self._flush_rx_batch()

    def _flush_rx_batch(self) -> None:
        """Emit the coalesced batch as one received() signal (fewer cross-thread hops)."""
        if not self._rx_batch:
            return
        data = bytes(self._rx_batch)
        self._rx_batch.clear()
        self.received.emit(time.monotonic(), data)

    # -- thread body ----------------------------------------------------------

    def run(self):
        """Thread body: drain the TX queue and read incoming bytes."""
        last_sig = 0.0
        while self._running:
            if self._port is None or not self._port.is_open:
                self._flush_rx_batch()
                time.sleep(0.05)
                continue
            if not self._port.is_open:     # silently dropped (USB unplugged)
                self._handle_disconnect("port closed")
                continue
            try:
                self._drain_tx()
                now = time.monotonic()
                if now - last_sig >= SIGNAL_POLL_INTERVAL:
                    last_sig = now
                    self._poll_signals()
                self._pump_rx()
            except (serial.SerialException, OSError) as exc:  # a failing read means the device
                # went away; report it and let the reconnect logic take over
                self.log.emit(f"read error: {exc}")
                self._handle_disconnect(str(exc))    # T14: try to come back
                continue
        # the worker closes its own handle on the way out (U64)
        self._flush_rx_batch()
        self._close_port_safely()
        with self._sig_lock:
            self._sig_cache = {"open": False, "cts": False, "dsr": False,
                               "dcd": False, "ri": False}
