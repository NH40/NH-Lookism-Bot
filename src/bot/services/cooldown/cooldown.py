"""Пуши «готово» по окончании КД — атака, личная тренировка, тренировка статистов (сервис).

Тестеры 2026-10-13: «будет уведомление о готовности атаки? О том, что КД прошёл; и личная
тренировка и тренировка статистов готовы». Сами КД — ключи Redis с TTL (`SET NX EX`), у них нет
события «истёк», поэтому в момент выставления КД игрок кладётся в отложенную очередь
(`ZSET cooldown:ready`, score — когда КД кончится). Фоновый проход (`main._cooldown_loop`)
забирает наступившие записи и шлёт пуш — если ключ КД за это время продлили (новый бой),
запись переносится на новый срок, а не шлёт пуш раньше времени. Каждый вид пуша — своя
категория в ⚙️ Настройках → 🔔 Уведомления (`notify_player` их уважает).
"""
from __future__ import annotations

import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import battle_cooldown, cooldown_ready_queue, personal_training_cooldown, train_extras_cooldown
from bot.constant.cooldown import CD_BATTLE, CD_EXTRAS, CD_PERSONAL
from bot.constant.map import CB_MAP_OPEN
from bot.constant.settings import CB_NOTIFY_OPEN, NOTIFY_CD_BATTLE, NOTIFY_CD_EXTRAS, NOTIFY_CD_PERSONAL
from bot.constant.training import CB_TRAIN_EXTRAS_OPEN
from bot.texts.cooldown import BTN_TO_MAP, BTN_TO_SETTINGS, BTN_TO_TRAINING, PUSH_MUTE_HINT, PUSH_READY

log = logging.getLogger(__name__)

# вид КД → (ключ Redis, категория пуша, кнопка под пушем)
_KINDS = {
    CD_BATTLE: (battle_cooldown, NOTIFY_CD_BATTLE, (BTN_TO_MAP, CB_MAP_OPEN)),
    CD_PERSONAL: (personal_training_cooldown, NOTIFY_CD_PERSONAL, (BTN_TO_TRAINING, CB_TRAIN_EXTRAS_OPEN)),
    CD_EXTRAS: (train_extras_cooldown, NOTIFY_CD_EXTRAS, (BTN_TO_TRAINING, CB_TRAIN_EXTRAS_OPEN)),
}
SWEEP_BATCH = 500


async def schedule(redis: Redis, user_id: int, kind: str, seconds: int) -> None:
    """Пуш «готово», когда КД `kind` кончится (через `seconds`). Best-effort — сбой Redis не ломает действие."""
    if kind not in _KINDS or seconds <= 0:
        return
    try:
        await redis.zadd(cooldown_ready_queue(), {f"{user_id}:{kind}": time.time() + seconds})
    except Exception:  # noqa: BLE001 — пуш вторичен, действие уже совершено
        log.exception("Cooldown push schedule failed")


async def sweep(bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> int:
    """Разослать наступившие пуши. → сколько отправлено (попыток)."""
    from bot.services.settings import notify_player

    queue = cooldown_ready_queue()
    now = time.time()
    due = await redis.zrangebyscore(queue, 0, now, start=0, num=SWEEP_BATCH)
    sent = 0
    for member in due:
        raw = member.decode() if isinstance(member, bytes) else member
        if not await redis.zrem(queue, raw):  # другой процесс уже забрал
            continue
        uid_raw, _, kind = raw.partition(":")
        if kind not in _KINDS or not uid_raw.isdigit():
            continue
        key_fn, category, (btn_text, btn_cb) = _KINDS[kind]
        left = await redis.ttl(key_fn(int(uid_raw)))
        if left and left > 0:  # КД продлили (новый бой/тренировка) — ждём новый срок
            await redis.zadd(queue, {raw: now + left})
            continue
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=btn_text, callback_data=btn_cb),
            InlineKeyboardButton(text=BTN_TO_SETTINGS, callback_data=CB_NOTIFY_OPEN),
        ]])
        async with session_factory() as session:
            await notify_player(bot, session, int(uid_raw), category, PUSH_READY[kind] + PUSH_MUTE_HINT, reply_markup=markup)
        sent += 1
    return sent
