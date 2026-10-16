"""Тренировка техники — путь к каждому уровню уникальной техники (сервис).

Пользователь 2026-10-12: «чтобы поднять уровень техники, необходимо пройти цепочку: Тренировки
→ тренировки техники → выбор учителя → оплата → квест → покупка за очки УИ». Учитель — тот, кто
дал технику (AskUserQuestion: «учитель своей техники»); «очки УИ» — фрагменты техники.

Состояние живёт в общем механизме квестов развития: квест `QUEST_TECH_LEVEL`, ref
`"<код>:<уровень>"`. Оплата и выдача квеста — одна транзакция; подъём уровня (закрыть квест +
списать фрагменты) — `services/unique_technique.level_up`.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.unique_path import bump_training_reps
from bot.services.build import get_build
from bot.config.development import MAX_LEVEL
from bot.config.unique_technique import tech_training_price, tech_training_quest, technique_level_cost
from bot.constant.dev_quest import QUEST_TECH_LEVEL
from bot.db.repositories import business as business_repo
from bot.db.repositories import unique_technique as tech_repo
from bot.services.dev_quest import QuestView, list_active, start


class TechniqueNotOwnedError(Exception):
    pass


class TechniqueMaxLevelError(Exception):
    pass


class TrainingActiveError(Exception):
    """Тренировка на этот уровень уже оплачена — выполняй квест."""


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int, balance: int) -> None:
        super().__init__(cost)
        self.cost = cost
        self.balance = balance


@dataclass(frozen=True, slots=True)
class TechTraining:
    code: str
    level: int
    next_level: int | None  # None — максимум
    price: int  # NHCoin за тренировку на следующий уровень
    fragments_cost: int  # фрагментов за сам уровень
    quest: QuestView | None  # оплаченная тренировка (квест учителя)
    tasks: dict[str, int]  # задания квеста на следующий уровень (для показа до оплаты)

    @property
    def stage(self) -> str:
        """pay — оплатить тренировку; quest — выполнять квест; level — можно поднять уровень; max."""
        if self.next_level is None:
            return "max"
        if self.quest is None:
            return "pay"
        return "level" if self.quest.complete else "quest"


def _ref(code: str, level: int) -> str:
    return f"{code}:{level}"


async def list_trainings(session: AsyncSession, user_id: int) -> tuple[list[TechTraining], int, int]:
    """Все техники игрока со стадией тренировки. → (техники, фрагменты, NHCoin)."""
    owned = dict(await tech_repo.list_owned(session, user_id))
    _, fragments = await tech_repo.get_state(session, user_id)
    quests = {q.ref: q for q in await list_active(session, user_id, QUEST_TECH_LEVEL)}
    wallet = await business_repo.get_wallet(session, user_id)
    kpd = (await get_build(session, user_id)).training_kpd  # Путь тренировок
    rows = []
    for code, level in sorted(owned.items(), key=lambda kv: (-kv[1], kv[0])):
        nxt = level + 1 if level < MAX_LEVEL else None
        rows.append(
            TechTraining(
                code=code, level=level, next_level=nxt,
                price=int(tech_training_price(nxt) * (1 - kpd)) if nxt else 0,
                fragments_cost=technique_level_cost(nxt) if nxt else 0,
                quest=quests.get(_ref(code, nxt)) if nxt else None,
                tasks={t: max(1, round(n * (1 - kpd / 2))) for t, n in tech_training_quest(code, nxt).items()} if nxt else {},
            )
        )
    return rows, fragments, wallet.nh_coins if wallet else 0


async def get_training(session: AsyncSession, user_id: int, code: str) -> TechTraining:
    rows, _, _ = await list_trainings(session, user_id)
    for row in rows:
        if row.code == code:
            return row
    raise TechniqueNotOwnedError


async def start_training(session: AsyncSession, user_id: int, code: str) -> TechTraining:
    """Оплатить тренировку у учителя → его квест на следующий уровень. Квест создаётся первым
    (частичный уникальный индекс — двойной клик не выдаст два), затем атомарное списание
    NHCoin; не хватило — откат. Коммитит."""
    row = await get_training(session, user_id, code)
    if row.next_level is None:
        raise TechniqueMaxLevelError
    if row.quest is not None:
        raise TrainingActiveError
    if not await start(session, user_id, QUEST_TECH_LEVEL, _ref(code, row.next_level), row.tasks):
        raise TrainingActiveError
    if row.price and not await business_repo.spend_coins(session, user_id, row.price):
        await session.rollback()
        wallet = await business_repo.get_wallet(session, user_id)
        raise NotEnoughCoinsError(row.price, wallet.nh_coins if wallet else 0)
    await bump_training_reps(session, user_id)
    await session.commit()
    return await get_training(session, user_id, code)
