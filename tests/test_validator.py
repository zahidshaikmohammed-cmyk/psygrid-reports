from datetime import datetime, timedelta, timezone

from app.config import DataConfig
from data.validator import DataQuality, validate_payload

INSTRUMENTS = ("XAUUSD", "EURUSD")
NOW = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)


def _candle(ts, o=1.1, h=1.11, l=1.09, cl=1.10, v=100.0):
    return {"timestamp": ts, "open": o, "high": h, "low": l, "close": cl, "volume": v}


def test_fresh_symbol_parses_correctly():
    payload = {
        "status": "ok",
        "symbols": {
            "EURUSD": {
                "market_state": "open",
                "status": "ok",
                "m1_valid": True,
                "last_candle_timestamp": NOW.isoformat(),
                "candles_1m": [_candle((NOW - timedelta(minutes=i)).isoformat()) for i in range(40)],
            }
        },
    }
    result = validate_payload(payload, DataConfig(), INSTRUMENTS, now=NOW)
    eurusd = result.symbols["EURUSD"]
    assert eurusd.quality == DataQuality.FRESH
    assert len(eurusd.candles) == 40


def test_missing_symbol_reported_as_missing():
    payload = {"status": "ok", "symbols": {}}
    result = validate_payload(payload, DataConfig(), INSTRUMENTS, now=NOW)
    assert result.symbols["XAUUSD"].quality == DataQuality.MISSING
    assert result.symbols["EURUSD"].quality == DataQuality.MISSING


def test_stale_data_detected():
    old_ts = NOW - timedelta(minutes=30)
    payload = {
        "symbols": {
            "EURUSD": {
                "m1_valid": True,
                "last_candle_timestamp": old_ts.isoformat(),
                "candles_1m": [_candle((old_ts - timedelta(minutes=i)).isoformat()) for i in range(40)],
            }
        }
    }
    result = validate_payload(payload, DataConfig(stale_after_seconds=180), INSTRUMENTS, now=NOW)
    assert result.symbols["EURUSD"].quality == DataQuality.STALE


def test_partial_when_below_min_bars():
    payload = {
        "symbols": {
            "EURUSD": {
                "m1_valid": True,
                "last_candle_timestamp": NOW.isoformat(),
                "candles_1m": [_candle(NOW.isoformat())],
            }
        }
    }
    result = validate_payload(payload, DataConfig(min_m1_bars_for_calc=30), INSTRUMENTS, now=NOW)
    assert result.symbols["EURUSD"].quality == DataQuality.PARTIAL


def test_malformed_candles_are_skipped_not_crashing():
    payload = {
        "symbols": {
            "EURUSD": {
                "m1_valid": True,
                "last_candle_timestamp": NOW.isoformat(),
                "candles_1m": [
                    {"timestamp": NOW.isoformat(), "open": "not-a-number", "high": 1, "low": 1, "close": 1},
                    {"timestamp": "garbage"},
                    "not-even-a-dict",
                    _candle(NOW.isoformat()),
                ],
            }
        }
    }
    result = validate_payload(payload, DataConfig(), INSTRUMENTS, now=NOW)
    eurusd = result.symbols["EURUSD"]
    assert len(eurusd.candles) == 1
    assert len(eurusd.issues) >= 3


def test_invalid_when_provider_flags_m1_invalid():
    payload = {
        "symbols": {
            "EURUSD": {
                "m1_valid": False,
                "candles_1m": [_candle(NOW.isoformat())],
            }
        }
    }
    result = validate_payload(payload, DataConfig(), INSTRUMENTS, now=NOW)
    assert result.symbols["EURUSD"].quality == DataQuality.INVALID


def test_completely_malformed_top_level_payload_does_not_crash():
    result = validate_payload("not a dict at all", DataConfig(), INSTRUMENTS, now=NOW)  # type: ignore[arg-type]
    assert result.top_level_issues
    assert all(s.quality == DataQuality.MISSING for s in result.symbols.values())


def test_bid_ask_optional_and_nullable():
    payload = {
        "symbols": {
            "EURUSD": {
                "m1_valid": True,
                "last_candle_timestamp": NOW.isoformat(),
                "candles_1m": [
                    {"timestamp": NOW.isoformat(), "open": 1.1, "high": 1.11, "low": 1.09,
                     "close": 1.10, "volume": 10.0, "bid": None, "ask": None}
                ],
            }
        }
    }
    result = validate_payload(payload, DataConfig(min_m1_bars_for_calc=1), INSTRUMENTS, now=NOW)
    candle = result.symbols["EURUSD"].candles[0]
    assert candle.bid is None and candle.ask is None
