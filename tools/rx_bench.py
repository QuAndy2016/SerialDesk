"""Receive-path throughput benchmark (2026-10-03, data-path work).

Feeds a synthetic serial stream through the *real* receive path (framing + fragment
store + receive pane) at a chosen baud rate and reports where the time goes, so
"can it keep up?" is a number instead of a feeling.

Run it offscreen so it works on a build server:

    QT_QPA_PLATFORM=offscreen python3 tools/rx_bench.py --baud 1000000 --seconds 5

The measurement emulates the worker's batching: every 10 ms the tool hands over the
bytes that baud rate would have delivered in that window. If the average batch cost
stays under the batch period, the UI keeps up with the line rate; if it does not, the
queue can only grow (Little's law) and the run reports the shortfall.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BATCH_MS = 10.0            # the worker's coalescing window (app/serial_worker.py)
LINE_CHARS = 40            # a realistic line length for the synthetic stream


def build_payload(seconds: float, baud: int) -> bytes:
    """Printable ASCII with regular line breaks - what a device actually sends."""
    total = int(baud / 10.0 * seconds)          # bytes/s at 8N1 is baud/10
    block = (b"T=24.6C  VIN=12.12V  IBUS=0.83A  RPM=1240\n")
    out = bytearray()
    while len(out) < total:
        out.extend(block)
    return bytes(out[:total])


def main() -> int:
    parser = argparse.ArgumentParser(description="SerialDesk receive-path benchmark")
    parser.add_argument("--baud", type=int, default=1000000)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--timestamp", action="store_true", help="leave timestamps on")
    parser.add_argument("--limit-ms", type=float, default=16.0,
                        help="fail when the batch p95 exceeds this (default 16 ms)")
    args = parser.parse_args()

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from ui.main_window import MainWindow
    from ui.regions import RX_ASCII, SPLIT_AUTO, SPLIT_FIXED, RECEIVE_MAX_LINES
    from ui.receive_controller import RX_STORE_MAX
    from app.display import rows_from_fragments

    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    for _ in range(3):
        app.processEvents()

    win.rx_fmt_combo.setCurrentIndex(RX_ASCII)
    win.ts_check.setChecked(args.timestamp)
    win.split_combo.setCurrentIndex(SPLIT_AUTO)
    win.rx_view.clear()
    win._rx_store = []

    payload = build_payload(args.seconds, args.baud)
    per_batch = max(1, int(args.baud / 10.0 * (BATCH_MS / 1000.0)))
    batches = [payload[i:i + per_batch] for i in range(0, len(payload), per_batch)]

    costs: list[float] = []
    pending: list[int] = []
    started = time.perf_counter()
    ts = 1000.0
    for chunk in batches:
        ts += BATCH_MS / 1000.0
        t0 = time.perf_counter()
        win.on_received(ts, chunk)
        app.processEvents()                     # what the GUI thread does per batch
        win._flush_rx_frames()                  # the settle timer's job in production
        app.processEvents()
        costs.append((time.perf_counter() - t0) * 1000.0)   # ms
        pending.append(len(getattr(win, "_rx_store", [])))
    wall = time.perf_counter() - started

    stream_ms = len(batches) * BATCH_MS
    sent = sum(len(c) for c in batches)
    received = win.rx_bytes
    rows = win.rx_view.blockCount()
    p50 = statistics.median(costs)
    p95 = sorted(costs)[int(len(costs) * 0.95) - 1]
    worst = max(costs)

    print("baud              : %d bits/s (%.0f B/s, 8N1)" % (args.baud, args.baud / 10.0))
    print("stream            : %d bytes in %d batches of %d B (%.0f ms of line time)"
          % (sent, len(batches), per_batch, stream_ms))
    print("timestamp switch  : %s" % ("on" if args.timestamp else "off"))
    print("per-batch cost ms : p50 %.2f  p95 %.2f  worst %.2f" % (p50, p95, worst))
    print("wall clock        : %.0f ms for %.0f ms of stream (%.2fx real time)"
          % (wall * 1000.0, stream_ms, wall * 1000.0 / stream_ms))
    print("receive pane      : %d rows, fragment store %d entries"
          % (rows, len(getattr(win, "_rx_store", []))))
    print("counted bytes     : %d received / %d sent  -> %s"
          % (received, sent, "no loss" if received == sent else "LOSS"))
    model_rows = len(rows_from_fragments(list(getattr(win, "_rx_store", []))))
    pane_rows = win.rx_view.blockCount()
    # The pane caps its display at RECEIVE_MAX_LINES and the fragment store at
    # RX_STORE_MAX; past either cap the two deliberately hold different windows, so
    # the row invariant only applies while the run still fits both.
    capped = (len(getattr(win, "_rx_store", [])) >= RX_STORE_MAX
              or pane_rows >= RECEIVE_MAX_LINES)
    print("row model         : pane %d blocks, model %d rows%s"
          % (pane_rows, model_rows, " (capped)" if capped else ""))
    verdict = "keeps up" if p95 <= BATCH_MS else "cannot keep up (queue would grow)"
    print("verdict           : %s (p95 %.2f ms vs %.0f ms batch period)" % (verdict, p95, BATCH_MS))
    ok_loss = received == sent
    ok_cost = p95 <= args.limit_ms
    ok_rows = (pane_rows == model_rows) or capped
    print("acceptance        : loss=%s  p95<=%.0fms=%s  rows=%s"
          % ("OK" if ok_loss else "FAIL", args.limit_ms,
             "OK" if ok_cost else "FAIL",
             "OK" if (pane_rows == model_rows) else ("n/a (capped)" if capped else "FAIL")))
    return 0 if (ok_loss and ok_cost and ok_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
