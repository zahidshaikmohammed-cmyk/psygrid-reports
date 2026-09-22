"""
Precision audit item #6/#7: the researched calendar contains genuine
simultaneous events (multiple distinct US releases at the same scheduled
UTC minute -- e.g. Initial Jobless Claims + PCE both at 08:30 ET, see
docs/PRECISION_AUDIT.md #4). These tests prove SetupTracker/app.main
handle two events at the identical timestamp, for the same symbol,
without any key collision or cross-contamination.
"""

from dataclasses import replace
from datetime import timedelta

from app.config import EngineConfig, DataConfig
from app.main import run_once
from data.calendar import EventCalendar
from data.endpoint_client import FetchResult
from market.m1 import M1Series
from storage.database import SignalStore
from strategy.signal import SetupTracker, SetupState
from tests.test_signal_pipeline import _build_long_scenario, _make_event


def test_two_simultaneous_events_same_symbol_produce_independent_signals():
    event_a, all_bars = _build_long_scenario()
    event_b = _make_event(event_a.event_datetime_utc, symbol="EURUSD", name="TEST EVENT B (simultaneous)")

    assert event_a.event_datetime_utc == event_b.event_datetime_utc
    assert event_a.event_id != event_b.event_id

    series = M1Series("EURUSD")
    series.update(all_bars)

    tracker_a = SetupTracker(event=event_a, symbol="EURUSD", config=EngineConfig())
    tracker_b = SetupTracker(event=event_b, symbol="EURUSD", config=EngineConfig())

    as_of = all_bars[0].timestamp
    end = all_bars[-1].timestamp
    step = timedelta(minutes=1)
    signal_a = signal_b = None
    while as_of <= end and not (tracker_a.is_terminal and tracker_b.is_terminal):
        if not tracker_a.is_terminal:
            sig = tracker_a.step(series, as_of)
            signal_a = signal_a or sig
        if not tracker_b.is_terminal:
            sig = tracker_b.step(series, as_of)
            signal_b = signal_b or sig
        as_of += step

    assert tracker_a.state == SetupState.SIGNAL_FIRED
    assert tracker_b.state == SetupState.SIGNAL_FIRED
    assert signal_a is not None and signal_b is not None
    assert signal_a.opportunity_id != signal_b.opportunity_id
    assert signal_a.event_id == event_a.event_id
    assert signal_b.event_id == event_b.event_id
    # Both trackers independently analyzed the same underlying price action
    # and reached the same trade parameters -- proving neither corrupted
    # the other's state, just that they agree given identical inputs.
    assert signal_a.entry == signal_b.entry
    assert signal_a.direction == signal_b.direction


class _FakeClient:
    def __init__(self, results):
        self._results = list(results)

    def fetch(self):
        return self._results.pop(0) if self._results else FetchResult(
            ok=False, payload=None, error="exhausted", fetched_at_epoch=0, attempts=0
        )


def test_run_once_creates_independent_trackers_for_simultaneous_events(tmp_path):
    event_a, all_bars = _build_long_scenario()
    event_b = _make_event(event_a.event_datetime_utc, symbol="EURUSD", name="TEST EVENT B (simultaneous)")
    event_b = replace(event_b, affected_instruments=("EURUSD",))

    calendar = EventCalendar(events=[event_a, event_b], metadata={})
    config = EngineConfig(instruments=("EURUSD",), data=DataConfig(enable_capture=False))

    m1_series = {"EURUSD": M1Series("EURUSD")}
    m1_series["EURUSD"].update(all_bars)
    trackers: dict = {}
    store = SignalStore(str(tmp_path / "db.sqlite"))

    client = _FakeClient([FetchResult(ok=True, payload={"symbols": {}}, error=None, fetched_at_epoch=0, attempts=1)])
    result = run_once(config, client, calendar, m1_series, trackers, store, now=event_a.event_datetime_utc)

    keys = set(trackers.keys())
    assert (event_a.event_id, "EURUSD") in keys
    assert (event_b.event_id, "EURUSD") in keys
    assert len(keys) == 2
    assert result.active_event_count == 2
