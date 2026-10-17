"""Админ-панель в Mini App — разделы мира и контента: рассылка и массовая выдача, промокоды,
реферальные кампании, события карты, мир (города/районы/императоры), кланы, сезон пасса и задания.
Те же сервисы, права и аудит, что у хендлеров бота `handlers/admin/*` — своей логики здесь нет.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session, session_factory
from api.push import get_bot
from api.routers._common import bad, clean_label
from api.routers.admin import access, background, done
from bot.constant.admin import (
    SECTION_CLANS,
    SECTION_EVENTS,
    SECTION_MASS,
    SECTION_PROMO,
    SECTION_REFERRAL,
    SECTION_SEASON,
    SECTION_WORLD,
)
from bot.constant.admin.mass import BROADCAST_CAPTION_LIMIT, BROADCAST_TEXT_LIMIT, FILTERS, FLT_CLAN, MASS_GRANT_MAX_AMOUNT
from bot.constant.referral import REF_NAME_MAX_LEN
from bot.constant.resource import RESOURCES
from bot.db.repositories import district as district_repo
from bot.services import promo as promo_service
from bot.services import referral as referral_service
from bot.services.admin import audit, players
from bot.services.admin import clans_admin
from bot.services.admin import events_admin
from bot.services.admin import mass as mass_service
from bot.services.admin import season_admin
from bot.services.admin import world as world_svc
from bot.texts.admin.mass import BROADCAST_FAILED, BROADCAST_REPORT, FILTER_LABELS
from bot.texts.dev_quest import TASK_LABELS
from bot.texts.resource import amount_label
from bot.utils.formatting import format_number
from bot.utils.notify import notify

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _player_label(user) -> str:
    return world_svc.player_label(user)


# ---------------------------------------------------------------- рассылка и массовая выдача

class AudienceIn(BaseModel):
    filter: str
    clan: str | None = None  # для фильтра «клан» — название или id


class BroadcastIn(AudienceIn):
    text: str = ""
    photo_url: str | None = None  # картинка по ссылке (в боте — фото сообщением)
    button: str | None = None  # «текст | https://ссылка»
    preview: bool = False  # True — только прислать предпросмотр в чат с ботом


class GrantIn(AudienceIn):
    resource: str
    amount: int


async def _audience(session: AsyncSession, body: AudienceIn) -> tuple[mass_service.Audience, str]:
    if body.filter not in FILTERS:
        raise bad("Неизвестный фильтр.")
    label = clean_label(FILTER_LABELS[body.filter])
    if body.filter != FLT_CLAN:
        return mass_service.Audience(body.filter), label
    clan = await mass_service.find_clan(session, body.clan or "")
    if clan is None:
        raise bad("Клан не найден.")
    return mass_service.Audience(body.filter, clan.id), f"{label}: {clan.name}"


@router.get("/mass/count")
async def get_mass_count(
    filter: str, clan: str | None = None, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_MASS)
    aud, label = await _audience(session, AudienceIn(filter=filter, clan=clan))
    return {"count": await mass_service.count_audience(session, aud), "audience": label}


def _content(body: BroadcastIn) -> mass_service.Content:
    text = body.text.strip()
    photo = (body.photo_url or "").strip() or None
    if photo and not photo.startswith(("https://", "http://")):
        raise bad("Картинка — ссылкой https://…")
    limit = BROADCAST_CAPTION_LIMIT if photo else BROADCAST_TEXT_LIMIT
    if (not text and not photo) or len(text) > limit:
        raise bad(f"Нужен текст (до {limit} символов) или картинка.")
    btn_text = btn_url = None
    if body.button and body.button.strip():
        parsed = mass_service.parse_button(body.button)
        if parsed is None:
            raise bad("Кнопка: «текст | https://ссылка».")
        btn_text, btn_url = parsed
    return mass_service.Content(text=text, photo=photo, btn_text=btn_text, btn_url=btn_url)


@router.post("/mass/broadcast")
async def post_broadcast(body: BroadcastIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_MASS)
    aud, label = await _audience(session, body)
    content = _content(body)
    bot = get_bot()
    if body.preview:
        try:
            await mass_service.send_content(bot, user_id, content)
        except Exception as exc:  # noqa: BLE001 — кривой HTML / недоступная картинка
            raise bad(f"Telegram не принял сообщение: {exc}")
        return done("Предпросмотр отправлен в чат с ботом.")
    count = await mass_service.count_audience(session, aud)
    await audit.log(
        session, user_id, "mass_broadcast", None,
        {**mass_service.audience_details(aud), "recipients": count, "photo": bool(content.photo), "text": content.text[:200]},
    )
    await session.commit()

    async def job() -> None:
        try:
            sent, failed = await mass_service.run_broadcast(bot, session_factory, aud, content)
        except Exception:
            log.exception("Broadcast failed")
            await notify(bot, user_id, BROADCAST_FAILED)
            return
        await notify(bot, user_id, BROADCAST_REPORT.format(audience=label, sent=sent, failed=failed))

    background(job())
    return done(f"Рассылка запущена: {format_number(count)} получателей. Отчёт придёт в чат с ботом.")


@router.post("/mass/grant")
async def post_grant(body: GrantIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_MASS)
    aud, _ = await _audience(session, body)
    if body.resource not in RESOURCES:
        raise bad("Неизвестный ресурс.")
    if not 0 < body.amount <= MASS_GRANT_MAX_AMOUNT:
        raise bad(f"Количество от 1 до {format_number(MASS_GRANT_MAX_AMOUNT)}.")
    affected = await mass_service.mass_grant(session, user_id, aud, body.resource, body.amount)
    return done(f"Выдано {amount_label(body.resource, body.amount)} — игроков: {format_number(affected)}.")


# ---------------------------------------------------------------- промокоды

class PromoCreateIn(BaseModel):
    line: str  # тот же формат одной строкой, что в боте


class PromoToggleIn(BaseModel):
    active: bool


def _promo(p) -> dict:
    return {
        "id": p.id, "code": p.code, "reward": [{"code": k, "amount": v, "label": amount_label(k, abs(v))} for k, v in p.reward.items()],
        "max_uses": p.max_uses, "used": p.used_count, "expires_at": p.expires_at, "users": p.allowed_usernames,
        "active": p.is_active, "alive": promo_service.is_alive(p), "created_at": p.created_at,
    }


@router.get("/promo")
async def get_promos(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_PROMO)
    return {"items": [_promo(p) for p in await promo_service.list_recent(session)], "resources": list(RESOURCES)}


@router.post("/promo")
async def post_promo_create(body: PromoCreateIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_PROMO)
    from bot.texts.admin.promo_admin import CODE_TAKEN, FORMAT_ERROR

    try:
        promo = await promo_service.create(session, user_id, promo_service.parse_create(body.line))
    except promo_service.PromoFormatError:
        raise bad(clean_label(FORMAT_ERROR))
    except promo_service.PromoCodeTakenError:
        raise bad(clean_label(CODE_TAKEN))
    return done(f"Промокод {promo.code} создан.", item=_promo(promo))


@router.post("/promo/{promo_id}/active")
async def post_promo_toggle(
    promo_id: int, body: PromoToggleIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_PROMO)
    if not await promo_service.set_active(session, user_id, promo_id, body.active):
        raise bad("Промокод не найден.")
    return done("Промокод включён." if body.active else "Промокод выключен.")


@router.post("/promo/{promo_id}/delete")
async def post_promo_delete(promo_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_PROMO)
    if not await promo_service.delete(session, user_id, promo_id):
        raise bad("Промокод не найден.")
    return done("Промокод удалён.")


# ---------------------------------------------------------------- реферальные кампании

class RefCreateIn(BaseModel):
    name: str


@router.get("/referral")
async def get_referrals(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_REFERRAL)
    username = (await get_bot().get_me()).username
    items = []
    for link, visits in await referral_service.list_campaigns(session):
        items.append({
            "id": link.id, "name": link.name, "code": link.code, "visits": visits, "created_at": link.created_at,
            "link": referral_service.deep_link(username, link.code), "stats": await referral_service.stats(session, link.id),
        })
    return {"items": items, "name_max": REF_NAME_MAX_LEN}


@router.post("/referral")
async def post_referral(body: RefCreateIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_REFERRAL)
    name = body.name.strip()
    if not name or len(name) > REF_NAME_MAX_LEN:
        raise bad(f"Название от 1 до {REF_NAME_MAX_LEN} символов.")
    link = await referral_service.create_campaign(session, user_id, name)
    username = (await get_bot().get_me()).username
    return done(f"Кампания «{name}» создана.", link=referral_service.deep_link(username, link.code))


@router.post("/referral/{link_id}/delete")
async def post_referral_delete(link_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_REFERRAL)
    if not await referral_service.delete_campaign(session, user_id, link_id):
        raise bad("Кампания не найдена.")
    return done("Кампания удалена.")


# ---------------------------------------------------------------- события карты

class SpawnIn(BaseModel):
    kind: str  # ключ вида из справочника (b/t/s)
    idx: int
    push: bool = True


def _event_title(kind: str, code: str) -> str:
    from api.routers.admin import _event_names

    return _event_names(kind).get(code, code)


@router.get("/events")
async def get_events(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_EVENTS)
    from bot.texts.admin.events_admin import KIND_NAMES

    rows = await events_admin.list_active(session)
    items = []
    for e in rows:
        full = await events_admin.get_active(session, e.id)
        items.append({
            "id": e.id, "kind": e.kind, "kind_name": clean_label(KIND_NAMES.get(e.kind, e.kind)), "title": _event_title(e.kind, e.code),
            "left_seconds": e.left_seconds, "clan_id": e.clan_id, "entries": full.entries if full else 0,
        })
    return {"items": items}


@router.post("/events/{event_id}/remove")
async def post_event_remove(event_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_EVENTS)
    if not await events_admin.remove(session, user_id, event_id):
        raise bad("Событие уже закончилось.")
    return done("Событие снято.")


@router.post("/events/spawn")
async def post_event_spawn(body: SpawnIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_EVENTS)
    spawned = await events_admin.spawn_now(session, user_id, body.kind, body.idx)
    if spawned is None:
        raise bad("Такое событие уже идёт.")
    if body.push:
        from bot.handlers.event import send_spawn_pushes
        from bot.handlers.school import school_push_text
        from bot.handlers.unique_technique import teacher_push_text

        background(send_spawn_pushes(get_bot(), session_factory, [spawned], lambda e: teacher_push_text(e) or school_push_text(e)))
    return done("Событие запущено, игрокам ушли пуши." if body.push else "Событие запущено без пушей.")


# ---------------------------------------------------------------- мир: города, районы, императоры

class QueryIn(BaseModel):
    query: str


def _owner(row) -> str | None:
    if row.owner_id is None:
        return None
    return f"{row.owner_gang or row.owner_name or 'id' + str(row.owner_id)} (id{row.owner_id})"


@router.get("/world/cities")
async def get_cities(q: str, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_WORLD)
    cities = await world_svc.find_cities(session, q)
    return {"items": [{"id": c.id, "name": c.name, "country": c.country_code} for c in cities]}


@router.get("/world/cities/{city_id}")
async def get_city(city_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_WORLD)
    view = await world_svc.city_view(session, city_id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Город не найден.")
    wars = await world_svc.pending_wars_of(session, view.emperor.id) if view.emperor else 0
    districts = []
    for r in view.districts:
        ch = await world_svc.district_pending(session, r.id)
        districts.append({
            "id": r.id, "number": r.number, "owner_id": r.owner_id, "owner": _owner(r),
            "challenge": {"attacker_id": ch.attacker_id, "defender_id": ch.defender_id} if ch else None,
        })
    return {
        "id": view.city.id, "name": view.city.name, "country": view.city.country_code,
        "emperor": {"id": view.emperor.id, "label": _player_label(view.emperor)} if view.emperor else None,
        "pending_challenges": view.pending_challenges, "pending_wars": wars, "districts": districts,
    }


@router.post("/world/districts/{district_id}/owner")
async def post_district_owner(
    district_id: int, body: QueryIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_WORLD)
    user = await players.find(session, body.query)
    if user is None:
        raise bad("Игрок не найден.")
    result = await world_svc.set_district_owner(session, user_id, district_id, user)
    if result == "same":
        raise bad("Этот игрок уже владеет районом.")
    if result != "ok":
        raise bad("Район не найден.")
    return done(f"Район передан: {_player_label(user)}.")


@router.post("/world/districts/{district_id}/reset")
async def post_district_reset(district_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_WORLD)
    row = await district_repo.get_row(session, district_id)
    if row is None:
        raise bad("Район не найден.")
    if row.owner_id is None:
        raise bad("Район и так у ботов.")
    await world_svc.reset_district(session, user_id, district_id)
    return done("Район возвращён ботам.")


@router.post("/world/cities/{city_id}/emperor")
async def post_set_emperor(
    city_id: int, body: QueryIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_WORLD)
    user = await players.find(session, body.query)
    if user is None:
        raise bad("Игрок не найден.")
    if not await world_svc.set_emperor(session, user_id, city_id, user):
        raise bad("Не получилось — данные устарели, обнови экран.")
    return done(f"Император назначен: {_player_label(user)}.")


@router.post("/world/cities/{city_id}/emperor/remove")
async def post_remove_emperor(city_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_WORLD)
    if not await world_svc.remove_emperor(session, user_id, city_id):
        raise bad("У города нет императора.")
    return done("Император снят.")


@router.post("/world/cities/{city_id}/challenges/cancel")
async def post_cancel_challenges(city_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_WORLD)
    n = await world_svc.cancel_city_challenges(session, user_id, city_id)
    return done(f"Отменено вызовов: {n}.")


@router.post("/world/cities/{city_id}/wars/cancel")
async def post_cancel_wars(city_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_WORLD)
    view = await world_svc.city_view(session, city_id)
    if view is None or view.emperor is None:
        raise bad("У города нет императора.")
    n = await world_svc.cancel_emperor_wars(session, user_id, view.emperor.id)
    return done(f"Отменено войн: {n}.")


# ---------------------------------------------------------------- кланы

class ClanValueIn(BaseModel):
    field: str  # lands | treasury | donate
    value: int


class ClanTransferIn(BaseModel):
    user_id: int


@router.get("/clans")
async def get_clans(q: str, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_CLANS)
    return {"items": [{"id": c.id, "name": c.name} for c in await clans_admin.find(session, q)]}


@router.get("/clans/{clan_id}")
async def get_clan(clan_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_CLANS)
    card = await clans_admin.card(session, clan_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клан не найден.")
    c = card.clan
    return {
        "id": c.id, "name": c.name, "owner_id": c.owner_id, "owner": card.owner_label, "lands": c.lands, "treasury": c.treasury,
        "donate_level": c.donate_level, "power": card.power, "shield_seconds": card.shield, "cooldown_seconds": card.cooldown,
        "buyers": card.buyers, "paid": card.paid,
        "members": [{"id": uid, "rank": rank, "label": label} for uid, rank, label in card.members],
        "limits": {"lands_min": clans_admin.LANDS_MIN, "lands_max": clans_admin.LANDS_MAX, "donate_max": clans_admin.DONATE_MAX},
    }


@router.post("/clans/{clan_id}/value")
async def post_clan_value(
    clan_id: int, body: ClanValueIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_CLANS)
    if body.field == "lands":
        if not await clans_admin.set_lands(session, user_id, clan_id, body.value):
            raise bad(f"Земель от {clans_admin.LANDS_MIN} до {clans_admin.LANDS_MAX}.")
        return done(f"Земель: {body.value}.")
    if body.field == "treasury":
        new = await clans_admin.change_treasury(session, user_id, clan_id, body.value)
        if new is None:
            raise bad("В казне нет столько.")
        return done(f"Казна {body.value:+d} — стало {format_number(new)}.")
    if body.field == "donate":
        if not await clans_admin.set_donate_level(session, user_id, clan_id, body.value):
            raise bad(f"Уровень от 0 до {clans_admin.DONATE_MAX}.")
        return done(f"Уровень клана: {body.value}.")
    raise bad("Неизвестное поле.")


@router.post("/clans/{clan_id}/transfer")
async def post_clan_transfer(
    clan_id: int, body: ClanTransferIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_CLANS)
    if not await clans_admin.transfer_owner(session, user_id, clan_id, body.user_id):
        raise bad("Передать нельзя: игрок не в этом клане или уже владелец.")
    return done("Владелец клана сменён.")


@router.post("/clans/{clan_id}/{action}")
async def post_clan_action(
    clan_id: int, action: str, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    await access(session, user_id, SECTION_CLANS)
    if action == "shield":
        ok, text = await clans_admin.remove_shield(session, user_id, clan_id), "Щит снят."
    elif action == "cooldown":
        ok, text = await clans_admin.remove_cooldown(session, user_id, clan_id), "КД войны снят."
    elif action == "delete":
        result = await clans_admin.delete_clan(session, user_id, clan_id)
        if result is None:
            raise bad("Клан не найден.")
        return done(f"Клан «{result[0]}» удалён. Возвращено донатерам: {format_number(result[2])}.", deleted=True)
    else:
        raise bad("Неизвестное действие.")
    if not ok:
        raise bad("Нечего снимать.")
    return done(text)


# ---------------------------------------------------------------- сезон пасса и задания

class XpIn(BaseModel):
    delta: int


class SlotIn(BaseModel):
    slot: int | None = None  # только для «quest»


@router.get("/season")
async def get_season(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SEASON)
    info = await season_admin.season_info(session)
    await session.commit()  # сезон мог открыться при чтении
    s = info.season
    return {"number": s.number, "starts_at": s.starts_at, "ends_at": s.ends_at, "premium": info.premium, "left_seconds": info.left_seconds}


@router.post("/season/new")
async def post_season_new(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SEASON)
    number = await season_admin.start_new_season(session, user_id)
    return done(f"Начат сезон №{number}.")


@router.get("/season/players/{uid}")
async def get_season_player(uid: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SEASON)
    user = await players.get_by_id(session, uid)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Игрок не найден.")
    p = await season_admin.pass_info(session, uid)
    q = await season_admin.quest_status(session, uid)
    await session.commit()  # строка пасса / набор заданий могли создаться при чтении
    return {
        "id": uid, "label": _player_label(user), "xp": p.xp, "level": p.level, "premium": p.premium,
        "claimed_free": p.claimed_free, "claimed_premium": p.claimed_premium,
        "quests": [
            {"slot": x.slot, "task": clean_label(TASK_LABELS.get(x.task, x.task)), "progress": x.progress, "target": x.target, "xp": x.xp, "done": x.done}
            for x in q.quests
        ],
    }


@router.post("/season/players/{uid}/xp")
async def post_season_xp(uid: int, body: XpIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await access(session, user_id, SECTION_SEASON)
    if not body.delta:
        raise bad("Нужно ненулевое число.")
    xp = await season_admin.give_xp(session, user_id, uid, body.delta)
    if xp is None:
        raise bad("Игрок не найден.")
    return done(f"Опыт пасса {body.delta:+d} — стало {format_number(xp)}.")


@router.post("/season/players/{uid}/{action}")
async def post_season_action(
    uid: int, action: str, body: SlotIn = SlotIn(), user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await access(session, user_id, SECTION_SEASON)
    if action == "premium":
        on = await season_admin.toggle_premium(session, user_id, uid)
        return done("Премиум пасса включён." if on else "Премиум пасса выключен.")
    if action == "reset":
        await season_admin.reset_claims(session, user_id, uid)
        return done("Полученные награды пасса сброшены.")
    if action == "quest":
        if body.slot is None or not await season_admin.complete_quest(session, user_id, uid, body.slot):
            raise bad("Задание уже выполнено.")
        return done("Задание засчитано.")
    if action == "reroll":
        await season_admin.reroll_set(session, user_id, uid)
        return done("Набор заданий обновлён.")
    raise bad("Неизвестное действие.")
