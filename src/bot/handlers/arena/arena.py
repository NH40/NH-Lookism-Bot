"""Онлайн-бой в боте (текст и кнопки) — тот же бой, что в Mini App (`services/arena`).

Мини-игр в боте нет (2026-11-20): свой перк с мини-игрой бьёт без бонуса, навязанное соперником испытание
засчитывается проваленным (полный дебафф) — сыграть можно в Mini App. Кнопки отвечают только участнику боя — в группе
чужие нажатия молча отклоняются алертом.
"""
from __future__ import annotations

import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services import arena as svc
from bot.services.combat import explain
from bot.utils.formatting import esc, format_number

router = Router(name="arena")
CB_START_DISTRICT = "ar:sd:"  # + id района
CB_START_CHALLENGE = "ar:sc:"  # + id вызова
CB_ACT = "ar:x:"  # + id боя + ":" + код действия
CB_AUTO = "ar:au:"  # + id боя + ":" + 0/1
CB_REFRESH = "ar:r:"  # + id боя
CB_FINISH = "ar:f:"  # + id боя — «⏩ Досчитать» (соперник бот или на автобое)
CB_HELP = "ar:h:"  # + id боя + ":" + 1 (перки) / 0 (лента)
BTN_ONLINE = "⚔️ Бой онлайн (перки)"
BTN_ACCEPT_ONLINE = "⚔️ Принять онлайн"
_NAMES = {"attack": "атака", "defend": "защита"}
_ERR = {"no_battle": "Бой уже закончен.", "not_yours": "Это не твой бой.", "in_battle": "Ты уже в бою — сначала доиграй его.",
        "foe_live": "Соперник ходит сам — досчитать сразу нельзя. Включи автобой, он доиграет за тебя."}
_MAX_PERK_BUTTONS = 8


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


KIND_TITLE = {"district": "Бой за район", "challenge": "Вызов", "boss": "Босс", "city": "Штурм города", "raid": "Рейд", "war": "Война вождей",
              "tom": "Том Ли", "throne": "Бой за трон", "liberation": "Освобождение страны", "clan_war": "Клановая война", "tutorial": "Обучение"}
SEP = "━━━━━━━━━━━━━━━━━━"


def _bar(cur: int, full: int, n: int = 10) -> str:
    k = max(0, min(n, round(n * cur / max(1, full))))
    return "▰" * k + "▱" * (n - k)


def _act_name(code: str | None) -> str:
    if code in (None, "", "attack"):
        return "Атака"
    if code == "defend":
        return "Защита"
    from bot.config.arena.perks import char_action

    perk = svc.PERK_REGISTRY.get(code) or char_action(code or "")
    return perk.name if perk else "Перк"


def _side_lines(mark: str, side: dict, mine: bool, intel: dict | None = None) -> list[str]:
    p0 = side.get("power0") or side["power"] or 1
    units = side.get("units")
    if side.get("afk"):
        state = "🤖 не ходит — автоатака"
    elif side["auto"]:
        state = "🤖 автоатака"
    elif side["action"] is not None:
        state = f"✅ {_act_name(side['action'].get('perk') or side['action'].get('kind'))}" if mine else (
            f"✅ сходил: {intel['read']} 👁" if intel and intel.get("read") else "✅ сходил")
    else:
        state = "⌛ твой ход" if mine else "🤔 думает"
    unit_txt = f"👥 {format_number(units)}/{format_number(side.get('units0') or units)} · " if units is not None else ""
    energy = "🥷 ?" if intel and intel.get("hidden") else f"{side['energy']}/{side.get('emax', 10)}"
    out = [
        f"{mark} <b>{esc(side['name'])}</b> — {format_number(side['power'])}",
        f"   {_bar(side['power'], p0)} {round(100 * side['power'] / max(1, p0))}%",
        f"   {unit_txt}⚡ {energy} · {state}",
    ]
    if intel and intel.get("ready") is not None:
        out.append(f"   👁 готово: {esc(', '.join(intel['ready']) or 'ничего')}")
    return out


