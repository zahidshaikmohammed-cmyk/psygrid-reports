# PsyGrid Report-Reaction Engine

A research-driven intraday engine for the hypothesis:

```
REPORT → PRICE IMPULSE → PULLBACK / RETRACEMENT → M5 STRUCTURE CONFIRMATION → M1 ENTRY TRIGGER → TRADE SIGNAL
```

This is **not** a "news = trade" bot. It reacts to actual price behaviour around scheduled
economic events, scores several stages of evidence, and only emits a signal (via Telegram) when
the full pattern is observed. See [`docs/STRATEGY_RESEARCH.md`](docs/STRATEGY_RESEARCH.md) for
the full design rationale, [`docs/EVENT_RESEARCH.md`](docs/EVENT_RESEARCH.md) for the researched
economic calendar (Sep 22 – Oct 31 2026), and [`docs/PRECISION_AUDIT.md`](docs/PRECISION_AUDIT.md)
for a correctness audit of the data/timing semantics, event classification, and instrument
mappings.

**Universe:** XAUUSD, EURUSD, GBPUSD, USDJPY, GBPJPY, AUDUSD, USDCAD, NZDUSD, XAGUSD, USOIL

> **Research status: RESEARCHED ≠ VALIDATED ≠ PROFITABLE.** The pipeline is researched and
> implemented correctly (that's what the test suite proves). It has **not** been validated
> against real historical outcomes, and no profitability claim is made anywhere in this
> codebase. See [`docs/PRECISION_AUDIT.md` §8](docs/PRECISION_AUDIT.md#8-research-status).

## Status

Phases 1–5 (research, data client, design, implementation, tests) are complete, and a precision
audit (`docs/PRECISION_AUDIT.md`) has been performed on the data/timing layer. Phase 6 (live
signal mode) is implemented, has a dedicated production entry point (`run_signal_engine.py`,
below), but **has not been run against real market data** — see
[`docs/STRATEGY_RESEARCH.md` §1](docs/STRATEGY_RESEARCH.md#1-what-this-document-is-and-is-not)
for exactly what that means and what running it will unlock (real backtest calibration).

## Project layout

```
run_signal_engine.py   <- the LIVE entry point (see "RUNNING PSYGRID LIVE" below)
app/            config.py (all tunables), main.py (run_once/handle_signal core used by the runner above)
data/           endpoint_client.py, validator.py, calendar.py, capture.py
market/         m1.py, m5.py, volatility.py, structure.py -- generic, causal primitives
strategy/       impulse.py, pullback.py, confirmation.py, trigger.py, signal.py
research/       replay.py, backtest.py, metrics.py -- reuses strategy/signal.py's SetupTracker
storage/        database.py -- SQLite signal store / duplicate prevention
notifications/  telegram.py
tests/          pytest suite (deterministic fixtures, no network/real data required)
docs/           EVENT_RESEARCH.md, STRATEGY_RESEARCH.md, PRECISION_AUDIT.md
data/events_sep22_oct31_2026.json   researched event calendar
```

`run_signal_engine.py` and `research/backtest.py` are deliberately separate (see "Do not confuse
research with live operation" below) — the live runner always uses the real endpoint and real M1
data; the research tools never do.

## Setup

```bash
pip install -r requirements-dev.txt   # includes requirements.txt + pytest
```

Environment variables (never hard-coded):

| Variable | Purpose | Required? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for signal delivery | **Yes**, for `run_signal_engine.py` |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel to post signals to | **Yes**, for `run_signal_engine.py` |
| `PSYGRID_LIVE_ENDPOINT` | Override the live data endpoint (defaults to the provided URL) | No |
| `PSYGRID_DB_PATH` | Override the SQLite signal-store path (default `storage/psygrid.db`) | No |
| `PSYGRID_ACTIVE_EVENT_CLASSES` | Comma-separated subset of `MAJOR,SECONDARY,RESEARCH_ONLY` to activate on (default: `MAJOR,SECONDARY`) | No |

`run_signal_engine.py` refuses to start without `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` set —
see below.

---

## RUNNING PSYGRID LIVE

This is the intended way to run PSYGRID day to day: a normal PowerShell (or bash/zsh) terminal,
Python, and the command below. No desktop GUI is required or used.

### PowerShell (Windows)

```powershell
cd <project-folder>
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:TELEGRAM_BOT_TOKEN = "123456:ABC-your-bot-token"
$env:TELEGRAM_CHAT_ID   = "123456789"

python run_signal_engine.py
```

### bash / zsh (macOS/Linux)

```bash
cd <project-folder>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="123456:ABC-your-bot-token"
export TELEGRAM_CHAT_ID="123456789"

python run_signal_engine.py
```

**That single command (`python run_signal_engine.py`) is the entire live operation surface.**
It requires no knowledge of the internal package layout. It will:

1. Refuse to start with a clear error if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are not set
   (Telegram is required, not optional, for live operation — see below).
2. Connect to the real PSYGRID live M1 endpoint and load the researched event calendar.
3. Continuously poll the endpoint, update rolling M1 history for all 10 configured instruments,
   watch for active scheduled-event windows, and run the report → impulse → pullback → M5
   structure → M1 trigger pipeline per (event, symbol).
4. Send a Telegram message and persist the signal to SQLite the moment a complete setup is
   confirmed — and never resend the same one (see "No duplicate Telegram alerts" below).
5. Print a periodic status block to the terminal (not spammed every poll — see below).
6. Keep running until you press **Ctrl+C**, at which point it shuts down cleanly (see "Graceful
   shutdown" below).
7. Recover from temporary endpoint/network failures on its own — a fetch timeout or a bad
   response is logged and the loop just tries again on the next poll; it does not crash.

### Terminal status

While running, PSYGRID prints a status block roughly every 30 seconds (and immediately whenever
a new signal fires, so you never wait to see one) — not on every single poll, to avoid spamming
the terminal:

```
PSYGRID SIGNAL ENGINE
Status: RUNNING
Endpoint: CONNECTED
Last data update: 2026-09-24 18:00:05 UTC
Instruments: 10/10 fresh
Active events: 1
Trackers: 3
Last scan: 18:00:05 UTC
Signals today: 2
----------------------------------------
```

`Endpoint` shows `DISCONNECTED (<error>)` when a poll fails, without stopping the engine.

### Telegram alerts

Telegram is **required**, not optional — `run_signal_engine.py` will not start without both
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set (see `require_telegram_configured` in
`run_signal_engine.py`). Every fired signal sends a message shaped exactly like this
(`strategy/signal.py::Signal.format_message`):

```
PSYGRID SIGNAL

Instrument: XAUUSD
Event: US CPI
Event time: 2026-09-24 18:00 UTC

Direction: LONG

Impulse: confirmed (strength 0.87)
Pullback: confirmed (retracement 32%)
M5 structure: confirmed (score 0.75)
M1 trigger: confirmed

Entry: 4348.20000
Stop: 4344.10000
Target: 4354.35000 (~1.50R)

Setup quality: 78/100
Expected holding window: <= 30 minutes

Opportunity ID: evt:XAUUSD:imp123
```

### No duplicate Telegram alerts

Every signal has a unique `opportunity_id` (`event_id` + `symbol` + `impulse_id`). Before
sending, the engine checks `storage/psygrid.db` (SQLite) for that `opportunity_id`; if it's
already there, the alert is silently suppressed. Because this check is against the on-disk
database rather than in-memory state, **it survives a full process restart**: if you stop and
restart PSYGRID, it will not resend a Telegram message for a signal that already fired before the
restart (`tests/test_run_signal_engine.py::test_run_forever_restart_does_not_resend_same_signal`
proves this explicitly). Note that in-memory tracker/price state is *not* persisted across a
restart — a setup that hadn't fired yet when you stopped the engine simply starts being
re-evaluated from scratch on the next run, which is safe (it is not a duplicate of anything
already sent).

### Graceful shutdown

Press **Ctrl+C**. The engine catches the interrupt at the top of its loop, logs a clean shutdown
message, and exits — it never holds an open SQLite transaction across a poll/sleep cycle (every
database write is its own short, committed operation), so there is nothing to corrupt.

### Do not confuse research with live operation

- **Research/backtest** (offline, uses captured historical data, never touches the live
  endpoint): `research/backtest.py`, `research/replay.py`, `research/metrics.py`.
- **Live operation** (always uses the real endpoint and real M1 data):
  `run_signal_engine.py`.

They share the exact same strategy code (`strategy/signal.py::SetupTracker`) so a backtest result
means something about live behavior, but the two entry points are otherwise independent — running
one never invokes the other.

---

## Running (internal / development use)

```bash
python -m app.main
```

This is the lower-level loop `run_signal_engine.py` builds on (`app.main.run_once` +
`handle_signal`) — same core behavior, but without the startup Telegram guard or the terminal
status output. Prefer `python run_signal_engine.py` for actual live use.

**Note:** the live endpoint was not reachable from the environment this project was built in
(confirmed: direct requests to it time out). The client, validator, and full pipeline are built
and unit-tested against the documented/observed schema regardless — run either entry point from
an environment that *can* reach the endpoint (per the project brief, that's expected to be the
production host, not necessarily a dev sandbox). It also appends every successful poll to
`data/captures/YYYY-MM-DD.jsonl` (disable via `DataConfig.enable_capture=False`), which is what
makes real backtesting possible later.

## Testing

```bash
pytest tests/ -q
```

All tests use deterministic synthetic fixtures (`tests/factories.py`) — no network access or real
market data required. Coverage includes: endpoint payload parsing/schema validation, M1
dedup/causal slicing, M5 aggregation (with an explicit no-look-ahead check), timezone conversion
(including a regression test for the US-evening/IST-midnight-rollover case), event window
activation, event-class/time-confirmation-tier filtering (live default: `MAJOR,SECONDARY`), the event-minute baseline-boundary fix
(`docs/PRECISION_AUDIT.md` §1), simultaneous-event handling, impulse/pullback/structure/trigger
detection, full long & short signal generation, the required Telegram message format,
duplicate-signal suppression (including across a simulated process restart),
stale/missing/malformed-data resilience, the `run_signal_engine.py` entry point itself (startup
guard, status formatting, graceful Ctrl+C), and a dedicated look-ahead-bias test that runs the
same scenario with all data pre-loaded vs. loaded incrementally and asserts identical output.

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
