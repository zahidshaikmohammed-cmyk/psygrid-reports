"""
Schema/data-quality validation for the live endpoint payload.

This module owns ONE concern: is the data we received usable, and to what
degree? It deliberately does not make any trading decision -- that split
(data quality vs. strategy logic) is a project requirement so the strategy
layer never has to know *why* a bar is missing, only that it is.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.config import DataConfig
from market.m1 import Candle, parse_timestamp

logger = logging.getLogger(__name__)


class DataQuality(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass
class SymbolParseResult:
    symbol: str
    quality: DataQuality
    candles: list[Candle] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    market_state: str | None = None
    status: str | None = None
    m1_valid: bool | None = None
    last_candle_timestamp: datetime | None = None
    updated_at: datetime | None = None
    websocket_connected: bool | None = None


@dataclass
class PayloadValidationResult:
    schema_version: str | None
    service: str | None
    provider: str | None
    timeframe: str | None
    generated_at: datetime | None
    status: str | None
    universe_size: int | None
    symbols: dict[str, SymbolParseResult]
    top_level_issues: list[str] = field(default_factory=list)


_REQUIRED_CANDLE_FIELDS = ("timestamp", "open", "high", "low", "close")


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_candle(raw: Any) -> tuple[Candle | None, str | None]:
    if not isinstance(raw, dict):
        return None, f"candle entry is not an object: {raw!r}"

    ts = parse_timestamp(raw.get("timestamp"))
    if ts is None:
        return None, f"candle missing/invalid timestamp: {raw.get('timestamp')!r}"

    values = {}
    for f in ("open", "high", "low", "close"):
        v = _coerce_float(raw.get(f))
        if v is None:
            return None, f"candle at {ts.isoformat()} missing/invalid field '{f}'"
        values[f] = v

    volume = _coerce_float(raw.get("volume"))
    bid = _coerce_float(raw.get("bid"))
    ask = _coerce_float(raw.get("ask"))

    if values["high"] < values["low"]:
        return None, f"candle at {ts.isoformat()} has high < low (corrupt bar)"

    return (
        Candle(
            timestamp=ts,
            open=values["open"],
            high=values["high"],
            low=values["low"],
            close=values["close"],
            volume=volume,
            bid=bid,
            ask=ask,
        ),
        None,
    )


def _parse_symbol_block(symbol: str, raw: Any, config: DataConfig, now: datetime) -> SymbolParseResult:
    if not isinstance(raw, dict):
        return SymbolParseResult(
            symbol=symbol,
            quality=DataQuality.INVALID,
            issues=[f"symbol block for {symbol} is not an object"],
        )

    issues: list[str] = []

    raw_candles = raw.get("candles_1m")
    if raw_candles is None:
        issues.append("missing 'candles_1m' field")
        raw_candles = []
    if not isinstance(raw_candles, list):
        issues.append("'candles_1m' is not a list")
        raw_candles = []

    candles: list[Candle] = []
    for entry in raw_candles:
        candle, err = _parse_candle(entry)
        if candle is not None:
            candles.append(candle)
        else:
            issues.append(err or "unknown candle parse error")

    candles.sort(key=lambda c: c.timestamp)

    last_ts = parse_timestamp(raw.get("last_candle_timestamp"))
    if last_ts is None and candles:
        last_ts = candles[-1].timestamp
    updated_at = parse_timestamp(raw.get("updated_at"))

    m1_valid = raw.get("m1_valid")
    if m1_valid is not None and not isinstance(m1_valid, bool):
        issues.append(f"'m1_valid' is not boolean: {m1_valid!r}")
        m1_valid = None

    market_state = raw.get("market_state") if isinstance(raw.get("market_state"), str) else None
    status = raw.get("status") if isinstance(raw.get("status"), str) else None
    websocket_connected = raw.get("websocket_connected")
    if not isinstance(websocket_connected, bool):
        websocket_connected = None

    # -- Determine overall quality --
    if not candles:
        quality = DataQuality.MISSING
        issues.append("no usable candles after parsing")
    else:
        freshness_reference = last_ts or updated_at
        is_stale = False
        if freshness_reference is not None:
            age = (now - freshness_reference).total_seconds()
            if age > config.stale_after_seconds:
                is_stale = True
                issues.append(
                    f"last known candle/update is {age:.0f}s old "
                    f"(> stale_after_seconds={config.stale_after_seconds})"
                )
        else:
            issues.append("no timestamp available to assess freshness")

        insufficient = len(candles) < config.min_m1_bars_for_calc
        had_parse_errors = any("candle" in i for i in issues if "missing" in i or "invalid" in i or "corrupt" in i)

        if m1_valid is False:
            quality = DataQuality.INVALID
            issues.append("provider reported m1_valid=false")
        elif is_stale:
            quality = DataQuality.STALE
        elif insufficient or had_parse_errors:
            quality = DataQuality.PARTIAL
            if insufficient:
                issues.append(
                    f"only {len(candles)} bars available "
                    f"(< min_m1_bars_for_calc={config.min_m1_bars_for_calc})"
                )
        else:
            quality = DataQuality.FRESH

    return SymbolParseResult(
        symbol=symbol,
        quality=quality,
        candles=candles,
        issues=issues,
        market_state=market_state,
        status=status,
        m1_valid=m1_valid,
        last_candle_timestamp=last_ts,
        updated_at=updated_at,
        websocket_connected=websocket_connected,
    )


def validate_payload(
    payload: dict[str, Any],
    config: DataConfig,
    instruments: tuple[str, ...],
    now: datetime | None = None,
) -> PayloadValidationResult:
    """
    Validate and parse a raw live.json payload. Never raises: any structural
    surprise becomes an entry in top_level_issues or a per-symbol issue, so
    a scanning loop can keep running on whatever subset of instruments is
    actually usable.
    """
    now = now or datetime.now(timezone.utc)
    top_level_issues: list[str] = []

    if not isinstance(payload, dict):
        top_level_issues.append("payload root is not a JSON object")
        payload = {}

    generated_at = parse_timestamp(payload.get("generated_at"))
    symbols_raw = payload.get("symbols")
    if symbols_raw is None:
        top_level_issues.append("payload missing 'symbols' object")
        symbols_raw = {}
    if not isinstance(symbols_raw, dict):
        top_level_issues.append("'symbols' is not an object")
        symbols_raw = {}

    results: dict[str, SymbolParseResult] = {}
    for symbol in instruments:
        if symbol not in symbols_raw:
            results[symbol] = SymbolParseResult(
                symbol=symbol,
                quality=DataQuality.MISSING,
                issues=[f"'{symbol}' not present in payload symbols"],
            )
            logger.debug("symbol %s missing from payload", symbol)
            continue
        results[symbol] = _parse_symbol_block(symbol, symbols_raw[symbol], config, now)

    extra_symbols = set(symbols_raw.keys()) - set(instruments)
    if extra_symbols:
        logger.debug("payload contained %d symbols outside configured universe: %s",
                     len(extra_symbols), sorted(extra_symbols))

    return PayloadValidationResult(
        schema_version=payload.get("schema_version"),
        service=payload.get("service"),
        provider=payload.get("provider"),
        timeframe=payload.get("timeframe"),
        generated_at=generated_at,
        status=payload.get("status") if isinstance(payload.get("status"), str) else None,
        universe_size=payload.get("universe_size") if isinstance(payload.get("universe_size"), int) else None,
        symbols=results,
        top_level_issues=top_level_issues,
    )
