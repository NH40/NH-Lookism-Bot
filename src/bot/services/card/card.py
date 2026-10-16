"""Уникальные персонажи — коллекция, распределение по лагерям, позиции отряда (сервис).

Модель подтверждена пользователем 2026-09-30 (`docs/design/unique_characters.md`, раздел 0):

- копии карты вне отряда — армия: стопки по лагерям (`card_stacks`), бьются и гибнут в бою
  вместе со статистами (боевой движок видит их как стопку «мощь карты × количество»);
- копия на позиции (`card_positions`) изъята из армии: не бьётся и не гибнет, работает
  навыком позиции (навыки подключатся, когда пользователь утвердит таблицу);
- одна копия — одна позиция; карта с двумя позициями встанет на обе, только если копий две;
- поставить на позицию можно только карту, у которой эта позиция в списке допустимых.

Все операции записи — одна транзакция с `FOR UPDATE` на затронутых строках, коммит один раз
в конце (правило 10); двойной клик не создаст и не потеряет копию.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.card import CARD_BY_CODE, CardDef
from bot.constant.card import POSITIONS, RARITY_INDEX
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE, CAMPS
from bot.db.repositories import card as card_repo


class UnknownCardError(Exception):
    pass


class PositionNotAllowedError(Exception):
    pass


class NoFreeCopyError(Exception):
    """Все копии карты уже стоят на позициях (или погибли) — ставить нечего."""


class PositionEmptyError(Exception):
    pass


class InvalidCampMoveError(Exception):
    pass


def card_power(code: str) -> int:
    """Мощь одной копии; карта, убранная из конфига, в бою весит 0 (не падаем)."""
    card = CARD_BY_CODE.get(code)
    return card.power if card else 0


@dataclass(frozen=True, slots=True)
class CollectionEntry:
    card: CardDef
    attack: int
    defense: int
    placed: tuple[str, ...]  # позиции, на которых стоит эта карта

    @property
    def army(self) -> int:
        return self.attack + self.defense

    @property
    def total(self) -> int:
        return self.army + len(self.placed)


async def get_collection(session: AsyncSession, user_id: int) -> list[CollectionEntry]:
    """Все карты игрока (армия + позиции) — два запроса по малым таблицам игрока, сборка в
    Python (строк не больше, чем карт в каталоге × 2 лагеря). Сильнейшие — сверху."""
    camps: dict[str, dict[str, int]] = {}
    for s in await card_repo.list_stacks(session, user_id):
        camps.setdefault(s.card_code, {c: 0 for c in CAMPS})[s.camp] += s.quantity
    placed: dict[str, list[str]] = {}
    for p in await card_repo.list_positions(session, user_id):
        placed.setdefault(p.card_code, []).append(p.position)

    entries = []
    for code in camps.keys() | placed.keys():
        card = CARD_BY_CODE.get(code)
        if card is None:
            continue
        c = camps.get(code, {CAMP_ATTACK: 0, CAMP_DEFENSE: 0})
        order = sorted(placed.get(code, []), key=POSITIONS.index)
        entries.append(CollectionEntry(card, c[CAMP_ATTACK], c[CAMP_DEFENSE], tuple(order)))
    entries.sort(key=lambda e: (RARITY_INDEX[e.card.rarity], e.card.power), reverse=True)
    return entries


async def get_entry(session: AsyncSession, user_id: int, code: str) -> CollectionEntry | None:
    return next((e for e in await get_collection(session, user_id) if e.card.code == code), None)


async def get_lineup(session: AsyncSession, user_id: int) -> dict[str, CardDef | None]:
    """Состав отряда: позиция → карта (None — пусто), во всех 9 позициях по порядку."""
    lineup: dict[str, CardDef | None] = {p: None for p in POSITIONS}
    for p in await card_repo.list_positions(session, user_id):
        if p.position in lineup:
            lineup[p.position] = CARD_BY_CODE.get(p.card_code)
    return lineup


async def eligible_for_position(session: AsyncSession, user_id: int, position: str) -> list[CollectionEntry]:
    """Карты, которые можно поставить на позицию: позиция в списке допустимых и есть свободная
    копия в армии ИЛИ карта стоит на другой позиции (тогда она переезжает, 2026-10-12)."""
    return [
        e for e in await get_collection(session, user_id)
        if position in e.card.positions and position not in e.placed and (e.army > 0 or e.placed)
    ]


async def move_copies(
    session: AsyncSession, user_id: int, code: str, from_camp: str, to_camp: str, amount: int | None
) -> int:
    """Перенос копий карты между лагерями (`amount=None` — все). Коммитит сама."""
    if from_camp not in CAMPS or to_camp not in CAMPS or from_camp == to_camp or (amount is not None and amount <= 0):
        raise InvalidCampMoveError
    stack = await card_repo.get_stack_for_update(session, user_id=user_id, card_code=code, camp=from_camp)
    available = stack.quantity if stack else 0
    moved = available if amount is None else min(amount, available)
    if moved:
        await card_repo.add_to_stack(session, user_id=user_id, card_code=code, camp=from_camp, quantity=-moved)
        await card_repo.add_to_stack(session, user_id=user_id, card_code=code, camp=to_camp, quantity=moved)
    await session.commit()
    return moved


async def move_all_copies(session: AsyncSession, user_id: int, from_camp: str, to_camp: str, percent: int) -> int:
    """Быстрый перевод уников (пользователь 2026-10-12: «такие же кнопки, как у статистов»):
    `percent`% копий КАЖДОЙ карты лагеря `from_camp` (100 — все) в `to_camp`. Только уники —
    статисты не двигаются. Стопки под `FOR UPDATE`, доля — от актуального количества. Коммитит."""
    if from_camp not in CAMPS or to_camp not in CAMPS or from_camp == to_camp or not 0 < percent <= 100:
        raise InvalidCampMoveError
    moved_total = 0
    for c in await card_repo.list_stacks(session, user_id, camp=from_camp, for_update=True):
        moved = c.quantity if percent == 100 else c.quantity * percent // 100
        if moved:
            moved_total += moved
            await card_repo.add_to_stack(session, user_id=user_id, card_code=c.card_code, camp=from_camp, quantity=-moved)
            await card_repo.add_to_stack(session, user_id=user_id, card_code=c.card_code, camp=to_camp, quantity=moved)
    await session.commit()
    return moved_total


async def _take_army_copy(session: AsyncSession, user_id: int, code: str) -> bool:
    """Изымает одну копию из армии — сначала из лагеря защиты, потом из атаки (атака —
    основная ударная сила, её трогаем в последнюю очередь). НЕ коммитит."""
    for camp in (CAMP_DEFENSE, CAMP_ATTACK):
        stack = await card_repo.get_stack_for_update(session, user_id=user_id, card_code=code, camp=camp)
        if stack is not None and stack.quantity > 0:
            await card_repo.add_to_stack(session, user_id=user_id, card_code=code, camp=camp, quantity=-1)
            return True
    return False


async def assign_position(session: AsyncSession, user_id: int, position: str, code: str) -> CardDef | None:
    """Ставит копию карты на позицию. Если там стояла другая карта — она возвращается в
    армию (лагерь атаки) и её CardDef возвращается вызывающему. Свободной копии в армии нет, но
    карта стоит на другой позиции — она переезжает оттуда (пользователь 2026-10-12: «можно снять,
    переставить на другую позицию, а на эту поставить другую»). Коммитит сама."""
    card = CARD_BY_CODE.get(code)
    if card is None:
        raise UnknownCardError
    if position not in POSITIONS or position not in card.positions:
        raise PositionNotAllowedError

    current = await card_repo.get_position_for_update(session, user_id, position)
    if current is not None and current.card_code == code:
        return None  # уже стоит — ничего не делаем (двойной клик)
    if not await _take_army_copy(session, user_id, code):
        other = next(
            (p.position for p in await card_repo.list_positions(session, user_id) if p.card_code == code and p.position != position),
            None,
        )
        if other is None:
            raise NoFreeCopyError
        await card_repo.get_position_for_update(session, user_id, other)
        await card_repo.delete_position(session, user_id, other)

    replaced = None
    if current is not None:
        await card_repo.add_to_stack(session, user_id=user_id, card_code=current.card_code, camp=CAMP_ATTACK, quantity=1)
        replaced = CARD_BY_CODE.get(current.card_code)
    await card_repo.set_position(session, user_id, position, code)
    await session.commit()
    return replaced


async def unassign_position(session: AsyncSession, user_id: int, position: str) -> CardDef:
    """Снимает карту с позиции — копия возвращается в армию (лагерь атаки). Коммитит сама."""
    current = await card_repo.get_position_for_update(session, user_id, position)
    if current is None:
        raise PositionEmptyError
    await card_repo.add_to_stack(session, user_id=user_id, card_code=current.card_code, camp=CAMP_ATTACK, quantity=1)
    await card_repo.delete_position(session, user_id, position)
    await session.commit()
    return CARD_BY_CODE.get(current.card_code)
