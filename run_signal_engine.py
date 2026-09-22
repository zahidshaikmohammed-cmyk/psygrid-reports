#!/usr/bin/env python3
"""
PSYGRID Signal Engine -- production entry point.

Run this file directly to start the LIVE report-reaction signal engine:

    python run_signal_engine.py

See README.md's "RUNNING PSYGRID LIVE" section for full setup instructions
(virtual environment, dependencies, required environment variables).

This connects to the REAL PSYGRID live M1 endpoint and watches REAL market
data. It is deliberately separate from the research/backtest tools
(research/backtest.py, research/replay.py) -- those are for offline
analysis of captured historical data, never for live signal generation,
and this file never touches them.

RESEARCH STATUS -- read before trusting any signal this produces:
RESEARCHED != VALIDATED != PROFITABLE. This engine implements and can run
the report -> impulse -> pullback -> M5 structure -> M1 trigger pipeline
correctly (that is what the test suite proves), but the strategy itself
has NOT been validated against real historical outcomes -- see
docs/PRECISION_AUDIT.md and docs/STRATEGY_RESEARCH.md for exactly what
has and has not been established.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

from app.config import EngineConfig, load_config
from app.main import RunOnceResult, run_once
from data.calendar import EventCalendar
from data.endpoint_client import LiveEndpointClient
from market.m1 import M1Series
from storage.database import SignalStore

logger = logging.getLogger("psygrid.run_signal_engine")

STATUS_INTERVAL_SECONDS = 30.0


class TelegramNotConfigured(RuntimeError):
    """Raised at startup when Telegram is not configured -- it is required for live operation."""


def require_telegram_configured(config: EngineConfig) -> None:
    """
    Telegram is not optional for the live engine (a signal nobody receives
    is not a signal): refuse to start rather than silently run without
    alerting.
    """
    if not config.telegram.enabled:
        raise TelegramNotConfigured(
            "TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID are not set.\n\n"
            "PSYGRID's live signal engine requires Telegram to be configured -- a signal that\n"
            "cannot reach you is not useful. Set both environment variables before starting.\n\n"
            "PowerShell:\n"
            '  $env:TELEGRAM_BOT_TOKEN = "123456:ABC-your-bot-token"\n'
            '  $env:TELEGRAM_CHAT_ID   = "123456789"\n\n'
            "bash/zsh:\n"
            '  export TELEGRAM_BOT_TOKEN="123456:ABC-your-bot-token"\n'
            '  export TELEGRAM_CHAT_ID="123456789"\n\n'
            'See README.md, section "RUNNING PSYGRID LIVE", for the full setup.'
        )


def format_status_line(result: RunOnceResult, active_trackers: int, signals_today: int) -> str:
    endpoint_state = "CONNECTED" if result.fetch_ok else f"DISCONNECTED ({result.fetch_error})"
    return (
        "PSYGRID SIGNAL ENGINE\n"
        "Status: RUNNING\n"
        f"Endpoint: {endpoint_state}\n"
        f"Last data update: {result.scan_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Instruments: {result.fresh_symbols}/{result.total_symbols} fresh\n"
        f"Active events: {result.active_event_count}\n"
        f"Trackers: {active_trackers}\n"
        f"Last scan: {result.scan_time.strftime('%H:%M:%S')} UTC\n"
        f"Signals today: {signals_today}"
    )


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run_forever(
    config: EngineConfig | None = None,
    client: Any | None = None,
    calendar: EventCalendar | None = None,
    m1_series: dict[str, M1Series] | None = None,
    trackers: dict[tuple[str, str], Any] | None = None,
    store: SignalStore | None = None,
    sleep_fn: Any = time.sleep,
    now_fn: Any = lambda: datetime.now(timezone.utc),
    max_iterations: int | None = None,
    status_interval_seconds: float = STATUS_INTERVAL_SECONDS,
) -> int:
    """
    The engine's main loop, factored out of main() so it is directly
    testable: every dependency is injectable, so tests can drive a
    handful of iterations against fakes (see
    tests/test_run_signal_engine.py) without touching the network,
    sleeping, or running forever. Real production use
    (`python run_signal_engine.py`) calls this with everything defaulted,
    which builds the real endpoint client, the real researched calendar,
    and a real SQLite-backed signal store.

    Returns a process exit code (0 = clean shutdown, including via Ctrl+C).
    """
    config = config or load_config()
    calendar = calendar if calendar is not None else EventCalendar.load(config.events_json_path)
    client = client if client is not None else LiveEndpointClient(config.data)
    m1_series = m1_series if m1_series is not None else {s: M1Series(s) for s in config.instruments}
    trackers = trackers if trackers is not None else {}
    store = store if store is not None else SignalStore(config.storage.db_path)

    logger.info(
        "loaded %d events (%d usable with confirmed times) from %s",
        len(calendar.events), len(calendar.usable_events()), config.events_json_path,
    )
    logger.info(
        "psygrid signal engine starting; endpoint=%s poll_interval=%.1fs instruments=%s",
        config.data.endpoint_url, config.data.poll_interval_seconds, ", ".join(config.instruments),
    )

    session_start = now_fn()
    last_status_print = 0.0
    iterations = 0

    try:
        while max_iterations is None or iterations < max_iterations:
            try:
                result = run_once(config, client, calendar, m1_series, trackers, store, now=now_fn())
            except Exception:
                # Anything unexpected (a bug, a truly malformed payload the
                # validator didn't anticipate, etc.) must not kill the
                # process -- log it and keep scanning.
                logger.exception("unhandled error in scan loop iteration; continuing")
                result = None

            now_wall = time.monotonic()
            should_print = result is not None and (
                now_wall - last_status_print >= status_interval_seconds or result.new_signal_count > 0
            )
            if should_print:
                signals_today = store.count_signals_since(session_start)
                active_trackers = sum(1 for t in trackers.values() if not t.is_terminal)
                print(format_status_line(result, active_trackers, signals_today))
                print("-" * 40)
                last_status_print = now_wall

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            sleep_fn(config.data.poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Ctrl+C received -- shutting down cleanly.")
        print("\nPSYGRID SIGNAL ENGINE\nStatus: STOPPED (Ctrl+C)")
        return 0

    return 0


def main() -> int:
    _configure_logging()
    config = load_config()
    try:
        require_telegram_configured(config)
    except TelegramNotConfigured as exc:
        print("ERROR: cannot start PSYGRID live signal engine.\n", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    return run_forever(config=config)


if __name__ == "__main__":
    raise SystemExit(main())
