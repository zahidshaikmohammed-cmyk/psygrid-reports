"""
Append-only raw capture of live endpoint polls, so historical M1 data
accumulates over time for future backtesting (research.backtest reads this
format back in via load_m1_history_from_captures). One JSON line per poll;
files are split by UTC date so they stay small and easy to ship around.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_capture(payload: dict[str, Any], capture_dir: str, fetched_at: datetime | None = None) -> Path:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    out_dir = Path(capture_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{fetched_at.strftime('%Y-%m-%d')}.jsonl"
    record = {"fetched_at": fetched_at.isoformat(), "payload": payload}
    with open(file_path, "a") as fh:
        fh.write(json.dumps(record) + "\n")
    return file_path
