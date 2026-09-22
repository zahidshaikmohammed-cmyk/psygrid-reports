from datetime import timedelta

from market.volatility import rolling_atr, rolling_return_stdev, volume_is_meaningful, rolling_avg_volume
from tests.factories import EPOCH, c


def test_rolling_atr_insufficient_data_returns_none():
    bars = [c(EPOCH + timedelta(minutes=i), 1, 1.001, 0.999, 1) for i in range(5)]
    assert rolling_atr(bars, lookback=20) is None


def test_rolling_atr_computes_expected_value():
    bars = [c(EPOCH + timedelta(minutes=i), 1, 1.001, 0.999, 1) for i in range(10)]
    atr = rolling_atr(bars, lookback=5)
    assert atr is not None
    assert abs(atr - 0.002) < 1e-9


def test_return_stdev_zero_for_flat_prices():
    bars = [c(EPOCH + timedelta(minutes=i), 1, 1.001, 0.999, 1) for i in range(10)]
    stdev = rolling_return_stdev(bars, lookback=5)
    assert stdev == 0.0


def test_volume_meaningful_detects_constant_volume_as_not_meaningful():
    bars = [c(EPOCH + timedelta(minutes=i), 1, 1.001, 0.999, 1, v=100.0) for i in range(10)]
    assert volume_is_meaningful(bars) is False


def test_volume_meaningful_detects_varying_volume():
    bars = [c(EPOCH + timedelta(minutes=i), 1, 1.001, 0.999, 1, v=float(100 + i * 10)) for i in range(10)]
    assert volume_is_meaningful(bars) is True
    assert rolling_avg_volume(bars, lookback=10) is not None


def test_none_volume_treated_as_not_meaningful():
    bars = [c(EPOCH + timedelta(minutes=i), 1, 1.001, 0.999, 1, v=None) for i in range(10)]
    assert volume_is_meaningful(bars) is False
    assert rolling_avg_volume(bars, lookback=10) is None
