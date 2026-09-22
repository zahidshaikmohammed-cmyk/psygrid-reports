from datetime import timedelta

from app.config import EngineConfig
from data.calendar import EventCalendar
from market.m1 import M1Series
from research.backtest import run_backtest, simulate_trade
from research.metrics import summarize, by_instrument
from tests.test_signal_pipeline import _build_long_scenario


def test_backtest_and_metrics_end_to_end():
    config = EngineConfig()
    event, all_bars = _build_long_scenario()

    # give the trade simulator room to run forward after the signal fires
    extra = [
        __import__("tests.factories", fromlist=["c"]).c(
            all_bars[-1].timestamp + timedelta(minutes=i + 1),
            all_bars[-1].close, all_bars[-1].close + 0.0005,
            all_bars[-1].close - 0.0002, all_bars[-1].close + 0.0003,
        )
        for i in range(35)
    ]
    series = M1Series("EURUSD")
    series.update(all_bars + extra)
    m1_history = {"EURUSD": series}

    calendar = EventCalendar(events=[event], metadata={})
    report = run_backtest(m1_history, calendar, config, step_minutes=1.0)

    assert len(report.replay.signals) == 1
    assert len(report.trades) == 1

    summary = summarize(report)
    assert summary.n_signals == 1
    assert summary.n_trades == 1
    assert summary.win_rate is not None

    per_symbol = by_instrument(report)
    assert "EURUSD" in per_symbol


def test_simulate_trade_hits_target():
    from strategy.signal import Signal
    from datetime import datetime, timezone

    signal = Signal(
        opportunity_id="x", symbol="EURUSD", event_id="e", event_name="n",
        event_time=datetime(2026, 1, 1, tzinfo=timezone.utc), direction="LONG",
        impulse_strength=0.8, impulse_size=0.003, retracement_fraction=0.3, structure_score=0.7,
        structure_evidence=[], entry=1.1000, stop=1.0980, target=1.1030, setup_quality=70.0,
        expected_holding_minutes=30.0, generated_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    from tests.factories import c as make_candle
    bars = [
        make_candle(datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc), 1.1000, 1.1010, 1.0995, 1.1005),
        make_candle(datetime(2026, 1, 1, 10, 2, tzinfo=timezone.utc), 1.1005, 1.1035, 1.1000, 1.1032),
    ]
    series = M1Series("EURUSD")
    series.update(bars)
    trade = simulate_trade(signal, series, EngineConfig())
    assert trade is not None
    assert trade.exit_reason == "target"
    assert trade.r_multiple > 0


def test_simulate_trade_hits_stop():
    from strategy.signal import Signal
    from datetime import datetime, timezone

    signal = Signal(
        opportunity_id="x", symbol="EURUSD", event_id="e", event_name="n",
        event_time=datetime(2026, 1, 1, tzinfo=timezone.utc), direction="LONG",
        impulse_strength=0.8, impulse_size=0.003, retracement_fraction=0.3, structure_score=0.7,
        structure_evidence=[], entry=1.1000, stop=1.0980, target=1.1030, setup_quality=70.0,
        expected_holding_minutes=30.0, generated_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    from tests.factories import c as make_candle
    bars = [make_candle(datetime(2026, 1, 1, 10, 1, tzinfo=timezone.utc), 1.1000, 1.1005, 1.0970, 1.0975)]
    series = M1Series("EURUSD")
    series.update(bars)
    trade = simulate_trade(signal, series, EngineConfig())
    assert trade is not None
    assert trade.exit_reason == "stop"
    assert trade.r_multiple < 0
