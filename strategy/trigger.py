"""
M1 entry trigger: deterministic micro-structure break of the most recent
opposing M1 swing point formed during the pullback. This is the ENTRY
mechanism only -- it does not re-argue the trade thesis (that's impulse +
pullback + M5 structure); it just answers "has price now actually broken
back in the trade direction on the lowest timeframe we have?"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from app.config import TriggerConfig
from market.m1 import Candle
from market.structure import find_swing_points, last_swing
from strategy.impulse import Direction


class TriggerStatus(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    WATCHING = "watching"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class TriggerResult:
    status: TriggerStatus
    level: float | None = None
    trigger_price: float | None = None
    trigger_time: datetime | None = None


def detect_trigger(
    direction: Direction,
    bars_since_pullback: list[Candle],
    pullback_started_at: datetime,
    as_of: datetime,
    config: TriggerConfig,
) -> TriggerResult:
    min_bars = 2 * config.micro_swing_lookback_bars + 1
    search_bars = bars_since_pullback[: config.trigger_search_max_bars]

    if len(search_bars) < min_bars:
        window_closed = as_of >= pullback_started_at + timedelta(minutes=config.trigger_search_max_bars)
        if window_closed and len(bars_since_pullback) >= config.trigger_search_max_bars:
            return TriggerResult(status=TriggerStatus.EXPIRED)
        return TriggerResult(status=TriggerStatus.INSUFFICIENT_DATA)

    swings = find_swing_points(search_bars, config.micro_swing_lookback_bars)
    kind = "high" if direction == "up" else "low"
    ref_swing = last_swing(swings, kind)

    if ref_swing is None:
        window_closed = len(search_bars) >= config.trigger_search_max_bars
        return TriggerResult(status=TriggerStatus.EXPIRED if window_closed else TriggerStatus.WATCHING)

    for bar in search_bars[ref_swing.index + 1:]:
        if direction == "up" and bar.close > ref_swing.price:
            return TriggerResult(
                status=TriggerStatus.CONFIRMED,
                level=ref_swing.price,
                trigger_price=bar.close,
                trigger_time=bar.timestamp,
            )
        if direction == "down" and bar.close < ref_swing.price:
            return TriggerResult(
                status=TriggerStatus.CONFIRMED,
                level=ref_swing.price,
                trigger_price=bar.close,
                trigger_time=bar.timestamp,
            )

    window_closed = len(search_bars) >= config.trigger_search_max_bars
    return TriggerResult(status=TriggerStatus.EXPIRED if window_closed else TriggerStatus.WATCHING, level=ref_swing.price)
