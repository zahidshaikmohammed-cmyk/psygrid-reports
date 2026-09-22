"""
Economic event calendar loader.

Loads data/events_sep22_oct31_2026.json (produced by the research phase,
see docs/EVENT_RESEARCH.md) into typed EconomicEvent objects the engine can
query by time and by instrument.

UTC is always derived from the event's (date, exact_release_time_local,
original_release_timezone) via zoneinfo, NOT from the researched IST field
directly. This matters: a US afternoon/evening release (e.g. 16:30 ET)
lands on the *next* calendar day in IST (02:00 IST), but the "date" field
records the US release date -- combining that date with the IST
time-of-day naively would silently compute a UTC instant a full day off.
Deriving from the authoritative local timezone instead sidesteps that
rollover ambiguity entirely and lets zoneinfo handle DST correctly. The
IST field is only used as a fallback when local time/timezone are missing
(same-calendar-day assumption, logged as a caveat), and otherwise purely
for display.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

IST_OFFSET = timedelta(hours=5, minutes=30)
IST_ZONE = timezone(IST_OFFSET)


@dataclass(frozen=True)
class EconomicEvent:
    event_id: str
    date: str
    day_of_week: str | None
    country_region: str | None
    currency: str | None
    event_name: str
    importance: str | None
    original_release_timezone: str | None
    exact_release_time_local: str | None
    exact_release_time_ist: str | None
    exact_time_confirmed: bool
    official_source: str | None
    secondary_crosscheck: str | None
    affected_instruments: tuple[str, ...]
    notes: str | None
    event_datetime_utc: datetime | None  # None if time not confirmed

    @property
    def usable_for_engine(self) -> bool:
        """Only events with a confirmed exact time can drive the live event clock."""
        return self.exact_time_confirmed and self.event_datetime_utc is not None


def _make_event_id(date: str, country_region: str | None, event_name: str) -> str:
    slug = "-".join((country_region or "unk", event_name)).lower()
    slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{date}:{slug.strip('-')}"


def _parse_hhmm(time_str: str) -> time | None:
    try:
        hh, mm = (int(p) for p in time_str.strip().split(":")[:2])
        return time(hour=hh, minute=mm)
    except (ValueError, IndexError):
        return None


def _compute_utc_from_local(date_str: str, local_time_str: str | None, tz_name: str | None) -> datetime | None:
    if not local_time_str or not tz_name:
        return None
    t = _parse_hhmm(local_time_str)
    if t is None:
        return None
    try:
        d = date_cls.fromisoformat(date_str)
        tz = ZoneInfo(tz_name)
    except (ValueError, ZoneInfoNotFoundError):
        logger.warning("could not resolve date/timezone for event: %s %s", date_str, tz_name)
        return None
    local_dt = datetime.combine(d, t, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def _compute_utc_from_ist_fallback(date_str: str, ist_time_str: str | None) -> datetime | None:
    """
    Fallback only: assumes the IST time falls on the SAME calendar date as
    `date_str`. This is wrong whenever the original local release rolls
    over midnight in IST (see module docstring) -- only used when local
    time/timezone are unavailable, which should be rare and is logged.
    """
    if not ist_time_str:
        return None
    t = _parse_hhmm(ist_time_str)
    if t is None:
        logger.warning("could not parse IST time for event: %s %s", date_str, ist_time_str)
        return None
    try:
        d = date_cls.fromisoformat(date_str)
    except ValueError:
        return None
    local_dt = datetime.combine(d, t, tzinfo=IST_ZONE)
    logger.warning(
        "event %s on %s has no local time/timezone; computed UTC from IST field "
        "assuming same-day, which is unverified across a midnight rollover",
        date_str, ist_time_str,
    )
    return local_dt.astimezone(timezone.utc)


def _parse_event(raw: dict) -> EconomicEvent | None:
    date_str = raw.get("date")
    event_name = raw.get("event_name")
    if not date_str or not event_name:
        logger.warning("skipping malformed event entry (missing date/event_name): %r", raw)
        return None

    exact_time_confirmed = bool(raw.get("exact_time_confirmed", False))
    ist_time = raw.get("exact_release_time_IST") or raw.get("exact_release_time_ist")

    event_dt_utc = None
    if exact_time_confirmed:
        event_dt_utc = _compute_utc_from_local(
            date_str, raw.get("exact_release_time_local"), raw.get("original_release_timezone")
        )
        if event_dt_utc is None:
            event_dt_utc = _compute_utc_from_ist_fallback(date_str, ist_time)

    affected = raw.get("affected_instruments") or []
    if not isinstance(affected, list):
        affected = []

    return EconomicEvent(
        event_id=raw.get("event_id") or _make_event_id(date_str, raw.get("country_region"), event_name),
        date=date_str,
        day_of_week=raw.get("day_of_week"),
        country_region=raw.get("country_region"),
        currency=raw.get("currency"),
        event_name=event_name,
        importance=raw.get("importance"),
        original_release_timezone=raw.get("original_release_timezone"),
        exact_release_time_local=raw.get("exact_release_time_local"),
        exact_release_time_ist=ist_time,
        exact_time_confirmed=exact_time_confirmed,
        official_source=raw.get("official_source"),
        secondary_crosscheck=raw.get("secondary_crosscheck"),
        affected_instruments=tuple(affected),
        notes=raw.get("notes"),
        event_datetime_utc=event_dt_utc,
    )


@dataclass
class EventCalendar:
    events: list[EconomicEvent] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "EventCalendar":
        p = Path(path)
        if not p.exists():
            logger.error("event calendar file not found: %s", p)
            return cls(events=[], metadata={"error": f"file not found: {p}"})
        try:
            raw = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            logger.error("event calendar file is not valid JSON: %s", exc)
            return cls(events=[], metadata={"error": f"invalid JSON: {exc}"})

        raw_events = raw.get("events", []) if isinstance(raw, dict) else []
        events = [e for e in (_parse_event(r) for r in raw_events) if e is not None]
        events.sort(key=lambda e: (e.event_datetime_utc is None, e.event_datetime_utc or datetime.max.replace(tzinfo=timezone.utc)))

        metadata = {k: v for k, v in raw.items() if k != "events"} if isinstance(raw, dict) else {}
        return cls(events=events, metadata=metadata)

    def usable_events(self) -> list[EconomicEvent]:
        return [e for e in self.events if e.usable_for_engine]

    def events_in_window(self, start: datetime, end: datetime) -> list[EconomicEvent]:
        return [
            e for e in self.usable_events()
            if start <= e.event_datetime_utc <= end  # type: ignore[operator]
        ]

    def next_event(self, now: datetime) -> EconomicEvent | None:
        upcoming = [e for e in self.usable_events() if e.event_datetime_utc >= now]  # type: ignore[operator]
        return upcoming[0] if upcoming else None

    def events_for_symbol(self, symbol: str) -> list[EconomicEvent]:
        return [e for e in self.usable_events() if symbol in e.affected_instruments]

    def active_events(self, now: datetime, lookback_minutes: float, lookahead_minutes: float) -> list[EconomicEvent]:
        """Events whose T0 falls within [now - lookback, now + lookahead]."""
        window_start = now - timedelta(minutes=lookback_minutes)
        window_end = now + timedelta(minutes=lookahead_minutes)
        return self.events_in_window(window_start, window_end)
