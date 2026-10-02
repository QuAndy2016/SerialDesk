"""U180: send auto-increment placeholder rules (pure functions)."""

from app.increment import apply_increment, has_placeholder, next_value, render

CFG = {"start": 0, "step": 1, "width": 1, "endian": "big", "base": 10, "wrap": True}


def test_hex_placeholder_width_and_endian():
    assert render("AA 55 {i:2} 0D", is_hex=True, value=1, cfg=CFG) == "AA 55 00 01 0D"
    little = dict(CFG, endian="le")
    assert render("{i:2}", is_hex=True, value=0x0102, cfg=little) == "02 01"
    assert render("{i:2}", is_hex=True, value=0x0102, cfg=CFG) == "01 02"


def test_ascii_placeholder_padding_and_base():
    assert render("N={i:4}", is_hex=False, value=3, cfg=CFG) == "N=0003"
    assert render("{i:3}", is_hex=False, value=10, cfg=dict(CFG, base=16)) == "00A"


def test_counter_advances_and_wraps():
    assert next_value(0, is_hex=True, cfg=CFG) == 1
    assert next_value(0xFF, is_hex=True, cfg=CFG) == 0x00          # wrap
    assert next_value(0, is_hex=False, cfg=dict(CFG, width=2)) == 1
    assert next_value(99, is_hex=False, cfg=dict(CFG, width=2)) == 0   # wrap at 2 digits


def test_stop_instead_of_wrap_returns_none():
    stop = dict(CFG, wrap=False)
    assert next_value(0xFF, is_hex=True, cfg=dict(stop, width=1)) is None
    assert next_value(9, is_hex=False, cfg=dict(stop, width=1)) is None


def test_negative_step_decrements_and_wraps():
    dec = dict(CFG, start=2, step=-1)
    assert next_value(1, is_hex=True, cfg=dec) == 0
    assert next_value(0, is_hex=True, cfg=dec) == 0xFF


def test_apply_increment_returns_text_and_next():
    text, nxt = apply_increment("AA {i:2}", is_hex=True, value=1, cfg=CFG)
    assert text == "AA 00 01" and nxt == 2


def test_escaped_placeholder_is_literal_and_no_placeholder_is_untouched():
    assert has_placeholder("AT") is False
    assert render(r"\{i}", is_hex=False, value=7, cfg=CFG) == "{i}"
    text, nxt = apply_increment("AT", is_hex=False, value=5, cfg=CFG)
    assert text == "AT" and nxt == 5          # nothing to advance


def test_exhausted_apply_returns_none_next():
    text, nxt = apply_increment("{i}", is_hex=True, value=0xFF,
                                cfg=dict(CFG, wrap=False))
    assert text == "FF" and nxt is None       # send this one, then stop
