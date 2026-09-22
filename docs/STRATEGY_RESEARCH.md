# Strategy Research — Report → Impulse → Pullback → M5 → M1 → Signal

**Companion documents:** [`EVENT_RESEARCH.md`](EVENT_RESEARCH.md) (event calendar research),
`data/events_sep22_oct31_2026.json` (structured calendar), the codebase itself
(`market/`, `strategy/`, `research/`).

---

## 1. What this document is, and is not

This is the design rationale for the mathematical framework implemented in `market/` and
`strategy/`. It explains *why* each detector is shaped the way it is, what evidence it scores,
and — critically — **what has and has not actually been validated**.

**What has NOT been done:** a real backtest against historical market data. This repository
ships no historical M1 candles for XAUUSD/EURUSD/etc., and none were fabricated — the project's
own "do not invent data" requirement rules that out. The live endpoint
(`http://140.245.226.102:8080/public/live.json`) is also not reachable from this development
environment (confirmed directly: outbound requests to it time out from here), so it could not be
polled to bootstrap history either. `research/replay.py`, `research/backtest.py`, and
`research/metrics.py` are fully implemented and exercised by `tests/test_research_backtest.py`
against synthetic fixtures, which prove the mechanics are correct (no look-ahead, correct trade
simulation, correct metric arithmetic) — but synthetic fixtures say nothing about whether the
report → impulse → pullback → M5 → M1 pattern actually recurs in real price action, how often,
or whether it is profitable. **That is the real Phase-3 research question, and it can only be
answered once `app/main.py` has run against the live endpoint for a while**, accumulating
captures under `data/captures/*.jsonl` (see `data/capture.py`), which `research/backtest.py`'s
`load_m1_history_from_captures` reads back in.

Every threshold in `app/config.py` is therefore a **documented starting point**, not a proven
constant. The architecture is deliberately built so all of them are swept by
`research/backtest.py` once real data exists, without touching strategy code.

---

## 2. Why evidence scores, not hard gates

The project brief is explicit: don't build a rigid rule cascade that rejects almost everything
("must retrace exactly 38.2%", "must wait exactly 5 minutes"). Two considerations drove the
scoring design instead:

1. **Cross-instrument normalization.** XAUUSD can move $8 in a minute; EURUSD's "big" minute
   move might be 8 pips. A single hard pip threshold cannot work across the 10-instrument
   universe. Every impulse/structure measure is instead expressed **relative to that
   instrument's own recent volatility** (rolling ATR, rolling return stdev) — see
   `market/volatility.py`.

2. **Real reactions are not binary.** A report can produce a clean impulse-pullback-continuation,
   a impulse that never pulls back (straight continuation), a pullback that becomes a full
   reversal, or a whipsaw. Collapsing these into a single pass/fail gate throws away information
   the eventual research/backtest calibration needs. Each stage instead produces a **0..1
   evidence score** from several weighted sub-signals (see `app/config.py`'s
   `ImpulseConfig`/`PullbackConfig`/`StructureConfig`/`SignalConfig`), and the final
   `setup_quality` (0..100) is a transparent weighted combination — never presented as a
   calibrated probability, per the project's own requirement, since no calibration has been done.

---

## 3. Stage by stage

### 3.1 Impulse detection (`strategy/impulse.py`)

For each M1 bar after the event time, five sub-signals are scored 0..1 via a saturating
function (`min(raw/target, 1)`) and combined with configurable weights:

| Evidence | What it measures | Why |
|---|---|---|
| Range expansion | bar range / rolling ATR | Directly implements "M1 range / rolling ATR" from the brief |
| Return z-score | \|close−open\|/open, divided by rolling return stdev | Normalized magnitude of the move |
| Directional run | consecutive same-direction closes | Distinguishes a real push from a single noisy bar |
| Volume expansion | bar volume / rolling avg volume | Only used **if volume is actually meaningful** — see §4 |
| Event distance | cumulative move from the event-start price / ATR | "How far has price actually travelled since T0" |

If volume is not meaningful for a symbol (see §4), its weight is redistributed proportionally
across the other four rather than silently penalizing every non-FX-volume instrument.

**A deliberate refinement found during testing:** confirming the impulse the instant a single
bar clears `impulse_score_threshold` and freezing its high/low as "the impulse" is naive — a
strong single bar is very often the *start* of a larger multi-bar move, not the whole thing.
`ImpulseResult.is_still_extending` tracks whether the best-scoring bar seen so far is also the
most recent bar; if so, `SetupTracker` keeps watching (up to `impulse_detection_minutes`) rather
than locking in prematurely, letting genuinely multi-bar impulses fully develop before their
extreme is fixed. This was discovered by the integration tests (`tests/test_signal_pipeline.py`)
failing on a synthetic 4-bar impulse that kept getting truncated to 1 bar, and is exactly the
kind of thing real backtesting should stress-test further.

### 3.2 Pullback classification (`strategy/pullback.py`)

Retracement is expressed as a **fraction of the impulse leg's size**, not a fixed price
distance, for the same cross-instrument reason as above. The classification bands
(`min_healthy_retracement=0.15`, `max_healthy_retracement=0.618`, etc.) borrow familiar
retracement landmarks as a *starting* lens, explicitly not gospel — the brief specifically warns
against blind Fibonacci imposition. Six distinct outcomes are distinguished, matching §10/§24 of
the brief: `HEALTHY`, `DEEP`, `CONTINUATION` (impulse kept extending, no real pullback),
`FAILURE` (fully round-tripped), `REVERSAL` (pushed meaningfully past the impulse start),
`WHIPSAW` (snapped back to a new extreme right after a deep retrace). Only `HEALTHY`/`DEEP`
pullbacks proceed to M5 structure confirmation; every other outcome is recorded (for research
metrics — see §5) but does not produce a signal, since it no longer matches the hypothesized
shape.

