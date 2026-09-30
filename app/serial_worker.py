"""Serial worker: background QThread doing read loop, emits (timestamp, data)."""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

import serial
from serial.tools import list_ports


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port: serial.Serial | None = None
        self._lock_port = False
        self._running = False

    # -- control (UI thread) ------------------------------------------------

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
                timeout=0.1,
            )
        except Exception as exc:  # noqa: BLE001 - surface any serial error
            self.log.emit(f"open failed: {exc}")
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
        if self._port is not None:
            try:
                self._port.close()
            except Exception:  # noqa: BLE001
                pass
            self._port = None
        self.opened.emit(False)

    def send(self, data: bytes):
        if self._port is None or not self._port.is_open:
            self.log.emit("send failed: port not open")
            return
        try:
            self._port.write(data)
            self.log.emit(f"TX {len(data)} bytes")
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"send failed: {exc}")

    def is_open(self) -> bool:
        return self._port is not None and self._port.is_open

    # -- thread body ----------------------------------------------------------

    def run(self):
        while self._running:
            if self._port is None or not self._port.is_open:
                time.sleep(0.05)
                continue
            try:
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