from datetime import timedelta

from app.config import TriggerConfig
from strategy.trigger import detect_trigger, TriggerStatus
from tests.factories import EPOCH, c


def _bullish_trigger_bars():
    return [
        c(EPOCH + timedelta(minutes=0), 1.10190, 1.10195, 1.10185, 1.10190),
        c(EPOCH + timedelta(minutes=1), 1.10190, 1.10200, 1.10180, 1.10185),
        c(EPOCH + timedelta(minutes=2), 1.10185, 1.10220, 1.10180, 1.10210),  # swing high @ 1.10220
        c(EPOCH + timedelta(minutes=3), 1.10210, 1.10212, 1.10170, 1.10175),
        c(EPOCH + timedelta(minutes=4), 1.10175, 1.10180, 1.10160, 1.10165),
        c(EPOCH + timedelta(minutes=5), 1.10165, 1.10170, 1.10150, 1.10155),
        c(EPOCH + timedelta(minutes=6), 1.10155, 1.10230, 1.10155, 1.10225),  # breaks above 1.10220
    ]


def _bearish_trigger_bars():
    return [
        c(EPOCH + timedelta(minutes=0), 1.10190, 1.10195, 1.10185, 1.10190),
        c(EPOCH + timedelta(minutes=1), 1.10190, 1.10200, 1.10180, 1.10185),
        c(EPOCH + timedelta(minutes=2), 1.10185, 1.10190, 1.10150, 1.10160),  # swing low @ 1.10150
        c(EPOCH + timedelta(minutes=3), 1.10160, 1.10195, 1.10158, 1.10190),
        c(EPOCH + timedelta(minutes=4), 1.10190, 1.10205, 1.10188, 1.10200),
        c(EPOCH + timedelta(minutes=5), 1.10200, 1.10210, 1.10198, 1.10205),
        c(EPOCH + timedelta(minutes=6), 1.10205, 1.10210, 1.10140, 1.10145),  # breaks below 1.10150
    ]


def test_bullish_trigger_confirms_on_break():
    bars = _bullish_trigger_bars()
    config = TriggerConfig()
    result = detect_trigger("up", bars, bars[0].timestamp, bars[-1].timestamp, config)
    assert result.status == TriggerStatus.CONFIRMED
    assert result.level == 1.10220
    assert result.trigger_price == 1.10225


def test_bearish_trigger_confirms_on_break():
    bars = _bearish_trigger_bars()
    config = TriggerConfig()
    result = detect_trigger("down", bars, bars[0].timestamp, bars[-1].timestamp, config)
    assert result.status == TriggerStatus.CONFIRMED
    assert result.level == 1.10150
    assert result.trigger_price == 1.10145


def test_insufficient_bars():
    bars = _bullish_trigger_bars()[:2]
    config = TriggerConfig()
    result = detect_trigger("up", bars, bars[0].timestamp, bars[-1].timestamp, config)
    assert result.status == TriggerStatus.INSUFFICIENT_DATA


def test_no_break_yet_is_watching():
    bars = _bullish_trigger_bars()[:5]  # stops before the breakout bar
    config = TriggerConfig(trigger_search_max_bars=20)
    result = detect_trigger("up", bars, bars[0].timestamp, bars[-1].timestamp, config)
    assert result.status == TriggerStatus.WATCHING


def test_expires_when_search_window_exhausted_without_break():
    bars = _bullish_trigger_bars()[:5]
    config = TriggerConfig(trigger_search_max_bars=5)
    result = detect_trigger("up", bars, bars[0].timestamp, bars[-1].timestamp, config)
    assert result.status == TriggerStatus.EXPIRED
