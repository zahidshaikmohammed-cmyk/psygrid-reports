from datetime import timedelta

from market.structure import find_swing_points, last_swing, broke_level
from tests.factories import EPOCH, c


def _v_shape():
    """down, down, down, up, up, up -> swing low in the middle."""
    prices = [1.10, 1.09, 1.08, 1.07, 1.08, 1.09, 1.10]
    bars = []
    for i, p in enumerate(prices):
        bars.append(c(EPOCH + timedelta(minutes=i), p, p + 0.001, p - 0.001, p))
    return bars


def test_swing_low_detected_at_bottom_of_v():
    bars = _v_shape()
    points = find_swing_points(bars, lookback=3)
    lows = [p for p in points if p.kind == "low"]
    assert len(lows) == 1
    assert lows[0].index == 3


def test_insufficient_bars_returns_no_swings():
    bars = _v_shape()[:4]
    assert find_swing_points(bars, lookback=3) == []


def test_last_swing_respects_before_index():
    bars = _v_shape() + _v_shape()  # two V shapes back to back
    points = find_swing_points(bars, lookback=3)
    first_low = last_swing(points, "low", before_index=5)
    assert first_low is not None
    assert first_low.index == 3


def test_broke_level_up_and_down():
    bars = _v_shape()
    assert broke_level(bars, level=1.075, direction="up") is True
    assert broke_level(bars, level=1.15, direction="up") is False
    assert broke_level(bars, level=1.075, direction="down") is True
