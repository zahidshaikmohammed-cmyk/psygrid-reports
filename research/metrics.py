"""
Aggregate metrics over a BacktestReport: the numbers that actually answer
the research hypothesis (does report->impulse->pullback->M5->M1 recur, how
often, and is it profitable) rather than just asserting it does.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from research.backtest import BacktestReport, SimulatedTrade
from research.replay import TrackerRecord

_INVALIDATING_OUTCOMES = {"pullback_continuation", "pullback_failure", "pullback_reversal", "pullback_whipsaw"}
_EXPIRY_OUTCOMES = {"no_impulse", "pullback_inconclusive", "structure_not_confirmed", "trigger_expired", "setup_expiry_deadline"}


@dataclass
class MetricsSummary:
    n_trackers: int = 0
    n_impulses: int = 0          # trackers that got at least past WATCHING_IMPULSE
    n_pullbacks_valid: int = 0   # trackers that reached a healthy/deep pullback
    n_structure_confirmed: int = 0
    n_signals: int = 0
    n_trades: int = 0

    win_rate: float | None = None
    avg_r: float | None = None
    expectancy: float | None = None
    avg_mfe_r: float | None = None
    avg_mae_r: float | None = None
    avg_minutes_to_exit: float | None = None

    continuation_rate: float | None = None   # impulse continued with no real pullback
    reversal_rate: float | None = None
    failed_setup_rate: float | None = None   # any invalidation/expiry before a signal fired
    whipsaw_rate: float | None = None

    outcome_counts: dict[str, int] = field(default_factory=dict)


def _rate(numerator: int, denominator: int) -> float | None:
    return (numerator / denominator) if denominator else None


def summarize(report: BacktestReport) -> MetricsSummary:
    records = report.replay.tracker_records
    trades = report.trades
    n = len(records)

    outcome_counts: dict[str, int] = defaultdict(int)
    n_impulse_stage = 0
    n_pullback_valid = 0
    n_structure_confirmed = 0
    n_continuation = 0
    n_reversal = 0
    n_whipsaw = 0
    n_failed = 0

    for rec in records:
        outcome_counts[rec.outcome_type] += 1
        if rec.final_state != "watching_impulse" or rec.outcome_type != "no_impulse":
            n_impulse_stage += 1
        if rec.outcome_type in {"signal"} or rec.final_state in {
            "watching_structure", "watching_trigger", "signal_fired"
        }:
            n_pullback_valid += 1
        if rec.final_state in {"watching_trigger", "signal_fired"}:
            n_structure_confirmed += 1
        if rec.outcome_type == "pullback_continuation":
            n_continuation += 1
        if rec.outcome_type == "pullback_reversal":
            n_reversal += 1
        if rec.outcome_type == "pullback_whipsaw":
            n_whipsaw += 1
        if rec.outcome_type in _INVALIDATING_OUTCOMES or rec.outcome_type in _EXPIRY_OUTCOMES:
            n_failed += 1

    summary = MetricsSummary(
        n_trackers=n,
        n_impulses=n_impulse_stage,
        n_pullbacks_valid=n_pullback_valid,
        n_structure_confirmed=n_structure_confirmed,
        n_signals=len(report.replay.signals),
        n_trades=len(trades),
        continuation_rate=_rate(n_continuation, n),
        reversal_rate=_rate(n_reversal, n),
        whipsaw_rate=_rate(n_whipsaw, n),
        failed_setup_rate=_rate(n_failed, n),
        outcome_counts=dict(outcome_counts),
    )

    if trades:
        r_values = [t.r_multiple for t in trades]
        wins = [t for t in trades if t.r_multiple > 0]
        summary.win_rate = len(wins) / len(trades)
        summary.avg_r = statistics.mean(r_values)
        summary.expectancy = summary.avg_r  # equivalent formulation given r_multiple already nets loss/win
        summary.avg_mfe_r = statistics.mean(t.mfe_r for t in trades)
        summary.avg_mae_r = statistics.mean(t.mae_r for t in trades)
        summary.avg_minutes_to_exit = statistics.mean(t.minutes_to_exit for t in trades)

    return summary


def _group(records: list[TrackerRecord], key_fn) -> dict:
    groups: dict = defaultdict(list)
    for r in records:
        groups[key_fn(r)].append(r)
    return groups


def by_instrument(report: BacktestReport) -> dict[str, MetricsSummary]:
    return _summarize_grouped(report, lambda rec: rec.symbol)


def by_event(report: BacktestReport) -> dict[str, MetricsSummary]:
    return _summarize_grouped(report, lambda rec: rec.event.event_name)


def by_instrument_and_event(report: BacktestReport) -> dict[tuple[str, str], MetricsSummary]:
    return _summarize_grouped(report, lambda rec: (rec.symbol, rec.event.event_name))


def _summarize_grouped(report: BacktestReport, key_fn) -> dict:
    grouped_records = _group(report.replay.tracker_records, key_fn)
    trades_by_opp = {t.opportunity_id: t for t in report.trades}
    signals_by_opp = {s.opportunity_id: s for s in report.replay.signals}

    result = {}
    for key, records in grouped_records.items():
        sub_signals = [
            rec.signal for rec in records if rec.signal is not None and rec.signal.opportunity_id in signals_by_opp
        ]
        sub_trades = [
            trades_by_opp[s.opportunity_id] for s in sub_signals if s.opportunity_id in trades_by_opp
        ]
        from research.replay import ReplayResult  # local import to avoid cycle at module load
        from research.backtest import BacktestReport as _BR

        fake_replay = ReplayResult(signals=sub_signals, tracker_records=records)
        fake_report = _BR(replay=fake_replay, trades=sub_trades)
        result[key] = summarize(fake_report)
    return result
