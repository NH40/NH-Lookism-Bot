"""Админ-панель в Mini App — игрок: поиск, карточка и действия из неё (выдача, статисты,
развитие, фаза, наказания, задания). Те же сервисы, права и записи аудита, что у хендлеров бота
`handlers/admin/{players,give,statists,dev,punish,quests}` — своей логики здесь нет.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.push import get_bot
from api.routers._common import bad, clean_label
from api.routers.admin import access, done, role_title
from bot.cache.keys import admin_recent_players
from bot.config.awakening import AWAKENING_MAX
from bot.config.card import CARD_BY_CODE
from bot.config.development import MAX_LEVEL
from bot.constant.admin import SECTION_DEV, SECTION_GIVE, SECTION_PLAYERS, SECTION_PUNISH
from bot.constant.admin.players_admin import (
    AST_ADD_AMOUNTS,
    AST_GIVE_AMOUNTS,
    AST_TAKE_PERCENTS,
    AUDIT_BAN,
    AUDIT_CLEAR_COOLDOWNS,
    AUDIT_DELETE_ACCOUNT,
    AUDIT_DEV_AWAKENING,
    AUDIT_DEV_BLOODLINE,
    AUDIT_DEV_BODY,
    AUDIT_DEV_PASS,
    AUDIT_DEV_POTENTIAL,
    AUDIT_DEV_SET_ACTIVE,
    AUDIT_DEV_SET_LEVEL,
    AUDIT_DEV_STAT,
    AUDIT_GIVE_BP_XP,
    AUDIT_GIVE_CARD,
    AUDIT_GIVE_RESOURCE,
    AUDIT_GIVE_SCROLLS,
    AUDIT_GIVE_STATIST,
    AUDIT_PHASE,
    AUDIT_RESET_PLAYER,
    AUDIT_UNBAN,
    AUDIT_WIPE_STATISTS,
    BAN_DURATIONS,
    BAN_REASON_MAX_LEN,
    BLOOD_SLOTS,
    DEV_KINDS,
)
from bot.constant.characteristic import POTENTIAL_ORDER, RANK_LADDER, STATS
from bot.constant.phase import PHASE_ORDER
from bot.constant.resource import RESOURCES
from bot.db.models.user import User
from bot.services.admin import audit, players, players_admin, roles
from bot.services.admin.testing import NotAdminError, QuestGoneError, complete, list_open
from bot.services.extra import get_army_stats, list_squads
from bot.services.resource import balances
from bot.services.resource.statists import StatistKey, give_statists, take_statists
from bot.texts.admin import players_admin as t
from bot.texts.admin.admin import QUEST_GONE_ALERT, QUESTS_DONE_ALERT
from bot.texts.dev_quest import TASK_LABELS, quest_title
from bot.texts.gang import squad_title
from bot.texts.profile import PHASE_LABELS
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import format_number
from bot.utils.notify import notify

router = APIRouter(prefix="/api/admin/players", tags=["admin"])
RECENT_PLAYERS_LIMIT = 10


def _sign(value: int) -> str:
    return "+" if value > 0 else "−"


def _name_of(user: User) -> str:
    return user.display_name or user.username or str(user.id)


async def _target(session: AsyncSession, uid: int) -> User:
    user = await session.get(User, uid)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Игрок не найден.")
    return user


# ---------------------------------------------------------------- поиск и карточка

@router.get("/find")
async def find_player(q: str, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_PLAYERS)
    user = await players.find(session, q)
    if user is None:
        raise bad(f"Игрок «{q.strip()[:40]}» не найден.")
    return {"id": user.id}


@router.get("/recent")
async def recent_players(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
) -> dict:
    """Последние 10 карточек, которые открывал этот админ (свежие сверху)."""
    await access(session, user_id, SECTION_PLAYERS)
    ids = [int(x) for x in await redis.lrange(admin_recent_players(user_id), 0, RECENT_PLAYERS_LIMIT - 1)]
    users = {u.id: u for u in (await session.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}
    return {
        "items": [
            {"id": i, "name": _name_of(users[i]), "username": users[i].username, "phase": clean_label(PHASE_LABELS.get(users[i].phase, users[i].phase or "")),
             "banned": players.is_banned(users[i])}
            for i in ids if i in users
        ]
    }


def _levels(items: list[tuple[str, int]], kind: str, active: str | None, active2: str | None = None) -> list[dict]:
    names = t.DEV_NAMES[kind]
    return [{"code": c, "name": names.get(c, c), "level": lvl, "active": c == active, "active2": c == active2} for c, lvl in items]


@router.get("/{uid}")
async def get_card(
    uid: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await access(session, user_id, SECTION_PLAYERS)
    card = await players.card(session, uid)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Игрок не найден.")
    await session.commit()  # сезон пасса мог открыться при чтении
    key = admin_recent_players(user_id)  # «последние игроки» админа: без дублей, свежий — первым
    async with redis.pipeline(transaction=True) as pipe:
        await pipe.lrem(key, 0, uid).lpush(key, uid).ltrim(key, 0, RECENT_PLAYERS_LIMIT - 1).execute()
    u = card.user
    blood = lambda code, level: {"code": code, "name": t.BLOODLINE_TITLES.get(code, code), "level": level} if code else None  # noqa: E731
    return {
        "id": u.id, "name": _name_of(u), "username": u.username,
        "role": card.role, "role_name": role_title(card.role) if card.role else None,
        "banned": card.banned, "ban_forever": bool(u.is_banned), "banned_until": u.banned_until, "ban_reason": u.ban_reason,
        "phase": u.phase, "phase_name": clean_label(PHASE_LABELS.get(u.phase, u.phase or "")),
        "gang": card.gang, "city": card.city, "districts": card.districts, "clan": card.clan,
        "last_active_at": u.last_active_at, "created_at": u.created_at,
        "resources": [
            {"code": c, "name": clean_label(resource_label(c)), "amount": a, "label": amount_label(c, a)} for c, a in card.resources.items()
        ],
        "bloodline": blood(u.bloodline, u.bloodline_level), "bloodline2": blood(u.bloodline2, u.bloodline2_level),
        "paths": _levels(card.paths, "path", u.active_path, u.active_path2),
        "techniques": _levels(card.techniques, "tech", u.active_technique),
        "geniuses": _levels(card.geniuses, "gen", u.active_genius),
        "awakening": u.awakening_level, "potential": u.potential, "second_body": bool(u.second_body),
        "stats": {s: RANK_LADDER[getattr(u, f"stat_{s}")] for s in STATS},
        "bp_level": card.bp_level, "bp_premium": card.bp_premium,
        "donated_rub": card.donated_rub, "donate_unlocks": card.donate_unlocks,
    }


# ---------------------------------------------------------------- выдача / изъятие

class GiveIn(BaseModel):
    kind: str  # resource | statist | card | scrolls | xp
    delta: int
    code: str | None = None  # ресурс или код карты
    rank: str | None = None  # статисты
    stars: int = 0


@router.get("/{uid}/give")
async def get_give(uid: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_GIVE)
    user = await _target(session, uid)
    res = await balances(session, uid)
    scrolls = await players_admin.skip_scrolls(session, uid)
    xp = await players_admin.bp_xp(session, uid)
    await session.commit()  # строка/сезон пасса могли создаться при чтении
    return {
        "name": _name_of(user),
        "resources": [{"code": c, "name": clean_label(resource_label(c)), "amount": a, "label": amount_label(c, a)} for c, a in res.items()],
        "scrolls": scrolls, "bp_xp": xp,
        "cards": [{"code": c, "name": d.name} for c, d in sorted(CARD_BY_CODE.items(), key=lambda x: x[1].name)],
    }


@router.post("/{uid}/give")
async def post_give(uid: int, body: GiveIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_GIVE)
    await _target(session, uid)
    delta = body.delta
    if not delta:
        raise bad("Нужно ненулевое число: плюс — выдать, минус — забрать.")
    try:
        if body.kind == "resource":
            if body.code not in RESOURCES:
                raise bad("Неизвестный ресурс.")
            applied, balance = await players_admin.give_resource(session, uid, body.code, delta)
            notice = t.DONE_RESOURCE.format(
                label=resource_label(body.code), sign=_sign(applied) if applied else "", amount=format_number(abs(applied)),
                balance=amount_label(body.code, balance),
            )
            action, details = AUDIT_GIVE_RESOURCE, {"resource": body.code, "requested": delta, "applied": applied}
        elif body.kind == "statist":
            if body.rank not in RANK_LADDER or body.stars < 0:
                raise bad("Неизвестный ранг.")
            await players_admin.give_statist(session, uid, StatistKey(body.rank, body.stars), delta)
            notice = t.DONE_STATIST.format(rank=body.rank, stars=body.stars, sign=_sign(delta), amount=format_number(abs(delta)))
            action, details = AUDIT_GIVE_STATIST, {"rank": body.rank, "stars": body.stars, "delta": delta}
        elif body.kind == "card":
            code = (body.code or "").lower()
            if code not in CARD_BY_CODE:
                raise bad("Неизвестная карта.")
            await players_admin.give_card(session, uid, code, delta)
            notice = t.DONE_CARD.format(name=CARD_BY_CODE[code].name, sign=_sign(delta), amount=format_number(abs(delta)))
            action, details = AUDIT_GIVE_CARD, {"card": code, "delta": delta}
        elif body.kind == "scrolls":
            balance = await players_admin.add_skip_scrolls(session, uid, delta)
            notice = t.DONE_SCROLLS.format(sign=_sign(delta), amount=format_number(abs(delta)), balance=format_number(balance))
            action, details = AUDIT_GIVE_SCROLLS, {"delta": delta}
        elif body.kind == "xp":
            balance = await players_admin.add_bp_xp(session, uid, delta)
            notice = t.DONE_XP.format(sign=_sign(delta), amount=format_number(abs(delta)), balance=format_number(balance))
            action, details = AUDIT_GIVE_BP_XP, {"delta": delta}
        else:
            raise bad("Неизвестный вид выдачи.")
    except players_admin.NotEnoughError as e:
        await session.rollback()
        raise bad(clean_label(t.GIVE_NOT_ENOUGH.format(have=format_number(e.have))))
    await audit.log(session, user_id, action, uid, details)
    await session.commit()
    return done(notice)


# ---------------------------------------------------------------- статисты (кнопками)

class StatistIn(BaseModel):
    action: str  # take | add | give | wipe
    key: str | None = None  # закодированный отряд (take/add)
    percent: int = 0  # take
    amount: int = 0  # add/give
    rank: str | None = None  # give — новый отряд ранга (0★)


def _squad_key(s) -> StatistKey:
    return StatistKey(s.rank, s.stars, s.training_level, s.school, s.school_level)


@router.get("/{uid}/statists")
async def get_statists(uid: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_GIVE)
    user = await _target(session, uid)
    squads = await list_squads(session, uid)
    army = await get_army_stats(session, uid)
    return {
        "name": _name_of(user),
        "total": army.total_quantity - army.cards_quantity, "attack": army.attack.quantity, "defense": army.defense.quantity,
        "squads": [
            {
                "key": _squad_key(s).encode(), "title": squad_title(s.rank, s.stars, s.training_level, s.school, s.school_level),
                "total": s.total, "attack": s.attack, "defense": s.defense,
            }
            for s in squads
        ],
    }


@router.post("/{uid}/statists")
async def post_statists(uid: int, body: StatistIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_GIVE)
    await _target(session, uid)
    if body.action == "wipe":
        n = await players_admin.wipe_statists(session, uid)
        await audit.log(session, user_id, AUDIT_WIPE_STATISTS, uid, {"removed": n})
        await session.commit()
        return done(t.AST_DONE_WIPE.format(n=format_number(n)))
    if body.action == "give":
        if body.rank not in RANK_LADDER or body.amount not in AST_GIVE_AMOUNTS:
            raise bad("Неизвестный ранг или количество.")
        key = StatistKey(body.rank, 0)
        await give_statists(session, uid, key, body.amount)
        await audit.log(session, user_id, AUDIT_GIVE_STATIST, uid, {"key": key.encode(), "delta": body.amount})
        await session.commit()
        return done(t.AST_DONE_ADD.format(n=format_number(body.amount), title=body.rank))
    try:
        key = StatistKey.decode(body.key or "")
    except ValueError:
        raise bad("Отряд не найден.")
    title = squad_title(key.rank, key.stars, key.training_level, key.school, key.school_level)
    if body.action == "add":
        if body.amount not in AST_ADD_AMOUNTS:
            raise bad("Неизвестное количество.")
        await give_statists(session, uid, key, body.amount)
        await audit.log(session, user_id, AUDIT_GIVE_STATIST, uid, {"key": key.encode(), "delta": body.amount})
        await session.commit()
        return done(t.AST_DONE_ADD.format(n=format_number(body.amount), title=title))
    if body.action == "take":
        if body.percent not in AST_TAKE_PERCENTS:
            raise bad("Неизвестная доля.")
        sq = next((s for s in await list_squads(session, uid) if _squad_key(s).encode() == key.encode()), None)
        n = (sq.total if body.percent == 100 else sq.total * body.percent // 100) if sq else 0
        if n <= 0 or not await take_statists(session, uid, key, n):
            await session.rollback()
            raise bad(t.AST_NOTHING)
        await audit.log(session, user_id, AUDIT_GIVE_STATIST, uid, {"key": key.encode(), "delta": -n})
        await session.commit()
        return done(t.AST_DONE_TAKE.format(n=format_number(n), title=title))
    raise bad("Неизвестное действие.")


# ---------------------------------------------------------------- развитие и фаза

class DevIn(BaseModel):
    action: str  # level | active | bloodline | blood_level | body | pass | awakening | potential | stat | phase
    kind: str | None = None
    code: str | None = None
    level: int = 0
    slot: int = 1
    value: str | None = None  # потенциал / ранг / фаза


@router.get("/{uid}/dev")
async def get_dev(uid: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_DEV)
    user = await _target(session, uid)
    systems = {}
    for kind in DEV_KINDS:
        owned, active = await players_admin.dev_state(session, uid, kind)
        systems[kind] = {"owned": owned, "active": active}
    blood = {}
    for slot in BLOOD_SLOTS:
        code, level = await players_admin.bloodline_state(session, uid, slot)
        blood[str(slot)] = {"code": code, "level": level}
    premium = await players_admin.premium_pass(session, uid)
    await session.commit()  # строка/сезон пасса могли создаться при чтении
    ranks = await players_admin.stat_ranks(session, uid)
    return {
        "name": _name_of(user), "systems": systems, "bloodlines": blood,
        "second_body": bool(user.second_body), "premium": premium, "awakening": user.awakening_level,
        "potential": user.potential, "stats": {s: RANK_LADDER[i] for s, i in ranks.items()}, "phase": user.phase,
    }


@router.post("/{uid}/dev")
async def post_dev(uid: int, body: DevIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_DEV)
    user = await _target(session, uid)
    a = body.action
    if a in ("level", "active"):
        if body.kind not in DEV_KINDS or body.code not in t.DEV_CODES[body.kind]:
            raise bad("Неизвестный пункт развития.")
        item, title = t.DEV_NAMES[body.kind].get(body.code, body.code), t.DEV_KIND_TITLES[body.kind]
        if a == "level":
            if not 0 <= body.level <= MAX_LEVEL:
                raise bad(f"Уровень от 0 до {MAX_LEVEL}.")
            await players_admin.set_dev_level(session, uid, body.kind, body.code, body.level)
            action, details = AUDIT_DEV_SET_LEVEL, {"kind": body.kind, "code": body.code, "level": body.level}
            notice = (t.DONE_LEVEL if body.level else t.DONE_TAKEN).format(title=title, item=item, level=body.level)
        else:
            if not await players_admin.set_dev_active(session, uid, body.kind, body.code):
                raise bad(t.NOT_OWNED_ALERT)
            action, details = AUDIT_DEV_SET_ACTIVE, {"kind": body.kind, "code": body.code}
            notice = t.DONE_ACTIVE.format(title=title, item=item)
    elif a in ("bloodline", "blood_level"):
        if body.slot not in BLOOD_SLOTS:
            raise bad("Неизвестный слот.")
        current, old_level = await players_admin.bloodline_state(session, uid, body.slot)
        if a == "bloodline":
            if body.code is not None and body.code not in t.BLOODLINE_CODES:
                raise bad("Неизвестная родословная.")
            code, level = (body.code, max(old_level, 1)) if body.code else (None, 0)
        else:
            if current is None or not 1 <= body.level <= MAX_LEVEL:
                raise bad(f"Сначала выдайте родословную; уровень от 1 до {MAX_LEVEL}.")
            code, level = current, body.level
        await players_admin.set_bloodline(session, uid, body.slot, code, level)
        action, details = AUDIT_DEV_BLOODLINE, {"slot": body.slot, "code": code, "level": level}
        notice = t.DONE_BLOOD.format(slot=body.slot, value=f"{t.BLOODLINE_TITLES.get(code, code)} {level}" if code else "—")
    elif a == "body":
        on = await players_admin.toggle_second_body(session, uid)
        action, details, notice = AUDIT_DEV_BODY, {"second_body": on}, t.DONE_BODY.format(state=t.STATE_ON if on else t.STATE_OFF)
    elif a == "pass":
        on = await players_admin.toggle_premium_pass(session, uid)
        action, details, notice = AUDIT_DEV_PASS, {"premium": on}, t.DONE_PASS.format(state=t.STATE_ON if on else t.STATE_OFF)
    elif a == "awakening":
        if not 0 <= body.level <= AWAKENING_MAX:
            raise bad(f"Пробуждение от 0 до {AWAKENING_MAX}.")
        await players_admin.set_awakening(session, uid, body.level)
        action, details, notice = AUDIT_DEV_AWAKENING, {"level": body.level}, t.DONE_AWAKEN.format(value=body.level)
    elif a == "potential":
        if body.value not in POTENTIAL_ORDER:
            raise bad("Неизвестный потенциал.")
        await players_admin.set_potential(session, uid, body.value)
        action, details, notice = AUDIT_DEV_POTENTIAL, {"potential": body.value}, t.DONE_POTENTIAL.format(value=body.value)
    elif a == "stat":
        index = players_admin.parse_rank(body.value or "")
        if body.code not in STATS or index is None:
            raise bad("Неизвестная характеристика или ранг.")
        await players_admin.set_stat_rank(session, uid, body.code, index)
        action, details = AUDIT_DEV_STAT, {"stat": body.code, "rank": RANK_LADDER[index]}
        notice = t.DONE_STAT.format(stat=t.STAT_NAMES[body.code], rank=RANK_LADDER[index])
    elif a == "phase":
        if body.value not in PHASE_ORDER:
            raise bad("Неизвестная фаза.")
        try:
            await players_admin.set_phase(session, uid, body.value)
        except players_admin.EmperorTakenError:
            await session.rollback()
            raise bad(t.PHASE_EMPEROR_TAKEN)
        action, details = AUDIT_PHASE, {"phase": body.value}
        notice = t.PHASE_DONE.format(label=PHASE_LABELS.get(body.value, body.value))
    else:
        raise bad("Неизвестное действие.")
    await audit.log(session, user_id, action, user.id, details)
    await session.commit()
    return done(notice)


# ---------------------------------------------------------------- наказания

class PunishIn(BaseModel):
    action: str  # ban | unban | cooldowns | reset | delete
    duration: str | None = None
    reason: str | None = None


@router.post("/{uid}/punish")
async def post_punish(
    uid: int, body: PunishIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await access(session, user_id, SECTION_PUNISH)
    user = await _target(session, uid)
    a = body.action
    # Как в боте: бан, сброс и удаление — не над собой и не над сотрудниками админки.
    if a in ("ban", "reset", "delete"):
        if uid == user_id:
            raise bad(t.TARGET_IS_SELF_ALERT)
        if await roles.role_of(session, uid) is not None:
            raise bad(t.TARGET_IS_STAFF_ALERT)
    bot = get_bot()
    if a == "ban":
        if body.duration not in BAN_DURATIONS:
            raise bad("Неизвестный срок.")
        reason = (body.reason or "").strip() or None
        if reason and len(reason) > BAN_REASON_MAX_LEN:
            raise bad(f"Причина длиннее {BAN_REASON_MAX_LEN} символов.")
        until = await players_admin.ban(session, uid, BAN_DURATIONS[body.duration], reason)
        await audit.log(session, user_id, AUDIT_BAN, uid, {"duration": body.duration, "reason": reason})
        await session.commit()
        duration = t.BAN_DURATION_TITLES[body.duration] if until is None else f"до {until.strftime('%d.%m.%Y %H:%M UTC')}"
        from bot.utils.formatting import esc

        await notify(bot, uid, t.PLAYER_BANNED.format(duration=duration, reason=t.PLAYER_BANNED_REASON.format(reason=esc(reason)) if reason else ""))
        return done(t.DONE_BAN.format(duration=t.BAN_DURATION_TITLES[body.duration]))
    if a == "unban":
        if not players.is_banned(user):
            raise bad(t.NOT_BANNED_ALERT)
        await players_admin.unban(session, uid)
        await audit.log(session, user_id, AUDIT_UNBAN, uid)
        await session.commit()
        await notify(bot, uid, t.PLAYER_UNBANNED)
        return done(t.DONE_UNBAN)
    if a == "cooldowns":
        removed = await players_admin.clear_cooldowns(redis, uid)
        await audit.log(session, user_id, AUDIT_CLEAR_COOLDOWNS, uid, {"keys": removed})
        await session.commit()
        return done(t.DONE_COOLDOWNS.format(count=removed))
    if a == "reset":
        await players_admin.reset_progress(session, uid)
        await audit.log(session, user_id, AUDIT_RESET_PLAYER, uid)
        await session.commit()
        return done(t.DONE_RESET)
    if a == "delete":
        try:
            await players_admin.delete_account(session, uid)
            await audit.log(session, user_id, AUDIT_DELETE_ACCOUNT, None, {"deleted_id": uid})
            await session.commit()
        except players_admin.OwnerBlockedError as e:
            await session.rollback()
            raise bad(clean_label(t.DELETE_OWNER_BLOCKED.format(members=e.members)))
        except IntegrityError as e:
            await session.rollback()
            raise bad(clean_label(t.DELETE_FAILED.format(reason=type(e.orig).__name__)))
        return done(f"Аккаунт {uid} удалён.", deleted=True)
    raise bad("Неизвестное действие.")


# ---------------------------------------------------------------- задания игрока

class QuestIn(BaseModel):
    slot: int | None = None
    dev_id: int | None = None  # оба пусто — засчитать все


@router.get("/{uid}/quests")
async def get_quests(uid: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_DEV)
    user = await _target(session, uid)
    daily, dev = await list_open(session, uid)
    return {
        "name": _name_of(user),
        "daily": [
            {"slot": q.slot, "title": clean_label(TASK_LABELS.get(q.task, q.task)), "progress": q.progress, "target": q.target}
            for q in daily
        ],
        "dev": [{"id": q.id, "title": clean_label(quest_title(q.kind, q.ref))} for q in dev],
    }


@router.post("/{uid}/quests")
async def post_quests(uid: int, body: QuestIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_DEV)
    await _target(session, uid)
    try:
        daily, dev = await complete(session, user_id, uid, slot=body.slot, dev_id=body.dev_id)
    except NotAdminError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав.")
    except QuestGoneError:
        raise bad(QUEST_GONE_ALERT)
    return done(QUESTS_DONE_ALERT.format(daily=daily, dev=dev))
