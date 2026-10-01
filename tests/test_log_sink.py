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


def test_prune_log_dir_drops_oldest_until_under_quota(tmp_path):
    # E4/U163d: the folder quota removes the oldest segments first
    import os
    from app.log_sink import prune_log_dir
    for i in range(3):
        p = os.path.join(str(tmp_path), "serial_%d.txt" % i)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("x" * 100)
        os.utime(p, (1000 + i, 1000 + i))
    removed = prune_log_dir(str(tmp_path), 250)      # 300 bytes -> drop the oldest
    assert removed == 1
    assert sorted(os.listdir(str(tmp_path))) == ["serial_1.txt", "serial_2.txt"]


def test_prune_log_dir_zero_means_unlimited(tmp_path):
    import os
    from app.log_sink import prune_log_dir
    p = os.path.join(str(tmp_path), "serial_0.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("x" * 100)
    assert prune_log_dir(str(tmp_path), 0) == 0
    assert os.path.exists(p)
