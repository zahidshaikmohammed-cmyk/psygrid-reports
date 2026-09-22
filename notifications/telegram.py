"""
Telegram notification sender. Reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
from the environment (via app.config.TelegramConfig) -- never hard-coded.
A failure to send never raises past this module: a notification problem
must not take down the scanning loop.
"""

from __future__ import annotations

import logging

import requests

from app.config import TelegramConfig
from strategy.signal import Signal

logger = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_signal(signal: Signal, config: TelegramConfig, session: requests.Session | None = None) -> bool:
    if not config.enabled:
        logger.info("Telegram not configured (missing bot token/chat id); skipping send for %s", signal.opportunity_id)
        return False

    session = session or requests.Session()
    url = _API_URL.format(token=config.bot_token)
    try:
        response = session.post(
            url,
            json={"chat_id": config.chat_id, "text": signal.format_message()},
            timeout=10,
        )
        if response.status_code != 200:
            logger.error("Telegram send failed (%s): %s", response.status_code, response.text[:500])
            return False
        return True
    except requests.RequestException as exc:
        logger.error("Telegram send raised an exception: %s", exc)
        return False
