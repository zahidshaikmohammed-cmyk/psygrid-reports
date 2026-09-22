import json
from datetime import datetime, timezone

from data.calendar import EventCalendar


def _write_calendar(tmp_path, events):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": events}))
    return str(path)


def test_ist_to_utc_conversion(tmp_path):
    # 18:00 IST == 12:30 UTC (IST is UTC+5:30, no DST)
    events = [{
        "date": "2026-09-24",
        "event_name": "US CPI",
        "country_region": "United States",
        "exact_time_confirmed": True,
        "exact_release_time_IST": "18:00",
        "affected_instruments": ["XAUUSD", "EURUSD"],
    }]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    assert len(calendar.events) == 1
    event = calendar.events[0]
    assert event.event_datetime_utc == datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)
    assert event.usable_for_engine is True


def test_local_timezone_is_authoritative_over_ist_field(tmp_path):
    # US CPI, 08:30 America/New_York (EDT, UTC-4 in September) == 12:30 UTC.
    # Deliberately give a WRONG IST field to prove local tz wins.
    events = [{
        "date": "2026-09-24",
        "event_name": "US CPI",
        "country_region": "United States",
        "exact_time_confirmed": True,
        "original_release_timezone": "America/New_York",
        "exact_release_time_local": "08:30",
        "exact_release_time_IST": "23:59",  # wrong on purpose
        "affected_instruments": ["XAUUSD"],
    }]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    event = calendar.events[0]
    assert event.event_datetime_utc == datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)


def test_midnight_rollover_handled_correctly_via_local_timezone(tmp_path):
    # 16:30 America/New_York on Sep 22 (EDT, UTC-4) == 20:30 UTC == 02:00 IST
    # on Sep 23 -- a naive same-day IST-field combination would get this wrong.
    events = [{
        "date": "2026-09-22",
        "event_name": "API Weekly Statistical Bulletin",
        "country_region": "United States",
        "exact_time_confirmed": True,
        "original_release_timezone": "America/New_York",
        "exact_release_time_local": "16:30",
        "exact_release_time_IST": "02:00",
        "affected_instruments": ["USOIL"],
    }]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    event = calendar.events[0]
    assert event.event_datetime_utc == datetime(2026, 9, 22, 20, 30, tzinfo=timezone.utc)


def test_ist_fallback_used_when_local_tz_missing(tmp_path):
    events = [{
        "date": "2026-09-24",
        "event_name": "Vague Report",
        "exact_time_confirmed": True,
        "exact_release_time_IST": "18:00",
        "affected_instruments": ["XAUUSD"],
    }]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    event = calendar.events[0]
    assert event.event_datetime_utc == datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)


def test_unconfirmed_time_excluded_from_engine(tmp_path):
    events = [{
        "date": "2026-09-24",
        "event_name": "Some Vague Report",
        "exact_time_confirmed": False,
        "affected_instruments": ["XAUUSD"],
    }]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    assert len(calendar.events) == 1
    assert calendar.events[0].usable_for_engine is False
    assert calendar.usable_events() == []


def test_events_for_symbol_filters_correctly(tmp_path):
    events = [
        {"date": "2026-09-24", "event_name": "US CPI", "exact_time_confirmed": True,
         "exact_release_time_IST": "18:00", "affected_instruments": ["XAUUSD", "EURUSD"]},
        {"date": "2026-09-29", "event_name": "RBA Decision", "exact_time_confirmed": True,
         "exact_release_time_IST": "09:00", "affected_instruments": ["AUDUSD"]},
    ]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    assert [e.event_name for e in calendar.events_for_symbol("AUDUSD")] == ["RBA Decision"]
    assert len(calendar.events_for_symbol("XAUUSD")) == 1


def test_active_events_window(tmp_path):
    events = [{
        "date": "2026-09-24", "event_name": "US CPI", "exact_time_confirmed": True,
        "exact_release_time_IST": "18:00", "affected_instruments": ["XAUUSD"],
    }]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    event_utc = calendar.events[0].event_datetime_utc
    assert calendar.active_events(event_utc, lookback_minutes=5, lookahead_minutes=5) != []
    far_away = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert calendar.active_events(far_away, lookback_minutes=5, lookahead_minutes=5) == []


def test_missing_file_returns_empty_calendar():
    calendar = EventCalendar.load("/nonexistent/path/events.json")
    assert calendar.events == []
    assert "error" in calendar.metadata


def test_malformed_event_entry_skipped_not_crashing(tmp_path):
    events = [
        {"date": "2026-09-24"},  # missing event_name
        {"event_name": "No date"},  # missing date
        {"date": "2026-09-24", "event_name": "Valid Event", "exact_time_confirmed": True,
         "exact_release_time_IST": "10:00", "affected_instruments": []},
    ]
    calendar = EventCalendar.load(_write_calendar(tmp_path, events))
    assert len(calendar.events) == 1
    assert calendar.events[0].event_name == "Valid Event"
