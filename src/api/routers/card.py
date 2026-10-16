"""API-роутер Mini App: уники банды — 9 позиций и коллекция (`services.card`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.routers._common import bad, clean_label, require_user
from bot.config.card import CARD_BY_CODE
from bot.constant.absolute import ABSOLUTES, STYLIST_CHOICES
from bot.services.absolute import StylistError, set_style_pick, style_pick
from bot.texts.absolute import PERKS, STYLIST_SET_ALERT
from bot.services.position_skill import card_skill_lines
from bot.texts.position_skill import KIND_LABELS
from bot.config.game import GANG_CAMP_MOVE_PERCENTS
from bot.constant.card import POSITIONS
from bot.services.card import (
    NoFreeCopyError,
    PositionEmptyError,
    PositionNotAllowedError,
    UnknownCardError,
    assign_position,
    get_collection,
    get_lineup,
    unassign_position,
)
from bot.texts.card import POSITION_DESCRIPTIONS, POSITION_LABELS, RARITY_LABELS

router = APIRouter(prefix="/api/cards", tags=["cards"])


class CardOut(BaseModel):
    code: str
    name: str
    rarity: str
    rarity_label: str
    power: int
    image: str | None


class SkillOut(BaseModel):
    code: str
    name: str
    kind: str
    kind_label: str
    text: str  # с числами редкости карты


class SlotOut(BaseModel):
    position: str
    label: str
    description: str
    card: CardOut | None
    skills: list[SkillOut] = []  # навыки карты на этой позиции


class CollectionCardOut(CardOut):
    attack: int
    defense: int
    free: int  # свободные копии в армии (можно поставить на позицию)
    placed: list[str]  # позиции, на которых стоит
    positions: list[str]  # допустимые позиции
    skills: dict[str, list[SkillOut]] = {}  # позиция → навыки карты на ней
    absolute_perk: str | None = None  # абсолют: пассивка за обладание


class CardsOut(BaseModel):
    slots: list[SlotOut]
    collection: list[CollectionCardOut]
    owned_total: int
    placed_total: int
    attack_total: int = 0
    defense_total: int = 0
    move_percents: list[int] = []
    stylist_pick: str | None = None  # перк, выбранный Стилистом
    stylist_choices: list[tuple[str, str]] = []  # (код, имя) абсолютов на выбор


class SetPositionIn(BaseModel):
    position: str
    card_code: str


class ClearPositionIn(BaseModel):
    position: str


class MessageOut(BaseModel):
    message: str


def _skills(card, position: str) -> list[SkillOut]:
    return [SkillOut(code=s.code, name=s.name, kind=s.kind, kind_label=KIND_LABELS[s.kind], text=s.text)
            for s in card_skill_lines(card, position)]


def _card(c) -> CardOut:
    return CardOut(
        code=c.code, name=c.name, rarity=c.rarity, rarity_label=RARITY_LABELS.get(c.rarity, c.rarity),
        power=c.power, image=c.image,
    )


@router.get("", response_model=CardsOut)
async def get_cards(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> CardsOut:
    user = await require_user(session, user_id, need_city=False)
    lineup = await get_lineup(session, user.id)
    collection = await get_collection(session, user.id)
    return CardsOut(
        slots=[
            SlotOut(
                position=p, label=clean_label(POSITION_LABELS[p]), description=POSITION_DESCRIPTIONS[p],
                card=_card(lineup[p]) if lineup[p] else None,
                skills=_skills(lineup[p], p) if lineup[p] else [],
            )
            for p in POSITIONS
        ],
        collection=[
            CollectionCardOut(
                **_card(e.card).model_dump(), attack=e.attack, defense=e.defense, free=e.army,
                placed=list(e.placed), positions=list(e.card.positions),
                skills={p: _skills(e.card, p) for p in e.card.positions},
                absolute_perk=PERKS.get(e.card.code) if e.card.code in ABSOLUTES else None,
            )
            for e in collection
        ],
        owned_total=sum(e.total for e in collection),
        placed_total=sum(1 for c in lineup.values() if c is not None),
        attack_total=sum(e.attack for e in collection),
        defense_total=sum(e.defense for e in collection),
        move_percents=list(GANG_CAMP_MOVE_PERCENTS),
        stylist_pick=await style_pick(session, user.id),
        stylist_choices=[(c, CARD_BY_CODE[c].name) for c in STYLIST_CHOICES],
    )


class StylistIn(BaseModel):
    code: str


@router.post("/stylist", response_model=MessageOut)
async def post_stylist(body: StylistIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> MessageOut:
    """Стилист выбирает перк любого абсолюта."""
    try:
        await set_style_pick(session, user_id, body.code)
    except StylistError:
        raise bad("Нужен Стилист, и перк — из списка абсолютов.")
    return MessageOut(message=STYLIST_SET_ALERT.format(name=CARD_BY_CODE[body.code].name))


class CardMoveIn(BaseModel):
    code: str
    from_camp: str
    amount: int | None = None  # None — все копии карты в этом лагере


@router.post("/move-card", response_model=MessageOut)
async def move_card(
    body: CardMoveIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MessageOut:
    """Копии одной карты между лагерями — тот же `move_copies`, что кнопки карточки в боте
    (до 2026-10-12 в Mini App перенести уника из защиты обратно было нельзя)."""
    from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
    from bot.services.card import InvalidCampMoveError, move_copies

    user = await require_user(session, user_id, need_city=False)
    to_camp = CAMP_DEFENSE if body.from_camp == CAMP_ATTACK else CAMP_ATTACK
    try:
        moved = await move_copies(session, user.id, body.code, body.from_camp, to_camp, body.amount)
    except InvalidCampMoveError:
        raise bad("Некорректный перенос.")
    if not moved:
        raise bad("В этом лагере нет копий этой карты.")
    where = "в защиту" if to_camp == CAMP_DEFENSE else "в атаку"
    return MessageOut(message=f"Перенесено {where}: {moved}")


class CampMoveIn(BaseModel):
    from_camp: str
    percent: int


@router.post("/move", response_model=MessageOut)
async def move_cards(
    body: CampMoveIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MessageOut:
    """Доля ВСЕХ уников лагеря `from_camp` в другой лагерь (как быстрый перевод статистов)."""
    from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE
    from bot.services.card import move_all_copies
    from bot.services.card import InvalidCampMoveError

    user = await require_user(session, user_id, need_city=False)
    to_camp = CAMP_DEFENSE if body.from_camp == CAMP_ATTACK else CAMP_ATTACK
    try:
        moved = await move_all_copies(session, user.id, body.from_camp, to_camp, body.percent)
    except InvalidCampMoveError:
        raise bad("Некорректный перевод.")
    if not moved:
        raise bad("Нечего переводить — в этом лагере нет уников (или их слишком мало для этой доли).")
    where = "в защиту" if to_camp == CAMP_DEFENSE else "в атаку"
    return MessageOut(message=f"Уников переведено {where}: {moved}")


@router.post("/position", response_model=MessageOut)
async def set_position(
    body: SetPositionIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    user = await require_user(session, user_id, need_city=False)
    if body.position not in POSITIONS:
        raise bad("Неизвестная позиция.")
    try:
        replaced = await assign_position(session, user.id, body.position, body.card_code)
    except (UnknownCardError, PositionNotAllowedError):
        raise bad("Эта карта не подходит на выбранную позицию.")
    except NoFreeCopyError:
        raise bad("Нет свободной копии: все копии карты уже стоят на позициях.")
    label = clean_label(POSITION_LABELS[body.position])
    lineup = await get_lineup(session, user.id)
    current = lineup[body.position]
    name = current.name if current else body.card_code
    text = f"{name} назначен: {label}"
    if replaced is not None:
        text += f" (вместо {replaced.name})"
    return MessageOut(message=text)


@router.post("/position/clear", response_model=MessageOut)
async def clear_position(
    body: ClearPositionIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    user = await require_user(session, user_id, need_city=False)
    if body.position not in POSITIONS:
        raise bad("Неизвестная позиция.")
    try:
        card = await unassign_position(session, user.id, body.position)
    except PositionEmptyError:
        raise bad("Позиция уже свободна.")
    return MessageOut(message=f"{card.name if card else 'Карта'} снят с позиции {clean_label(POSITION_LABELS[body.position])}")
