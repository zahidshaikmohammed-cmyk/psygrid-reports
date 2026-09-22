# Precision Audit

**Scope:** a targeted correctness audit of the implementation completed so far (data
semantics, event calendar fidelity, instrument mapping, simultaneous-event handling),
performed *before* adding any new strategy features, per an explicit request not to expand
scope until this audit was done. No thresholds were tuned and no strategy gates were added or
removed as part of this audit — see §7.

**Companion documents:** [`STRATEGY_RESEARCH.md`](STRATEGY_RESEARCH.md) (design rationale),
[`EVENT_RESEARCH.md`](EVENT_RESEARCH.md) (calendar research write-up).

---

## 1. Candle timestamp semantics (OPEN vs. CLOSE)

**Question:** does a M1 candle's `timestamp` field mark when the bar *opened* or when it
*closed*?

**Finding:** this cannot be empirically verified in this environment — the live endpoint
(`http://140.245.226.102:8080/public/live.json`) is not reachable from here (direct requests
time out; confirmed again during this audit). The project brief's own example schema does not
state the convention either.

**Decision:** the codebase assumes **OPEN time** — a candle timestamped `12:30:00` is treated
as covering `[12:30:00, 12:31:00)`. This is documented as an explicit, load-bearing assumption
in `market/m1.py`'s module docstring, including exactly how to verify it once the live endpoint
is reachable (compare `updated_at`/`last_candle_timestamp` staleness against the newest
`candles_1m` entry — open-time feeds show the newest bar as still-forming/~1 minute "behind";
close-time feeds show it exactly caught up). This is the near-universal convention for OHLC
feeds (MetaTrader, most broker/vendor REST APIs) and the most reasonable reading of the brief's
schema, but it is **not verified**, and every place that depends on it is now cross-referenced
in code comments so the assumption can be flipped in one place if the live data proves otherwise.

