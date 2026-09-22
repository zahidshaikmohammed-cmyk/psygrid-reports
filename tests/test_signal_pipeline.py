"""
End-to-end integration tests driving strategy.signal.SetupTracker exactly
the way the live engine and the replay engine do: minute by minute,
causally, through M1Series.as_of(). These are the "long signal" / "short
signal" tests plus a direct look-ahead-bias check.
"""

from datetime import timedelta

from app.config import EngineConfig
from data.calendar import EconomicEvent
from market.m1 import M1Series, Candle
from strategy.signal import SetupTracker, SetupState
from tests.factories import (
    EPOCH, c, flat_baseline, bullish_impulse_bars, bearish_impulse_bars,
    pullback_bars_down, pullback_bars_up,
)


def _make_event(event_time, symbol="EURUSD", name="TEST EVENT"):
    return EconomicEvent(
        event_id=f"test:{name}",
        date=event_time.date().isoformat(),
        day_of_week=None,
        country_region="Testland",
        currency="USD",
        event_name=name,
        importance="high",
        original_release_timezone="UTC",
        exact_release_time_local=None,
        exact_release_time_ist=None,
        exact_time_confirmed=True,
        official_source="synthetic fixture",
        secondary_crosscheck=None,
        affected_instruments=(symbol,),
        notes=None,
        event_datetime_utc=event_time,
    )


def _bullish_trigger_bars(start, base):
    step = [
        (0.00005, -0.00005, 0.0),
        (0.00010, -0.00010, -0.00005),
        (0.00030, -0.00010, 0.00020),   # swing high forms at base+0.00030
        (0.00022, -0.00020, -0.00015),
        (-0.00010, -0.00030, -0.00025),
        (-0.00020, -0.00035, -0.00030),
        (0.00040, -0.00030, 0.00035),   # breakout close > base+0.00030
    ]
    bars = []
    px = base
    for i, (h_off, l_off, cl_off) in enumerate(step):
        ts = start + timedelta(minutes=i)
        bars.append(c(ts, px, base + h_off, base + l_off, base + cl_off))
        px = base + cl_off
    return bars


def _bearish_trigger_bars(start, base):
    step = [
        (0.00005, -0.00005, 0.0),
        (0.00010, -0.00010, 0.00005),
        (0.00010, -0.00030, -0.00020),   # swing low forms at base-0.00030
        (0.00020, -0.00022, 0.00015),
        (0.00030, 0.00010, 0.00025),
        (0.00035, 0.00020, 0.00030),
        (0.00030, -0.00040, -0.00035),   # breakout close < base-0.00030
    ]
    bars = []
    px = base
    for i, (h_off, l_off, cl_off) in enumerate(step):
        ts = start + timedelta(minutes=i)
        bars.append(c(ts, px, base + h_off, base + l_off, base + cl_off))
        px = base + cl_off
    return bars


def _build_long_scenario():
    baseline = flat_baseline(EPOCH, 45)
    event_time = baseline[-1].timestamp + timedelta(minutes=1)
    event = _make_event(event_time)

    impulse_bars = bullish_impulse_bars(event_time + timedelta(minutes=1), open_price=baseline[-1].close, n=4)
    impulse_extreme = max(b.high for b in impulse_bars)
    impulse_start = baseline[-1].close
    impulse_size = impulse_extreme - impulse_start

    pullback_start = impulse_bars[-1].timestamp + timedelta(minutes=1)
    target_low = impulse_extreme - 0.35 * impulse_size
    pullback_bars = pullback_bars_down(
        pullback_start,
        open_price=impulse_bars[-1].close,
        lows=[impulse_extreme - 0.10 * impulse_size, target_low, target_low + 0.05 * impulse_size],
        closes=[impulse_extreme - 0.05 * impulse_size, target_low + 0.02 * impulse_size, target_low + 0.08 * impulse_size],
    )

    trigger_start = pullback_bars[-1].timestamp + timedelta(minutes=1)
    trigger_bars = _bullish_trigger_bars(trigger_start, base=pullback_bars[-1].close)

    all_bars = baseline + impulse_bars + pullback_bars + trigger_bars
    return event, all_bars


