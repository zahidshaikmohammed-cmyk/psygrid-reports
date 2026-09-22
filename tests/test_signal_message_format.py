from datetime import datetime, timezone

from strategy.signal import Signal

REQUIRED_LABELS = [
    "PSYGRID SIGNAL",
    "Instrument:",
    "Event:",
    "Event time:",
    "Direction:",
    "Impulse:",
    "Pullback:",
    "M5 structure:",
    "M1 trigger:",
    "Entry:",
    "Stop:",
    "Target:",
    "Setup quality:",
    "Expected holding window:",
    "Opportunity ID:",
]


def _make_signal():
    return Signal(
        opportunity_id="evt:EURUSD:imp1", symbol="EURUSD", event_id="evt", event_name="US CPI",
        event_time=datetime(2026, 9, 24, 18, 0, tzinfo=timezone.utc), direction="LONG",
        impulse_strength=0.87, impulse_size=0.003, retracement_fraction=0.32, structure_score=0.75,
        structure_evidence=["ok"], entry=1.1050, stop=1.1030, target=1.1080, setup_quality=78.0,
        expected_holding_minutes=30.0, generated_at=datetime(2026, 9, 24, 18, 7, tzinfo=timezone.utc),
    )


def test_message_contains_every_required_field_label():
    message = _make_signal().format_message()
    for label in REQUIRED_LABELS:
        assert label in message, f"missing required label: {label!r}"


def test_message_includes_opportunity_id_value():
    signal = _make_signal()
    message = signal.format_message()
    assert signal.opportunity_id in message
