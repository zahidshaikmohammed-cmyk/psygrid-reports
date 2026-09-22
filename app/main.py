"""
Live engine entry point (Phase 6).

Loop: fetch the live endpoint -> validate/parse -> update rolling M1
history per instrument -> find events whose reaction window is currently
active -> step every (event, symbol) SetupTracker -> send + persist any
signal that fires -> sleep -> repeat.

This intentionally contains almost no strategy logic itself; it is glue
between data/, market/, strategy/, storage/ and notifications/, all of
which are independently unit-tested.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import EngineConfig, load_config
from data.calendar import EventCalendar
from data.capture import append_capture
from data.endpoint_client import LiveEndpointClient
from data.validator import DataQuality, validate_payload
from market.m1 import M1Series
from notifications.telegram import send_signal
from storage.database import SignalStore
from strategy.signal import SetupTracker, Signal

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def handle_signal(signal: Signal, store: SignalStore, config: EngineConfig) -> bool:
    """Send + persist a newly fired signal. Returns True iff it was newly recorded (not a duplicate)."""
    # Claim the opportunity in SQLite BEFORE touching Telegram. This closes
    # the race where two workers could both observe "not sent" and both post.
    claimed = store.claim_signal(signal)
    if not claimed:
        logger.debug("duplicate signal suppressed: %s", signal.opportunity_id)
        return False

    sent = send_signal(signal, config.telegram)
    if sent:
        store.mark_telegram_sent(signal.opportunity_id)
        logger.info("SIGNAL FIRED\n%s", signal.format_message())
    else:
        # The opportunity stays persisted with telegram_sent=0. We do not
        # automatically retry because that would trade a known delivery
        # failure for possible duplicate delivery after an ambiguous timeout.
        logger.error(
            "SIGNAL CLAIMED BUT TELEGRAM DELIVERY FAILED: %s",
            signal.opportunity_id,
        )
    return True


@dataclass
class RunOnceResult:
    """Everything a status display (e.g. run_signal_engine.py) needs about one scan iteration."""

    scan_time: datetime
    fetch_ok: bool
    fetch_error: str | None = None
    fresh_symbols: int = 0
    total_symbols: int = 0
    active_event_count: int = 0
    active_tracker_count: int = 0
    new_signal_count: int = 0
    new_opportunity_ids: list[str] = field(default_factory=list)


def run_once(
    config: EngineConfig,
    client: LiveEndpointClient,
    calendar: EventCalendar,
    m1_series: dict[str, M1Series],
    trackers: dict[tuple[str, str], SetupTracker],
    store: SignalStore,
    now: datetime | None = None,
) -> RunOnceResult:
    now = now or datetime.now(timezone.utc)
    fetch_result = client.fetch()
    fresh_symbols = 0

    if fetch_result.ok and fetch_result.payload is not None:
        validated = validate_payload(fetch_result.payload, config.data, config.instruments, now=now)
        if validated.top_level_issues:
            logger.warning("payload-level issues: %s", validated.top_level_issues)

        for symbol, parsed in validated.symbols.items():
            if parsed.candles:
                m1_series[symbol].update(parsed.candles)
            if parsed.quality == DataQuality.FRESH:
                fresh_symbols += 1
            if parsed.quality in (DataQuality.STALE, DataQuality.MISSING, DataQuality.INVALID):
                logger.debug("%s data quality=%s issues=%s", symbol, parsed.quality.value, parsed.issues)

        if config.data.enable_capture:
            try:
                append_capture(fetch_result.payload, config.data.capture_dir, fetched_at=now)
            except OSError as exc:
                logger.warning("failed to persist capture: %s", exc)
    else:
        logger.warning("live endpoint fetch failed: %s", fetch_result.error)

    active_event_classes = set(config.active_event_classes) if config.active_event_classes else None
    active_events = calendar.active_events(
        now,
        lookback_minutes=config.windows.setup_expiry_minutes,
        lookahead_minutes=config.windows.pre_event_context_minutes,
        classes=active_event_classes,
    )

    new_opportunity_ids: list[str] = []
    for event in active_events:
        symbols = [s for s in event.affected_instruments if s in config.instruments]
        if not symbols:
            logger.warning(
                "skipping event %s (%s): no explicitly mapped configured instruments",
                event.event_id,
                event.event_name,
            )
            continue
        for symbol in symbols:
            key = (event.event_id, symbol)
            tracker = trackers.get(key)
            if tracker is None:
                tracker = SetupTracker(event=event, symbol=symbol, config=config)
                trackers[key] = tracker
            if tracker.is_terminal:
                continue

            series = m1_series.get(symbol)
            if series is None or len(series) == 0:
                continue

            signal = tracker.step(series, now)
            if signal is not None:
                if handle_signal(signal, store, config):
                    new_opportunity_ids.append(signal.opportunity_id)
            elif tracker.is_terminal and tracker.outcome_type:
                logger.debug("tracker %s:%s terminated: %s", event.event_id, symbol, tracker.outcome_type)

    return RunOnceResult(
        scan_time=now,
        fetch_ok=fetch_result.ok,
        fetch_error=fetch_result.error,
        fresh_symbols=fresh_symbols,
        total_symbols=len(config.instruments),
        active_event_count=len(active_events),
        active_tracker_count=sum(1 for t in trackers.values() if not t.is_terminal),
        new_signal_count=len(new_opportunity_ids),
        new_opportunity_ids=new_opportunity_ids,
    )


def main() -> None:
    _configure_logging()
    config = load_config()
    calendar = EventCalendar.load(config.events_json_path)
    logger.info(
        "loaded %d events (%d usable with confirmed times) from %s",
        len(calendar.events), len(calendar.usable_events()), config.events_json_path,
    )

    client = LiveEndpointClient(config.data)
    m1_series = {s: M1Series(s) for s in config.instruments}
    trackers: dict[tuple[str, str], SetupTracker] = {}
    store = SignalStore(config.storage.db_path)

    logger.info("psygrid report-reaction engine starting; polling %s every %.1fs",
                config.data.endpoint_url, config.data.poll_interval_seconds)

    while True:
        try:
            run_once(config, client, calendar, m1_series, trackers, store)
        except Exception:
            logger.exception("unhandled error in scan loop iteration; continuing")
        time.sleep(config.data.poll_interval_seconds)


if __name__ == "__main__":
    main()