def render(st: dict, user_id: int, *, perks_help: bool = False, detail: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """Текстовый экран боя (дизайн 2026-11-20): обе стороны полосками, лента раундов, кнопки ходов и перков.
    Мини-игр в боте нет: свой перк — без бонуса мини-игры, навязанное испытание — провалено (полный дебафф)."""
    me = "a" if st["a"]["uid"] == user_id else "d"
    foe = "d" if me == "a" else "a"
    s, o = st[me], st[foe]
    i_me = 0 if me == "a" else 1
    left = max(0, int(st["deadline"] - time.time()))
    live = st["status"] == "live"
    head = f"⚔️ <b>{KIND_TITLE.get(st['kind'], 'Бой')}</b>"
    head += f" · раунд {st['round'] + 1} · ⏳ {left} с" if live else f" · раундов: {st['round']}"
    lines = [head, SEP, *_side_lines("🟦", s, True), "", *_side_lines("🟥", o, False, svc.foe_intel(st, me)), SEP]
    pw = st.get("pw")
    if pw:
        lines.append(esc(explain.power_line(pw["ratio"], pw["stronger"] == me, pw["w"])))
    perks = svc.perks_view(st, me)
    if perks_help:
        lines.append("📖 <b>Твои способности</b>")
        for p in perks:
            perk = svc.PERK_REGISTRY[p.code]
            mg = " 🎮" if perk.minigame == "self" else " 🎯" if perk.minigame == "enemy" else ""
            ready = "готов" if p.ready_in == 0 and p.affordable else f"через {p.ready_in} р." if p.ready_in else "мало ⚡"
            lines.append(f"✦ <b>{esc(p.name)}</b>{mg} · ⚡{p.cost} · {ready}\n   <i>{esc(p.about)}</i>")
        lines.append("🎮 — в Mini App мини-игра усиливает удар, в боте перк бьёт без бонуса. 🎯 — сопернику испытание.")
    elif detail and st["log"] and st["log"][-1].get("det"):
        e = st["log"][-1]
        det = e["det"]
        lines.append(f"🔎 <b>Разбор раунда {len(st['log'])}</b>")
        lines.append(f"🟦 <b>Ты: {esc(_act_name(e[me]['code']))}</b>")
        lines += [esc(x) for x in explain.side_lines(det[i_me], det[1 - i_me], _act_name(e[me]["code"]))]
        lines.append(f"🟥 <b>Противник: {esc(_act_name(e[foe]['code']))}</b>")
        lines += [esc(x) for x in explain.side_lines(det[1 - i_me], det[i_me], _act_name(e[foe]["code"]))]
    else:
        log = st["log"][-4:]
        if log:
            lines.append("📜 <b>Лента боя</b>")
        start = len(st["log"]) - len(log) + 1
        for n, e in enumerate(log, start):
            hit = e.get("hit", [0, 0])
            fired = e.get("fired", [[], []])
            k_me, k_foe = e["kills"][i_me], e["kills"][1 - i_me]
            lines.append(f"<b>Р{n}</b> {'▲' if k_me >= k_foe else '▼'}")
            lines.append(f"   🟦 {esc(_act_name(e[me]['code']))}: 💥 {format_number(hit[i_me])} · ☠️ {format_number(k_me)}"
                         + (f" · ✨ {esc(', '.join(fired[i_me][:3]))}" if fired[i_me] else ""))
            lines.append(f"   🟥 {esc(_act_name(e[foe]['code']))}: 💥 {format_number(hit[1 - i_me])} · ☠️ {format_number(k_foe)}"
                         + (f" · ✨ {esc(', '.join(fired[1 - i_me][:3]))}" if fired[1 - i_me] else ""))
    if live and s.get("pending_game") and not s["auto"]:
        lines.append("🎯 <b>Соперник навязал испытание!</b> В боте оно засчитывается проваленным — получишь больше урона. "
                     "Сыграть можно в Mini App.")
    rows: list[list[InlineKeyboardButton]] = []
    bid = st["id"]
    if live:
        if s["action"] is not None:
            lines.append("✅ Ход сделан — ждём соперника. Жми «Обновить».")
        elif s["auto"]:
            lines.append("🤖 Ходит автоатака. Выключи её, чтобы ходить самому.")
        else:
            lines.append("👇 <b>Твой ход</b>")
            rows.append([_b("🗡 Атака", f"{CB_ACT}{bid}:attack"), _b("🛡 Защита +⚡", f"{CB_ACT}{bid}:defend")])
            acts = [a for a in svc.actions_view(st, me) if a.ready_in == 0 and a.affordable]  # действия характеристик
            for i in range(0, len(acts), 2):
                rows.append([_b(f"{a.name} ⚡{a.cost}"[:60], f"{CB_ACT}{bid}:{a.code}") for a in acts[i:i + 2]])
            ready = [p for p in perks if p.ready_in == 0 and p.affordable][:_MAX_PERK_BUTTONS]
            for i in range(0, len(ready), 2):
                rows.append([_b(f"{'🎯' if svc.PERK_REGISTRY[p.code].minigame == 'enemy' else '✦'} {p.name} ⚡{p.cost}"[:60],
                                f"{CB_ACT}{bid}:{p.code}") for p in ready[i:i + 2]])
        rows.append([_b("📜 Лента" if perks_help or detail else "📖 Перки", f"{CB_HELP}{bid}:{0 if perks_help or detail else 1}"),
                     _b("🔄 Обновить", f"{CB_REFRESH}{bid}")])
        if st["log"] and not detail:
            rows.append([_b("🔎 Разбор раунда", f"{CB_HELP}{bid}:2")])
        auto_row = [_b("🤖 Выключить авто" if s["auto"] else "🤖 Автоатака", f"{CB_AUTO}{bid}:{0 if s['auto'] else 1}")]
        if o["auto"]:  # соперник — бот или на автобое: можно доиграть мгновенно
            auto_row.append(_b("⏩ Досчитать", f"{CB_FINISH}{bid}"))
        rows.append(auto_row)
    else:
        won = st["result"]["attacker_won"] == (me == "a")
        lines.append(SEP)
        lines.append("🏆 <b>Победа!</b>" if won else "💀 <b>Поражение</b>")
        rep = st.get("report") or {}
        if rep.get("captured") and won:
            lines.append("🚩 Район захвачен.")
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _show(callback: CallbackQuery, st: dict, *, perks_help: bool = False, detail: bool = False) -> None:
    text, markup = render(st, callback.from_user.id, perks_help=perks_help, detail=detail)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:  # то же сообщение — не страшно
        pass


async def start_reply(callback: CallbackQuery, coro) -> None:
    """Запустить онлайн-бой из кнопки другого экрана (Том, трон, клановая война): ошибки → алерт, бой → экран боя."""
    from bot.handlers.district.district import attack_error_text

    try:
        st = await coro
    except svc.ArenaError as exc:
        await callback.answer(_ERR.get(exc.code, "Не вышло."), show_alert=True)
        return
    except Exception as exc:  # noqa: BLE001 — ошибки атаки (КД, лагерь пуст…) — тем же текстом, что у автобоя
        text = attack_error_text(exc)
        if text is None:
            raise
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()
    if not isinstance(st, dict):
        return
    text, markup = render(st, callback.from_user.id)
    await callback.message.answer(text, reply_markup=markup)


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
    # Текстовый режим без мини-игр: своя — без бонуса (0), навязанная — провалена (0, полный дебафф).
    action = {"kind": code} if code in ("attack", "defend") else {"kind": "perk", "perk": code, "score": 0.0}
    action["game_score"] = 0.0
    try:
        st = await svc.act(redis, bid, callback.from_user.id, action)
    except svc.ArenaError as exc:
        await callback.answer(_ERR.get(exc.code, "Не вышло."), show_alert=True)
        return
    await callback.answer()
    await _show(callback, st)


@router.callback_query(F.data.startswith(CB_FINISH))
async def cb_finish(callback: CallbackQuery, redis: Redis) -> None:
    try:
        st = await svc.finish_now(redis, callback.data.removeprefix(CB_FINISH), callback.from_user.id)
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
    await svc.mark_seen(redis, st, callback.from_user.id)
    await callback.answer()
    await _show(callback, st)


@router.callback_query(F.data.startswith(CB_HELP))
async def cb_help(callback: CallbackQuery, redis: Redis) -> None:
    bid, _, on = callback.data.removeprefix(CB_HELP).partition(":")
    st = await svc.tick(redis, bid)
    if st is None or callback.from_user.id not in (st["a"]["uid"], st["d"]["uid"]):
        await callback.answer(_ERR["no_battle"] if st is None else _ERR["not_yours"], show_alert=True)
        return
    await callback.answer()
    await _show(callback, st, perks_help=on == "1", detail=on == "2")
