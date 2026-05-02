from dataclasses import dataclass


@dataclass
class QuestConfig:
    quest_id: str
    name: str
    description: str
    emoji: str
    target: int
    reward_coins: int
    reward_tickets: int


DAILY_QUESTS: list[QuestConfig] = [
    QuestConfig(
        quest_id="attacks",
        name="Боец",
        description="Совершить атак",
        emoji="⚔️",
        target=5,
        reward_coins=50_000,
        reward_tickets=0,
    ),
    QuestConfig(
        quest_id="wins",
        name="Победитель",
        description="Победить в боях",
        emoji="🏆",
        target=3,
        reward_coins=100_000,
        reward_tickets=0,
    ),
    QuestConfig(
        quest_id="recruit",
        name="Вербовщик",
        description="Завербовать статистов",
        emoji="👥",
        target=10,
        reward_coins=75_000,
        reward_tickets=0,
    ),
    QuestConfig(
        quest_id="train",
        name="Тренер",
        description="Провести тренировок",
        emoji="🏋",
        target=3,
        reward_coins=80_000,
        reward_tickets=0,
    ),
    QuestConfig(
        quest_id="income",
        name="Бизнесмен",
        description="Заработать NHCoin через доход",
        emoji="💰",
        target=500_000,
        reward_coins=150_000,
        reward_tickets=1,
    ),
    QuestConfig(
        quest_id="all_done",
        name="Мастер на все руки",
        description="Выполнить все остальные задания дня",
        emoji="🌟",
        target=4,  # кол-во остальных заданий
        reward_coins=300_000,
        reward_tickets=2,
    ),
]

QUESTS_BY_ID: dict[str, QuestConfig] = {q.quest_id: q for q in DAILY_QUESTS}