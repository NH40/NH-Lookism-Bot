"""Админ-панель в Mini App (пользователь 2026-10-17: «все 17 разделов, родные экраны») — ядро:
права, справочники для экранов, бета/техрежим, роли, настройки на лету, патч/вайп, статистика,
журналы. Остальные разделы — `admin_players` (игрок и действия над ним) и `admin_ops`.

Та же модель прав, что в боте (`services/admin/roles`): роль игрока и минимальная роль раздела.
Каждое действие вызывает тот же сервис, что хендлер бота, и пишет тот же аудит — своей логики
здесь нет. Ошибки — HTTP 400/403 с текстом для тоста (без эмодзи и HTML).
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session, session_factory
from api.deps import get_redis
from api.push import get_bot
from api.routers._common import bad, clean_label
from bot.cache.keys import tech_mode_flag
from bot.config.admin import ADMIN_AUDIT_PAGE
from bot.config.awakening import AWAKENING_MAX
from bot.config.development import MAX_LEVEL
from bot.config.settings import get_settings
from bot.constant.admin import (
    ROLE_SUPER,
    ROLES,
    SECTION_CONFIG,
    SECTION_DEV,
    SECTION_GIVE,
    SECTION_LOGS,
    SECTION_PATCH,
    SECTION_PUNISH,
    SECTION_ROLES,
    SECTION_STATS,
    SECTION_SYSTEM,
)
from bot.constant.admin.live_config import (
    AUDIT_PATCH,
    AUDIT_ROLE_REMOVE,
    AUDIT_ROLE_SET,
    AUDIT_WIPE,
    CONFIG_DURATIONS,
    CONFIRM_KIND_PATCH,
    CONFIRM_KIND_WIPE,
)
from bot.constant.admin.mass import FILTERS, MASS_GRANT_MAX_AMOUNT
from bot.constant.admin.players_admin import (
    AST_ADD_AMOUNTS,
    AST_GIVE_AMOUNTS,
    AST_TAKE_PERCENTS,
    BAN_DURATIONS,
    BAN_REASON_MAX_LEN,
    DEV_KINDS,
)
from bot.constant.characteristic import POTENTIAL_ORDER, RANK_LADDER, STATS
from bot.constant.phase import PHASE_ORDER
from bot.constant.referral import REF_NAME_MAX_LEN
from bot.constant.resource import RESOURCES
from bot.services.admin import audit, beta, live_config, players, roles
from bot.services.admin import events_admin
from bot.services.admin import logs as logs_svc
from bot.services.admin import patch as patch_service
from bot.services.admin import stats as stats_svc
from bot.texts.admin.admin import ROLE_NAMES, SECTION_TITLES
from bot.texts.admin.events_admin import KIND_TITLES as EVENT_KIND_TITLES
from bot.texts.admin.mass import FILTER_LABELS
from bot.texts.admin.patch import PATCH_DONE, PATCH_FAILED, WIPE_NOTIFY
from bot.texts.admin import players_admin as tp
from bot.texts.admin.roles_admin import NOTIFY_REMOVE, NOTIFY_SET
from bot.texts.event import BOSS_NAMES
from bot.texts.profile import PHASE_LABELS
from bot.texts.resource import resource_label
from bot.texts.school import SCHOOL_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import format_number
from bot.utils.notify import notify

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

NO_RIGHTS = "Недостаточно прав для этого раздела."
NOT_ADMIN = "Админ-панель недоступна."
_tasks: set[asyncio.Task] = set()  # ссылки на фоновые задачи (иначе GC может собрать)


# ---------------------------------------------------------------- права и общее

async def access(session: AsyncSession, user_id: int, section: str | None = None) -> str:
    """Роль вызывающего; нет роли или права на раздел — 403."""
    role = await roles.role_of(session, user_id)
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_ADMIN)
    if section is not None and not roles.allowed(role, section):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_RIGHTS)
    return role


def done(message: str, **extra) -> dict:
    """Ответ действия: текст тоста (как алерт бота, без эмодзи/HTML) + данные."""
    return {"message": clean_label(message), **extra}


def background(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def role_title(role: str | None) -> str:
    return clean_label(ROLE_NAMES.get(role, role or ""))


def plain(value):
    """dataclass/tuple/Decimal из сервисов → JSON-совместимое."""
    if dataclasses.is_dataclass(value):
        return {k: plain(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "__float__") and not isinstance(value, (int, float, bool)):
        return float(value)
    return value


# ---------------------------------------------------------------- главная + справочники

@router.get("")
async def get_admin(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    role = await access(session, user_id)
    named = lambda codes, names: [{"code": c, "name": names.get(c, c)} for c in codes]  # noqa: E731
    return {
        "role": role,
        "role_name": role_title(role),
        "is_super": role == ROLE_SUPER,
        "sections": [{"code": s, "title": clean_label(SECTION_TITLES[s])} for s in roles.visible_sections(role)],
        # Действия из карточки игрока — отдельные права (как кнопки карточки в боте).
        "player_rights": {
            "give": roles.allowed(role, SECTION_GIVE), "dev": roles.allowed(role, SECTION_DEV),
            "punish": roles.allowed(role, SECTION_PUNISH), "logs": roles.allowed(role, SECTION_LOGS),
        },
        "catalog": {
            "resources": [{"code": c, "name": clean_label(resource_label(c))} for c in RESOURCES],
            "ranks": list(RANK_LADDER),
            "dev_kinds": [
                {"kind": k, "title": tp.DEV_KIND_TITLES[k], "items": named(tp.DEV_CODES[k], tp.DEV_NAMES[k])} for k in DEV_KINDS
            ],
            "bloodlines": named(tp.BLOODLINE_CODES, tp.BLOODLINE_TITLES),
            "potentials": list(POTENTIAL_ORDER),
            "stats": [{"code": s, "name": tp.STAT_NAMES[s]} for s in STATS],
            "max_level": MAX_LEVEL,
            "awakening_max": AWAKENING_MAX,
            "phases": [{"code": p, "name": clean_label(PHASE_LABELS.get(p, p))} for p in PHASE_ORDER],
            "ban_durations": [{"code": k, "name": tp.BAN_DURATION_TITLES[k]} for k in BAN_DURATIONS],
            "ban_reason_max": BAN_REASON_MAX_LEN,
            "statist_take_percents": list(AST_TAKE_PERCENTS),
            "statist_add_amounts": list(AST_ADD_AMOUNTS),
            "statist_give_amounts": list(AST_GIVE_AMOUNTS),
            "mass_filters": [{"code": f, "name": clean_label(FILTER_LABELS[f])} for f in FILTERS],
            "mass_max_amount": MASS_GRANT_MAX_AMOUNT,
            "config_durations": [{"hours": h, "name": n} for h, n in CONFIG_DURATIONS],
            "ref_name_max": REF_NAME_MAX_LEN,
            "roles": [{"code": r, "name": role_title(r)} for r in ROLES],
            "event_kinds": [
                {
                    "key": key, "title": clean_label(EVENT_KIND_TITLES[key]),
                    "items": [
                        {"idx": i, "name": _event_names(kind).get(code, code)} for i, code in enumerate(events_admin.CODES_BY_KIND[kind])
                    ],
                }
                for key, kind in events_admin.KIND_BY_KEY.items()
            ],
        },
    }


def _event_names(kind: str) -> dict[str, str]:
    from bot.constant.event import EVENT_BOSS, EVENT_TEACHER

    return BOSS_NAMES if kind == EVENT_BOSS else TECHNIQUE_NAMES if kind == EVENT_TEACHER else SCHOOL_NAMES


# ---------------------------------------------------------------- бета и техрежим

class BetaIn(BaseModel):
    action: str  # enable | change | disable
    code: str | None = None  # пусто при enable/change — сгенерировать


async def _system_state(redis: Redis) -> dict:
    state = await beta.get_state(redis)
    return {
        "beta": {"code": state.code, "allowed": await beta.allowed_count(redis, state)} if state else None,
        "tech": bool(await redis.get(tech_mode_flag())),
    }


@router.get("/system")
async def get_system(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
) -> dict:
    await access(session, user_id, SECTION_SYSTEM)
    return await _system_state(redis)


@router.post("/system/tech")
async def post_tech(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
) -> dict:
    await access(session, user_id, SECTION_SYSTEM)
    from bot.texts.admin.admin import TECH_TOGGLED_OFF, TECH_TOGGLED_ON

    turned_off = bool(await redis.delete(tech_mode_flag()))
    if not turned_off:
        await redis.set(tech_mode_flag(), "1")
    return done(TECH_TOGGLED_OFF if turned_off else TECH_TOGGLED_ON)


@router.post("/system/beta")
async def post_beta(
    body: BetaIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await access(session, user_id, SECTION_SYSTEM)
    from bot.texts.admin.admin import (
        BETA_ALREADY_OFF, BETA_ALREADY_ON, BETA_CODE_CHANGED, BETA_DISABLED, BETA_ENABLED, CODE_TOO_LONG, CODE_TOO_SHORT,
    )

    if body.action == "disable":
        allowed = await beta.disable(redis)
        if allowed is None:
            raise bad(clean_label(BETA_ALREADY_OFF))
        return done(BETA_DISABLED.format(allowed=format_number(allowed)))
    if body.action not in ("enable", "change"):
        raise bad("Неизвестное действие.")
    try:
        code = beta.validate_code(body.code) if body.code else beta.generate_code()
    except beta.InvalidBetaCodeError as exc:
        raise bad(clean_label(CODE_TOO_SHORT if exc.reason == "too_short" else CODE_TOO_LONG))
    if body.action == "enable":
        result = await beta.enable(redis, code)
        if result is None:
            raise bad(clean_label(BETA_ALREADY_ON))
        return done(_strip_tags(BETA_ENABLED.format(code=result.code)))
    result = await beta.change_code(redis, code)
    if result is None:
        raise bad(clean_label(BETA_ALREADY_OFF))
    return done(_strip_tags(BETA_CODE_CHANGED.format(code=result.code)))


def _strip_tags(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text)


# ---------------------------------------------------------------- роли (супер-админ)

class RoleSetIn(BaseModel):
    query: str  # @ник или id
    role: str


class RoleRemoveIn(BaseModel):
    user_id: int


@router.get("/roles")
async def get_roles(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_ROLES)
    staff = await roles.list_staff(session)
    return {
        "supers": sorted(get_settings().admin_ids),
        "staff": [{"id": uid, "username": name, "role": role, "role_name": role_title(role)} for uid, name, role in staff],
    }


@router.post("/roles/set")
async def post_role_set(body: RoleSetIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_ROLES)
    from bot.texts.admin.roles_admin import SET_DONE_ALERT, SUPER_ALERT

    if body.role not in ROLES:
        raise bad("Неизвестная роль.")
    target = await players.find(session, body.query)
    if target is None:
        raise bad("Игрок не найден.")
    if target.id in get_settings().admin_ids:
        raise bad(clean_label(SUPER_ALERT))
    await roles.set_role(session, target.id, body.role)
    await audit.log(session, user_id, AUDIT_ROLE_SET, target.id, {"role": body.role})
    await session.commit()
    await notify(get_bot(), target.id, NOTIFY_SET.format(role=ROLE_NAMES[body.role]))
    return done(SET_DONE_ALERT)


@router.post("/roles/remove")
async def post_role_remove(body: RoleRemoveIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_ROLES)
    from bot.texts.admin.roles_admin import DEL_DONE_ALERT, SUPER_ALERT

    if body.user_id in get_settings().admin_ids:
        raise bad(clean_label(SUPER_ALERT))
    if not await roles.set_role(session, body.user_id, None):
        raise bad("Игрок не найден.")
    await audit.log(session, user_id, AUDIT_ROLE_REMOVE, body.user_id, {})
    await session.commit()
    await notify(get_bot(), body.user_id, NOTIFY_REMOVE)
    return done(DEL_DONE_ALERT)


# ---------------------------------------------------------------- настройки на лету (супер-админ)

class ConfigSetIn(BaseModel):
    key: str
    value: str
    hours: int = 0  # 0 — навсегда; только для ключей со сроком


class ConfigKeyIn(BaseModel):
    key: str


def _num(value) -> float | int:
    return value if isinstance(value, int) else float(value)


@router.get("/config")
async def get_config(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_CONFIG)
    keys = []
    for key, spec in live_config.LIVE_KEYS.items():
        entry = live_config.override(key)
        left = None
        if entry and entry[1] is not None:
            left = max(0, int((entry[1] - datetime.now(timezone.utc)).total_seconds()))
        keys.append({
            "key": key, "title": spec.title, "value": _num(live_config.get(key)), "default": _num(spec.default()),
            "min": _num(spec.min), "max": _num(spec.max), "integer": spec.type is int, "expiring": spec.expiring,
            "overridden": entry is not None, "left_seconds": left,
        })
    return {"keys": keys}


@router.post("/config/set")
async def post_config_set(body: ConfigSetIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_CONFIG)
    spec = live_config.LIVE_KEYS.get(body.key)
    if spec is None:
        raise bad("Неизвестная настройка.")
    value = live_config.validate(body.key, body.value)
    if value is None:
        raise bad(f"Нужно число от {spec.min:g} до {spec.max:g}.")
    hours = body.hours if spec.expiring else 0
    if hours not in dict(CONFIG_DURATIONS):
        raise bad("Неизвестный срок.")
    await live_config.set_value(session, user_id, body.key, value, hours)
    return done(f"{spec.title}: {value:g} — {dict(CONFIG_DURATIONS)[hours]}")


@router.post("/config/reset")
async def post_config_reset(body: ConfigKeyIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_CONFIG)
    from bot.texts.admin.live_config import RESET_DONE_ALERT

    if body.key not in live_config.LIVE_KEYS:
        raise bad("Неизвестная настройка.")
    await live_config.reset(session, user_id, body.key)
    return done(RESET_DONE_ALERT)


# ---------------------------------------------------------------- патч и вайп (супер-админ)

class PatchIn(BaseModel):
    kind: str  # patch | wipe


@router.get("/patch")
async def get_patch(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)
) -> dict:
    await access(session, user_id, SECTION_PATCH)
    from bot.cache.keys import patch_running_flag

    return {
        "start_coins": live_config.get("starting_nh_coins"), "start_tickets": live_config.get("starting_tickets"),
        "running": bool(await redis.exists(patch_running_flag())),
    }


@router.post("/patch/arm")
async def post_patch_arm(
    body: PatchIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Первое нажатие: подтверждение живёт 30 с (как в боте — два нажатия, не одно)."""
    await access(session, user_id, SECTION_PATCH)
    if body.kind not in (CONFIRM_KIND_PATCH, CONFIRM_KIND_WIPE):
        raise bad("Неизвестное действие.")
    await patch_service.arm(redis, body.kind, user_id)
    return done("Подтверди ещё раз в течение 30 секунд.")


