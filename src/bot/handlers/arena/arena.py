"""Онлайн-бой в боте (текст и кнопки) — тот же бой, что в Mini App (`services/arena`).

Мини-игры в текстовом режиме засчитываются средним результатом. Кнопки отвечают только участнику боя — в группе
чужие нажатия молча отклоняются алертом.
"""
from __future__ import annotations

import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services import arena as svc
from bot.utils.formatting import esc, format_number

router = Router(name="arena")
CB_START_DISTRICT = "ar:sd:"  # + id района
CB_START_CHALLENGE = "ar:sc:"  # + id вызова
CB_ACT = "ar:x:"  # + id боя + ":" + код действия
CB_AUTO = "ar:au:"  # + id боя + ":" + 0/1
CB_REFRESH = "ar:r:"  # + id боя
BTN_ONLINE = "⚔️ Бой онлайн (перки)"
BTN_ACCEPT_ONLINE = "⚔️ Принять онлайн"
_NAMES = {"attack": "атака", "defend": "защита"}
_ERR = {"no_battle": "Бой уже закончен.", "not_yours": "Это не твой бой.", "in_battle": "Ты уже в бою — сначала доиграй его."}
_MAX_PERK_BUTTONS = 8


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def render(st: dict, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    me = "a" if st["a"]["uid"] == user_id else "d"
    foe = "d" if me == "a" else "a"
    s, o = st[me], st[foe]
    left = max(0, int(st["deadline"] - time.time()))
    lines = [f"⚔️ <b>{esc(s['name'])}</b> vs <b>{esc(o['name'])}</b>", "━━━━━━━━━━━━━━━━━━"]
    if st["status"] == "live":
        lines.append(f"Раунд {st['round'] + 1} · ⏳ {left} с{' · 🤖 автоатака' if s['auto'] else ''}")
    lines.append(f"🛡 Твоя мощь: <b>{format_number(s['power'])}</b> · ⚡ {s['energy']}/{s.get('emax', 10)}")
    lines.append(f"💢 Противник: <b>{format_number(o['power'])}</b> · ⚡ {o['energy']}")
    for e in st["log"][-3:]:
        mine = e[me]["code"]
        lines.append(f"· {_NAMES.get(mine, svc.PERK_REGISTRY.get(mine).name if mine in svc.PERK_REGISTRY else mine)} — "
                     f"выбито {format_number(e['kills'][0 if me == 'a' else 1])}, потеряно {format_number(e['kills'][1 if me == 'a' else 0])}")
    if s.get("pending_game"):
        lines.append("🎯 Противник навязал испытание — в боте засчитается средне.")
    rows: list[list[InlineKeyboardButton]] = []
    bid = st["id"]
    if st["status"] == "live":
        if s["action"] is not None:
            lines.append("✅ Ход сделан — ждём соперника.")
        elif not s["auto"]:
            rows.append([_b("🗡 Атака", f"{CB_ACT}{bid}:attack"), _b("🛡 Защита", f"{CB_ACT}{bid}:defend")])
            ready = [p for p in svc.perks_view(st, me) if p.ready_in == 0 and p.affordable][:_MAX_PERK_BUTTONS]
            for i in range(0, len(ready), 2):
                rows.append([_b(f"✨ {p.name} ⚡{p.cost}"[:60], f"{CB_ACT}{bid}:{p.code}") for p in ready[i:i + 2]])
        rows.append([_b("🤖 Выключить авто" if s["auto"] else "🤖 Автоатака", f"{CB_AUTO}{bid}:{0 if s['auto'] else 1}"),
                     _b("🔄 Обновить", f"{CB_REFRESH}{bid}")])
    else:
        won = st["result"]["attacker_won"] == (me == "a")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("🏆 <b>Победа!</b>" if won else "💀 <b>Поражение</b>")
        rep = st.get("report") or {}
        if "captured" in rep:
            lines.append("Район захвачен." if rep["captured"] and won else "")
    return "\n".join(x for x in lines if x), InlineKeyboardMarkup(inline_keyboard=rows)


async def _show(callback: CallbackQuery, st: dict) -> None:
    text, markup = render(st, callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:  # то же сообщение — не страшно
        pass


@router.callback_query(F.data.startswith(CB_START_DISTRICT))
async def cb_start_district(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    from bot.db.repositories.user import get_by_id
    from bot.handlers.district.district import attack_error_text

    user = await get_by_id(session, callback.from_user.id)
    try:
        st = await svc.start_district(session, redis, user, int(callback.data.removeprefix(CB_START_DISTRICT)))
    except svc.ArenaError as exc:
        await callback.answer(_ERR.get(exc.code, "Не вышло."), show_alert=True)
        return
    except Exception as exc:  # noqa: BLE001 — ошибки атаки (КД, свой район…) — тем же текстом, что у автобоя
        text = attack_error_text(exc)
        if text is None:
            raise
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()
    text, markup = render(st, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_START_CHALLENGE))
async def cb_start_challenge(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    from bot.db.repositories.user import get_by_id
    from bot.services.district.challenge import ChallengeNotFoundError

    user = await get_by_id(session, callback.from_user.id)
    try:
        st = await svc.start_challenge(session, redis, user, int(callback.data.removeprefix(CB_START_CHALLENGE)))
    except ChallengeNotFoundError:
        await callback.answer("Вызов уже неактуален.", show_alert=True)
        return
    except svc.ArenaError as exc:
        await callback.answer(_ERR.get(exc.code, "Не вышло."), show_alert=True)
        return
    await callback.answer()
    if not isinstance(st, dict):
        await callback.message.answer("⏳ Вызов уже истёк — бой провела рота защиты.")
        return
    from bot.keyboards.arena_push import battle_markup

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001 — старое сообщение могло быть удалено
        pass
    await callback.message.answer("⚔️ <b>Бой начался!</b> Жми «Войти в бой» — там перки и мини-игры. Не зайдёшь — ходит автоатака.",
                                  reply_markup=battle_markup(st["id"]))


@router.callback_query(F.data.startswith(CB_ACT))
async def cb_act(callback: CallbackQuery, redis: Redis) -> None:
    bid, _, code = callback.data.removeprefix(CB_ACT).partition(":")
    action = {"kind": code} if code in ("attack", "defend") else {"kind": "perk", "perk": code, "score": 0.5}
    action["game_score"] = 0.5
    try:
        st = await svc.act(redis, bid, callback.from_user.id, action)
    except svc.ArenaError as exc:
        await callback.answer(_ERR.get(exc.code, "Не вышло."), show_alert=True)
        return
    await callback.answer()
    await _show(callback, st)


@router.callback_query(F.data.startswith(CB_AUTO))
async def cb_auto(callback: CallbackQuery, redis: Redis) -> None:
    bid, _, on = callback.data.removeprefix(CB_AUTO).partition(":")
    try:
        st = await svc.set_auto(redis, bid, callback.from_user.id, on == "1")
    except svc.ArenaError as exc:
        await callback.answer(_ERR.get(exc.code, "Не вышло."), show_alert=True)
        return
    await callback.answer()
    await _show(callback, st)


@router.callback_query(F.data.startswith(CB_REFRESH))
async def cb_refresh(callback: CallbackQuery, redis: Redis) -> None:
    st = await svc.tick(redis, callback.data.removeprefix(CB_REFRESH))
    if st is None or callback.from_user.id not in (st["a"]["uid"], st["d"]["uid"]):
        await callback.answer(_ERR["no_battle"] if st is None else _ERR["not_yours"], show_alert=True)
        return
    await callback.answer()
    await _show(callback, st)
