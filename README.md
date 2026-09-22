# PsyGrid Report-Reaction Engine

A research-driven intraday engine for the hypothesis:

```
REPORT → PRICE IMPULSE → PULLBACK / RETRACEMENT → M5 STRUCTURE CONFIRMATION → M1 ENTRY TRIGGER → TRADE SIGNAL
```

This is **not** a "news = trade" bot. It reacts to actual price behaviour around scheduled
economic events, scores several stages of evidence, and only emits a signal (via Telegram) when
the full pattern is observed. See [`docs/STRATEGY_RESEARCH.md`](docs/STRATEGY_RESEARCH.md) for
the full design rationale, and [`docs/EVENT_RESEARCH.md`](docs/EVENT_RESEARCH.md) for the
researched economic calendar (Sep 22 – Oct 31 2026).

**Universe:** XAUUSD, EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAGUSD, USOIL

## Status

Phases 1–5 (research, data client, design, implementation, tests) are complete. Phase 6 (live
signal mode) is implemented but **has not been run against real market data** — see
[`docs/STRATEGY_RESEARCH.md` §1](docs/STRATEGY_RESEARCH.md#1-what-this-document-is-and-is-not)
for exactly what that means and what running it will unlock (real backtest calibration).

## Project layout

```
app/            config.py (all tunables), main.py (live engine loop)
data/           endpoint_client.py, validator.py, calendar.py, capture.py
market/         m1.py, m5.py, volatility.py, structure.py -- generic, causal primitives
strategy/       impulse.py, pullback.py, confirmation.py, trigger.py, signal.py
research/       replay.py, backtest.py, metrics.py -- reuses strategy/signal.py's SetupTracker
storage/        database.py -- SQLite signal store / duplicate prevention
notifications/  telegram.py
tests/          pytest suite (deterministic fixtures, no network/real data required)
docs/           EVENT_RESEARCH.md, STRATEGY_RESEARCH.md
data/events_sep22_oct31_2026.json   researched event calendar
```

## Setup

```bash
pip install -r requirements-dev.txt   # includes requirements.txt + pytest
```

Environment variables (never hard-coded):

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for signal delivery |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel to post signals to |
| `PSYGRID_LIVE_ENDPOINT` | Override the live data endpoint (defaults to the provided URL) |
| `PSYGRID_DB_PATH` | Override the SQLite signal-store path |

## Running

```bash
python -m app.main
```

This polls the live endpoint, updates rolling M1 history per instrument, watches for active
event windows, drives the impulse → pullback → M5 → M1 pipeline per (event, symbol), and sends +
persists any signal that fires. It also appends every successful poll to
`data/captures/YYYY-MM-DD.jsonl` (disable with `PSYGRID_LIVE_ENDPOINT`'s sibling config
`DataConfig.enable_capture=False`), which is what makes real backtesting possible later.

**Note:** the live endpoint was not reachable from the environment this project was built in
(confirmed: direct requests to it time out). The client, validator, and full pipeline are built
and unit-tested against the documented/observed schema regardless — run `python -m app.main` from
an environment that *can* reach the endpoint (per the project brief, that's expected to be the
production host, not necessarily a dev sandbox).

## Testing

```bash
pytest tests/ -q
```

All tests use deterministic synthetic fixtures (`tests/factories.py`) — no network access or real
market data required. Coverage includes: endpoint payload parsing/schema validation, M1
dedup/causal slicing, M5 aggregation (with an explicit no-look-ahead check), timezone conversion
(including a regression test for the US-evening/IST-midnight-rollover case), event window
activation, impulse/pullback/structure/trigger detection, full long & short signal generation,
duplicate-signal suppression, stale/missing/malformed-data resilience, and a dedicated
look-ahead-bias test that runs the same scenario with all data pre-loaded vs. loaded
incrementally and asserts identical output.

## Research / backtesting

`research/backtest.py` drives the *exact same* `strategy.signal.SetupTracker` used live, bar by
bar, against historical M1 data — there is no separate backtest-only strategy code. Real
historical data does not exist in this repository (none was fabricated); once `app/main.py` has
run for a while and accumulated `data/captures/*.jsonl`, run:

```python
from app.config import load_config
from data.calendar import EventCalendar
from research.backtest import load_m1_history_from_captures, run_backtest
from research.metrics import summarize, by_instrument, by_event

config = load_config()
calendar = EventCalendar.load(config.events_json_path)
history = load_m1_history_from_captures(config.data.capture_dir, config.instruments, config.data)
report = run_backtest(history, calendar, config)
print(summarize(report))
```

See [`docs/STRATEGY_RESEARCH.md` §5](docs/STRATEGY_RESEARCH.md#5-what-researchbacktestpy-will-need-to-answer-once-data-exists)
for what this is expected to answer.
