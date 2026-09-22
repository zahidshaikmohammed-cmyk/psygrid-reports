"""
Causal M5 aggregation from the underlying M1 series.

A 5-minute bucket [b, b+5m) is only ever reported as a *completed* M5
candle once `as_of` has reached b+5m -- i.e. once every M1 bar that could
possibly belong to it has had a chance to arrive. This is what keeps M5
structure analysis look-ahead free: at any instant, `build_m5` returns
exactly what an M5 chart would have shown a trader at that instant, no
more.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from market.m1 import Candle, M1Series

BUCKET_MINUTES = 5


def _bucket_start(ts: datetime) -> datetime:
    floored_minute = (ts.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    return ts.replace(minute=floored_minute, second=0, microsecond=0)


def _aggregate(m1_bars: list[Candle]) -> Candle | None:
    if not m1_bars:
        return None
    return Candle(
        timestamp=m1_bars[0].timestamp,
        open=m1_bars[0].open,
        high=max(c.high for c in m1_bars),
        low=min(c.low for c in m1_bars),
        close=m1_bars[-1].close,
        volume=sum(c.volume for c in m1_bars if c.volume is not None) or None,
    )


def build_m5(m1_series: M1Series, as_of: datetime, lookback_bars: int | None = None) -> list[Candle]:
    """Return completed M5 candles as of `as_of`, oldest first, causal only."""
    m1_bars = m1_series.as_of(as_of)
    if not m1_bars:
        return []

    buckets: dict[datetime, list[Candle]] = {}
    order: list[datetime] = []
    for bar in m1_bars:
        b = _bucket_start(bar.timestamp)
        if b not in buckets:
            buckets[b] = []
            order.append(b)
        buckets[b].append(bar)

    m5_candles: list[Candle] = []
    for bucket_start in order:
        bucket_end = bucket_start + timedelta(minutes=BUCKET_MINUTES)
        if as_of < bucket_end:
            continue  # bucket still forming -- not causal-safe to report as complete
        agg = _aggregate(buckets[bucket_start])
        if agg is not None:
            m5_candles.append(agg)

    if lookback_bars is not None and lookback_bars >= 0:
        m5_candles = m5_candles[-lookback_bars:]
    return m5_candles


def forming_m5(m1_series: M1Series, as_of: datetime) -> Candle | None:
    """The in-progress (not-yet-complete) M5 bucket, explicitly separate from build_m5's output."""
    m1_bars = m1_series.as_of(as_of)
    if not m1_bars:
        return None
    current_bucket = _bucket_start(as_of)
    in_bucket = [c for c in m1_bars if _bucket_start(c.timestamp) == current_bucket]
    return _aggregate(in_bucket)
