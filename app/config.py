"""
Central configuration for the PsyGrid report-reaction engine.

Every threshold here is a STARTING POINT, not a proven constant. Values are
grouped by concern (data quality, impulse, pullback, structure, trigger,
scoring, windows) so the research/backtest layer can sweep them and the
live engine can be recalibrated without touching strategy code.

Nothing here claims to be "correct" until research/backtest.py has been run
against real historical data captured from the live endpoint and the
results are documented in docs/STRATEGY_RESEARCH.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


INSTRUMENTS: tuple[str, ...] = (
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "GBPJPY",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "XAGUSD",
    "USOIL",
)


@dataclass(frozen=True)
class DataConfig:
    """Config for fetching/validating the live endpoint."""

    endpoint_url: str = field(
        default_factory=lambda: os.environ.get(
            "PSYGRID_LIVE_ENDPOINT", "http://140.245.226.102:8080/public/m1-live.json"
        )
    )
    request_timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_backoff_base_seconds: float = 1.5
    poll_interval_seconds: float = 5.0

    # A symbol's data is considered "stale" if its last candle / updated_at
    # timestamp is older than this many seconds relative to "now".
    stale_after_seconds: float = 180.0

    # Minimum number of M1 candles required before any volatility/impulse
    # calculation is attempted for a symbol. Below this, calculations report
    # "insufficient data" rather than a (misleadingly precise) number.
    min_m1_bars_for_calc: int = 30

    # Every successful poll is appended here (see data/capture.py) so the
    # engine accumulates real historical data over time for future
    # research/backtest.py runs. Set enable_capture=False to disable.
    enable_capture: bool = True
    capture_dir: str = "data/captures"


@dataclass(frozen=True)
class EventWindowConfig:
    """
    Configurable timing windows around a scheduled report, in minutes
    relative to event_time (T0). All are intentionally generous defaults;
    research/backtest.py should be used to test the candidate windows named
    in the task spec (1-3m, 3-5m, 5-10m, 10-15m, 15-20m, 20-30m) and narrow
    these once evidence supports it.
    """

    pre_event_context_minutes: float = 15.0          # T-15 .. T0: build baseline
    impulse_detection_minutes: float = 10.0           # T0 .. T+10: look for impulse
    pullback_detection_minutes: float = 20.0          # after impulse end, watch for pullback
    setup_expiry_minutes: float = 30.0                # whole setup must resolve within T0..T+30
    max_holding_minutes: float = 30.0                 # intraday: hard time-exit for any open trade


@dataclass(frozen=True)
class ImpulseConfig:
    """
    Impulse detection is evidence-based, not a single hard gate. Each
    sub-signal contributes a 0..1 evidence score; the weighted sum is the
    impulse_score. `impulse_score_threshold` is the only hard cutoff, and it
    is deliberately configurable/sweepable.
    """

    atr_lookback_bars: int = 20          # M1 bars used for rolling ATR-like baseline
    vol_lookback_bars: int = 20          # M1 bars used for rolling return stdev

    # Evidence weights (should sum to ~1.0; not enforced, kept adjustable).
    weight_range_expansion: float = 0.30   # M1 range / rolling ATR
    weight_return_zscore: float = 0.30     # abs(return) / rolling stdev
    weight_directional_run: float = 0.20   # consecutive same-direction M1 closes
    weight_volume_expansion: float = 0.10  # volume / rolling avg volume (if volume meaningful)
    weight_event_distance: float = 0.10    # cumulative move from event-start price / ATR

    impulse_score_threshold: float = 0.55  # min weighted score to call it an impulse
    min_directional_run_bars: int = 2
    max_impulse_search_bars: int = 10      # cap impulse window scan (ties to impulse_detection_minutes)


@dataclass(frozen=True)
class PullbackConfig:
    """
    Retracement is measured as a fraction of the impulse leg
    (0 = no retracement, 1 = fully round-tripped back to impulse start).
    Bands below are DEFAULTS informed by common market-structure heuristics
    (not "the" answer) and are meant to be recalibrated from backtest.py.
    """

    min_healthy_retracement: float = 0.15
    max_healthy_retracement: float = 0.618
    deep_retracement_threshold: float = 0.618   # beyond this: "deep", still tradeable but weaker
    failure_retracement_threshold: float = 1.0  # >= this: impulse fully round-tripped -> failure
    reversal_retracement_threshold: float = 1.2  # >= this: price pushed meaningfully past impulse start -> reversal
    continuation_extension_threshold: float = 0.25  # impulse extends this much further with no real pullback -> continuation
    whipsaw_max_bars: int = 3                   # a retrace-then-reimpulse within this many bars looks like noise
    pullback_search_max_bars: int = 20          # cap search window (ties to pullback_detection_minutes)


@dataclass(frozen=True)
class StructureConfig:
    """M5 structure confirmation parameters."""

    swing_lookback_bars: int = 3          # bars each side required to confirm a swing point (fractal)
    min_m5_bars_required: int = 6         # need at least this many M5 bars to assess structure
    structure_score_threshold: float = 0.5


@dataclass(frozen=True)
class TriggerConfig:
    """M1 entry trigger parameters."""

    micro_swing_lookback_bars: int = 2
    trigger_search_max_bars: int = 15     # cap search window on M1 after structure confirmation


@dataclass(frozen=True)
class SignalConfig:
    """Final setup-quality scoring and trade-level construction."""

    weight_impulse: float = 0.30
    weight_pullback: float = 0.25
    weight_structure: float = 0.25
    weight_trigger: float = 0.20

    setup_quality_threshold: float = 55.0  # 0..100 scale

    stop_atr_multiple: float = 1.0     # stop placed at pullback extreme +/- this*ATR buffer
    target_r_multiple: float = 1.5     # target expressed as multiple of initial risk (R)


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str | None = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN"))
    chat_id: str | None = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID"))

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass(frozen=True)
class StorageConfig:
    db_path: str = field(default_factory=lambda: os.environ.get("PSYGRID_DB_PATH", "storage/psygrid.db"))


def _default_active_event_classes() -> tuple[str, ...] | None:
    """
    Which of the researched events (see data/calendar.py's `event_class`:
    MAJOR/SECONDARY/RESEARCH_ONLY) the live engine will actually activate
    trackers for. None = no restriction (every usable-for-engine event, of
    any class, is activated) -- the historical default, kept as-is unless
    the operator opts into a narrower set via PSYGRID_ACTIVE_EVENT_CLASSES
    (comma-separated, e.g. "MAJOR" or "MAJOR,SECONDARY"). This does not
    delete or hide any event from the researched calendar (see
    docs/PRECISION_AUDIT.md #3) -- it only controls what the live engine
    reacts to.
    """
    raw = os.environ.get("PSYGRID_ACTIVE_EVENT_CLASSES")
    if not raw:
        return ("MAJOR", "SECONDARY")
    return tuple(c.strip().upper() for c in raw.split(",") if c.strip())


@dataclass(frozen=True)
class EngineConfig:
    instruments: tuple[str, ...] = INSTRUMENTS
    events_json_path: str = "data/events_sep22_oct31_2026.json"
    active_event_classes: tuple[str, ...] | None = field(default_factory=_default_active_event_classes)
    data: DataConfig = field(default_factory=DataConfig)
    windows: EventWindowConfig = field(default_factory=EventWindowConfig)
    impulse: ImpulseConfig = field(default_factory=ImpulseConfig)
    pullback: PullbackConfig = field(default_factory=PullbackConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


def load_config() -> EngineConfig:
    """Single entry point for obtaining engine configuration."""
    return EngineConfig()