**Bug found and fixed as a consequence:** `strategy/signal.py`'s event-time processing computed
the pre-event baseline as `bars where timestamp <= event_time` and the post-event reaction
window as `bars where event_time < timestamp`. Under OPEN-time semantics, the bar timestamped
exactly at `event_time` is the bar **during which the event fires** — the old code put that bar
in the baseline (contaminating the "normal, pre-event" volatility measure with the event's own
first-minute impact) and simultaneously excluded it from impulse detection entirely (discarding
the event's first minute of reaction). Both bugs came from the same off-by-one boundary.

**Fix:** extracted a single, directly-tested boundary function,
`strategy.signal.split_baseline_and_post_event(all_bars, event_time, window_end, as_of)`:
baseline = `timestamp < event_time` (strict), post-event window = `event_time <= timestamp <=
min(as_of, window_end)`. See `tests/test_event_minute_boundary.py` (4 tests) and
`tests/test_signal_pipeline.py::test_event_minute_candle_not_double_counted_through_full_tracker`
for regression coverage proving the fix at both the unit and full-pipeline level.

---

## 2. Event timestamp confirmation audit

The original dataset (`data/events_sep22_oct31_2026.json`) carried a single boolean,
`exact_time_confirmed`. Per this audit's requirement not to treat the whole 74-event set as
uniformly "verified," every event now also carries a **`time_confirmation_tier`**:

| Tier | Meaning | Count |
|---|---|---|
| `official_source_cited` | `exact_time_confirmed=true` and the cited `official_source` is a genuine institutional calendar/page (Fed, BLS, BEA, Census, ECB, BoE/ONS, BoJ, RBA/ABS, RBNZ/StatsNZ, BoC/StatsCanada, EIA, API, OPEC, IEA, China NBS/Customs) | 59 |
| `secondary_calendar_only` | `exact_time_confirmed=true` but the primary cited source is a secondary aggregator (TradingEconomics/Investing.com/FXStreet/etc.), not an official page | 0 |
| `pattern_estimate` | `exact_time_confirmed=false` — inferred from a release-day pattern/cadence, not confirmed for this specific date | 15 |

**Important caveat carried over from the original research** (already stated in
`EVENT_RESEARCH.md` §1, restated here because it directly qualifies the tiers above): no
official page in any tier was fetched and read directly in this research environment — every
`official_source_cited` date/time came from a web-search snippet that quotes or indexes the
official page, not from opening the page itself. **`official_source_cited` means "an official
institutional source was the cited origin," not "the official page was fetched and verified."**
Re-verify every `MAJOR`-class event against its named `official_source` in the week before
trading it. This audit did not change that underlying research limitation — it only makes the
distinction between confirmed/estimated events machine-readable instead of a single boolean, and
it does not call the 74-event set verified.

---

## 3. Event classification: MAJOR / SECONDARY / RESEARCH_ONLY

Per the requirement to preserve the full 74-event research universe while letting the engine
selectively activate on a subset, every event now also carries an **`event_class`**, derived
mechanically from `importance` × `exact_time_confirmed` (no event was deleted):

```
if not exact_time_confirmed:
    event_class = "SECONDARY" if importance == "high" else "RESEARCH_ONLY"
elif importance == "high":
    event_class = "MAJOR"
elif importance == "medium":
    event_class = "SECONDARY"
else:
    event_class = "RESEARCH_ONLY"
```

| Class | Count | Meaning |
|---|---|---|
| `MAJOR` | 33 | High-importance AND confirmed time — FOMC/ECB/BoC/RBNZ/RBA decisions, CPI, NFP, GDP, PCE, ISM/flash PMIs, weekly EIA |
| `SECONDARY` | 31 | Medium-importance confirmed events, or high-importance events whose exact time is not yet confirmed |
| `RESEARCH_ONLY` | 10 | Low-importance events, or non-high-importance events with an estimated/pattern-based time |

**Engine wiring:** `EventCalendar.usable_events()/events_in_window()/active_events()` all take
an optional `classes: set[str] | None` parameter (`data/calendar.py`); `EngineConfig` gets
`active_event_classes: tuple[str, ...] | None` (`app/config.py`), settable via the
`PSYGRID_ACTIVE_EVENT_CLASSES` environment variable (comma-separated, e.g. `MAJOR` or
`MAJOR,SECONDARY`), and `app/main.py::run_once` passes it through. **Default is `None` — no
restriction — identical to pre-audit behavior**, so nothing changes unless an operator opts in.
No event was removed from the JSON file or the loader; classification only controls what the
*live engine* reacts to.

---

## 4. `affected_instruments` mapping audit

**Basis, as found in the existing data (not changed by this audit except the one fix in
§4.1):** an event's currency determines the FX pairs directly exposed to it — every instrument
containing that currency as a leg (e.g. a GBP event → `GBPUSD` and `GBPJPY`; a JPY event →
`USDJPY` and `GBPJPY`). Broad, top-tier USD macro releases (NFP, CPI, GDP, PCE, FOMC, ISM PMIs)
additionally include `XAUUSD`/`XAGUSD` (USD-denominated metals with well-established broad-USD
sensitivity) but **deliberately exclude `USOIL`** — oil is reserved for oil-specific events (EIA,
API, OPEC, IEA) and for pairs with an established petro-currency link (`USDCAD` on the EIA/API
reports), not included on the theory that "everything correlates with USD strength a little."
CNY events include only `AUDUSD`/`NZDUSD`(+commodities) per the project brief's own guidance,
never the EUR/GBP/JPY pairs. No event was found assigned all 10 instruments — the largest
mapping (9 instruments) is reserved for the broadest top-tier USD/EUR releases, and even those
consistently exclude `USOIL`.

**Audit method:** for every event whose `currency` is EUR/GBP/JPY/AUD/CAD/NZD, verified that
`affected_instruments` includes every FX pair containing that currency as a leg (a minimum
direct-exposure rule); separately checked that no event was assigned all 10 instruments, and
sampled the single-instrument and nine-instrument events for sanity.

### 4.1 Issue found and fixed

**GBP Retail Sales, September 2026 (2026-10-23)** was mapped to `["GBPUSD"]` only — missing
`GBPJPY`, unlike every other GBP-currency event in the dataset (UK Labour Market, GDP Monthly
Estimate, CPI all correctly include both `GBPUSD` and `GBPJPY`) and every JPY-currency event
(which all correctly include `GBPJPY` alongside `USDJPY`). This was a single data-entry
inconsistency, not a systemic mapping-logic error — a scripted check of the minimum
direct-currency-exposure rule across all 74 events found exactly this one violation. **Fixed:**
`GBPJPY` added to that event's `affected_instruments`.

**Remaining uncertainty:** the broader mapping basis (which secondary instruments like
`XAUUSD`/`USOIL` "should" be included for a given event, beyond the direct-currency-exposure
minimum) is a judgment call documented above, not something derivable mechanically or verified
against real correlation data. Whether it is the *right* set of secondary instruments per event
is a research/backtest question (see `docs/STRATEGY_RESEARCH.md` §5), not a code-correctness
one — this audit only verified internal consistency and the absence of obviously wrong mappings.

---

## 5. Duplicate / overlapping events

**Checked:** exact duplicate `(date, country_region, event_name)` entries — **none found**.
Duplicate `event_id` values (which would silently collide as dict keys) — **none found** (74
unique IDs for 74 events).

**Found (expected, not a bug):** genuine **simultaneous events** — multiple distinct releases
scheduled at the exact same UTC minute. Five such clusters exist in the researched calendar, e.g.
`2026-10-29 12:30:00 UTC`: Initial Jobless Claims + GDP (Advance Estimate) + PCE Price Index, all
released together at 08:30 ET as is standard practice for the US government. This is real-world
behavior the engine must handle, not a data error.

---

## 6. Simultaneous-event handling in `SetupTracker`

**Verified:** `app/main.py::run_once` keys trackers by `(event.event_id, symbol)`, and every
event has a unique `event_id` (derived from date+country+name), so two simultaneous events
affecting the same symbol create two independent `SetupTracker` instances that read the same
(shared, read-only during a tracker's `.step()`) `M1Series` without interfering with each other's
state. Added `tests/test_simultaneous_events.py`:
- `test_two_simultaneous_events_same_symbol_produce_independent_signals` — two events with
  identical `event_datetime_utc`, both affecting `EURUSD`, driven through the same M1 series;
  both independently reach `SIGNAL_FIRED` with distinct `opportunity_id`s.
- `test_run_once_creates_independent_trackers_for_simultaneous_events` — proves `run_once`
  itself creates both tracker entries in a single scan iteration.

No changes to `SetupTracker`/`run_once` were required — the `(event_id, symbol)` keying already
supported this correctly.

---

## 7. Signal-generation path — no new gates added

Confirmed: every change in this audit is a **data-correctness or plumbing fix**
(event-minute boundary, calendar field parsing, one instrument-mapping fix, class/tier
metadata, an optional activation filter defaulting to "no restriction"). No new hard
threshold, no new rejection gate, and no existing threshold value in `app/config.py` was
changed. The evidence-scoring architecture in `strategy/impulse.py`, `pullback.py`,
`confirmation.py`, and `trigger.py` is untouched apart from the boundary-slicing fix (§1),
which changes *which bars* are classified as baseline vs. post-event, not how any bar is scored.

---

## 8. Research status

**RESEARCHED ≠ VALIDATED ≠ PROFITABLE.**

- **Researched:** the event calendar (`data/events_sep22_oct31_2026.json`) reflects real
  research effort with cited sources, cross-checks, and now explicit confidence tiers (§2). The
  strategy pipeline (impulse → pullback → M5 structure → M1 trigger → signal) is a researched,
  documented design (`STRATEGY_RESEARCH.md`) grounded in standard market-microstructure
  reasoning, not arbitrary rules.
- **Validated** would mean: run against real historical M1 data and shown to correctly identify
  the hypothesized pattern with known, measured false-positive/false-negative rates. **This has
  not been done.** No historical M1 data exists in this repository (the live endpoint is
  unreachable from this environment, and none was fabricated). `research/backtest.py` is fully
  implemented and tested against synthetic fixtures only (`tests/test_research_backtest.py`),
  which proves the mechanics (no look-ahead, correct trade simulation, correct metrics) but says
  nothing about real market behavior.
- **Profitable** would require validated backtest results showing positive expectancy across a
  meaningful sample. **No such result exists, and none is claimed anywhere in this codebase or
  its documentation.**

Passing the test suite (below) proves the software behaves as designed. It is not evidence of
trading profitability.

---

## Files changed in this audit

- `strategy/signal.py` — event-minute boundary fix (`split_baseline_and_post_event`); Telegram
  message template updated to match the operator's required field labels (unrelated to the
  audit itself but bundled per the same request).
- `market/m1.py` — expanded docstring documenting the OPEN-time assumption and how to verify it.
- `data/calendar.py` — `time_confirmation_tier`/`event_class` fields on `EconomicEvent`
  (conservative defaults for any caller that doesn't specify them); `classes` filter parameter
  threaded through `usable_events`/`events_in_window`/`next_event`/`events_for_symbol`/`active_events`.
- `data/events_sep22_oct31_2026.json` — added `time_confirmation_tier` + `event_class` to all 74
  events; fixed the GBPJPY mapping gap on the Oct 23 GBP Retail Sales event; added a methodology
  addendum. All 74 events preserved.
- `app/config.py` — `EngineConfig.active_event_classes` (default `None` = unrestricted),
  settable via `PSYGRID_ACTIVE_EVENT_CLASSES`.
- `app/main.py` — `run_once` now accepts an optional `now` override (for testability) and
  returns a `RunOnceResult` status summary; `handle_signal` now returns whether a signal was
  newly recorded (vs. a suppressed duplicate); active-event-class filter wired through.
- `run_signal_engine.py` (new) — production live-engine entry point.
- `storage/database.py` — `SignalStore.count_signals_since`.
- Tests: `tests/test_event_minute_boundary.py` (new), `tests/test_simultaneous_events.py` (new),
  `tests/test_run_signal_engine.py` (new), `tests/test_signal_message_format.py` (new), plus one
  added integration test in `tests/test_signal_pipeline.py`.

## Remaining uncertainties (unchanged by this audit, carried forward honestly)

1. Candle OPEN-vs-CLOSE timestamp semantics is an assumption, not a verified fact (§1).
2. No official calendar source was fetched and read directly during research; all
  `official_source_cited` events rest on search-snippet attribution (§2).
3. 15 events remain `pattern_estimate` — their timing could be wrong by hours or even a day.
4. The secondary-instrument portion of `affected_instruments` mappings (beyond direct currency
  exposure) is a documented judgment call, not empirically validated (§4).
5. No real backtest has been run; every threshold in `app/config.py` remains a starting point.
