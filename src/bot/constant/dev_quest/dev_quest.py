"""Задания систем развития (константы) — виды квестов, статусы и события-задачи."""
from __future__ import annotations

QUEST_TEACHER = "teacher"  # квест учителя уникальной техники, ref — код техники
QUEST_CONVICTION = "conviction"  # «подтверждение убеждений» (начало пути)
QUEST_PATH = "path"  # бывший квест на путь (убран 2026-10-04) — только для сброса старых строк
QUEST_SCHOOL = "school"  # квест учителя статистов, ref — код школы
QUEST_TECH_LEVEL = "tech_level"  # тренировка техники у её учителя, ref — "<код техники>:<следующий уровень>"
QUEST_AWAKENING = "awakening"  # квест кулака на пробуждение, ref — номер следующего этапа

STATUS_ACTIVE = "active"
STATUS_DONE = "done"  # выполнен и награда получена

# События игры, из которых складываются задания (`services/dev_quest.emit`).
TASK_WIN_PVE = "win_pve"  # победа над ботами района/города
TASK_WIN_PVP = "win_pvp"  # победа нападающим в PvP-вызове
TASK_BOSS_WIN = "boss_win"  # победа над боссом на карте
TASK_PERSONAL_TRAIN = "personal_train"  # личная тренировка
TASK_TRAIN_EXTRAS = "train_extras"  # тренировка статистов
TASK_RECRUIT = "recruit"  # вербовка статиста
TASK_ROLL = "roll"  # крутка уника
TASK_COLLECT = "collect"  # сбор дохода бизнеса
TASK_BUILD = "build"  # постройка здания
TASK_WAR_WIN = "war_win"  # победа в войне императоров (нападающим или защитником)
TASK_SCHOOL_LESSON = "school_lesson"  # занятие у учителя статистов
# Ещё события — для ежедневных заданий (`config/quest`), 2026-10-04.
TASK_POTION = "potion"  # купить и выпить зелье
TASK_CASINO = "casino"  # ставка в казино (слоты, раздача блэкджека)
TASK_POKER_HAND = "poker_hand"  # сыгранная раздача покера
TASK_EXCHANGE_DEAL = "ex_deal"  # сделка на бирже покупателем (лот, выигранный аукцион, принятый обмен)
TASK_EXCHANGE_LIST = "ex_list"  # выставить лот или аукцион
TASK_DEPOSIT = "deposit"  # открыть вклад
TASK_STORAGE = "storage"  # положить в ячейку хранения
TASK_CONTRACT = "contract"  # нанять статистов по контракту
TASK_CLAN_DONATE = "clan_donate"  # взнос в казну клана
TASK_GARRISON = "garrison"  # внести бойцов в клановую роту
TASK_STAT_INVEST = "stat_invest"  # поднять ранг характеристики (за каждый ранг)
TASK_DEV_LEVEL = "dev_level"  # поднять уровень пути / техники / гениальности / родословной
TASK_PVP_CHALLENGE = "pvp_call"  # бросить PvP-вызов
TASK_BP_CLAIM = "bp_claim"  # забрать награду Battle Pass (за каждый уровень)
TASK_INCOME = "income"  # заработать NHCoin бизнесом (n — сумма)
TASKS: tuple[str, ...] = (
    TASK_WIN_PVE, TASK_WIN_PVP, TASK_BOSS_WIN, TASK_PERSONAL_TRAIN, TASK_TRAIN_EXTRAS,
    TASK_RECRUIT, TASK_ROLL, TASK_COLLECT, TASK_BUILD, TASK_WAR_WIN, TASK_SCHOOL_LESSON,
    TASK_POTION, TASK_CASINO, TASK_POKER_HAND, TASK_EXCHANGE_DEAL, TASK_EXCHANGE_LIST, TASK_DEPOSIT,
    TASK_STORAGE, TASK_CONTRACT, TASK_CLAN_DONATE, TASK_GARRISON, TASK_STAT_INVEST, TASK_DEV_LEVEL,
    TASK_PVP_CHALLENGE, TASK_BP_CLAIM, TASK_INCOME,
)
