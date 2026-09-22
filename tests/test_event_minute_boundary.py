"""
Regression test for the event-minute baseline-leak bug found during the
precision audit (docs/PRECISION_AUDIT.md §1): under OPEN-time candle
semantics, the bar timestamped exactly at event_time is the bar DURING
WHICH the event fires and must never be counted as pre-event baseline.
"""

from datetime import timedelta

from strategy.signal import split_baseline_and_post_event
from tests.factories import EPOCH, c


def _bars(n):
    return [c(EPOCH + timedelta(minutes=i), 1.1, 1.101, 1.099, 1.1) for i in range(n)]


def test_event_minute_candle_excluded_from_baseline():
    bars = _bars(10)  # timestamps EPOCH+0 .. EPOCH+9
    event_time = EPOCH + timedelta(minutes=5)  # a candle exists exactly at this timestamp
    window_end = event_time + timedelta(minutes=10)
    as_of = EPOCH + timedelta(minutes=9)

    baseline, post_event = split_baseline_and_post_event(bars, event_time, window_end, as_of)

    baseline_timestamps = {b.timestamp for b in baseline}
    post_event_timestamps = {b.timestamp for b in post_event}

    assert event_time not in baseline_timestamps, "event-minute candle leaked into the pre-event baseline"
    assert event_time in post_event_timestamps, "event-minute candle must be the first post-event bar"
    assert baseline_timestamps == {EPOCH + timedelta(minutes=i) for i in range(5)}
    assert post_event_timestamps == {EPOCH + timedelta(minutes=i) for i in range(5, 10)}


def test_no_overlap_between_baseline_and_post_event():
    bars = _bars(20)
    event_time = EPOCH + timedelta(minutes=12)
    window_end = event_time + timedelta(minutes=10)
    as_of = EPOCH + timedelta(minutes=19)

    baseline, post_event = split_baseline_and_post_event(bars, event_time, window_end, as_of)
    baseline_ts = {b.timestamp for b in baseline}
    post_ts = {b.timestamp for b in post_event}
    assert baseline_ts.isdisjoint(post_ts)
    assert baseline_ts | post_ts <= {b.timestamp for b in bars}


def test_post_event_respects_as_of_and_window_end():
    bars = _bars(30)
    event_time = EPOCH + timedelta(minutes=5)
    window_end = event_time + timedelta(minutes=3)  # narrower than available data
    as_of = EPOCH + timedelta(minutes=25)  # far beyond window_end

    _, post_event = split_baseline_and_post_event(bars, event_time, window_end, as_of)
    assert max(b.timestamp for b in post_event) == window_end


def test_missing_event_minute_candle_still_splits_correctly():
    """No candle exists exactly at event_time (a gap) -- baseline/post-event must still split cleanly."""
    bars = [b for b in _bars(10) if b.timestamp != EPOCH + timedelta(minutes=5)]
    event_time = EPOCH + timedelta(minutes=5)
    window_end = event_time + timedelta(minutes=10)
    as_of = EPOCH + timedelta(minutes=9)

    baseline, post_event = split_baseline_and_post_event(bars, event_time, window_end, as_of)
    assert {b.timestamp for b in baseline} == {EPOCH + timedelta(minutes=i) for i in range(5)}
    assert {b.timestamp for b in post_event} == {EPOCH + timedelta(minutes=i) for i in range(6, 10)}
