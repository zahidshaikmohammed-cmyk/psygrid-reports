"""Deterministic candle/fixture builders shared across the test suite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from market.m1 import Candle

EPOCH = datetime(2026, 1, 5, 10, 0, 0, tzinfo=timezone.utc)  # aligned to a 5-min boundary


def c(ts, o, h, l, cl, v=100.0):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=v)


def flat_baseline(start: datetime, n: int, base_price: float = 1.10000, noise: float = 0.00005) -> list[Candle]:
    """n minutes of low-volatility doji bars, alternating +/- `noise` around base_price."""
    bars = []
    for i in range(n):
        ts = start + timedelta(minutes=i)
        px = base_price + (noise if i % 2 == 0 else -noise)
        bars.append(c(ts, px, px + noise * 2, px - noise * 2, px))
    return bars


def bullish_impulse_bars(start: datetime, open_price: float, n: int = 4, step: float = 0.00070) -> list[Candle]:
    bars = []
    px = open_price
    for i in range(n):
        ts = start + timedelta(minutes=i)
        o = px
        cl = px + step
        h = cl + step * 0.07
        l = o - step * 0.14
        bars.append(c(ts, o, h, l, cl))
        px = cl
    return bars


def bearish_impulse_bars(start: datetime, open_price: float, n: int = 4, step: float = 0.00070) -> list[Candle]:
    bars = []
    px = open_price
    for i in range(n):
        ts = start + timedelta(minutes=i)
        o = px
        cl = px - step
        l = cl - step * 0.07
        h = o + step * 0.14
        bars.append(c(ts, o, h, l, cl))
        px = cl
    return bars


def pullback_bars_down(start: datetime, open_price: float, lows: list[float], closes: list[float]) -> list[Candle]:
    """Bars retracing downward (used after a bullish impulse)."""
    bars = []
    px = open_price
    for i, (low, close) in enumerate(zip(lows, closes)):
        ts = start + timedelta(minutes=i)
        o = px
        h = max(o, close) + 0.00003
        bars.append(c(ts, o, h, low, close))
        px = close
    return bars


def pullback_bars_up(start: datetime, open_price: float, highs: list[float], closes: list[float]) -> list[Candle]:
    """Bars retracing upward (used after a bearish impulse)."""
    bars = []
    px = open_price
    for i, (high, close) in enumerate(zip(highs, closes)):
        ts = start + timedelta(minutes=i)
        o = px
        l = min(o, close) - 0.00003
        bars.append(c(ts, o, high, l, close))
        px = close
    return bars
