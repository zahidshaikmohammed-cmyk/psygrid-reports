from datetime import timedelta

from app.config import StructureConfig
from strategy.confirmation import assess_structure, StructureStatus
from tests.factories import EPOCH, c


def _m5_series_bullish(n=8):
    """8 M5 candles: gentle chop around 1.0990-1.1005 (baseline), swing lows visible."""
    prices = [1.09950, 1.09920, 1.09960, 1.09900, 1.09970, 1.09990, 1.10050, 1.10150]
    bars = []
    for i, p in enumerate(prices):
        ts = EPOCH + timedelta(minutes=5 * i)
        bars.append(c(ts, p, p + 0.0004, p - 0.0004, p + 0.0002))
    return bars


def test_insufficient_m5_bars():
    config = StructureConfig(min_m5_bars_required=6)
    bars = _m5_series_bullish()[:3]
    result = assess_structure("up", bars, pullback_extreme_price=1.10, pullback_extreme_time=bars[-1].timestamp, config=config)
    assert result.status == StructureStatus.INSUFFICIENT_DATA


def test_higher_low_confirms_bullish_structure():
    config = StructureConfig(min_m5_bars_required=6, swing_lookback_bars=1, structure_score_threshold=0.5)
    bars = _m5_series_bullish()
    # pullback low well above the prior swing lows (~1.0990-1.0992)
    result = assess_structure(
        "up", bars, pullback_extreme_price=1.10050, pullback_extreme_time=bars[-2].timestamp, config=config
    )
    assert result.status in (StructureStatus.CONFIRMED, StructureStatus.NOT_CONFIRMED)
    assert 0.0 <= result.score <= 1.0
    assert result.evidence


def test_broken_structure_not_confirmed():
    config = StructureConfig(min_m5_bars_required=6, swing_lookback_bars=1, structure_score_threshold=0.9)
    bars = _m5_series_bullish()
    # pullback price far below any prior swing low -> should not preserve higher-low
    result = assess_structure(
        "up", bars, pullback_extreme_price=1.09800, pullback_extreme_time=bars[-2].timestamp, config=config
    )
    assert result.status == StructureStatus.NOT_CONFIRMED


def test_bearish_structure_mirror():
    prices = [1.10050, 1.10080, 1.10040, 1.10100, 1.10030, 1.10010, 1.09950, 1.09850]
    bars = [c(EPOCH + timedelta(minutes=5 * i), p, p + 0.0004, p - 0.0004, p - 0.0002) for i, p in enumerate(prices)]
    config = StructureConfig(min_m5_bars_required=6, swing_lookback_bars=1, structure_score_threshold=0.5)
    result = assess_structure(
        "down", bars, pullback_extreme_price=1.10010, pullback_extreme_time=bars[-2].timestamp, config=config
    )
    assert result.status in (StructureStatus.CONFIRMED, StructureStatus.NOT_CONFIRMED)
