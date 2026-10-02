"""Data-path regression harness (2026-10-03).

These tests exist for the promise that matters: bytes that arrive must arrive
complete - no frame cut in half, no byte lost on the way to the pane, and the pane
and the fragment store must agree about line structure.

They feed synthetic chunked streams (the driver hands over arbitrary slices, so the
chunk sizes here are random) through the pure framing layer and through the window's
receive path, then compare what came out with what went in.
"""

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.framing import ByteFrameSplitter  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def win(app):
    """One window for the module: construction is the expensive part."""
    from ui.main_window import MainWindow
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    for _ in range(3):
        app.processEvents()
    yield window
    window.close()


def _chunks(payload, seed=7, lo=1, hi=97):
    """Yield random slices of the payload - how a serial driver actually delivers."""
    rnd = random.Random(seed)
    i = 0
    while i < len(payload):
        size = rnd.randrange(lo, hi)
        yield payload[i:i + size]
        i += size


def test_fixed_frames_lose_nothing_under_chunky_input():
    payload = bytes(range(256)) * 24                 # 6144 bytes, every value
    splitter = ByteFrameSplitter()
    splitter.configure(mode="fixed", size=7)
    frames = []
    for chunk in _chunks(payload):
        frames.extend(splitter.feed(chunk))
    tail = splitter.take_pending()
    assert b"".join(frames + [tail]) == payload      # byte-for-byte, in order
    assert all(len(frame) == 7 for frame in frames)
    assert len(tail) == len(payload) % 7


def test_delimited_frames_lose_nothing_under_chunky_input():
    payload = b"".join(b"<%d>" % i for i in range(400))
    splitter = ByteFrameSplitter()
    splitter.configure(mode="delimited", start=b"<", end=b">", include=True)
    frames = []
    for chunk in _chunks(payload):
        frames.extend(splitter.feed(chunk))
    tail = splitter.take_pending()
    assert b"".join(frames + [tail]) == payload
    assert frames[0] == b"<0>" and frames[-1] == b"<399>"


def test_length_prefixed_frames_lose_nothing_under_chunky_input():
    """The length prefix is consumed, so the payloads must come back intact."""
    frames_in = [bytes([(i * 7) % 256]) * (i % 17 + 1) for i in range(120)]
    payload = b"".join(bytes([len(frame)]) + frame for frame in frames_in)
    splitter = ByteFrameSplitter()
    splitter.configure(mode="tlv", prefix_bytes=1, little=True, crc_bytes=0)
    frames = []
    for chunk in _chunks(payload):
        frames.extend(splitter.feed(chunk))
    assert frames == frames_in                       # every frame, in order, whole
    assert splitter.take_pending() == b""


def test_every_byte_reaches_the_pane_in_a_fixed_frame_flood(app, win):
    """End-to-end: a chunked 6 KB stream at 'fixed 8' must land complete.

    The framing layer is checked above; this checks the receive path that runs on
    the GUI thread - counters, fragment store and pane included.
    """
    from app.display import rows_from_fragments
    from ui.regions import RX_ASCII, SPLIT_FIXED

    payload = bytes(0x30 + (i % 10) for i in range(6000))
    before = win.rx_bytes
    fmt_before = win.rx_fmt_combo.currentIndex()
    splitter = getattr(win, "_byte_splitter", None)
    if splitter is not None:
        splitter.reset()
    win.rx_fmt_combo.setCurrentIndex(RX_ASCII)        # compare text, not hex bytes
    win.split_combo.setCurrentIndex(SPLIT_FIXED)
    win.split_size_spin.setValue(8)
    win.rx_view.clear()
    win._rx_store = []
    try:
        for i, chunk in enumerate(_chunks(payload)):
            win.on_received(1000.0 + i / 100.0, chunk)
        win._flush_byte_frames()
        app.processEvents()

        shown = "".join(text for text, kind in win._rx_store
                        if kind == 0 and text != "\n")   # payload only, no line breaks
        assert shown == payload.decode("ascii")       # nothing lost, nothing reordered
        assert win.rx_bytes - before == len(payload)
        # the row model and the document must agree (the P0 invariant, under load)
        assert len(rows_from_fragments(win._rx_store)) == win.rx_view.blockCount()
    finally:
        win.rx_fmt_combo.setCurrentIndex(fmt_before)
        app.processEvents()
