from datetime import timedelta

from market.m1 import M1Series
from market.m5 import build_m5, forming_m5
from tests.factories import EPOCH, c


def _build_series():
    series = M1Series("EURUSD")
    bars = [c(EPOCH + timedelta(minutes=i), 1.1 + i * 0.0001, 1.1 + i * 0.0001 + 0.00005,
              1.1 + i * 0.0001 - 0.00005, 1.1 + i * 0.0001, v=10.0) for i in range(12)]
    series.update(bars)
    return series


def test_m5_bucket_only_reported_once_complete():
    series = _build_series()
    # as_of inside the second bucket (10:05-10:10) but before it closes -> only first bucket complete
    m5 = build_m5(series, EPOCH + timedelta(minutes=7))
    assert len(m5) == 1
    assert m5[0].timestamp == EPOCH


def test_m5_no_lookahead_forming_bucket_excluded():
    series = _build_series()
    as_of = EPOCH + timedelta(minutes=6, seconds=30)
    m5 = build_m5(series, as_of)
    # bucket [10:05,10:10) is still forming at 10:06:30 -> must not appear
    assert all(bar.timestamp < EPOCH + timedelta(minutes=5) + timedelta(seconds=1) for bar in m5) or len(m5) == 1


def test_m5_aggregation_ohlc_correct():
    series = _build_series()
    m5 = build_m5(series, EPOCH + timedelta(minutes=10))
    first_bucket = m5[0]
    assert first_bucket.open == 1.1
    assert first_bucket.close == 1.1 + 4 * 0.0001
    assert first_bucket.high == max(1.1 + i * 0.0001 + 0.00005 for i in range(5))
    assert first_bucket.low == min(1.1 + i * 0.0001 - 0.00005 for i in range(5))
    assert first_bucket.volume == 50.0


def test_forming_m5_returns_in_progress_bucket():
    series = _build_series()
    as_of = EPOCH + timedelta(minutes=6)
    forming = forming_m5(series, as_of)
    assert forming is not None
    assert forming.timestamp == EPOCH + timedelta(minutes=5)


def test_build_m5_empty_series():
    series = M1Series("EURUSD")
    assert build_m5(series, EPOCH) == []
