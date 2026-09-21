"""Валидация Telegram WebApp `initData` — единственный способ авторизации Mini App,
без паролей/сессий. Алгоритм — официальный, тот же, что в Universe Anime Planet:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status

from bot.config.settings import get_settings

INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60


def _validate_init_data(init_data: str) -> dict[str, str]:
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed initData") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash in initData")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))

    settings = get_settings()
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid initData signature")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if time.time() - auth_date > INIT_DATA_MAX_AGE_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")

    return pairs


async def get_current_user_id(x_telegram_init_data: str = Header(alias="X-Telegram-Init-Data")) -> int:
    pairs = _validate_init_data(x_telegram_init_data)
    user_raw = pairs.get("user")
    if not user_raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing user in initData")

    try:
        user = json.loads(user_raw)
        return int(user["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed user in initData") from exc
