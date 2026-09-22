from datetime import datetime, timezone

import requests

from app.config import TelegramConfig
from notifications.telegram import send_signal
from strategy.signal import Signal


def _make_signal():
    return Signal(
        opportunity_id="evt:EURUSD:imp1", symbol="EURUSD", event_id="evt", event_name="Test",
        event_time=datetime(2026, 1, 5, 10, 45, tzinfo=timezone.utc), direction="LONG",
        impulse_strength=0.9, impulse_size=0.003, retracement_fraction=0.35, structure_score=0.8,
        structure_evidence=["ok"], entry=1.1050, stop=1.1030, target=1.1080, setup_quality=75.0,
        expected_holding_minutes=30.0, generated_at=datetime(2026, 1, 5, 10, 52, tzinfo=timezone.utc),
    )


def test_disabled_when_not_configured():
    config = TelegramConfig(bot_token=None, chat_id=None)
    assert send_signal(_make_signal(), config) is False


class _FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class _FakeSession:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise_exc = raise_exc
        self.last_call = None

    def post(self, url, json, timeout):
        self.last_call = (url, json, timeout)
        if self._raise_exc:
            raise self._raise_exc
        return self._response


def test_successful_send():
    config = TelegramConfig(bot_token="TOKEN", chat_id="CHAT")
    session = _FakeSession(response=_FakeResponse(200))
    assert send_signal(_make_signal(), config, session=session) is True
    assert "TOKEN" in session.last_call[0]
    assert session.last_call[1]["chat_id"] == "CHAT"


def test_non_200_response_returns_false():
    config = TelegramConfig(bot_token="TOKEN", chat_id="CHAT")
    session = _FakeSession(response=_FakeResponse(500, "server error"))
    assert send_signal(_make_signal(), config, session=session) is False


def test_network_exception_does_not_raise():
    config = TelegramConfig(bot_token="TOKEN", chat_id="CHAT")
    session = _FakeSession(raise_exc=requests.ConnectionError("boom"))
    assert send_signal(_make_signal(), config, session=session) is False
