"""Статисты — стопки по (лагерь, ранг, звёзды, уровень тренировки) (сервис)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.characteristic import extra_unit_power, statist_unit_power
from bot.constant.characteristic import RANK_INDEX
from bot.constant.extra import CAMP_ATTACK, CAMP_DEFENSE, CAMPS, CONTRACT_SQUAD
from bot.db.repositories import card as card_repo
from bot.db.repositories import contract as contract_repo
from bot.db.repositories.extra import add_to_stack, get_stack_for_update, list_stacks
from bot.services.card import card_power
from bot.services.characteristic import strength_power_multiplier


class InvalidCampMoveError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Squad:
    """Отряд — все статисты игрока одного ранга, звёзд и уровня тренировки, в обоих
    лагерях сразу (в БД это две стопки: атака и защита). Единица ручной сборки лагерей —
    игрок видит, сколько таких бойцов где стоит, и перекидывает точное количество
    (запрос пользователя 2026-09-29: "чтобы игрок сам мог составлять оба лагеря")."""

    rank: str
    stars: int
    training_level: int
    unit_power: int
    attack: int
    defense: int
    school: str = ""
    school_level: int = 0

    @property
    def total(self) -> int:
        return self.attack + self.defense


async def recruit_into_stack(session: AsyncSession, user_id: int, rank: str) -> None:
    """Новый статист = +1 к стопке (атака, ранг, 0 звёзд, 0 уровень тренировки) —
    новички сразу в лагере атаки (подтверждено пользователем 2026-09-29). НЕ коммитит
    сама (правило 10, вызывается из `services/recruit`, тот коммитит один раз)."""
    await add_to_stack(session, user_id=user_id, camp=CAMP_ATTACK, rank=rank, quantity=1)


@dataclass(frozen=True, slots=True)
class CampStats:
    quantity: int
    power: int


@dataclass(frozen=True, slots=True)
class ArmyStats:
    total_quantity: int  # статисты + копии уников в армии
    total_power: int
    by_rank: list[tuple[str, int]]  # (ранг, количество) — только статисты, от лучшего ранга
    attack: CampStats
    defense: CampStats
    cards_quantity: int = 0  # копии уников в армии (без стоящих на позициях отряда)


async def get_army_stats(session: AsyncSession, user_id: int) -> ArmyStats:
    """Число стопок на игрока ограничено комбинаторикой (лагерь×ранг×звёзды×уровень
    тренировки), а не размером армии — даже при "сотнях миллиардов" статистов
    агрегация здесь работает над МАЛЫМ числом строк-стопок, не над единицами (правило 3)."""
    stacks = await list_stacks(session, user_id)

    by_rank_totals: dict[str, int] = {}
    camp_qty = {camp: 0 for camp in CAMPS}
    camp_power = {camp: 0 for camp in CAMPS}
    for s in stacks:
        unit_power = statist_unit_power(s.rank, s.stars, s.training_level, s.school, s.school_level)
        by_rank_totals[s.rank] = by_rank_totals.get(s.rank, 0) + s.quantity
        camp_qty[s.camp] += s.quantity
        camp_power[s.camp] += s.quantity * unit_power

    # Уники в армии бьются как статисты (подтверждено 2026-09-30) — их мощь входит в
    # мощь лагеря; уники на позициях отряда в бою не участвуют и сюда не попадают.
    cards_quantity = 0
    for c in await card_repo.list_stacks(session, user_id):
        cards_quantity += c.quantity
        camp_qty[c.camp] += c.quantity
        camp_power[c.camp] += c.quantity * card_power(c.card_code)
    # Контрактники — тоже бойцы своего лагеря, пока контракт действует.
    for k in await contract_repo.list_active(session, user_id):
        camp_qty[k.camp] += k.quantity
        camp_power[k.camp] += k.quantity * extra_unit_power(k.rank, 0, 0)

    # Сила игрока: +1% к мощи за ранг — та же поправка, что в бою (`load_camp`).
    multiplier = await strength_power_multiplier(session, user_id)
    if multiplier != 100:
        camp_power = {camp: power * multiplier // 100 for camp, power in camp_power.items()}

    by_rank = sorted(by_rank_totals.items(), key=lambda kv: RANK_INDEX[kv[0]], reverse=True)
    return ArmyStats(
        total_quantity=sum(camp_qty.values()),
        total_power=sum(camp_power.values()),
        by_rank=by_rank,
        attack=CampStats(quantity=camp_qty[CAMP_ATTACK], power=camp_power[CAMP_ATTACK]),
        defense=CampStats(quantity=camp_qty[CAMP_DEFENSE], power=camp_power[CAMP_DEFENSE]),
        cards_quantity=cards_quantity,
    )


async def list_squads(session: AsyncSession, user_id: int) -> list[Squad]:
    """Сильнейшие отряды — первыми (по мощи одного бойца). Число отрядов ограничено
    комбинаторикой ранг×звёзды×уровень тренировки, не размером армии."""
    by_key: dict[tuple[str, int, int, str, int], dict[str, int]] = {}
    for s in await list_stacks(session, user_id):
        key = (s.rank, s.stars, s.training_level, s.school, s.school_level)
        camps = by_key.setdefault(key, {camp: 0 for camp in CAMPS})
        camps[s.camp] += s.quantity
    squads = [
        Squad(
            rank=rank, stars=stars, training_level=level,
            unit_power=round(statist_unit_power(rank, stars, level, school, school_level)),
            attack=camps[CAMP_ATTACK], defense=camps[CAMP_DEFENSE], school=school, school_level=school_level,
        )
        for (rank, stars, level, school, school_level), camps in by_key.items()
    ]
    squads.sort(key=lambda sq: (sq.unit_power, RANK_INDEX[sq.rank]), reverse=True)
    return squads


async def list_army_squads(session: AsyncSession, user_id: int) -> list[Squad]:
    """Отряды экрана банды: свои статисты + контрактники (по рангу, метка `CONTRACT_SQUAD` в
    поле школы). Только для ручной сборки лагерей — роты, ячейки, биржа и казино берут
    `list_squads` (контрактников туда отдать нельзя)."""
    by_rank: dict[str, dict[str, int]] = {}
    for k in await contract_repo.list_active(session, user_id):
        by_rank.setdefault(k.rank, {camp: 0 for camp in CAMPS})[k.camp] += k.quantity
    contracts = [
        Squad(rank=rank, stars=0, training_level=0, unit_power=round(extra_unit_power(rank, 0, 0)),
              attack=camps[CAMP_ATTACK], defense=camps[CAMP_DEFENSE], school=CONTRACT_SQUAD)
        for rank, camps in by_rank.items()
    ]
    squads = await list_squads(session, user_id) + contracts
    squads.sort(key=lambda sq: (sq.unit_power, RANK_INDEX[sq.rank]), reverse=True)
    return squads


async def get_squad(
    session: AsyncSession, user_id: int, rank: str, stars: int, training_level: int, school: str = "", school_level: int = 0
) -> Squad | None:
    for squad in await list_army_squads(session, user_id):
        if (squad.rank, squad.stars, squad.training_level, squad.school, squad.school_level) == (
            rank, stars, training_level, school, school_level
        ):
            return squad
    return None


async def move_squad(
    session: AsyncSession,
    user_id: int,
    *,
    rank: str,
    stars: int,
    training_level: int,
    from_camp: str,
    to_camp: str,
    amount: int | None = None,
    percent: int | None = None,
    school: str = "",
    school_level: int = 0,
) -> int:
    """Переносит часть ОДНОГО отряда между лагерями: ровно `amount` бойцов (сколько есть,
    если просят больше) или `percent`% от того, что сейчас в `from_camp` ("половину"/"всех").
    Остаток читается под `FOR UPDATE` в той же транзакции, что и списание (правило 1) —
    доля/число считаются от актуального количества, не от того, что игрок видел на экране
    секунду назад (за это время тренировка/бой могли его изменить). Коммитит сама."""
    if from_camp not in CAMPS or to_camp not in CAMPS or from_camp == to_camp:
        raise InvalidCampMoveError
    if (amount is None) == (percent is None) or (amount is not None and amount <= 0) or (
        percent is not None and not 0 < percent <= 100
    ):
        raise InvalidCampMoveError

    if school == CONTRACT_SQUAD:
        moved = await _move_contracts(session, user_id, rank, from_camp, to_camp, amount, percent)
        await session.commit()
        return moved
    key = {
        "user_id": user_id, "rank": rank, "stars": stars, "training_level": training_level,
        "school": school, "school_level": school_level,
    }
    stack = await get_stack_for_update(session, camp=from_camp, **key)
    available = stack.quantity if stack is not None else 0
    moved = min(amount, available) if amount is not None else available * percent // 100
    if moved > 0:
        await add_to_stack(session, camp=from_camp, quantity=-moved, **key)
        await add_to_stack(session, camp=to_camp, quantity=moved, **key)
    await session.commit()
    return moved


async def _move_contracts(
    session: AsyncSession, user_id: int, rank: str | None, from_camp: str, to_camp: str, amount: int | None, percent: int | None
) -> int:
    """Перевести контрактников между лагерями: ровно `amount` (ранга `rank`) или `percent`% каждого
    контракта. Раньше истекающие — первыми; часть контракта расщепляется с тем же сроком. НЕ коммитит."""
    rows = [r for r in await contract_repo.list_active(session, user_id, camp=from_camp, for_update=True) if rank is None or r.rank == rank]
    moved_total = 0
    for row in rows:
        if amount is not None:
            count = min(row.quantity, amount - moved_total)
        else:
            count = row.quantity if percent == 100 else row.quantity * percent // 100
        if count <= 0:
            continue
        await contract_repo.move(session, row, to_camp, count)
        moved_total += count
        if amount is not None and moved_total >= amount:
            break
    return moved_total


async def move_between_camps(session: AsyncSession, user_id: int, from_camp: str, to_camp: str, percent: int) -> int:
    """Переводит `percent`% КАЖДОЙ стопки лагеря `from_camp` в `to_camp` — пропорционально,
    состав по рангам/звёздам сохраняется в обоих лагерях. Детерминированно (`qty *
    percent // 100`, 100% — ровно всё): игрок нажимает "перевести половину" и ждёт
    половину, не случайное число. Для совсем маленьких стопок часть процентов может
    дать 0 — тогда просто ничего не переносится из этой стопки. Коммитит сама —
    отдельная логическая операция, ни с чем не композируется. Возвращает, сколько
    статистов перенесено всего."""
    if from_camp not in CAMPS or to_camp not in CAMPS or from_camp == to_camp or not 0 < percent <= 100:
        raise InvalidCampMoveError
    stacks = await list_stacks(session, user_id, camp=from_camp, for_update=True)
    moved_total = 0
    for s in stacks:
        moved = s.quantity if percent == 100 else s.quantity * percent // 100
        if moved == 0:
            continue
        moved_total += moved
        key = {
            "user_id": user_id, "rank": s.rank, "stars": s.stars, "training_level": s.training_level,
            "school": s.school, "school_level": s.school_level,
        }
        await add_to_stack(session, camp=from_camp, quantity=-moved, **key)
        await add_to_stack(session, camp=to_camp, quantity=moved, **key)
    # Уники в армии распределяются по лагерям так же (подтверждено 2026-09-30) — быстрый
    # перевод доли армии двигает и их той же долей.
    for c in await card_repo.list_stacks(session, user_id, camp=from_camp, for_update=True):
        moved = c.quantity if percent == 100 else c.quantity * percent // 100
        if moved:
            moved_total += moved
            await card_repo.add_to_stack(session, user_id=user_id, card_code=c.card_code, camp=from_camp, quantity=-moved)
            await card_repo.add_to_stack(session, user_id=user_id, card_code=c.card_code, camp=to_camp, quantity=moved)
    moved_total += await _move_contracts(session, user_id, None, from_camp, to_camp, None, percent)
    await session.commit()
    return moved_total
