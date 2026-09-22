"""
Proves the top-level production entry point (run_signal_engine.py) is
wired correctly: the Telegram-required startup guard, the injectable
main loop actually driving app.main.run_once end-to-end (reusing the same
long-scenario fixture as the strategy pipeline tests, so a real signal
fires and gets sent+persisted through the real code path), duplicate
suppression across "restarts", status-line formatting, and graceful
Ctrl+C handling.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config import DataConfig, EngineConfig, TelegramConfig
from data.calendar import EventCalendar
from data.endpoint_client import FetchResult
from market.m1 import M1Series
from run_signal_engine import (
    TelegramNotConfigured,
    format_status_line,
    require_telegram_configured,
    run_forever,
)
from app.main import RunOnceResult
from storage.database import SignalStore
from tests.test_signal_pipeline import _build_long_scenario


class _FakeClient:
    def __init__(self):
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return FetchResult(ok=True, payload={"symbols": {}}, error=None, fetched_at_epoch=0, attempts=1)


class _MinuteClock:
    """
    Advances one minute per call -- mirrors how run_forever actually
    operates in production (each poll iteration is a new point in real
    time), unlike a single jump straight to the end which would let
    later-stage detectors (e.g. pullback) see the whole future window at
    once and pick a different, non-causal-in-spirit extreme.
    """

    def __init__(self, start: datetime):
        self._next = start

    def __call__(self) -> datetime:
        now = self._next
        self._next += timedelta(minutes=1)
        return now


def _config(tmp_path, telegram_enabled=True):
    telegram = TelegramConfig(bot_token="TOKEN", chat_id="CHAT") if telegram_enabled else TelegramConfig(bot_token=None, chat_id=None)
    return EngineConfig(
        instruments=("EURUSD",),
        data=DataConfig(enable_capture=False, poll_interval_seconds=0.0),
        telegram=telegram,
    )


def test_require_telegram_configured_raises_when_missing():
    config = EngineConfig(telegram=TelegramConfig(bot_token=None, chat_id=None))
    with pytest.raises(TelegramNotConfigured):
        require_telegram_configured(config)


def test_require_telegram_configured_passes_when_set():
    config = EngineConfig(telegram=TelegramConfig(bot_token="T", chat_id="C"))
    require_telegram_configured(config)  # must not raise


def test_run_forever_drives_real_pipeline_and_sends_signal(tmp_path, monkeypatch):
    sent_messages = []
    monkeypatch.setattr(
        "notifications.telegram.send_signal",
        lambda signal, cfg, session=None: sent_messages.append(signal.opportunity_id) or True,
    )
    # app.main imports send_signal by name, so patch it there too.
    import app.main as app_main
    monkeypatch.setattr(app_main, "send_signal", lambda signal, cfg: sent_messages.append(signal.opportunity_id) or True)

    event, all_bars = _build_long_scenario()
    calendar = EventCalendar(events=[event], metadata={})
    config = _config(tmp_path)

    m1_series = {"EURUSD": M1Series("EURUSD")}
    m1_series["EURUSD"].update(all_bars)
    store = SignalStore(str(tmp_path / "db.sqlite"))
    client = _FakeClient()
    iterations = len(all_bars) + 5

    exit_code = run_forever(
        config=config,
        client=client,
        calendar=calendar,
        m1_series=m1_series,
        trackers={},
        store=store,
        sleep_fn=lambda seconds: None,
        now_fn=_MinuteClock(all_bars[0].timestamp),
        max_iterations=iterations,
        status_interval_seconds=0.0,
    )

    assert exit_code == 0
    assert client.calls == iterations
    assert len(sent_messages) == 1
    assert store.has_signal(sent_messages[0])


def test_run_forever_restart_does_not_resend_same_signal(tmp_path, monkeypatch):
    """Simulates a process restart: a fresh SignalStore pointed at the same db file must not resend."""
    sent_calls = []
    import app.main as app_main
    monkeypatch.setattr(app_main, "send_signal", lambda signal, cfg: sent_calls.append(signal.opportunity_id) or True)

    event, all_bars = _build_long_scenario()
    calendar = EventCalendar(events=[event], metadata={})
    config = _config(tmp_path)
    db_path = str(tmp_path / "db.sqlite")

    m1_series = {"EURUSD": M1Series("EURUSD")}
    m1_series["EURUSD"].update(all_bars)
    client = _FakeClient()
    iterations = len(all_bars) + 5

    # "First run" -- fires and persists the signal.
    store1 = SignalStore(db_path)
    run_forever(
        config=config, client=client, calendar=calendar, m1_series=m1_series, trackers={}, store=store1,
        sleep_fn=lambda s: None, now_fn=_MinuteClock(all_bars[0].timestamp),
        max_iterations=iterations, status_interval_seconds=0.0,
    )
    assert len(sent_calls) == 1

    # "Restart": brand-new in-memory state (fresh M1Series/trackers/store instance),
    # but the SAME underlying db file -- the tracker will re-detect the setup from
    # scratch, but must NOT re-send an already-persisted opportunity_id.
    m1_series_2 = {"EURUSD": M1Series("EURUSD")}
    m1_series_2["EURUSD"].update(all_bars)
    store2 = SignalStore(db_path)
    client2 = _FakeClient()
    run_forever(
        config=config, client=client2, calendar=calendar, m1_series=m1_series_2, trackers={}, store=store2,
        sleep_fn=lambda s: None, now_fn=_MinuteClock(all_bars[0].timestamp),
        max_iterations=iterations, status_interval_seconds=0.0,
    )

    assert len(sent_calls) == 1  # still just the one send -- no duplicate alert after "restart"


def test_failed_telegram_delivery_is_not_resent_after_restart(tmp_path, monkeypatch):
    """A failed/ambiguous Telegram send is persisted as undelivered and is not retried automatically."""
    send_attempts = []
    import app.main as app_main
    monkeypatch.setattr(
        app_main,
        "send_signal",
        lambda signal, cfg: send_attempts.append(signal.opportunity_id) or False,
    )

    event, all_bars = _build_long_scenario()
    calendar = EventCalendar(events=[event], metadata={})
    config = _config(tmp_path)
    db_path = str(tmp_path / "db.sqlite")

    series1 = {"EURUSD": M1Series("EURUSD")}
    series1["EURUSD"].update(all_bars)
    store1 = SignalStore(db_path)
    run_forever(
        config=config, client=_FakeClient(), calendar=calendar, m1_series=series1,
        trackers={}, store=store1, sleep_fn=lambda s: None,
        now_fn=_MinuteClock(all_bars[0].timestamp), max_iterations=len(all_bars) + 5,
        status_interval_seconds=0.0,
    )
    assert len(send_attempts) == 1
    rows = store1.all_signals()
    assert len(rows) == 1
    assert rows[0]["telegram_sent"] == 0

    series2 = {"EURUSD": M1Series("EURUSD")}
    series2["EURUSD"].update(all_bars)
    store2 = SignalStore(db_path)
    run_forever(
        config=config, client=_FakeClient(), calendar=calendar, m1_series=series2,
        trackers={}, store=store2, sleep_fn=lambda s: None,
        now_fn=_MinuteClock(all_bars[0].timestamp), max_iterations=len(all_bars) + 5,
        status_interval_seconds=0.0,
    )
    assert len(send_attempts) == 1


def test_run_forever_handles_keyboard_interrupt_gracefully(tmp_path):
    config = _config(tmp_path)
    calendar = EventCalendar(events=[], metadata={})
    store = SignalStore(str(tmp_path / "db.sqlite"))

    def raising_sleep(_seconds):
        raise KeyboardInterrupt

    exit_code = run_forever(
        config=config,
        client=_FakeClient(),
        calendar=calendar,
        m1_series={"EURUSD": M1Series("EURUSD")},
        trackers={},
        store=store,
        sleep_fn=raising_sleep,
        max_iterations=None,
        status_interval_seconds=0.0,
    )
    assert exit_code == 0  # clean shutdown, no exception propagated


def test_format_status_line_contains_expected_fields():
    result = RunOnceResult(
        scan_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        fetch_ok=True, fresh_symbols=10, total_symbols=10, active_event_count=2,
    )
    line = format_status_line(result, active_trackers=3, signals_today=1)
    assert "PSYGRID SIGNAL ENGINE" in line
    assert "Status: RUNNING" in line
    assert "Endpoint: CONNECTED" in line
    assert "Instruments: 10/10" in line
    assert "Active events: 2" in line
    assert "Trackers: 3" in line
    assert "Signals today: 1" in line


def test_format_status_line_shows_disconnected_on_fetch_failure():
    result = RunOnceResult(
        scan_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        fetch_ok=False, fetch_error="timeout", fresh_symbols=0, total_symbols=10, active_event_count=0,
    )
    line = format_status_line(result, active_trackers=0, signals_today=0)
    assert "DISCONNECTED" in line
