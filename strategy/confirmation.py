"""
M5 structure confirmation: does the pullback preserve enough of the
impulse's directional market structure to justify treating this as a
continuation setup rather than noise?

This composes the generic swing-point primitives in market.structure into
report-reaction-specific evidence. Like impulse/pullback, this produces a
0..1 evidence score plus a threshold rather than a single rigid boolean
gate, so borderline cases are visible in the final setup-quality score
instead of being silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.config import StructureConfig
from market.m1 import Candle
from market.structure import find_swing_points, last_swing, closed_below, closed_above
from strategy.impulse import Direction


class StructureStatus(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"


@dataclass(frozen=True)
class StructureResult:
    status: StructureStatus
    score: float
    evidence: list[str] = field(default_factory=list)


def _index_at_or_before(m5_candles: list[Candle], ts: datetime) -> int | None:
    idx = None
    for i, c in enumerate(m5_candles):
        if c.timestamp <= ts:
            idx = i
        else:
            break
    return idx


def assess_structure(
    direction: Direction,
    m5_candles: list[Candle],
    pullback_extreme_price: float,
    pullback_extreme_time: datetime,
    config: StructureConfig,
) -> StructureResult:
    if len(m5_candles) < config.min_m5_bars_required:
        return StructureResult(
            status=StructureStatus.INSUFFICIENT_DATA,
            score=0.0,
            evidence=[f"only {len(m5_candles)} M5 bars available (< {config.min_m5_bars_required})"],
        )

    swings = find_swing_points(m5_candles, config.swing_lookback_bars)
    pullback_idx = _index_at_or_before(m5_candles, pullback_extreme_time)

    evidence: list[str] = []
    components: list[float] = []

    if direction == "up":
        prior_swing = last_swing(swings, "low", before_index=pullback_idx)
        if prior_swing is not None:
            if pullback_extreme_price > prior_swing.price:
                components.append(1.0)
                evidence.append(
                    f"higher-low preserved: pullback low {pullback_extreme_price:.5f} "
                    f"> prior M5 swing low {prior_swing.price:.5f}"
                )
            else:
                components.append(0.0)
                evidence.append(
                    f"pullback low {pullback_extreme_price:.5f} broke prior M5 swing low {prior_swing.price:.5f}"
                )

            bars_since = m5_candles[prior_swing.index + 1:]
            if bars_since and not closed_below(bars_since, prior_swing.price):
                components.append(1.0)
                evidence.append("no M5 close below prior swing low since it formed")
            else:
                components.append(0.0)
                evidence.append("an M5 candle closed below the prior swing low")
        else:
            evidence.append("no prior M5 swing low available for comparison")

        last_candle = m5_candles[-1]
        components.append(1.0 if last_candle.is_bullish else 0.0)
        evidence.append(f"most recent M5 candle is {'bullish' if last_candle.is_bullish else 'bearish'}")

    else:  # down
        prior_swing = last_swing(swings, "high", before_index=pullback_idx)
        if prior_swing is not None:
            if pullback_extreme_price < prior_swing.price:
                components.append(1.0)
                evidence.append(
                    f"lower-high preserved: pullback high {pullback_extreme_price:.5f} "
                    f"< prior M5 swing high {prior_swing.price:.5f}"
                )
            else:
                components.append(0.0)
                evidence.append(
                    f"pullback high {pullback_extreme_price:.5f} broke prior M5 swing high {prior_swing.price:.5f}"
                )

            bars_since = m5_candles[prior_swing.index + 1:]
            if bars_since and not closed_above(bars_since, prior_swing.price):
                components.append(1.0)
                evidence.append("no M5 close above prior swing high since it formed")
            else:
                components.append(0.0)
                evidence.append("an M5 candle closed above the prior swing high")
        else:
            evidence.append("no prior M5 swing high available for comparison")

        last_candle = m5_candles[-1]
        components.append(1.0 if last_candle.is_bearish else 0.0)
        evidence.append(f"most recent M5 candle is {'bearish' if last_candle.is_bearish else 'bullish'}")

    if not components:
        return StructureResult(status=StructureStatus.INSUFFICIENT_DATA, score=0.0, evidence=evidence)

    score = sum(components) / len(components)
    status = StructureStatus.CONFIRMED if score >= config.structure_score_threshold else StructureStatus.NOT_CONFIRMED
    return StructureResult(status=status, score=score, evidence=evidence)
