"""Донат (константы): виды покупок чёрного рынка, callback'и, локи."""
from __future__ import annotations

KIND_GENIUS = "genius"
KIND_PATH = "path"
KIND_TECHNIQUE = "tech"
DONATE_KINDS = (KIND_GENIUS, KIND_PATH, KIND_TECHNIQUE)

LOCK_ACTION_DONATE = "donate"
PAYLOAD_DONATE_PREFIX = "donate:"  # payload инвойса: donate:<рубли>

CB_DONATE_OPEN = "dn:open"
CB_DONATE_PRESET_PREFIX = "dn:pay:"  # dn:pay:<рубли>
CB_DONATE_CUSTOM = "dn:custom"
# Выбор способа оплаты после суммы (2026-10-30): карта (форма Telegram) или СБП.
CB_DONATE_CARD_PREFIX = "dn:card:"  # dn:card:<рубли>
CB_DONATE_SBP_PREFIX = "dn:sbp:"  # dn:sbp:<рубли>
CB_DONATE_SBP_CHECK_PREFIX = "dn:chk:"  # dn:chk:<id строки sbp_payments>
LOCK_ACTION_DONATE_SBP = "donate_sbp"
# Статусы счёта СБП (`sbp_payments.status`).
SBP_STATUS_PENDING = "pending"
SBP_STATUS_SUCCEEDED = "succeeded"
SBP_STATUS_CANCELED = "canceled"
SBP_STATUS_EXPIRED = "expired"  # бот перестал проверять сам; вебхук/«Я оплатил» всё равно зачислят
# Метка бота в metadata платежа ЮKassa: если оба бота на одном магазине, вебхук одного
# пропускает чужие платежи (их подберёт фоновая проверка другого бота).
SBP_METADATA_BOT = "lbp"
CB_MARKET_OPEN = "bm:open"
CB_MARKET_BODY = "bm:body"
CB_MARKET_BODY_BUY = "bm:body:ok"
CB_MARKET_KIND_PREFIX = "bm:k:"  # bm:k:<вид>
CB_MARKET_ITEM_PREFIX = "bm:i:"  # bm:i:<вид>:<код>
CB_MARKET_UNLOCK_PREFIX = "bm:u:"  # bm:u:<вид>:<код>
CB_MARKET_LEVEL_PREFIX = "bm:l:"  # bm:l:<вид>:<код>
