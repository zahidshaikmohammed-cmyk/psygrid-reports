from datetime import timedelta

from app.config import PullbackConfig
from strategy.impulse import ImpulseEvent
from strategy.pullback import detect_pullback, PullbackStatus
from tests.factories import EPOCH, c


def _bullish_impulse():
    return ImpulseEvent(
        symbol="EURUSD",
        direction="up",
        event_time=EPOCH,
        start_price=1.10000,
        extreme_time=EPOCH + timedelta(minutes=4),
        extreme_price=1.10285,
        confirmed_at=EPOCH + timedelta(minutes=4),
        duration_bars=4,
        strength_score=0.9,
    )


def test_healthy_pullback_classified_correctly():
    impulse = _bullish_impulse()
    config = PullbackConfig()
    start = impulse.extreme_time + timedelta(minutes=1)
    bars = [
        c(start, 1.10280, 1.10282, 1.10220, 1.10225),
        c(start + timedelta(minutes=1), 1.10225, 1.10228, 1.10185, 1.10190),  # retrace ~35%
        c(start + timedelta(minutes=2), 1.10190, 1.10210, 1.10188, 1.10205),
    ]
    result = detect_pullback(impulse, bars, bars[-1].timestamp, config)
    assert result.status == PullbackStatus.HEALTHY
    assert config.min_healthy_retracement <= result.retracement_fraction <= config.max_healthy_retracement


def test_shallow_retracement_is_watching_or_continuation():
    impulse = _bullish_impulse()
    config = PullbackConfig()
    start = impulse.extreme_time + timedelta(minutes=1)
    bars = [c(start, 1.10280, 1.10283, 1.10278, 1.10282)]
    result = detect_pullback(impulse, bars, bars[-1].timestamp, config)
    assert result.status in (PullbackStatus.WATCHING, PullbackStatus.CONTINUATION)


def test_failure_when_fully_round_tripped():
    impulse = _bullish_impulse()
    config = PullbackConfig()
    start = impulse.extreme_time + timedelta(minutes=1)
    bars = [c(start, 1.10280, 1.10282, 1.09990, 1.10000)]  # retraces all the way to start_price
    result = detect_pullback(impulse, bars, bars[-1].timestamp, config)
    assert result.status in (PullbackStatus.FAILURE, PullbackStatus.REVERSAL)


def test_reversal_when_pushed_past_start():
    impulse = _bullish_impulse()
    config = PullbackConfig()
    start = impulse.extreme_time + timedelta(minutes=1)
    # impulse.size = 0.00285; reversal threshold 1.2 -> need low <= extreme - 1.2*size = 1.10285-0.00342=1.09943
    bars = [c(start, 1.10280, 1.10282, 1.09900, 1.09910)]
    result = detect_pullback(impulse, bars, bars[-1].timestamp, config)
    assert result.status == PullbackStatus.REVERSAL


def test_continuation_when_impulse_extends_without_pullback():
    impulse = _bullish_impulse()
    config = PullbackConfig()
    start = impulse.extreme_time + timedelta(minutes=1)
    bars = [
        c(start + timedelta(minutes=i), 1.10285 + i * 0.0005, 1.10285 + i * 0.0005 + 0.0001,
          1.10285 + i * 0.0005 - 0.00005, 1.10285 + i * 0.0005 + 0.00008)
        for i in range(3)
    ]
    result = detect_pullback(impulse, bars, bars[-1].timestamp, config)
    assert result.status == PullbackStatus.CONTINUATION


def test_whipsaw_detected_on_snapback():
    impulse = _bullish_impulse()
    config = PullbackConfig(whipsaw_max_bars=3)
    start = impulse.extreme_time + timedelta(minutes=1)
    bars = [
        c(start, 1.10280, 1.10282, 1.09990, 1.10000),  # deep retrace (failure level)
        c(start + timedelta(minutes=1), 1.10000, 1.10300, 1.09995, 1.10295),  # snaps back beyond extreme
    ]
    result = detect_pullback(impulse, bars, bars[-1].timestamp, config)
    assert result.status == PullbackStatus.WHIPSAW


def test_no_post_impulse_bars_yet():
    impulse = _bullish_impulse()
    config = PullbackConfig()
    result = detect_pullback(impulse, [], impulse.extreme_time + timedelta(seconds=30), config)
    assert result.status == PullbackStatus.WATCHING


def test_zero_size_impulse_is_expired():
    impulse = ImpulseEvent(
        symbol="EURUSD", direction="up", event_time=EPOCH, start_price=1.1,
        extreme_time=EPOCH, extreme_price=1.1, confirmed_at=EPOCH, duration_bars=1, strength_score=0.6,
    )
    config = PullbackConfig()
    result = detect_pullback(impulse, [c(EPOCH, 1.1, 1.1, 1.1, 1.1)], EPOCH, config)
    assert result.status == PullbackStatus.EXPIRED
