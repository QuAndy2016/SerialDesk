"""Log segment writing, rotation and the session header (refactor step 2)."""

import os

from app.log_sink import LogSink


def test_open_writes_the_session_header(tmp_path):
    sink = LogSink(str(tmp_path), header=lambda: "# SerialDesk log COM5 @ 115200")
    path = sink.open()
    assert os.path.basename(path).startswith("serial_")
    assert open(path, encoding="utf-8").read().startswith("# SerialDesk log")
    sink.close()


def test_append_accumulates_and_counts_bytes(tmp_path):
    sink = LogSink(str(tmp_path), header=None)
    sink.open()
    sink.append("abc")
    sink.append("de")
    sink.close()
    assert sink.bytes_written == 5
    assert open(sink.path, encoding="utf-8").read() == "abcde"


def test_rotation_by_size_starts_a_new_segment(tmp_path):
    sink = LogSink(str(tmp_path), max_bytes=3, header=None)
    sink.open()
    first = sink.path
    sink.append("aaaa")
    sink.append("bbbb")          # exceeds 4 bytes -> rotates before writing
    sink.close()
    assert sink.path != first
    assert open(os.path.join(str(tmp_path), os.path.basename(first)), encoding="utf-8").read() == "aaaa"


def test_rotation_by_age_uses_the_injected_clock(tmp_path):
    now = [1000.0]
    sink = LogSink(str(tmp_path), max_seconds=10, header=None, clock=lambda: now[0])
    sink.open()
    first = sink.path
    now[0] += 11
    sink.append("late")
    sink.close()
    assert sink.path != first


def test_append_without_open_is_a_noop(tmp_path):
    sink = LogSink(str(tmp_path), header=None)
    sink.append("ignored")
    assert sink.bytes_written == 0
