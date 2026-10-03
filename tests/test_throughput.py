"""Data-path P2: rolling throughput meter (pure logic, no window)."""

from __future__ import annotations

from app.throughput import ThroughputMeter, human_rate


def test_meter_averages_over_the_live_window():
    meter = ThroughputMeter(window_s=1.0)
    meter.record(10.0, 1000, 4, 1.0)
    meter.record(10.5, 1000, 4, 2.0)
    snap = meter.snapshot(10.6)
    assert snap["bps"] > 1500.0          # ~2000 B over the live span
    assert snap["batches"] > 2.0
    assert snap["merge"] == 4.0
    assert snap["max_ms"] == 2.0


def test_meter_forgets_samples_older_than_the_window():
    meter = ThroughputMeter(window_s=1.0)
    meter.record(10.0, 5000, 1, 3.0)
    snap = meter.snapshot(12.0)
    assert snap["bps"] == 0.0 and snap["batches"] == 0.0
    assert snap["max_ms"] == 3.0         # the peak survives until reset
    meter.reset_peak()
    assert meter.snapshot(12.0)["max_ms"] == 0.0


def test_meter_counts_dropped_fragments():
    meter = ThroughputMeter()
    meter.note_dropped(3)
    meter.note_dropped()
    assert meter.snapshot(0.0)["dropped"] == 4


def test_human_rate_units():
    assert human_rate(512) == "512 B/s"
    assert human_rate(2048).endswith("KB/s")
    assert human_rate(3 * 1024 * 1024).endswith("MB/s")
