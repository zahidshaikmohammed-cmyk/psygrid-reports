"""
Trade simulation and end-to-end backtest orchestration.

IMPORTANT — data availability: this repo ships NO historical intraday M1
data for these instruments, and fabricating any would violate the "do not
invent data" requirement. Real backtesting only becomes possible once the
live engine (app/main.py) has been run for a while against the actual
endpoint, using data.capture to persist raw polls to data/captures/*.jsonl.
`load_m1_history_from_captures` below reads exactly that format. Until
such a capture exists, research/backtest.py can only be exercised against
synthetic fixtures (see tests/), which prove the mechanics are correct but
say nothing about real market behaviour -- see docs/STRATEGY_RESEARCH.md.
"""

from __future__ import annotations

import glob
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.config import EngineConfig
from data.calendar import EventCalendar
from data.validator import validate_payload
from market.m1 import M1Series
from research.replay import ReplayResult, run_replay
from strategy.signal import Signal

logger = logging.getLogger(__name__)

ExitReason = Literal["target", "stop", "time"]


@dataclass(frozen=True)
class SimulatedTrade:
    opportunity_id: str
    symbol: str
    event_id: str
    direction: str
    entry_time: datetime
    entry_price: float
    stop: float
    target: float
    exit_time: datetime
    exit_price: float
    exit_reason: ExitReason
    r_multiple: float
    mfe_r: float
    mae_r: float
    minutes_to_exit: float


def load_m1_history_from_captures(capture_dir: str, instruments: tuple[str, ...], data_config) -> dict[str, M1Series]:
    """Rebuild per-symbol M1Series from captured raw live.json polls."""
    series_by_symbol = {s: M1Series(s) for s in instruments}
    files = sorted(glob.glob(f"{capture_dir.rstrip('/')}/*.jsonl"))
    if not files:
        logger.warning("no capture files found under %s", capture_dir)
        return series_by_symbol

    for path in files:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload", record)
                validated = validate_payload(payload, data_config, instruments)
                for symbol, parsed in validated.symbols.items():
                    if parsed.candles:
                        series_by_symbol[symbol].update(parsed.candles)
    return series_by_symbol


def simulate_trade(signal: Signal, m1_series: M1Series, config: EngineConfig) -> SimulatedTrade | None:
    """
    Simulate trade management forward from the signal's generation time.
    Uses bars strictly after signal.generated_at -- this is the one place
    in the codebase permitted to look at "future" bars relative to a
    signal, because it is scoring an already-generated signal's outcome,
    not generating a new one.
    """
    risk = abs(signal.entry - signal.stop)
    if risk <= 0:
        return None

    all_bars = m1_series.all()
    bars_after = [c for c in all_bars if c.timestamp > signal.generated_at]
    if not bars_after:
        return None

    max_end = signal.generated_at + timedelta(minutes=config.windows.max_holding_minutes)
    is_long = signal.direction == "LONG"

    mfe_r = 0.0
    mae_r = 0.0
    exit_reason: ExitReason | None = None
    exit_price: float | None = None
    exit_time: datetime | None = None
    last_seen = None

    for bar in bars_after:
        if bar.timestamp > max_end:
            break
        last_seen = bar

        if is_long:
            r_high = (bar.high - signal.entry) / risk
            r_low = (bar.low - signal.entry) / risk
        else:
            r_high = (signal.entry - bar.low) / risk
            r_low = (signal.entry - bar.high) / risk
        mfe_r = max(mfe_r, r_high)
        mae_r = min(mae_r, r_low)

        hit_stop = (bar.low <= signal.stop) if is_long else (bar.high >= signal.stop)
        hit_target = (bar.high >= signal.target) if is_long else (bar.low <= signal.target)

        if hit_stop:
            # Conservative convention: if both stop and target fall inside the
            # same bar's range, assume the adverse outcome (stop) triggered first.
            exit_reason, exit_price, exit_time = "stop", signal.stop, bar.timestamp
            break
        if hit_target:
            exit_reason, exit_price, exit_time = "target", signal.target, bar.timestamp
            break

    if exit_reason is None:
        reference_bar = last_seen or bars_after[0]
        exit_reason, exit_price, exit_time = "time", reference_bar.close, reference_bar.timestamp

    r_multiple = (exit_price - signal.entry) / risk if is_long else (signal.entry - exit_price) / risk
    minutes_to_exit = (exit_time - signal.generated_at).total_seconds() / 60.0

    return SimulatedTrade(
        opportunity_id=signal.opportunity_id,
        symbol=signal.symbol,
        event_id=signal.event_id,
        direction=signal.direction,
        entry_time=signal.generated_at,
        entry_price=signal.entry,
        stop=signal.stop,
        target=signal.target,
        exit_time=exit_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        r_multiple=r_multiple,
        mfe_r=mfe_r,
        mae_r=mae_r,
        minutes_to_exit=minutes_to_exit,
    )


@dataclass
class BacktestReport:
    replay: ReplayResult
    trades: list[SimulatedTrade]


def run_backtest(
    m1_history: dict[str, M1Series],
    calendar: EventCalendar,
    config: EngineConfig,
    step_minutes: float = 1.0,
) -> BacktestReport:
    replay_result = run_replay(m1_history, calendar, config, step_minutes=step_minutes)
    trades: list[SimulatedTrade] = []
    for sig in replay_result.signals:
        series = m1_history.get(sig.symbol)
        if series is None:
            continue
        trade = simulate_trade(sig, series, config)
        if trade is not None:
            trades.append(trade)
    return BacktestReport(replay=replay_result, trades=trades)
