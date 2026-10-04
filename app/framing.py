"""Frame assembly for received bytes.

USB serial adapters do not deliver one frame per read: the driver and the OS
scheduler hand over a frame in several chunks (1-16 ms apart). Deciding a line
break from the gap *between chunks* therefore splits frames in the middle.

This module merges chunks inside a short "settle" window and only then decides
whether the group starts a new line, comparing timestamps between *flushes*.
Qt-free on purpose so the timing rules can be unit-tested with synthetic clocks.
"""

from __future__ import annotations

#: How long a group may keep collecting before it is flushed.
#:
#: The number is not a guess about the wire: it is the USB *driver*'s own batching delay.
#: On this machine the adapter is an FTDI FT232 (VID_0403+PID_6001, COM5); the vendor INF
#: sets `LatencyTimer` = 16 ms - `C:\Windows\INF\oem8.inf:382`
#: (`HKR,,"LatencyTimer",0x00010001,16`) - and the live device node reports the same value
#: (`HKLM\SYSTEM\CurrentControlSet\Enum\FTDIBUS\VID_0403+PID_6001+A50285BIA\0000\
#: Device Parameters\LatencyTimer = 16`). FTDI's driver deliberately holds received data up
#: to that timer before handing it to the application, so one frame reaches us in chunks
#: tens of milliseconds apart; the reported case measured 31 ms between the first chunk and
#: the rest of a 57-byte frame at 115200 baud (2026-10-04). 50 ms covers the default timer
#: with margin and stays adjustable by the user (Device Manager -> Port Settings ->
#: Advanced -> Latency Timer; 1 ms makes chunks arrive almost immediately).
#:
#: The window must also scale with slow links, where one character takes longer than the
#: timer: `__init__` raises it to at least the line-break threshold, and
#: `ui/params_controller.split_threshold_ms()` keeps that threshold at
#: max(3.5 char times, 50 ms). It stays a *fixed* window from the group's first byte (not a
#: debounce) so a steady stream keeps flushing instead of starving.
DEFAULT_SETTLE_MS = 50.0
MIN_SETTLE_MS = 2.0
MAX_SETTLE_MS = 200.0

#: Gap sampling for the diagnostics read-out (see FrameAssembler.gap_stats).
GAP_SAMPLE_LIMIT = 4000          # keep the newest N gaps
MAX_GAP_SAMPLE_MS = 200.0        # above this it is an inter-frame silence, not a chunk gap


class FrameAssembler:
    """Collect chunks into a frame, then report when it is ready to display."""

    def __init__(self, settle_ms: float = DEFAULT_SETTLE_MS,
                 threshold_ms: float | None = None) -> None:
        self.threshold_ms = threshold_ms
        # A group can only be "complete" once the silence that would start a new line has
        # passed, so the collection window never sits below the break threshold.
        self.settle_ms = min(MAX_SETTLE_MS,
                             max(MIN_SETTLE_MS, float(settle_ms),
                                 float(threshold_ms or 0.0)))
        self._buf = bytearray()
        self._first_ts: float | None = None
        self._last_flush_ts: float | None = None
        self._start_new_line = True
        #: Inter-chunk gaps seen inside a burst (ms). The USB adapter's latency timer is what
        #: these measure, so they are the evidence for tuning the window: the diagnostics
        #: dialog prints them, and a gap above the window is exactly what splits a frame.
        self._gaps_ms: list[float] = []
        self._last_chunk_ts: float | None = None

    # -- input (called from the GUI thread on every received chunk) ----------

    def feed(self, ts: float, data: bytes) -> None:
        """Add a chunk; the line-break decision is taken once per group."""
        if not data:
            return
        if self._last_chunk_ts is not None:
            gap = (ts - self._last_chunk_ts) * 1000.0
            if 0.0 < gap < MAX_GAP_SAMPLE_MS:      # ignore the long inter-frame silences
                self._gaps_ms.append(gap)
                if len(self._gaps_ms) > GAP_SAMPLE_LIMIT:
                    del self._gaps_ms[:len(self._gaps_ms) - GAP_SAMPLE_LIMIT]
        self._last_chunk_ts = ts
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
        """True while a partial frame is waiting for more bytes."""
        return self._first_ts is not None

    def pending_bytes(self) -> int:
        """Bytes currently held in the partial frame."""
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

    def gap_stats(self) -> dict:
        """Observed intra-burst chunk gaps in ms: count, p95 and max (0 when none yet)."""
        if not self._gaps_ms:
            return {"count": 0, "p95": 0.0, "max": 0.0}
        ordered = sorted(self._gaps_ms)
        index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
        return {"count": len(ordered), "p95": ordered[index], "max": ordered[-1]}


# -- B3: stream splitters (pure, Qt-free) -----------------------------------
#
# The time-based FrameAssembler above decides *where a line breaks*; these
# helpers decide *what a frame is* from the bytes themselves. They are pure so
# each rule can be unit-tested without a serial port or a QApplication.


def split_fixed(buf: bytes, size: int) -> tuple[list[bytes], bytes]:
    """Cut ``buf`` into fixed-size frames; returns (frames, remainder)."""
    if size <= 0:
        return [], bytes(buf)
    whole = len(buf) - (len(buf) % size)
    frames = [bytes(buf[i:i + size]) for i in range(0, whole, size)]
    return frames, bytes(buf[whole:])


