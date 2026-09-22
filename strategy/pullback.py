"""
Pullback/retracement classification after an impulse has been confirmed.

Retracement is expressed as a fraction of the impulse leg's size (0 = no
retracement, 1.0 = fully round-tripped back to the impulse start price).
The classification bands are configurable defaults (see
app.config.PullbackConfig), not hard-coded Fibonacci gospel -- they exist
so research/backtest.py has something concrete to calibrate against real
outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from app.config import PullbackConfig
from market.m1 import Candle
from strategy.impulse import ImpulseEvent


class PullbackStatus(str, Enum):
    WATCHING = "watching"            # still inside the search window, no verdict yet
    CONTINUATION = "continuation"    # impulse kept extending, no meaningful pullback occurred
    HEALTHY = "healthy"
    DEEP = "deep"
    FAILURE = "failure"              # fully round-tripped back through the impulse start
    REVERSAL = "reversal"            # pushed meaningfully past the impulse start in the opposite direction
    WHIPSAW = "whipsaw"              # snapped back to a new extreme right after a deep/failure retrace
    EXPIRED = "expired"              # window closed with only a shallow, inconclusive retracement


@dataclass(frozen=True)
class PullbackResult:
    status: PullbackStatus
    retracement_fraction: float
    extreme_price: float | None = None
    extreme_time: datetime | None = None
    continuation_extreme_price: float | None = None
    bars_elapsed: int = 0


def detect_pullback(
    impulse: ImpulseEvent,
    post_impulse_bars: list[Candle],
    as_of: datetime,
    config: PullbackConfig,
) -> PullbackResult:
    if impulse.size <= 0:
        return PullbackResult(status=PullbackStatus.EXPIRED, retracement_fraction=0.0)

    if not post_impulse_bars:
        window_closed = as_of >= impulse.extreme_time + timedelta(minutes=config.pullback_search_max_bars)
        return PullbackResult(
            status=PullbackStatus.EXPIRED if window_closed else PullbackStatus.WATCHING,
            retracement_fraction=0.0,
        )

    search_bars = post_impulse_bars[: config.pullback_search_max_bars]
    direction = impulse.direction

    continuation_extreme = impulse.extreme_price
    max_retracement = 0.0
    retrace_extreme_price: float | None = None
    retrace_extreme_time: datetime | None = None
    reached_failure_at: int | None = None

    for i, bar in enumerate(search_bars):
        if direction == "up":
            if bar.high > continuation_extreme:
                continuation_extreme = bar.high
            candidate_price = bar.low
            retracement = (continuation_extreme - candidate_price) / impulse.size
        else:
            if bar.low < continuation_extreme:
                continuation_extreme = bar.low
            candidate_price = bar.high
            retracement = (candidate_price - continuation_extreme) / impulse.size

        if retracement > max_retracement:
            max_retracement = retracement
            retrace_extreme_price = candidate_price
            retrace_extreme_time = bar.timestamp

        if reached_failure_at is None and max_retracement >= config.failure_retracement_threshold:
            reached_failure_at = i

        if reached_failure_at is not None and (i - reached_failure_at) <= config.whipsaw_max_bars:
            recovered = (
                bar.high > impulse.extreme_price if direction == "up" else bar.low < impulse.extreme_price
            )
            if recovered and i > reached_failure_at:
                return PullbackResult(
                    status=PullbackStatus.WHIPSAW,
                    retracement_fraction=max_retracement,
                    extreme_price=retrace_extreme_price,
                    extreme_time=retrace_extreme_time,
                    continuation_extreme_price=continuation_extreme,
                    bars_elapsed=i + 1,
                )

    bars_elapsed = len(search_bars)
    extension = abs(continuation_extreme - impulse.extreme_price) / impulse.size

    if max_retracement >= config.reversal_retracement_threshold:
        status = PullbackStatus.REVERSAL
    elif max_retracement >= config.failure_retracement_threshold:
        status = PullbackStatus.FAILURE
    elif max_retracement >= config.deep_retracement_threshold:
        status = PullbackStatus.DEEP
    elif max_retracement >= config.min_healthy_retracement:
        status = PullbackStatus.HEALTHY
    elif extension >= config.continuation_extension_threshold:
        status = PullbackStatus.CONTINUATION
    else:
        window_closed = bars_elapsed >= config.pullback_search_max_bars or as_of >= impulse.extreme_time + timedelta(
            minutes=config.pullback_search_max_bars
        )
        status = PullbackStatus.EXPIRED if window_closed else PullbackStatus.WATCHING

    return PullbackResult(
        status=status,
        retracement_fraction=max_retracement,
        extreme_price=retrace_extreme_price,
        extreme_time=retrace_extreme_time,
        continuation_extreme_price=continuation_extreme,
        bars_elapsed=bars_elapsed,
    )