def _build_short_scenario():
    baseline = flat_baseline(EPOCH, 45)
    event_time = baseline[-1].timestamp + timedelta(minutes=1)
    event = _make_event(event_time, name="TEST EVENT SHORT")

    impulse_bars = bearish_impulse_bars(event_time + timedelta(minutes=1), open_price=baseline[-1].close, n=4)
    impulse_extreme = min(b.low for b in impulse_bars)
    impulse_start = baseline[-1].close
    impulse_size = impulse_start - impulse_extreme

    pullback_start = impulse_bars[-1].timestamp + timedelta(minutes=1)
    target_high = impulse_extreme + 0.35 * impulse_size
    pullback_bars = pullback_bars_up(
        pullback_start,
        open_price=impulse_bars[-1].close,
        highs=[impulse_extreme + 0.10 * impulse_size, target_high, target_high - 0.05 * impulse_size],
        closes=[impulse_extreme + 0.05 * impulse_size, target_high - 0.02 * impulse_size, target_high - 0.08 * impulse_size],
    )

    trigger_start = pullback_bars[-1].timestamp + timedelta(minutes=1)
    trigger_bars = _bearish_trigger_bars(trigger_start, base=pullback_bars[-1].close)

    all_bars = baseline + impulse_bars + pullback_bars + trigger_bars
    return event, all_bars


def _run_tracker_fully_loaded(event, all_bars, config):
    """All bars pre-loaded into the series; causality enforced purely via as_of."""
    series = M1Series("EURUSD")
    series.update(all_bars)
    tracker = SetupTracker(event=event, symbol="EURUSD", config=config)
    signal = None
    as_of = all_bars[0].timestamp
    end = all_bars[-1].timestamp
    step = timedelta(minutes=1)
    while as_of <= end and not tracker.is_terminal:
        sig = tracker.step(series, as_of)
        if sig is not None:
            signal = sig
        as_of += step
    return tracker, signal


def _run_tracker_incrementally_loaded(event, all_bars, config):
    """Bars only added to the series once as_of reaches them -- a stricter causality check."""
    series = M1Series("EURUSD")
    tracker = SetupTracker(event=event, symbol="EURUSD", config=config)
    signal = None
    as_of = all_bars[0].timestamp
    end = all_bars[-1].timestamp
    step = timedelta(minutes=1)
    idx = 0
    while as_of <= end and not tracker.is_terminal:
        while idx < len(all_bars) and all_bars[idx].timestamp <= as_of:
            series.update([all_bars[idx]])
            idx += 1
        sig = tracker.step(series, as_of)
        if sig is not None:
            signal = sig
        as_of += step
    return tracker, signal


def test_long_signal_fires_with_expected_shape():
    config = EngineConfig()
    event, all_bars = _build_long_scenario()
    tracker, signal = _run_tracker_fully_loaded(event, all_bars, config)

    assert tracker.state == SetupState.SIGNAL_FIRED
    assert signal is not None
    assert signal.direction == "LONG"
    assert signal.symbol == "EURUSD"
    assert 0 <= signal.setup_quality <= 100
    assert signal.stop < signal.entry < signal.target
    assert signal.opportunity_id.startswith(event.event_id)


def test_short_signal_fires_with_expected_shape():
    config = EngineConfig()
    event, all_bars = _build_short_scenario()
    tracker, signal = _run_tracker_fully_loaded(event, all_bars, config)

    assert tracker.state == SetupState.SIGNAL_FIRED
    assert signal is not None
    assert signal.direction == "SHORT"
    assert signal.target < signal.entry < signal.stop


def test_no_look_ahead_bias_incremental_matches_fully_loaded():
    config = EngineConfig()
    event, all_bars = _build_long_scenario()

    _, signal_full = _run_tracker_fully_loaded(event, all_bars, config)
    _, signal_incremental = _run_tracker_incrementally_loaded(event, all_bars, config)

    assert signal_full is not None and signal_incremental is not None
    assert signal_full.opportunity_id == signal_incremental.opportunity_id
    assert signal_full.entry == signal_incremental.entry
    assert signal_full.stop == signal_incremental.stop
    assert signal_full.setup_quality == signal_incremental.setup_quality


def test_setup_expires_when_nothing_happens():
    config = EngineConfig()
    baseline = flat_baseline(EPOCH, 45)
    event_time = baseline[-1].timestamp + timedelta(minutes=1)
    event = _make_event(event_time)
    flat_after = flat_baseline(event_time + timedelta(minutes=1), 40)
    all_bars = baseline + flat_after

    tracker, signal = _run_tracker_fully_loaded(event, all_bars, config)
    assert signal is None
    assert tracker.state in (SetupState.EXPIRED, SetupState.WATCHING_IMPULSE)
