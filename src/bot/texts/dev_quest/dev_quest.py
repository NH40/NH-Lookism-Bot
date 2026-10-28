"""Задания систем развития (тексты)."""
from __future__ import annotations

from bot.constant.dev_quest import (
    TASK_BP_CLAIM,
    TASK_CASINO,
    TASK_CLAN_DONATE,
    TASK_CONTRACT,
    TASK_DEPOSIT,
    TASK_DEV_LEVEL,
    TASK_EXCHANGE_DEAL,
    TASK_EXCHANGE_LIST,
    TASK_GARRISON,
    TASK_INCOME,
    TASK_POKER_HAND,
    TASK_POTION,
    TASK_PVP_CHALLENGE,
    TASK_STAT_INVEST,
    TASK_STORAGE,
    TASK_BOSS_WIN,
    TASK_BUILD,
    TASK_COLLECT,
    TASK_PERSONAL_TRAIN,
    TASK_RECRUIT,
    TASK_ROLL,
    TASK_SCHOOL_LESSON,
    TASK_TRAIN_EXTRAS,
    TASK_WIN_PVE,
    TASK_WAR_WIN,
    TASK_WIN_PVP,
)

TASK_LABELS: dict[str, str] = {
    TASK_WIN_PVE: "Победить ботов района/города или игрока нападающим",
    TASK_WIN_PVP: "Победить игрока нападающим (вызов, трон, освобождение)",
    TASK_BOSS_WIN: "Победить босса на карте",
    TASK_PERSONAL_TRAIN: "Личная тренировка",
    TASK_TRAIN_EXTRAS: "Тренировка статистов",
    TASK_RECRUIT: "Завербовать статистов",
    TASK_ROLL: "Крутка уника",
    TASK_COLLECT: "Собрать доход бизнеса",
    TASK_BUILD: "Построить здание",
    TASK_WAR_WIN: "Победить в войне императоров",
    TASK_SCHOOL_LESSON: "Занятие у учителя статистов",
    TASK_POTION: "Выпить зелье из магазина",
    TASK_CASINO: "Сыграть в казино (слоты или блэкджек)",
    TASK_POKER_HAND: "Сыграть раздачу в покер",
    TASK_EXCHANGE_DEAL: "Купить на бирже (лот, аукцион или обмен)",
    TASK_EXCHANGE_LIST: "Выставить лот или аукцион на бирже",
    TASK_DEPOSIT: "Открыть вклад",
    TASK_STORAGE: "Положить что-то в ячейку хранения",
    TASK_CONTRACT: "Нанять статистов по контракту",
    TASK_CLAN_DONATE: "Внести NHCoin в казну клана",
    TASK_GARRISON: "Внести бойцов в клановую роту",
    TASK_STAT_INVEST: "Поднять ранги характеристик",
    TASK_DEV_LEVEL: "Поднять уровень пути, техники, гениальности или родословной",
    TASK_PVP_CHALLENGE: "Бросить PvP-вызов",
    TASK_BP_CLAIM: "Забрать награды Battle Pass",
    TASK_INCOME: "Заработать NHCoin бизнесом",
}
TASK_LINE = "{mark} {label}: {done}/{need}"
MARK_DONE = "✅"
MARK_TODO = "▫️"


def render_tasks(tasks: dict[str, int], progress: dict[str, int]) -> str:
    return "\n".join(
        TASK_LINE.format(
            mark=MARK_DONE if progress.get(t, 0) >= n else MARK_TODO,
            label=TASK_LABELS.get(t, t),
            done=min(progress.get(t, 0), n),
            need=n,
        )
        for t, n in tasks.items()
    )


def quest_title(kind: str, ref: str) -> str:
    """Название квеста развития для списков (админка, свиток): вид + чей/какой."""
    from bot.texts.school import SCHOOL_TEACHERS
    from bot.texts.unique_technique import TEACHER_NAMES, TECHNIQUE_NAMES

    if kind == "teacher":
        return f"Учитель техники: {TEACHER_NAMES.get(ref, ref)}"
    if kind == "school":
        return f"Учитель статистов: {SCHOOL_TEACHERS.get(ref, ref)}"
    if kind == "conviction":
        return "Подтверждение убеждений"
    if kind == "tech_level":
        code, _, level = ref.partition(":")
        return f"Тренировка техники: {TECHNIQUE_NAMES.get(code, code)} → ур. {level}"
    if kind == "awakening":
        return f"Пробуждение: этап {ref}"
    return f"{kind}: {ref}"
