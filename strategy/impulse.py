"""
Impulse detection: evidence-scored, not a single hard gate.

Each M1 bar after the event time contributes a weighted combination of
five 0..1 "evidence" components (range expansion vs. baseline ATR,
return z-score vs. baseline volatility, consecutive directional run,
volume expansion where volume is meaningful, and distance travelled from
the event-start price vs. baseline ATR). The bar with the highest weighted
score becomes the impulse candidate; if its score clears
`impulse_score_threshold` the impulse is confirmed.

All weights and the threshold live in app.config.ImpulseConfig and are
meant to be swept by research/backtest.py, not treated as fixed truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from app.config import ImpulseConfig
from market.m1 import Candle
from market.volatility import rolling_atr, rolling_return_stdev, rolling_avg_volume, volume_is_meaningful

Direction = Literal["up", "down"]


class ImpulseStatus(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"   # not enough baseline history to even try
    WATCHING = "watching"                     # inside detection window, no confirmation yet
    CONFIRMED = "confirmed"
    EXPIRED = "expired"                       # detection window closed with no confirmation


@dataclass(frozen=True)
class ImpulseEvent:
    symbol: str
    direction: Direction
    event_time: datetime
    start_price: float
    extreme_time: datetime
    extreme_price: float
    confirmed_at: datetime
    duration_bars: int
    strength_score: float  # 0..1

    @property
    def size(self) -> float:
        return abs(self.extreme_price - self.start_price)

    @property
    def impulse_id(self) -> str:
        return f"{self.symbol}:{self.event_time.isoformat()}:{self.confirmed_at.isoformat()}:{self.direction}"


@dataclass(frozen=True)
class ImpulseResult:
    status: ImpulseStatus
    impulse: ImpulseEvent | None = None
    best_score: float = 0.0
    reason: str = ""
    is_still_extending: bool = False  # best-scoring bar is the most recent one seen so far


def _saturating(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return max(0.0, min(value / target, 1.0))


def _effective_weights(config: ImpulseConfig, volume_available: bool) -> dict[str, float]:
    weights = {
        "range_expansion": config.weight_range_expansion,
        "return_zscore": config.weight_return_zscore,
        "directional_run": config.weight_directional_run,
        "volume_expansion": config.weight_volume_expansion,
        "event_distance": config.weight_event_distance,
    }
    if volume_available:
        return weights
    # redistribute volume's weight proportionally across the remaining components
    vol_w = weights.pop("volume_expansion")
    remaining_total = sum(weights.values()) or 1.0
    for k in weights:
        weights[k] += vol_w * (weights[k] / remaining_total)
    weights["volume_expansion"] = 0.0
    return weights


def detect_impulse(
    symbol: str,
    baseline_bars: list[Candle],
    post_event_bars: list[Candle],
    event_time: datetime,
    as_of: datetime,
    config: ImpulseConfig,
) -> ImpulseResult:
    """
    baseline_bars: causal M1 bars strictly before event_time (for computing
        the "normal" volatility this event's reaction should be measured against).
    post_event_bars: causal M1 bars with timestamp > event_time and <= as_of,
        already capped by the caller to the impulse-detection window.
    """
    min_baseline = max(config.atr_lookback_bars, config.vol_lookback_bars) + 1
    if len(baseline_bars) < min_baseline:
        return ImpulseResult(status=ImpulseStatus.INSUFFICIENT_DATA, reason="not enough baseline history")

    baseline_atr = rolling_atr(baseline_bars, config.atr_lookback_bars)
    baseline_stdev = rolling_return_stdev(baseline_bars, config.vol_lookback_bars)
    if not baseline_atr:
        return ImpulseResult(status=ImpulseStatus.INSUFFICIENT_DATA, reason="baseline ATR unavailable/zero")

    if not post_event_bars:
        return ImpulseResult(status=ImpulseStatus.WATCHING, reason="no post-event bars yet")

    event_start_price = baseline_bars[-1].close
    volume_available = volume_is_meaningful(baseline_bars + post_event_bars)
    baseline_avg_volume = rolling_avg_volume(baseline_bars, config.vol_lookback_bars) if volume_available else None
    weights = _effective_weights(config, volume_available and bool(baseline_avg_volume))

    best_score = 0.0
    best_index: int | None = None
    best_direction: Direction | None = None
    up_run = 0
    down_run = 0

    search_bars = post_event_bars[: config.max_impulse_search_bars]

    for i, bar in enumerate(search_bars):
        up_run = up_run + 1 if bar.is_bullish else 0
        down_run = down_run + 1 if bar.is_bearish else 0

        cumulative_move = bar.close - event_start_price
        if cumulative_move == 0:
            continue
        direction: Direction = "up" if cumulative_move > 0 else "down"
        run = up_run if direction == "up" else down_run

        range_expansion = bar.range / baseline_atr
        bar_return = abs(bar.close - bar.open) / bar.open if bar.open else 0.0
        return_z = (bar_return / baseline_stdev) if baseline_stdev else 0.0
        event_distance = abs(cumulative_move) / baseline_atr

        vol_score = 0.0
        if weights["volume_expansion"] > 0 and bar.volume is not None and baseline_avg_volume:
            vol_score = _saturating(bar.volume / baseline_avg_volume, target=2.0)

        score = (
            weights["range_expansion"] * _saturating(range_expansion, target=2.0)
            + weights["return_zscore"] * _saturating(return_z, target=2.0)
            + weights["directional_run"] * _saturating(run, target=config.min_directional_run_bars * 2)
            + weights["volume_expansion"] * vol_score
            + weights["event_distance"] * _saturating(event_distance, target=3.0)
        )

        if score > best_score:
            best_score = score
            best_index = i
            best_direction = direction

    if best_index is None or best_direction is None or best_score < config.impulse_score_threshold:
        window_elapsed = as_of >= event_time + _search_horizon(config, post_event_bars)
        if window_elapsed and len(post_event_bars) >= config.max_impulse_search_bars:
            return ImpulseResult(status=ImpulseStatus.EXPIRED, best_score=best_score, reason="detection window exhausted")
        return ImpulseResult(status=ImpulseStatus.WATCHING, best_score=best_score, reason="threshold not yet reached")

    is_still_extending = best_index == len(search_bars) - 1
    window = search_bars[: best_index + 1]
    if best_direction == "up":
        extreme_idx = max(range(len(window)), key=lambda k: window[k].high)
        extreme_price = window[extreme_idx].high
    else:
        extreme_idx = min(range(len(window)), key=lambda k: window[k].low)
        extreme_price = window[extreme_idx].low

    impulse = ImpulseEvent(
        symbol=symbol,
        direction=best_direction,
        event_time=event_time,
        start_price=event_start_price,
        extreme_time=window[extreme_idx].timestamp,
        extreme_price=extreme_price,
        confirmed_at=window[best_index].timestamp,
        duration_bars=extreme_idx + 1,
        strength_score=best_score,
    )
    return ImpulseResult(
        status=ImpulseStatus.CONFIRMED, impulse=impulse, best_score=best_score, is_still_extending=is_still_extending
    )


def _search_horizon(config: ImpulseConfig, post_event_bars: list[Candle]) -> timedelta:
    bars = min(len(post_event_bars), config.max_impulse_search_bars)
    return timedelta(minutes=bars)
