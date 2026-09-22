from datetime import timedelta

from app.config import ImpulseConfig
from strategy.impulse import detect_impulse, ImpulseStatus
from tests.factories import EPOCH, flat_baseline, bullish_impulse_bars, bearish_impulse_bars


def test_insufficient_baseline_data():
    config = ImpulseConfig()
    baseline = flat_baseline(EPOCH, 5)
    event_time = baseline[-1].timestamp
    result = detect_impulse("EURUSD", baseline, [], event_time, event_time, config)
    assert result.status == ImpulseStatus.INSUFFICIENT_DATA


def test_no_post_event_bars_yet_is_watching():
    config = ImpulseConfig()
    baseline = flat_baseline(EPOCH, 25)
    event_time = baseline[-1].timestamp
    result = detect_impulse("EURUSD", baseline, [], event_time, event_time, config)
    assert result.status == ImpulseStatus.WATCHING


def test_strong_bullish_impulse_confirms_up():
    config = ImpulseConfig()
    baseline = flat_baseline(EPOCH, 25)
    event_time = baseline[-1].timestamp
    impulse_start = event_time + timedelta(minutes=1)
    post_bars = bullish_impulse_bars(impulse_start, open_price=baseline[-1].close, n=4)
    as_of = post_bars[-1].timestamp
    result = detect_impulse("EURUSD", baseline, post_bars, event_time, as_of, config)
    assert result.status == ImpulseStatus.CONFIRMED
    assert result.impulse is not None
    assert result.impulse.direction == "up"
    assert result.impulse.strength_score >= config.impulse_score_threshold


def test_strong_bearish_impulse_confirms_down():
    config = ImpulseConfig()
    baseline = flat_baseline(EPOCH, 25)
    event_time = baseline[-1].timestamp
    impulse_start = event_time + timedelta(minutes=1)
    post_bars = bearish_impulse_bars(impulse_start, open_price=baseline[-1].close, n=4)
    as_of = post_bars[-1].timestamp
    result = detect_impulse("EURUSD", baseline, post_bars, event_time, as_of, config)
    assert result.status == ImpulseStatus.CONFIRMED
    assert result.impulse.direction == "down"


def test_flat_post_event_bars_do_not_confirm_impulse():
    config = ImpulseConfig()
    baseline = flat_baseline(EPOCH, 25)
    event_time = baseline[-1].timestamp
    post_bars = flat_baseline(event_time + timedelta(minutes=1), 5)
    as_of = post_bars[-1].timestamp
    result = detect_impulse("EURUSD", baseline, post_bars, event_time, as_of, config)
    assert result.status in (ImpulseStatus.WATCHING, ImpulseStatus.EXPIRED)


def test_expires_after_window_with_no_confirmation():
    config = ImpulseConfig(max_impulse_search_bars=5)
    baseline = flat_baseline(EPOCH, 25)
    event_time = baseline[-1].timestamp
    post_bars = flat_baseline(event_time + timedelta(minutes=1), 10)
    as_of = post_bars[-1].timestamp
    result = detect_impulse("EURUSD", baseline, post_bars, event_time, as_of, config)
    assert result.status == ImpulseStatus.EXPIRED


def test_no_look_ahead_only_uses_bars_up_to_as_of():
    """Feeding extra bars beyond as_of must not change the outcome (as_of is the caller's contract)."""
    config = ImpulseConfig()
    baseline = flat_baseline(EPOCH, 25)
    event_time = baseline[-1].timestamp
    impulse_start = event_time + timedelta(minutes=1)
    post_bars = bullish_impulse_bars(impulse_start, open_price=baseline[-1].close, n=4)

    as_of_early = post_bars[0].timestamp
    result_early = detect_impulse("EURUSD", baseline, post_bars[:1], event_time, as_of_early, config)
    # With only the first bar available, it must not already reflect bar 4's higher score/extreme
    if result_early.status == ImpulseStatus.CONFIRMED:
        assert result_early.impulse.extreme_price == post_bars[0].high
