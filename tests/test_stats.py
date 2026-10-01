"""Session counters (refactor step 1) - the bug this replaces was U103."""

from app.stats import SessionStats


def test_add_tx_counts_bytes_and_sends():
    s = SessionStats()
    s.add_tx(5)
    s.add_tx(5)
    assert s.snapshot() == (2, 10, 0)


def test_file_chunks_count_bytes_but_not_sends():
    s = SessionStats()
    s.add_tx(1024, count_send=False)
    assert s.snapshot() == (0, 1024, 0)


def test_receive_and_reset():
    s = SessionStats()
    s.add_rx(3)
    s.add_rx(7)
    assert s.rx_bytes == 10
    s.reset()
    assert s.snapshot() == (0, 0, 0)


def test_negative_input_is_ignored():
    s = SessionStats()
    s.add_rx(-5)
    s.add_tx(-5, count_send=False)
    assert s.snapshot() == (0, 0, 0)
