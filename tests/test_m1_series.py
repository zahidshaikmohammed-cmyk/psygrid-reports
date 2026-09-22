from datetime import timedelta

from market.m1 import Candle, M1Series
from tests.factories import EPOCH, c


def test_update_deduplicates_by_timestamp():
    series = M1Series("EURUSD")
    series.update([c(EPOCH, 1.1, 1.11, 1.09, 1.10)])
    assert len(series) == 1
    # same timestamp, revised close (provider revising the forming bar) -> overwrite, not append
    series.update([c(EPOCH, 1.1, 1.12, 1.09, 1.105)])
    assert len(series) == 1
    assert series.all()[0].close == 1.105


def test_update_sorts_out_of_order_input():
    series = M1Series("EURUSD")
    series.update([c(EPOCH + timedelta(minutes=2), 1, 1, 1, 1)])
    series.update([c(EPOCH, 1, 1, 1, 1)])
    series.update([c(EPOCH + timedelta(minutes=1), 1, 1, 1, 1)])
    timestamps = [bar.timestamp for bar in series.all()]
    assert timestamps == sorted(timestamps)


def test_as_of_is_causal():
    series = M1Series("EURUSD")
    series.update([c(EPOCH + timedelta(minutes=i), 1, 1, 1, 1) for i in range(5)])
    window = series.as_of(EPOCH + timedelta(minutes=2))
    assert [b.timestamp for b in window] == [EPOCH + timedelta(minutes=i) for i in range(3)]


def test_as_of_respects_lookback():
    series = M1Series("EURUSD")
    series.update([c(EPOCH + timedelta(minutes=i), 1, 1, 1, 1) for i in range(10)])
    window = series.as_of(EPOCH + timedelta(minutes=9), lookback=3)
    assert len(window) == 3
    assert window[-1].timestamp == EPOCH + timedelta(minutes=9)


def test_max_bars_evicts_oldest():
    series = M1Series("EURUSD", max_bars=3)
    series.update([c(EPOCH + timedelta(minutes=i), 1, 1, 1, 1) for i in range(5)])
    assert len(series) == 3
    assert series.all()[0].timestamp == EPOCH + timedelta(minutes=2)
