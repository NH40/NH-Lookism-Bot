"""Навыки позиций и журнал боя — тексты."""
from __future__ import annotations

from bot.constant.position_skill import (
    F_ATTACK_POWER,
    F_BATTLES,
    F_BLOODLINE,
    F_BUSINESS,
    F_CHALLENGES,
    F_CLAN,
    F_COOLDOWNS,
    F_DEFENSE_POWER,
    F_EMPTY_SLOTS,
    F_FORECAST,
    F_GENIUS,
    F_HEADCOUNT,
    F_LINEUP,
    F_PATH,
    F_POTIONS,
    F_RANKS,
    F_SKILLS,
    F_TECHNIQUE,
    F_TOP_SQUADS,
    F_WALLET,
    KIND_ATK,
    KIND_AURA,
    KIND_DEF,
    KIND_ECO,
    KIND_HIDE,
    KIND_INTEL,
    KIND_META,
    KIND_SPY,
    KIND_TRIGGER,
    KIND_VS,
)

KIND_LABELS: dict[str, str] = {
    KIND_AURA: "всегда", KIND_ATK: "в нападении", KIND_DEF: "в защите", KIND_VS: "тип боя", KIND_TRIGGER: "условие",
    KIND_SPY: "перед атакой", KIND_INTEL: "разведка", KIND_HIDE: "сокрытие", KIND_ECO: "вне боя", KIND_META: "усиление",
}

FIELD_LABELS: dict[str, str] = {
    F_HEADCOUNT: "Статистов", F_ATTACK_POWER: "Мощь атаки", F_DEFENSE_POWER: "Мощь защиты", F_RANKS: "Ранги",
    F_TOP_SQUADS: "Сильнейшие отряды", F_LINEUP: "На позициях", F_EMPTY_SLOTS: "Пустые позиции", F_SKILLS: "Навыки позиций",
    F_BLOODLINE: "Родословная", F_PATH: "Путь", F_TECHNIQUE: "Техника", F_GENIUS: "Гениальность", F_POTIONS: "Зелья",
    F_WALLET: "Кошелёк", F_BUSINESS: "Бизнесы", F_BATTLES: "Последние бои", F_COOLDOWNS: "Сможет атаковать",
    F_CLAN: "Клан", F_CHALLENGES: "Висящие вызовы", F_FORECAST: "Прогноз боя",
}
HIDDEN_VALUE = "скрыто"
RANGE_VALUE = "~{low}–{high}"

# --- Журнал боя ---
JOURNAL_TITLE = "📜 <b>Ход боя</b>"
JOURNAL_PRE = "<b>Перед боем</b>"
JOURNAL_SPY_OK = "🕵️ {name} ({card}) — сработал"
JOURNAL_SPY_FAIL = "🕵️ {name} — не вышло"
JOURNAL_SPY_BLOCKED = "🕵️ {name} — сорван контрразведкой"
JOURNAL_DISABLED = "⛔ Отключена позиция противника: {positions}"
JOURNAL_WITHHELD = "💸 Не вышли на бой у противника: {count}"
JOURNAL_FIRST_STRIKE_MINE = "⚡ До боя выбито у противника: {count}"
JOURNAL_FIRST_STRIKE_FOE = "⚡ До боя противник выбил у тебя: {count}"
JOURNAL_ROUND = "<b>Раунд {n}</b> · {you}: {dealt} урона{chaos} · {foe}: {taken}{foe_chaos} · убито: {kills} / потери: {lost}"
JOURNAL_CHAOS = " (хаос ×2)"
JOURNAL_FIRED = "   ✨ {side}: {names}"
JOURNAL_AFTER = "✨ После боя — {side}: {names}"
JOURNAL_RESULT_WIN = "<b>Итог</b> · победа за {rounds} р."
JOURNAL_RESULT_LOSS = "<b>Итог</b> · поражение за {rounds} р."
SIDE_YOU = "ты"
SIDE_FOE = "противник"

# --- Навыки на экране позиции / карты ---
SKILLS_HEADER = "✨ <b>Навыки на позиции «{position}»</b> ({count}):"
SKILL_LINE = "• <b>{name}</b> · <i>{kind}</i> — {desc}"
NO_SKILLS = "У этой карты нет навыков на этой позиции."
