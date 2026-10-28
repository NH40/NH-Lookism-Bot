"""Мастерство — цепочка «Преодоление стены», бой с Томом Ли, тренер (константы).

Статусы цепочки и коды заданий хранятся в БД и сравниваются — константы, не литералы.
"""
from __future__ import annotations

# Статус текущего этапа цепочки (`mastery_quests.status`).
QUEST_PENDING = "pending"  # условие выполнено, задание придёт в случайный момент
QUEST_ACTIVE = "active"  # задания этапа в работе
QUEST_TRAINER = "trainer"  # Том побеждён — у тренера можно купить очки этапа
QUEST_COMPLETE = "complete"  # все три этапа пройдены
QUEST_BREAKTHROUGH = "breakthrough"  # этап пройден — нужен «прорыв», чтобы пошло ожидание следующего

# Задания этапов (пользователь 2026-09-30; «какое-то задание» — придумано автором кода).
TASK_TRAININGS = "trainings"  # этап 2: провести N личных тренировок
TASK_PVP_WINS = "pvp_wins"  # этап 3: выиграть N PvP-вызовов нападающим
TASK_EQUAL_WIN = "equal_win"  # этап 3: победить игрока с мощью ±10% от своей
TASK_EXTRAS = "extras"  # провести N тренировок статистов
TASK_TOM = "tom"  # каждый этап: победить Тома Ли (открывается после остальных заданий)

CB_MASTERY_OPEN = "mastery:open"
CB_MASTERY_TOM_FIGHT = "mastery:tom"
CB_MASTERY_INVEST_PREFIX = "mastery:inv:"
"""f"{CB_MASTERY_INVEST_PREFIX}{mastery_code}" — вложить очко мастерства."""

# Прорывы перед этапами 2 и 3 (пользователь 2026-10-28): «сделать что-то грандиозное».
BT_PATH = "path"  # путь пробуждён
BT_TECH10 = "tech10"  # любая уникальная техника на 10 уровне
BT_AWAKEN = "awaken"  # пройден хотя бы один этап пробуждения
BT_PHASE = "phase"  # стал кругом или императором
BREAKTHROUGHS: tuple[str, ...] = (BT_PATH, BT_TECH10, BT_AWAKEN, BT_PHASE)
