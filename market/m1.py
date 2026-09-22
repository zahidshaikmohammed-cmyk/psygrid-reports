"""
M1 candle representation and rolling per-symbol M1 series.

CANDLE TIMESTAMP SEMANTICS (audited, see docs/PRECISION_AUDIT.md §1):
`Candle.timestamp` is treated as the candle's OPEN time -- a bar timestamped
12:30:00 is assumed to cover the interval [12:30:00, 12:31:00). This is the
near-universal convention for M1/OHLC feeds (MetaTrader, most broker/vendor
REST APIs) and is the most reasonable reading of the schema example in the
project brief, but it has NOT been empirically verified against the live
PSYGRID endpoint -- that endpoint was not reachable from the environment
this code was built in (direct requests to it time out). If/when the live
endpoint is confirmed reachable, verify this assumption by checking whether
a symbol's `updated_at`/`last_candle_timestamp` lags the newest
`candles_1m[-1].timestamp` by ~1 minute (consistent with open-time: the bar
is still forming when first seen) or is equal to it (consistent with
close-time). Every place in this codebase that treats a bar as "the bar
during which event/instant X occurred" (see
strategy.signal.split_baseline_and_post_event) depends on this assumption
being correct.

The series is the single source of truth for "what did we know as of time T"
-- every read method that takes an `as_of` timestamp returns only candles
with timestamp <= as_of, which is what makes the same code path safe to
reuse for both the live engine and the historical replay/backtest engine
(see research/replay.py) without look-ahead bias.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone


def parse_timestamp(raw: object) -> datetime | None:
    """Best-effort parse of a timestamp field into an aware UTC datetime."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


@dataclass(frozen=True)
class Candle:
    timestamp: datetime  # aware, UTC, represents the candle OPEN time
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    bid: float | None = None
    ask: float | None = None

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


class M1Series:
    """
    Append-only, timestamp-sorted, de-duplicated M1 candle history for a
    single instrument. Safe to feed the same overlapping payload repeatedly
    (as the live poller will) -- candles are merged by timestamp.
    """

    def __init__(self, symbol: str, max_bars: int = 5000):
        self.symbol = symbol
        self._max_bars = max_bars
        self._candles: list[Candle] = []
        self._timestamps: list[datetime] = []

    def __len__(self) -> int:
        return len(self._candles)

    def update(self, candles: list[Candle]) -> int:
        """
        Merge new candles into the series. Existing timestamps are
        overwritten (the latest fetch wins, in case a provider revises the
        most recent still-forming bar). Returns the number of new
        (previously unseen) timestamps added.
        """
        if not candles:
            return 0
        existing = {ts: i for i, ts in enumerate(self._timestamps)}
        added = 0
        for candle in candles:
            if candle.timestamp in existing:
                self._candles[existing[candle.timestamp]] = candle
            else:
                self._candles.append(candle)
                added += 1
        self._candles.sort(key=lambda c: c.timestamp)
        self._timestamps = [c.timestamp for c in self._candles]
        if len(self._candles) > self._max_bars:
            overflow = len(self._candles) - self._max_bars
            self._candles = self._candles[overflow:]
            self._timestamps = self._timestamps[overflow:]
        return added

    def as_of(self, as_of: datetime, lookback: int | None = None) -> list[Candle]:
        """Causal slice: all candles with timestamp <= as_of, oldest first."""
        idx = bisect_right(self._timestamps, as_of)
        window = self._candles[:idx]
        if lookback is not None and lookback >= 0:
            window = window[-lookback:]
        return window

    def latest(self, as_of: datetime) -> Candle | None:
        window = self.as_of(as_of, lookback=1)
        return window[-1] if window else None

    def all(self) -> list[Candle]:
        return list(self._candles)
