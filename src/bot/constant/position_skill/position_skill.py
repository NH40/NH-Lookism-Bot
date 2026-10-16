"""Навыки позиций банды — константы (виды навыков, условия, типы боя, поля разведки).

Каталог и числа — `config/position_skill`; здесь только сравниваемые строки.
"""
from __future__ import annotations

# --- Вид навыка: когда он работает ---
KIND_AURA = "aura"  # весь бой, оба лагеря
KIND_ATK = "atk"  # когда игрок нападает (лагерь атаки)
KIND_DEF = "def"  # когда нападают на игрока (лагерь защиты)
KIND_VS = "vs"  # только в бою определённого типа (`fx["vs"]`)
KIND_TRIGGER = "trigger"  # условие внутри боя (`fx["when"]`), пишется в журнал
KIND_SPY = "spy"  # один раз перед атакой игрока, с шансом
KIND_INTEL = "intel"  # разведка: открывает поле данных о цели
KIND_HIDE = "hide"  # безопасность: прячет поле данных
KIND_ECO = "eco"  # экономика / скорость / развитие (вне боя)
KIND_META = "meta"  # меняет другие навыки

# --- Роль стороны в бою ---
ROLE_ATTACK = "attack"
ROLE_DEFENSE = "defense"

# --- Тип боя (`fx["vs"]` и контекст боя у вызывающего сервиса) ---
VS_DISTRICT = "district"  # бой с ботами района
VS_CITY = "city"  # штурм ботов города
VS_BOTS = "bots"  # любой бой с ботами (район или город)
VS_PVP = "pvp"  # вызов игроку (район или город)
VS_THRONE = "throne"  # бой за трон и освобождение страны
VS_WAR = "war"  # война императоров
VS_BOSS = "boss"  # боссы и учителя на карте
VS_CLAN_WAR = "clan_war"  # война кланов (рота)

# --- Условия триггеров (`fx["when"]`) ---
WHEN_ROUND_1 = "round_1"
WHEN_ROUNDS_2_3 = "rounds_2_3"
WHEN_ROUND_3 = "round_3"
WHEN_ROUND_4_PLUS = "round_4_plus"
WHEN_EVERY_3RD = "every_3rd"
WHEN_LOST_30 = "lost_30"  # потеряно 30% армии — до конца боя
WHEN_BELOW_50 = "below_50"
WHEN_BELOW_20 = "below_20"
WHEN_HEAVY_ROUND = "heavy_round"  # прошлый раунд унёс >25% армии — следующий раунд
WHEN_ENEMY_STRONGER = "enemy_stronger"  # противник сильнее на старте — 1-й раунд
WHEN_WEAKER_ROUND_3 = "weaker_round_3"  # сторона слабее на старте — с 3-го раунда
WHEN_ON_LOSS = "on_loss"  # бой проигран — после боя
WHEN_DEF_ROUND_1 = "def_round_1"
WHEN_DEF_ROUNDS_1_2 = "def_rounds_1_2"
WHEN_DEF_BELOW_30 = "def_below_30"
WHEN_DEF_WIN = "def_win"  # атака отбита — после боя

# --- Поля разведки (разведка открывает, безопасность прячет) ---
F_HEADCOUNT = "headcount"
F_ATTACK_POWER = "attack_power"
F_DEFENSE_POWER = "defense_power"
F_RANKS = "ranks"
F_TOP_SQUADS = "top_squads"
F_LINEUP = "lineup"
F_EMPTY_SLOTS = "empty_slots"
F_SKILLS = "skills"
F_BLOODLINE = "bloodline"
F_PATH = "path"
F_TECHNIQUE = "technique"
F_GENIUS = "genius"
F_POTIONS = "potions"
F_WALLET = "wallet"
F_BUSINESS = "business"
F_BATTLES = "battles"
F_COOLDOWNS = "cooldowns"
F_CLAN = "clan"
F_CHALLENGES = "challenges"
F_FORECAST = "forecast"  # прогноз боя с целью (только разведка)
F_ATTACKER_POWER = "attacker_power"  # мощь нападающего в пуше вызова (Защитник «Бдительность»)

INTEL_FIELDS: tuple[str, ...] = (
    F_HEADCOUNT, F_ATTACK_POWER, F_DEFENSE_POWER, F_RANKS, F_TOP_SQUADS, F_LINEUP, F_EMPTY_SLOTS, F_SKILLS,
    F_BLOODLINE, F_PATH, F_TECHNIQUE, F_GENIUS, F_POTIONS, F_WALLET, F_BUSINESS, F_BATTLES, F_COOLDOWNS, F_CLAN,
    F_CHALLENGES, F_FORECAST,
)

# Видимость поля в отчёте разведки.
SEEN_EXACT = "exact"
SEEN_RANGE = "range"  # уровни равны — вилка
SEEN_HIDDEN = "hidden"

# --- Разведка: кнопка и отчёты ---
CB_SCOUT_PREFIX = "scout:do:"
"""f"{CB_SCOUT_PREFIX}{target_id}" — разведать игрока (без КД, по навыкам Разведки)."""
CB_SCOUT_REPORT_PREFIX = "scout:rep:"
"""f"{CB_SCOUT_REPORT_PREFIX}{target_id}" — открыть сохранённый отчёт."""
CB_SKILLS_POSITION_PREFIX = "pskill:pos:"
"""f"{CB_SKILLS_POSITION_PREFIX}{position}" — навыки карты на позиции."""
