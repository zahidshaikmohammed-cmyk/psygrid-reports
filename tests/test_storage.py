from datetime import datetime, timezone

from storage.database import SignalStore
from strategy.signal import Signal


def _make_signal(opportunity_id="evt:EURUSD:imp1"):
    return Signal(
        opportunity_id=opportunity_id,
        symbol="EURUSD",
        event_id="evt",
        event_name="Test Event",
        event_time=datetime(2026, 1, 5, 10, 45, tzinfo=timezone.utc),
        direction="LONG",
        impulse_strength=0.9,
        impulse_size=0.003,
        retracement_fraction=0.35,
        structure_score=0.8,
        structure_evidence=["ok"],
        entry=1.1050,
        stop=1.1030,
        target=1.1080,
        setup_quality=75.0,
        expected_holding_minutes=30.0,
        generated_at=datetime(2026, 1, 5, 10, 52, tzinfo=timezone.utc),
    )


def test_record_signal_prevents_duplicates(tmp_path):
    store = SignalStore(str(tmp_path / "test.db"))
    signal = _make_signal()

    assert store.has_signal(signal.opportunity_id) is False
    inserted_first = store.record_signal(signal, telegram_sent=True)
    assert inserted_first is True
    assert store.has_signal(signal.opportunity_id) is True

    inserted_second = store.record_signal(signal, telegram_sent=True)
    assert inserted_second is False

    all_rows = store.all_signals()
    assert len(all_rows) == 1


def test_different_opportunity_ids_both_stored(tmp_path):
    store = SignalStore(str(tmp_path / "test.db"))
    store.record_signal(_make_signal("evt:EURUSD:imp1"), telegram_sent=False)
    store.record_signal(_make_signal("evt:EURUSD:imp2"), telegram_sent=False)
    assert len(store.all_signals()) == 2


def test_record_outcome_does_not_raise(tmp_path):
    store = SignalStore(str(tmp_path / "test.db"))
    store.record_outcome("evt1", "EURUSD", "pullback_failure", datetime.now(timezone.utc))
