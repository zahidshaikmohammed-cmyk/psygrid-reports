"""
The report-reaction pipeline orchestrator.

`SetupTracker` runs ONE (event, symbol) pair through:

    WATCHING_IMPULSE -> WATCHING_PULLBACK -> WATCHING_STRUCTURE -> WATCHING_TRIGGER -> SIGNAL_FIRED
                                            \\-> INVALIDATED / EXPIRED at any stage

It is deliberately the *only* place that runs this pipeline. Both the live
engine (app/main.py) and the historical replay/backtest engine
(research/replay.py) drive the same SetupTracker.step() causally, bar by
bar, so there is no separate "backtest logic" that could silently diverge
from what actually runs live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from app.config import EngineConfig
from data.calendar import EconomicEvent
from market.m1 import M1Series
from market.m5 import build_m5
from market.volatility import rolling_atr
from strategy.impulse import ImpulseEvent, ImpulseStatus, detect_impulse
from strategy.pullback import PullbackResult, PullbackStatus, detect_pullback
from strategy.confirmation import StructureResult, StructureStatus, assess_structure
from strategy.trigger import TriggerResult, TriggerStatus, detect_trigger


class SetupState(str, Enum):
    WATCHING_IMPULSE = "watching_impulse"
    WATCHING_PULLBACK = "watching_pullback"
    WATCHING_STRUCTURE = "watching_structure"
    WATCHING_TRIGGER = "watching_trigger"
    SIGNAL_FIRED = "signal_fired"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


TERMINAL_STATES = {SetupState.SIGNAL_FIRED, SetupState.INVALIDATED, SetupState.EXPIRED}


@dataclass(frozen=True)
class Signal:
    opportunity_id: str
    symbol: str
    event_id: str
    event_name: str
    event_time: datetime
    direction: str  # "LONG" / "SHORT"

    impulse_strength: float
    impulse_size: float
    retracement_fraction: float
    structure_score: float
    structure_evidence: list[str]

    entry: float
    stop: float
    target: float
    setup_quality: float  # 0..100
    expected_holding_minutes: float
    generated_at: datetime

    def format_message(self) -> str:
        """
        Matches the field-by-field template PSYGRID's operator requires for
        the Telegram alert (see README.md's "Telegram alerts" section) --
        every labeled line below is a literal requirement, not just a
        convenient layout.
        """
        r_multiple = abs(self.target - self.entry) / abs(self.entry - self.stop) if self.entry != self.stop else 0.0
        return (
            "PSYGRID SIGNAL\n\n"
            f"Instrument: {self.symbol}\n"
            f"Event: {self.event_name}\n"
            f"Event time: {self.event_time.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"Direction: {self.direction}\n\n"
            f"Impulse: confirmed (strength {self.impulse_strength:.2f})\n"
            f"Pullback: confirmed (retracement {self.retracement_fraction * 100:.0f}%)\n"
            f"M5 structure: confirmed (score {self.structure_score:.2f})\n"
            f"M1 trigger: confirmed\n\n"
            f"Entry: {self.entry:.5f}\n"
            f"Stop: {self.stop:.5f}\n"
            f"Target: {self.target:.5f} (~{r_multiple:.2f}R)\n\n"
            f"Setup quality: {self.setup_quality:.0f}/100\n"
            f"Expected holding window: <= {self.expected_holding_minutes:.0f} minutes\n\n"
            f"Opportunity ID: {self.opportunity_id}"
        )


def split_baseline_and_post_event(
    all_bars: list, event_time: datetime, window_end: datetime, as_of: datetime
) -> tuple[list, list]:
    """
    Split a symbol's causal M1 bars into pre-event baseline vs. post-event
    reaction bars, relative to event_time (T0).

    Candle timestamp semantics: per market/m1.py, a candle's `timestamp` is
    its OPEN time -- e.g. a bar timestamped 12:30:00 covers [12:30, 12:31).
    That means the bar timestamped exactly at event_time is the bar DURING
    WHICH the event fires: it must never leak into the "normal, pre-event"
    baseline used to compute rolling ATR/volatility (that would contaminate
    the baseline with the event's own impact), and it IS the first bar
    eligible for impulse detection (excluding it there would silently
    discard the event's very first minute of reaction). Baseline therefore
    uses a strict `<`; the post-event window starts at (not after)
    event_time.
    """
    baseline = [c for c in all_bars if c.timestamp < event_time]
    post_event = [c for c in all_bars if event_time <= c.timestamp <= min(as_of, window_end)]
    return baseline, post_event


_VALID_PULLBACK_STATES_FOR_STRUCTURE = {PullbackStatus.HEALTHY, PullbackStatus.DEEP}
_INVALIDATING_PULLBACK_STATES = {
    PullbackStatus.CONTINUATION,
    PullbackStatus.FAILURE,
    PullbackStatus.REVERSAL,
    PullbackStatus.WHIPSAW,
}


def _pullback_quality(pullback: PullbackResult, config: EngineConfig) -> float:
    pc = config.pullback
    if pullback.status == PullbackStatus.HEALTHY:
        mid = (pc.min_healthy_retracement + pc.max_healthy_retracement) / 2
        half_range = (pc.max_healthy_retracement - pc.min_healthy_retracement) / 2
        if half_range <= 0:
            return 1.0
        return max(0.0, 1.0 - abs(pullback.retracement_fraction - mid) / half_range)
    if pullback.status == PullbackStatus.DEEP:
        return 0.5
    return 0.0


@dataclass
class SetupTracker:
    event: EconomicEvent
    symbol: str
    config: EngineConfig

    state: SetupState = SetupState.WATCHING_IMPULSE
    outcome_type: str = ""
    impulse: ImpulseEvent | None = None
    pullback: PullbackResult | None = None
    structure: StructureResult | None = None
    trigger: TriggerResult | None = None
    signal: Signal | None = None
    _structure_watch_started_at: datetime | None = None

    @property
    def opportunity_id_prefix(self) -> str:
        return f"{self.event.event_id}:{self.symbol}"

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def step(self, m1_series: M1Series, as_of: datetime) -> Signal | None:
        if self.is_terminal:
            return None

        event_time = self.event.event_datetime_utc
        assert event_time is not None  # only usable_for_engine events reach a tracker

        overall_deadline = event_time + timedelta(minutes=self.config.windows.setup_expiry_minutes)
        if as_of > overall_deadline and self.state != SetupState.SIGNAL_FIRED:
            self.state = SetupState.EXPIRED
            self.outcome_type = self.outcome_type or "setup_expiry_deadline"
            return None

        if self.state == SetupState.WATCHING_IMPULSE:
            self._step_impulse(m1_series, as_of)
        if self.state == SetupState.WATCHING_PULLBACK:
            self._step_pullback(m1_series, as_of)
        if self.state == SetupState.WATCHING_STRUCTURE:
            self._step_structure(m1_series, as_of)
        if self.state == SetupState.WATCHING_TRIGGER:
            return self._step_trigger(m1_series, as_of)
        return None

    def _step_impulse(self, m1_series: M1Series, as_of: datetime) -> None:
        event_time = self.event.event_datetime_utc
        all_bars = m1_series.as_of(as_of)
        window_end = event_time + timedelta(minutes=self.config.windows.impulse_detection_minutes)
        baseline_bars, post_event_bars = split_baseline_and_post_event(all_bars, event_time, window_end, as_of)

        result = detect_impulse(
            self.symbol, baseline_bars, post_event_bars, event_time, as_of, self.config.impulse
        )
        if result.status == ImpulseStatus.CONFIRMED and result.impulse is not None:
            # Evidence already clears the threshold, but if the best bar seen so far is
            # still the most recent one, the move may still be extending -- lock in the
            # impulse (and its extreme) once momentum pauses for a bar, or the detection
            # window closes, whichever comes first. This avoids freezing the impulse on
            # a single early bar while a stronger multi-bar move is still developing.
            if result.is_still_extending and as_of < window_end:
                return
            self.impulse = result.impulse
            self.state = SetupState.WATCHING_PULLBACK
        elif result.status == ImpulseStatus.EXPIRED:
            self.state = SetupState.EXPIRED
            self.outcome_type = "no_impulse"

    def _step_pullback(self, m1_series: M1Series, as_of: datetime) -> None:
        assert self.impulse is not None
        all_bars = m1_series.as_of(as_of)
        window_end = self.impulse.extreme_time + timedelta(minutes=self.config.windows.pullback_detection_minutes)
        post_impulse_bars = [
            c for c in all_bars if self.impulse.extreme_time < c.timestamp <= min(as_of, window_end)
        ]

        result = detect_pullback(self.impulse, post_impulse_bars, as_of, self.config.pullback)
        if result.status in _VALID_PULLBACK_STATES_FOR_STRUCTURE:
            self.pullback = result
            self.state = SetupState.WATCHING_STRUCTURE
            self._structure_watch_started_at = as_of
        elif result.status in _INVALIDATING_PULLBACK_STATES:
            self.pullback = result
            self.state = SetupState.INVALIDATED
            self.outcome_type = f"pullback_{result.status.value}"
        elif result.status == PullbackStatus.EXPIRED:
            self.pullback = result
            self.state = SetupState.EXPIRED
            self.outcome_type = "pullback_inconclusive"

    def _step_structure(self, m1_series: M1Series, as_of: datetime) -> None:
        assert self.impulse is not None and self.pullback is not None
        assert self.pullback.extreme_price is not None and self.pullback.extreme_time is not None

        m5_candles = build_m5(m1_series, as_of)
        result = assess_structure(
            self.impulse.direction,
            m5_candles,
            self.pullback.extreme_price,
            self.pullback.extreme_time,
            self.config.structure,
        )
        self.structure = result
        if result.status == StructureStatus.CONFIRMED:
            self.state = SetupState.WATCHING_TRIGGER
        elif result.status == StructureStatus.NOT_CONFIRMED:
            watch_deadline = (self._structure_watch_started_at or as_of) + timedelta(
                minutes=self.config.windows.setup_expiry_minutes
            )
            if as_of >= watch_deadline:
                self.state = SetupState.INVALIDATED
                self.outcome_type = "structure_not_confirmed"
        # INSUFFICIENT_DATA: keep watching; overall setup_expiry_deadline check in step() bounds this.

    def _step_trigger(self, m1_series: M1Series, as_of: datetime) -> Signal | None:
        assert self.impulse is not None and self.pullback is not None and self.structure is not None
        assert self.pullback.extreme_time is not None

        all_bars = m1_series.as_of(as_of)
        window_end = self.pullback.extreme_time + timedelta(minutes=self.config.windows.setup_expiry_minutes)
        bars_since_pullback = [
            c for c in all_bars if self.pullback.extreme_time < c.timestamp <= min(as_of, window_end)
        ]

        result = detect_trigger(
            self.impulse.direction,
            bars_since_pullback,
            self.pullback.extreme_time,
            as_of,
            self.config.trigger,
        )
        self.trigger = result
        if result.status == TriggerStatus.CONFIRMED:
            self.state = SetupState.SIGNAL_FIRED
            self.outcome_type = "signal"
            self.signal = self._build_signal(m1_series, as_of)
            return self.signal
        if result.status == TriggerStatus.EXPIRED:
            self.state = SetupState.EXPIRED
            self.outcome_type = "trigger_expired"
        return None

    def _build_signal(self, m1_series: M1Series, as_of: datetime) -> Signal:
        assert self.impulse and self.pullback and self.structure and self.trigger
        assert self.trigger.trigger_price is not None and self.trigger.trigger_time is not None
        assert self.pullback.extreme_price is not None

        cfg = self.config.signal
        recent_bars = m1_series.as_of(as_of)
        atr = rolling_atr(recent_bars, self.config.impulse.atr_lookback_bars) or (self.impulse.size / 3)

        entry = self.trigger.trigger_price
        if self.impulse.direction == "up":
            stop = self.pullback.extreme_price - cfg.stop_atr_multiple * atr
            direction_label = "LONG"
        else:
            stop = self.pullback.extreme_price + cfg.stop_atr_multiple * atr
            direction_label = "SHORT"

        risk = abs(entry - stop)
        target = entry + cfg.target_r_multiple * risk if self.impulse.direction == "up" else entry - cfg.target_r_multiple * risk

        pullback_quality = _pullback_quality(self.pullback, self.config)
        setup_quality = 100 * (
            cfg.weight_impulse * self.impulse.strength_score
            + cfg.weight_pullback * pullback_quality
            + cfg.weight_structure * self.structure.score
            + cfg.weight_trigger * 1.0
        )

        opportunity_id = f"{self.opportunity_id_prefix}:{self.impulse.impulse_id}"

        return Signal(
            opportunity_id=opportunity_id,
            symbol=self.symbol,
            event_id=self.event.event_id,
            event_name=self.event.event_name,
            event_time=self.event.event_datetime_utc,  # type: ignore[arg-type]
            direction=direction_label,
            impulse_strength=self.impulse.strength_score,
            impulse_size=self.impulse.size,
            retracement_fraction=self.pullback.retracement_fraction,
            structure_score=self.structure.score,
            structure_evidence=list(self.structure.evidence),
            entry=entry,
            stop=stop,
            target=target,
            setup_quality=setup_quality,
            expected_holding_minutes=self.config.windows.max_holding_minutes,
            generated_at=as_of,
        )
