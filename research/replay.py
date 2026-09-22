"""
Walk-forward replay engine.

This drives strategy.signal.SetupTracker exactly the way the live engine
does: minute by minute, causally, using only M1Series.as_of(as_of) data.
The ONLY difference between this and live operation is where the M1 data
comes from (a stored historical capture instead of the live endpoint) --
the strategy code path is identical, which is what makes backtest results
meaningful for the live engine.

Trade *simulation* (what happened to price after a signal fired) is
deliberately kept in research/backtest.py, not here: that step uses bars
strictly after the signal's generation time to score the outcome, which is
legitimate for research but must never leak into signal generation itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.config import EngineConfig
from data.calendar import EconomicEvent, EventCalendar
from market.m1 import M1Series
from strategy.signal import SetupTracker, Signal


@dataclass
class TrackerRecord:
    event: EconomicEvent
    symbol: str
    outcome_type: str
    final_state: str
    signal: Signal | None


@dataclass
class ReplayResult:
    signals: list[Signal] = field(default_factory=list)
    tracker_records: list[TrackerRecord] = field(default_factory=list)

    def outcome_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for rec in self.tracker_records:
            counts[rec.outcome_type] = counts.get(rec.outcome_type, 0) + 1
        return counts


def _data_bounds(m1_history: dict[str, M1Series]) -> tuple[datetime, datetime] | None:
    all_ts = []
    for series in m1_history.values():
        bars = series.all()
        if bars:
            all_ts.append((bars[0].timestamp, bars[-1].timestamp))
    if not all_ts:
        return None
    return min(t[0] for t in all_ts), max(t[1] for t in all_ts)


def run_replay(
    m1_history: dict[str, M1Series],
    calendar: EventCalendar,
    config: EngineConfig,
    step_minutes: float = 1.0,
) -> ReplayResult:
    bounds = _data_bounds(m1_history)
    result = ReplayResult()
    if bounds is None:
        return result
    data_start, data_end = bounds

    for event in calendar.usable_events():
        event_time = event.event_datetime_utc
        assert event_time is not None
        symbols = [s for s in event.affected_instruments if s in config.instruments] or list(config.instruments)

        window_start = event_time - timedelta(minutes=config.windows.pre_event_context_minutes)
        window_end = event_time + timedelta(minutes=config.windows.setup_expiry_minutes)
        if window_end < data_start or window_start > data_end:
            continue  # no data coverage for this event at all

        for symbol in symbols:
            series = m1_history.get(symbol)
            if series is None or len(series) == 0:
                continue

            tracker = SetupTracker(event=event, symbol=symbol, config=config)
            as_of = max(window_start, data_start)
            step = timedelta(minutes=step_minutes)
            capped_end = min(window_end, data_end)

            fired_signal: Signal | None = None
            while as_of <= capped_end and not tracker.is_terminal:
                sig = tracker.step(series, as_of)
                if sig is not None:
                    fired_signal = sig
                    result.signals.append(sig)
                as_of += step

            outcome_type = tracker.outcome_type or (
                "unresolved_data_exhausted" if not tracker.is_terminal else tracker.state.value
            )
            result.tracker_records.append(
                TrackerRecord(
                    event=event,
                    symbol=symbol,
                    outcome_type=outcome_type,
                    final_state=tracker.state.value,
                    signal=fired_signal,
                )
            )

    return result
