from datetime import datetime, timedelta, timezone

from app.config import EngineConfig, DataConfig
from app.main import run_once
from data.calendar import EconomicEvent, EventCalendar
from data.endpoint_client import FetchResult
from market.m1 import M1Series
from storage.database import SignalStore


class _FakeClient:
    def __init__(self, results):
        self._results = list(results)

    def fetch(self):
        return self._results.pop(0) if self._results else FetchResult(
            ok=False, payload=None, error="exhausted", fetched_at_epoch=0, attempts=0
        )


def _calendar_with_one_event(now):
    event = EconomicEvent(
        event_id="evt1", date=now.date().isoformat(), day_of_week=None, country_region="Testland",
        currency="USD", event_name="Resilience Test Event", importance="high",
        original_release_timezone="UTC", exact_release_time_local=None, exact_release_time_ist=None,
        exact_time_confirmed=True, official_source="fixture", secondary_crosscheck=None,
        affected_instruments=("EURUSD",), notes=None, event_datetime_utc=now,
    )
    return EventCalendar(events=[event], metadata={})


def test_run_once_survives_network_failure(tmp_path):
    config = EngineConfig(instruments=("EURUSD",), data=DataConfig(enable_capture=False))
    now = datetime.now(timezone.utc)
    calendar = _calendar_with_one_event(now)
    client = _FakeClient([FetchResult(ok=False, payload=None, error="timeout", fetched_at_epoch=0, attempts=3)])
    m1_series = {"EURUSD": M1Series("EURUSD")}
    store = SignalStore(str(tmp_path / "db.sqlite"))

    # Must not raise.
    run_once(config, client, calendar, m1_series, {}, store)


def test_run_once_survives_malformed_payload(tmp_path):
    config = EngineConfig(instruments=("EURUSD",), data=DataConfig(enable_capture=False))
    now = datetime.now(timezone.utc)
    calendar = _calendar_with_one_event(now)
    client = _FakeClient([FetchResult(ok=True, payload={"unexpected": "shape"}, error=None, fetched_at_epoch=0, attempts=1)])
    m1_series = {"EURUSD": M1Series("EURUSD")}
    store = SignalStore(str(tmp_path / "db.sqlite"))

    run_once(config, client, calendar, m1_series, {}, store)
    assert len(m1_series["EURUSD"]) == 0


def test_run_once_ignores_events_outside_active_window(tmp_path):
    config = EngineConfig(instruments=("EURUSD",), data=DataConfig(enable_capture=False))
    far_future_event_time = datetime.now(timezone.utc) + timedelta(days=5)
    calendar = _calendar_with_one_event(far_future_event_time)
    client = _FakeClient([FetchResult(ok=True, payload={"symbols": {}}, error=None, fetched_at_epoch=0, attempts=1)])
    m1_series = {"EURUSD": M1Series("EURUSD")}
    trackers = {}
    store = SignalStore(str(tmp_path / "db.sqlite"))

    run_once(config, client, calendar, m1_series, trackers, store)
    assert trackers == {}  # event is far outside the active window; no tracker created


def test_run_once_updates_m1_series_from_valid_payload(tmp_path):
    config = EngineConfig(instruments=("EURUSD",), data=DataConfig(enable_capture=False))
    now = datetime.now(timezone.utc)
    calendar = _calendar_with_one_event(now)
    payload = {
        "symbols": {
            "EURUSD": {
                "m1_valid": True,
                "last_candle_timestamp": now.isoformat(),
                "candles_1m": [
                    {"timestamp": (now - timedelta(minutes=i)).isoformat(),
                     "open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1005, "volume": 100.0}
                    for i in range(40)
                ],
            }
        }
    }
    client = _FakeClient([FetchResult(ok=True, payload=payload, error=None, fetched_at_epoch=0, attempts=1)])
    m1_series = {"EURUSD": M1Series("EURUSD")}
    store = SignalStore(str(tmp_path / "db.sqlite"))

    run_once(config, client, calendar, m1_series, {}, store)
    assert len(m1_series["EURUSD"]) == 40