def split_delimited(buf: bytes, start: bytes, end: bytes = b"",
                    include: bool = True) -> tuple[list[bytes], bytes]:
    """Cut frames delimited by ``start``..``end`` (``end`` empty = start-to-start).

    Returns (frames, remainder); an unterminated tail stays in the remainder so
    the caller can wait for the next chunk.
    """
    frames: list[bytes] = []
    i = 0
    while True:
        s = buf.find(start, i) if start else i
        if s < 0:
            return frames, bytes(buf[i:])
        if end:
            e = buf.find(end, s + len(start))
            if e < 0:
                return frames, bytes(buf[s:])
            stop = e + len(end)
            seg = buf[s:stop] if include else buf[s + len(start):e]
        else:
            nxt = buf.find(start, s + len(start))
            if nxt < 0:
                return frames, bytes(buf[s:])
            stop = nxt
            seg = buf[s:stop]
        frames.append(bytes(seg))
        i = stop


def split_length_prefixed(buf: bytes, prefix_bytes: int = 1, little: bool = False,
                          crc_bytes: int = 0) -> tuple[list[bytes], bytes]:
    """Cut frames whose first ``prefix_bytes`` bytes hold the payload length.

    ``crc_bytes`` (0 or 2, CRC-16/Modbus over the payload) is validated and
    stripped when present; an odd/too-short tail stays in the remainder.
    """
    frames: list[bytes] = []
    off = 0
    while True:
        if len(buf) - off < prefix_bytes:
            return frames, bytes(buf[off:])
        raw = bytes(buf[off:off + prefix_bytes])
        n = int.from_bytes(raw, "little" if little else "big")
        need = prefix_bytes + n + crc_bytes
        if len(buf) - off < need:
            return frames, bytes(buf[off:])
        payload = bytes(buf[off + prefix_bytes:off + prefix_bytes + n])
        if crc_bytes:
            got = int.from_bytes(buf[off + need - crc_bytes:off + need],
                                 "little" if little else "big")
            if got != crc16_modbus(payload):
                off += need          # bad CRC: drop the frame and resync
                continue
        frames.append(payload)
        off += need


def crc16_modbus(data: bytes) -> int:
    """CRC-16/Modbus (poly 0xA001, init 0xFFFF) - the check Modbus RTU uses."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


# -- B3: stateful wrappers ---------------------------------------------------
#
# The split_* helpers above cut a complete buffer; a serial port hands over a
# stream, so the partial tail has to survive between chunks. These small
# classes keep that tail and re-run the rule whenever new bytes arrive.

SPLIT_FIXED = "fixed"
SPLIT_DELIMITED = "delimited"
SPLIT_TLV = "tlv"


class ByteFrameSplitter:
    """Hold a byte tail and cut frames with one of the pure B3 rules.

    One instance per receive path: ``feed()`` returns the frames that became
    complete with the new chunk, and the unfinished tail stays buffered until
    the next chunk (or until ``take_pending()`` flushes it).
    """

    def __init__(self, mode: str = SPLIT_FIXED, size: int = 8,
                 start: bytes = b"", end: bytes = b"", include: bool = True,
                 prefix_bytes: int = 1, little: bool = False,
                 crc_bytes: int = 0) -> None:
        self._buf = bytearray()
        self.mode = mode
        self.size = max(1, int(size))
        self.start = bytes(start)
        self.end = bytes(end)
        self.include = bool(include)
        self.prefix_bytes = max(1, int(prefix_bytes))
        self.little = bool(little)
        self.crc_bytes = 2 if int(crc_bytes) else 0

    def configure(self, mode: str = SPLIT_FIXED, size: int = 8,
                  start: bytes = b"", end: bytes = b"", include: bool = True,
                  prefix_bytes: int = 1, little: bool = False,
                  crc_bytes: int = 0) -> None:
        """Replace the rule without dropping the buffered tail."""
        self.mode = mode
        self.size = max(1, int(size))
        self.start = bytes(start)
        self.end = bytes(end)
        self.include = bool(include)
        self.prefix_bytes = max(1, int(prefix_bytes))
        self.little = bool(little)
        self.crc_bytes = 2 if int(crc_bytes) else 0

    def feed(self, data: bytes) -> list[bytes]:
        """Add a chunk and return the frames it completed (never a partial)."""
        if data:
            self._buf.extend(data)
        frames, rest = self._cut(bytes(self._buf))
        self._buf[:] = rest
        return frames

    def pending(self) -> bytes:
        """The unfinished tail held for the next chunk."""
        return bytes(self._buf)

    def take_pending(self) -> bytes:
        """Flush and clear the tail (mode change, port close, clear)."""
        out = bytes(self._buf)
        self._buf.clear()
        return out

    def reset(self) -> None:
        """Drop the tail (display cleared)."""
        self._buf.clear()

    def _cut(self, buf: bytes) -> tuple[list[bytes], bytes]:
        if self.mode == SPLIT_DELIMITED:
            if not self.start and not self.end:
                return [], buf          # no delimiter set yet: nothing to cut
            return split_delimited(buf, self.start, self.end, self.include)
        if self.mode == SPLIT_TLV:
            return split_length_prefixed(buf, self.prefix_bytes, self.little,
                                         self.crc_bytes)
        return split_fixed(buf, self.size)