@router.post("/patch/confirm")
async def post_patch_confirm(
    body: PatchIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await access(session, user_id, SECTION_PATCH)
    from bot.texts.admin.patch import ALREADY_RUNNING, EXPIRED_ALERT, WIPE_DONE

    if body.kind not in (CONFIRM_KIND_PATCH, CONFIRM_KIND_WIPE):
        raise bad("Неизвестное действие.")
    if not await patch_service.take(redis, body.kind, user_id):
        raise bad(clean_label(EXPIRED_ALERT))
    bot = get_bot()
    if body.kind == CONFIRM_KIND_WIPE:
        tables = await patch_service.wipe_database(session)
        # Журнал аудита тоже очищен вайпом — запись о самом вайпе уже после него.
        await audit.log(session, user_id, AUDIT_WIPE, None, {"tables": len(tables)})
        await session.commit()
        await live_config.load(session_factory)
        for uid in get_settings().admin_ids:
            await notify(bot, uid, WIPE_NOTIFY.format(admin=user_id))
        return done(_strip_tags(WIPE_DONE.format(n=len(tables))))
    if not await patch_service.try_start(redis):
        raise bad(clean_label(ALREADY_RUNNING))
    await audit.log(session, user_id, AUDIT_PATCH, None, {})
    await session.commit()

    async def job() -> None:
        try:
            count = await patch_service.season_patch(bot, session_factory)
            await notify(bot, user_id, PATCH_DONE.format(done=format_number(count)))
        except Exception as exc:  # отчёт инициатору, остальное — в лог
            log.exception("Patch failed")
            await notify(bot, user_id, PATCH_FAILED.format(done="?", error=type(exc).__name__))
        finally:
            await patch_service.finish(redis)

    background(job())
    return done("Патч запущен. Отчёт придёт в чат с ботом.")


# ---------------------------------------------------------------- статистика

@router.get("/stats/{tab}")
async def get_stats(
    tab: str, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await access(session, user_id, SECTION_STATS)
    if tab == "overview":
        return plain(await stats_svc.overview(session))
    if tab == "donate":
        data = plain(await stats_svc.donate(session))
        data["top"] = [{"user_id": u, "username": n, "total": t} for u, n, t in data["top"]]
        return data
    if tab == "economy":
        data = plain(await stats_svc.economy(session))
        data["biz"] = [{"type": t, "count": c} for t, c in data["biz"]]
        return data
    if tab == "server":
        return plain(await stats_svc.server(session, redis))
    raise bad("Неизвестная вкладка.")


# ---------------------------------------------------------------- журналы

@router.get("/logs/audit")
async def get_audit(
    admin_id: int | None = None, target_id: int | None = None, page: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
) -> dict:
    await access(session, user_id, SECTION_LOGS)
    rows, total = await audit.page(session, admin_id=admin_id, target_id=target_id, offset=page * ADMIN_AUDIT_PAGE, limit=ADMIN_AUDIT_PAGE)
    staff = {uid: name for uid, name, _ in await roles.list_staff(session)}
    for uid in get_settings().admin_ids:
        staff.setdefault(uid, None)
    return {
        "rows": [
            {"id": r.id, "admin_id": r.admin_id, "action": r.action, "target_id": r.target_id, "details": r.details, "created_at": r.created_at}
            for r in rows
        ],
        "total": total, "per_page": ADMIN_AUDIT_PAGE,
        "staff": [{"id": uid, "username": name} for uid, name in sorted(staff.items())],
    }


@router.get("/logs/{kind}")
async def get_log(
    kind: str, page: int = Query(0, ge=0), target_id: int | None = None,
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
) -> dict:
    await access(session, user_id, SECTION_LOGS)
    per, offset = ADMIN_AUDIT_PAGE, page * ADMIN_AUDIT_PAGE
    if kind == "payments":
        rows, total = await logs_svc.payments_page(session, user_id=target_id, offset=offset, limit=per)
        items = [{"user_id": u, "username": n, "rub": r, "coins": c, "created_at": t} for u, n, r, c, t in rows]
    elif kind == "clan":
        rows, total = await logs_svc.clan_purchases_page(session, offset=offset, limit=per)
        items = [{"clan": cl, "user_id": u, "username": n, "price": p, "created_at": t} for cl, u, n, p, t in rows]
    elif kind == "blackmarket":
        rows = await logs_svc.blackmarket_summary(session)
        items, total = [{"kind": k, "code": c, "buyers": b, "max_level": m} for k, c, b, m in rows], len(rows)
    elif kind == "activity":
        if target_id is None:
            raise bad("Нужен id игрока.")
        rows, total = await logs_svc.activity_page(session, target_id, offset=offset, limit=per)
        items = [{"kind": k, "text": clean_label(t), "created_at": ts} for k, t, ts in rows]
    else:
        raise bad("Неизвестный журнал.")
    return {"rows": plain(items), "total": total, "per_page": per}