### 3.3 M5 structure confirmation (`strategy/confirmation.py`)

Causal M5 candles are built from the M1 series (`market/m5.py`) — a 5-minute bucket is only ever
reported once `as_of` has passed its close, so structure analysis never sees a forming bar.
Structure evidence composes generic swing-point primitives (`market/structure.py`, a causal
fractal detector) into the report-reaction-specific question: for a bullish setup, did the
pullback's low stay **above** the prior M5 swing low (higher-low preserved), did price avoid
closing back below it, and is the most recent M5 candle itself bullish? Each is a 0/1 evidence
component; the mean is the structure score. This is intentionally simpler than the
impulse/pullback scoring because M5 structure functions here as a confirming filter, not the
primary signal generator — the brief's diagram treats it as gatekeeping "does the pullback
preserve enough structure to continue", not as an independent scoring engine.

### 3.4 M1 trigger (`strategy/trigger.py`)

Deterministic and mechanical by design (the brief explicitly forbids subjective language like
"looks strong"): once structure is confirmed, the tracker looks for the most recent M1 micro
swing point opposing the trade direction (a swing high during a bullish pullback, a swing low
during a bearish one) and fires the moment a subsequent M1 bar **closes** back through it. This
is the "break of the pullback's own micro-structure" trigger named in the brief, not a break of
the original impulse extreme — that would usually be too far away to serve as a timely entry.

### 3.5 Signal assembly (`strategy/signal.py`)

`SetupTracker` is a small state machine
(`WATCHING_IMPULSE → WATCHING_PULLBACK → WATCHING_STRUCTURE → WATCHING_TRIGGER → SIGNAL_FIRED`,
with `INVALIDATED`/`EXPIRED` branches at every stage) driven one bar at a time by `.step()`. This
is the **one and only** place this pipeline runs — both `app/main.py` (live) and
`research/replay.py` (historical) drive the identical `SetupTracker.step()` causally, so there is
no separate "backtest-only" code path that could silently diverge from live behavior (a common
and serious source of backtest/live mismatch in trading systems).

`setup_quality` (0..100) is `100 × (w_impulse·impulse_score + w_pullback·pullback_quality +
w_structure·structure_score + w_trigger·1.0)` — the trigger contributes fully once confirmed
since it is a deterministic yes/no by construction. `pullback_quality` peaks at the center of the
"healthy" retracement band and is scored 0.5 for "deep" pullbacks (weaker evidence, still
tradeable). Stop is placed at the pullback extreme with an ATR buffer
(`stop_atr_multiple`); target is a configurable R-multiple of the resulting risk
(`target_r_multiple`).

`opportunity_id = f"{event_id}:{symbol}:{impulse_id}"` is the duplicate-prevention key (project
requirement §22) — persisted in `storage/database.py`'s SQLite store, checked before every
Telegram send, so a restart or a repeated poll can never re-alert the same setup.

---

## 4. Data-quality handling (kept separate from strategy logic)

Per the brief's explicit requirement (§28), `data/validator.py` owns *only* the question "is this
data usable, and how much of it" — `fresh` / `stale` / `partial` / `missing` / `invalid` — and
never makes a trading decision. The strategy layer never asks "why" a bar is missing, only
whether it has enough bars to compute something; `market/volatility.py`'s ATR/stdev functions
return `None` rather than a fabricated number below a configured minimum bar count, and callers
propagate that as "insufficient data" rather than crashing or silently proceeding with noise.

Volume is a known trap for FX/CFD feeds: many providers report zero, constant, or purely
synthetic tick-count "volume" that carries no real information. `volume_is_meaningful()` checks
for actual variance before any volume-based evidence is used, and redistributes that evidence's
weight elsewhere when it isn't — this must be re-examined once real endpoint data is seen, since
the brief's own example schema shows a real `volume` field (188.0) that may or may not turn out
to be meaningful in practice.

---

## 5. What research/backtest.py will need to answer, once data exists

`research/metrics.py` computes exactly the quantities the brief's Phase-3/§23-24 hypothesis
section asks for: counts of events/impulses/valid-pullbacks/structure-confirmations/signals, win
rate, average R, expectancy, MFE/MAE, time-to-exit, and — critically — the **rates of each
non-signal outcome** (`continuation_rate`, `reversal_rate`, `whipsaw_rate`,
`failed_setup_rate`), broken down `by_instrument`/`by_event`/`by_instrument_and_event`. These
directly answer the brief's research questions: how often does the hypothesized pattern actually
occur, which instruments/events show it, and is it profitable where it does. None of these
numbers exist yet in this repository — running `app/main.py` against the live endpoint to
accumulate `data/captures/*.jsonl`, then `research/backtest.py` against that capture, is the next
required step before any of `app/config.py`'s thresholds should be treated as tuned rather than
starting points.

## 6. Candidate holding-window sweep (§15 of the brief)

`EventWindowConfig.max_holding_minutes` currently defaults to 30 (the brief's stated intraday
ceiling). The brief asks specifically for 1–3m / 3–5m / 5–10m / 10–15m / 15–20m / 20–30m to be
tested against real trade outcomes — `research/backtest.py`'s `simulate_trade` already takes
`config.windows.max_holding_minutes` as a parameter, so this sweep is a matter of re-running
`run_backtest` with different `EngineConfig.windows` once real captured data exists, not a code
change.
