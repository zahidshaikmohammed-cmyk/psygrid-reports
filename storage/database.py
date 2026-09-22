"""
SQLite-backed storage for emitted signals and sent-alert state.

Its main job is duplicate prevention (req #22): once a signal for a given
opportunity_id has been recorded/sent, it must never be sent again, even if
the live engine restarts.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from strategy.signal import Signal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    opportunity_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    setup_quality REAL NOT NULL,
    generated_at TEXT NOT NULL,
    telegram_sent INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS setup_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    outcome_type TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""


class SignalStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def has_signal(self, opportunity_id: str) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM signals WHERE opportunity_id = ?", (opportunity_id,)
            ).fetchone()
            return row is not None

    def record_signal(self, signal: Signal, telegram_sent: bool) -> bool:
        """Insert the signal if new. Returns True if newly inserted, False if it already existed."""
        payload = asdict(signal)
        payload["event_time"] = signal.event_time.isoformat()
        payload["generated_at"] = signal.generated_at.isoformat()
        with closing(self._connect()) as conn:
            try:
                conn.execute(
                    "INSERT INTO signals "
                    "(opportunity_id, symbol, event_id, event_name, direction, setup_quality, "
                    "generated_at, telegram_sent, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        signal.opportunity_id,
                        signal.symbol,
                        signal.event_id,
                        signal.event_name,
                        signal.direction,
                        signal.setup_quality,
                        signal.generated_at.isoformat(),
                        int(telegram_sent),
                        json.dumps(payload),
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def mark_telegram_sent(self, opportunity_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE signals SET telegram_sent = 1 WHERE opportunity_id = ?", (opportunity_id,)
            )
            conn.commit()

    def record_outcome(self, event_id: str, symbol: str, outcome_type: str, recorded_at: datetime) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO setup_outcomes (event_id, symbol, outcome_type, recorded_at) VALUES (?, ?, ?, ?)",
                (event_id, symbol, outcome_type, recorded_at.isoformat()),
            )
            conn.commit()

    def count_signals_since(self, since: datetime) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE generated_at >= ?", (since.isoformat(),)
            ).fetchone()
            return row[0] if row else 0

    def all_signals(self) -> list[dict]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM signals ORDER BY generated_at").fetchall()
            return [dict(r) for r in rows]
