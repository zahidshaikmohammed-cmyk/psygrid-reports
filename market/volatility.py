"""
Rolling, causal volatility measures used to normalize impulse detection
across instruments with very different natural pip/point scales (e.g.
XAUUSD vs EURUSD). Every function here operates on a candle list the
caller has already sliced causally (see M1Series.as_of) and returns None
rather than a fabricated number when there isn't enough history yet --
"insufficient data" is a legitimate result, not an error.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from market.m1 import Candle


def true_range(prev_close: float, high: float, low: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def rolling_atr(candles: list[Candle], lookback: int) -> float | None:
    """
    Simple moving average of True Range over the last `lookback` bars.
    Requires lookback+1 candles (one extra for the first bar's prev_close).
    """
    if len(candles) < lookback + 1:
        return None
    window = candles[-(lookback + 1):]
    trs = [
        true_range(window[i - 1].close, window[i].high, window[i].low)
        for i in range(1, len(window))
    ]
    if not trs:
        return None
    return sum(trs) / len(trs)


def close_returns(candles: list[Candle]) -> list[float]:
    """Simple close-to-close returns (fractional, not %) for consecutive bars."""
    returns = []
    for i in range(1, len(candles)):
        prev = candles[i - 1].close
        if prev == 0:
            continue
        returns.append((candles[i].close - prev) / prev)
    return returns


def rolling_return_stdev(candles: list[Candle], lookback: int) -> float | None:
    if len(candles) < lookback + 1:
        return None
    window = candles[-(lookback + 1):]
    rets = close_returns(window)
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def volume_is_meaningful(candles: list[Candle]) -> bool:
    """
    Some feeds report zero/constant/None volume for FX (no real tick
    volume). Treat volume evidence as usable only if it actually varies.
    """
    vols = [c.volume for c in candles if c.volume is not None]
    if len(vols) < max(5, len(candles) // 2):
        return False
    return len(set(vols)) > 1 and statistics.pstdev(vols) > 0


def rolling_avg_volume(candles: list[Candle], lookback: int) -> float | None:
    if not volume_is_meaningful(candles):
        return None
    window = candles[-lookback:] if lookback else candles
    vols = [c.volume for c in window if c.volume is not None]
    if not vols:
        return None
    return sum(vols) / len(vols)


@dataclass(frozen=True)
class VolatilitySnapshot:
    atr: float | None
    return_stdev: float | None
    avg_volume: float | None
    volume_meaningful: bool
    sufficient_data: bool
