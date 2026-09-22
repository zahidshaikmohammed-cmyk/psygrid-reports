"""
Generic, causal market-structure primitives (swing points, break/reclaim
checks). This module knows nothing about "impulses" or "pullbacks" -- it
just answers structural questions about a candle series. The strategy
layer (strategy/confirmation.py) composes these primitives into the
report-reaction-specific "did the pullback preserve bullish/bearish
structure" judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from market.m1 import Candle

SwingKind = Literal["high", "low"]


@dataclass(frozen=True)
class SwingPoint:
    index: int
    timestamp: datetime
    price: float
    kind: SwingKind


def find_swing_points(candles: list[Candle], lookback: int) -> list[SwingPoint]:
    """
    Fractal swing detection: bar i is a swing high/low if it is the
    extreme among [i-lookback, i+lookback]. Only points with `lookback`
    bars fully available on both sides are returned, which is what makes
    this causal-safe -- a swing at index i is only ever reported once the
    caller's candle list already extends to at least i+lookback.
    """
    n = len(candles)
    points: list[SwingPoint] = []
    if n < (2 * lookback + 1):
        return points

    for i in range(lookback, n - lookback):
        window = candles[i - lookback: i + lookback + 1]
        this = candles[i]
        if this.high == max(c.high for c in window) and _is_strict_high(window, lookback):
            points.append(SwingPoint(index=i, timestamp=this.timestamp, price=this.high, kind="high"))
        if this.low == min(c.low for c in window) and _is_strict_low(window, lookback):
            points.append(SwingPoint(index=i, timestamp=this.timestamp, price=this.low, kind="low"))
    return points


def _is_strict_high(window: list[Candle], lookback: int) -> bool:
    center = window[lookback]
    return all(c.high <= center.high for j, c in enumerate(window) if j != lookback)


def _is_strict_low(window: list[Candle], lookback: int) -> bool:
    center = window[lookback]
    return all(c.low >= center.low for j, c in enumerate(window) if j != lookback)


def last_swing(points: list[SwingPoint], kind: SwingKind, before_index: int | None = None) -> SwingPoint | None:
    candidates = [p for p in points if p.kind == kind and (before_index is None or p.index <= before_index)]
    return candidates[-1] if candidates else None


def closed_above(candles: list[Candle], level: float) -> bool:
    return any(c.close > level for c in candles)


def closed_below(candles: list[Candle], level: float) -> bool:
    return any(c.close < level for c in candles)


def broke_level(candles: list[Candle], level: float, direction: Literal["up", "down"]) -> bool:
    if direction == "up":
        return closed_above(candles, level)
    return closed_below(candles, level)
