"""Минимальный клиент API ЮKassa v3 — только то, что нужно для СБП: создать платёж и
прочитать его статус. На aiohttp (уже есть в зависимостях через aiogram), без SDK `yookassa`
— у того синхронный requests, блокировал бы event loop (правило 5)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

import aiohttp

from bot.config.settings import get_settings

log = logging.getLogger(__name__)

API_URL = "https://api.yookassa.ru/v3/payments"
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class YooKassaError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class YkPayment:
    id: str
    status: str  # pending / waiting_for_capture / succeeded / canceled
    paid: bool
    amount_rub: Decimal
    confirmation_url: str | None
    metadata: dict


def _auth() -> aiohttp.BasicAuth:
    s = get_settings()
    return aiohttp.BasicAuth(s.yookassa_shop_id, s.yookassa_secret_key)


def _parse(data: dict) -> YkPayment:
    return YkPayment(
        id=data["id"],
        status=data["status"],
        paid=bool(data.get("paid")),
        amount_rub=Decimal(data["amount"]["value"]),
        confirmation_url=(data.get("confirmation") or {}).get("confirmation_url"),
        metadata=data.get("metadata") or {},
    )


async def _request(method: str, url: str, **kwargs) -> dict:
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT, auth=_auth()) as http:
            async with http.request(method, url, **kwargs) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    log.error("YooKassa %s %s -> %s %s", method, url, resp.status, data)
                    raise YooKassaError(str((data or {}).get("description") or resp.status))
                return data
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise YooKassaError(str(exc)) from exc


async def create_payment(amount_rub: int, description: str, return_url: str, metadata: dict) -> YkPayment:
    """Платёж сразу методом СБП (`payment_method_data.type=sbp`), подтверждение — redirect:
    ссылка открывает страницу выбора банка / QR-код. `capture=True` — без двухстадийки."""
    body = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "payment_method_data": {"type": "sbp"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description[:128],
        "metadata": metadata,
    }
    data = await _request("POST", API_URL, json=body, headers={"Idempotence-Key": str(uuid.uuid4())})
    return _parse(data)


async def get_payment(payment_id: str) -> YkPayment:
    return _parse(await _request("GET", f"{API_URL}/{payment_id}"))
