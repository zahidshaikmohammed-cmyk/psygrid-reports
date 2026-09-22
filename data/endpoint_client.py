"""
HTTP client for the PsyGrid live market-data endpoint.

The endpoint is reachable from the environment that actually runs this
engine (per the project brief), not necessarily from every development
sandbox. This client makes no assumption about the JSON beyond "it is
JSON" -- structural validation of the payload happens in data/validator.py,
deliberately kept separate so a schema surprise degrades a calculation
rather than crashing the fetch layer.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from app.config import DataConfig

logger = logging.getLogger(__name__)


class EndpointError(Exception):
    """Base class for endpoint-client failures."""


class EndpointUnreachable(EndpointError):
    """Network-level failure (timeout, connection refused, DNS, etc.)."""


class EndpointBadResponse(EndpointError):
    """Endpoint responded but with a non-2xx status or non-JSON body."""


@dataclass
class FetchResult:
    ok: bool
    payload: dict[str, Any] | None
    error: str | None
    fetched_at_epoch: float
    attempts: int


class LiveEndpointClient:
    """Thin, retrying HTTP client around the m1-live.json endpoint."""

    def __init__(self, config: DataConfig, session: requests.Session | None = None):
        self._config = config
        self._session = session or requests.Session()

    def fetch(self) -> FetchResult:
        """
        Fetch the live payload with retry/backoff. Never raises -- callers
        get a FetchResult so a single bad poll cannot crash a scanning loop
        (see project requirement: data failures must degrade, not crash).
        """
        last_error: str | None = None
        attempts = 0
        for attempt in range(1, self._config.max_retries + 1):
            attempts = attempt
            try:
                response = self._session.get(
                    self._config.endpoint_url,
                    timeout=self._config.request_timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = f"network error on attempt {attempt}: {exc}"
                logger.warning(last_error)
            else:
                if response.status_code != 200:
                    last_error = (
                        f"non-200 status on attempt {attempt}: {response.status_code}"
                    )
                    logger.warning(last_error)
                else:
                    try:
                        payload = response.json()
                    except (json.JSONDecodeError, ValueError) as exc:
                        last_error = f"invalid JSON on attempt {attempt}: {exc}"
                        logger.warning(last_error)
                    else:
                        return FetchResult(
                            ok=True,
                            payload=payload,
                            error=None,
                            fetched_at_epoch=time.time(),
                            attempts=attempt,
                        )

            if attempt < self._config.max_retries:
                backoff = self._config.retry_backoff_base_seconds * (2 ** (attempt - 1))
                time.sleep(backoff)

        logger.error("live endpoint fetch failed after %s attempts: %s", attempts, last_error)
        return FetchResult(
            ok=False,
            payload=None,
            error=last_error,
            fetched_at_epoch=time.time(),
            attempts=attempts,
        )
