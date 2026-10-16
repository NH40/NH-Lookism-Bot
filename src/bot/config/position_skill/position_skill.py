"""Навыки позиций банды — каталог (дизайн одобрен к реализации 2026-10-16,
`docs/design/position_skills/`). 9 позиций × 30 навыков.

Навык — атомарный эффект. Сила растёт с редкостью карты (`GRADE`), число навыков у карты — тоже
(`SKILL_COUNT`), а редкие навыки выпадают только старшим редкостям (`tier` → `TIER_MIN_RARITY`).
Значения в `fx` — на ступени «член банды» (×1); `desc` — шаблон описания с {v}/{v2}/{v3}/{p}.
Какие навыки у какой карты — `card_skills.py` (генерируется `scripts/gen_position_skills.py`).

Ключи `fx` — имена полей `CombatMods`/`EconomyMods` или особые эффекты, которые читает
`services/position_skill` (`enemy_*`, `per_filled_slot`, `p`, `disable`, …).
"""
from __future__ import annotations

from typing import NamedTuple

from bot.constant.card import (
    POS_BUSINESSMAN,
    POS_DEFENDER,
    POS_DEPUTY,
    POS_LEADER,
    POS_SCOUT,
    POS_SECURITY,
    POS_SPY,
    POS_TACTICIAN,
    POS_WARLORD,
    RARITY_ORDER,
)
from bot.constant.position_skill import (
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
    VS_BOSS,
    VS_BOTS,
    VS_CITY,
    VS_CLAN_WAR,
    VS_DISTRICT,
    VS_PVP,
    VS_THRONE,
    VS_WAR,
    WHEN_BELOW_20,
    WHEN_BELOW_50,
    WHEN_DEF_BELOW_30,
    WHEN_DEF_ROUNDS_1_2,
    WHEN_DEF_ROUND_1,
    WHEN_DEF_WIN,
    WHEN_ENEMY_STRONGER,
    WHEN_EVERY_3RD,
    WHEN_HEAVY_ROUND,
    WHEN_LOST_30,
    WHEN_ON_LOSS,
    WHEN_ROUNDS_2_3,
    WHEN_ROUND_1,
    WHEN_ROUND_3,
    WHEN_ROUND_4_PLUS,
    WHEN_WEAKER_ROUND_3,
)

# Множитель силы навыка и число навыков на позиции — по редкости (порядок `RARITY_ORDER`).
GRADE: tuple[float, ...] = (1.0, 1.25, 1.6, 2.0, 2.5, 3.0, 3.6, 4.5, 4.5)
SKILL_COUNT: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8, 10, 10)
# tier навыка → индекс редкости, с которой он может достаться карте.
TIER_MIN_RARITY: tuple[int, ...] = (0, 2, 4, 6, 7)
# Потолок шанса шпионского навыка.
SPY_CHANCE_CAP = 0.9
assert len(GRADE) == len(SKILL_COUNT) == len(RARITY_ORDER)


class Skill(NamedTuple):
    code: str
    name: str
    kind: str
    tags: tuple[str, ...]
    tier: int
    fx: dict
    desc: str


def S(code, name, kind, tags, tier, fx, desc) -> Skill:
    return Skill(code, name, kind, tuple(tags.split()), tier, fx, desc)


def grade(rarity: str) -> float:
    return GRADE[RARITY_ORDER.index(rarity)]


POOLS: dict[str, list[Skill]] = {}

# ───────────────────────── ГЛАВА: аура на всю банду ─────────────────────────
POOLS[POS_LEADER] = [
    S("banner", "Знамя банды", KIND_AURA, "leader power", 0, {"army_power": 0.02}, "+{v}% мощи всей армии"),
    S("iron_will", "Железная воля", KIND_AURA, "leader endurance", 0, {"loss_save": 0.02}, "{v}% павших выживают после боя"),
    S("authority", "Авторитет", KIND_ECO, "leader", 0, {"influence": 2}, "+{v} влияния (выше потолок ранга вербовки)"),
    S("charisma", "Харизма", KIND_ECO, "leader support", 0, {"recruit_double": 0.02}, "{v}% шанс завербовать сразу двоих"),
    S("under_wing", "Под крылом", KIND_ECO, "leader support", 0, {"recruit_cooldown": 0.03}, "−{v}% КД вербовки"),
    S("kings_fist", "Кулак короля", KIND_AURA, "leader power", 0, {"attack": 0.02}, "+{v}% к атаке"),
    S("kings_shield", "Щит короля", KIND_AURA, "leader defense", 0, {"durability": 0.02}, "+{v}% ХП бойцов"),
    S("example", "Личный пример", KIND_AURA, "leader discipline", 0, {"dodge": 0.005, "block": 0.005, "counter": 0.005}, "+{v} п.п. к уклонению, блоку и контратаке"),
    S("mentor", "Наставник", KIND_ECO, "leader support", 0, {"extras_training": 1.0}, "+{v} п.п. к шансам тренировки статистов"),
    S("teacher", "Учитель", KIND_ECO, "leader support", 0, {"dev_points": 0.03}, "+{v}% очков развития с личной тренировки"),
    S("district_king", "Король района", KIND_VS, "leader", 1, {"vs": VS_DISTRICT, "attack": 0.04}, "+{v}% атаки в боях за районы"),
    S("city_king", "Король города", KIND_VS, "leader power", 1, {"vs": VS_CITY, "attack": 0.04}, "+{v}% атаки в боях за города"),
    S("country_king", "Король страны", KIND_VS, "leader", 1, {"vs": VS_THRONE, "attack": 0.05}, "+{v}% атаки в боях за трон и освобождение страны"),
    S("emperor", "Император", KIND_VS, "leader", 1, {"vs": VS_WAR, "attack": 0.05}, "+{v}% атаки в войнах императоров"),
    S("overcoming", "Преодоление", KIND_AURA, "leader power endurance", 1, {"overcome": 0.02}, "атака растёт от полученного урона (+{v}% силы преодоления)"),
    S("pressure", "Давление авторитета", KIND_AURA, "leader", 1, {"suppress": 0.02}, "реакции противника слабее на {v}%"),
    S("crowd_breaker", "Сокрушитель толп", KIND_AURA, "leader power", 1, {"cleave": 0.02}, "+{v}% урона по толпе (удар по нескольким целям)"),
    S("never_give_up", "Не сдаваться", KIND_TRIGGER, "leader endurance", 1, {"when": WHEN_LOST_30, "attack": 0.06}, "потеряв 30% армии — +{v}% атаки до конца боя"),
    S("last_order", "Последний приказ", KIND_TRIGGER, "leader", 1, {"when": WHEN_BELOW_20, "attack": 0.08, "dodge": 0.02}, "армия ниже 20% — +{v}% атаки и +{v2} п.п. уклонения"),
    S("one_gen", "Первое поколение", KIND_AURA, "leader power", 1, {"card_power": 0.05}, "+{v}% мощи уников в армии (не на позициях)"),
    S("intimidation", "Устрашение", KIND_TRIGGER, "leader dark", 2, {"when": WHEN_ROUND_1, "enemy_attack": -0.05}, "в 1-м раунде атака противника −{v}%"),
    S("seoul_king", "Король Сеула", KIND_AURA, "leader power", 2, {"ramp": 0.01, "ramp_cap": 0.08}, "+{v}% атаки за каждый раунд (до +{v2}%)"),
    S("undefeated", "Непобедимый", KIND_AURA, "leader power", 2, {"opening": 0.06}, "+{v}% атаки в первом раунде"),
    S("old_guard", "Старая гвардия", KIND_AURA, "leader discipline", 2, {"top_ranks_power": 0.04}, "+{v}% мощи статистов трёх старших рангов армии"),
    S("young_blood", "Молодая кровь", KIND_AURA, "leader support", 2, {"low_ranks_power": 0.06}, "+{v}% мощи статистов младших рангов (ниже середины армии)"),
    S("legend_hunter", "Охотник на легенды", KIND_ECO, "leader", 2, {"fragment_bonus": 0.04}, "+{v}% фрагментов с боссов"),
    S("treasury", "Казна банды", KIND_ECO, "leader money", 2, {"income": 0.02}, "+{v}% дохода зданий"),
    S("brotherhood", "Братство", KIND_AURA, "leader support", 2, {"per_filled_slot": 0.004}, "+{v}% мощи армии за каждую занятую позицию банды"),
    S("absolute_power", "Абсолютная власть", KIND_META, "leader", 3, {"deputy_boost": 0.07}, "навыки Заместителя сильнее на {v}%"),
    S("king_of_all", "Король всех", KIND_META, "leader power", 4, {"all_skills": 0.04}, "все навыки позиций банды сильнее на {v}%"),
]

# ───────────────────────── ЗАМЕСТИТЕЛЬ: опора и подмена главы ─────────────────────────
POOLS[POS_DEPUTY] = [
    S("right_hand", "Правая рука", KIND_META, "support leader", 0, {"leader_boost": 0.04}, "навыки Главы сильнее на {v}%"),
    S("stand_in", "Подмена", KIND_META, "support", 0, {"stand_in": 0.1}, "если Глава пуст или выведен шпионом — навыки Заместителя сильнее на {v}%"),
    S("shadow_banner", "Тень знамени", KIND_AURA, "support power", 0, {"army_power": 0.01}, "+{v}% мощи всей армии"),
    S("order", "Порядок в рядах", KIND_AURA, "discipline", 0, {"loss_save": 0.015}, "{v}% павших выживают после боя"),
    S("discipline", "Дисциплина", KIND_AURA, "discipline defense", 0, {"block": 0.006}, "+{v} п.п. к блоку"),
    S("muster", "Сбор", KIND_ECO, "support speed", 0, {"battle_cooldown": 0.02}, "−{v}% КД сражений"),
    S("duty", "Дежурство", KIND_ECO, "support", 0, {"recruit_cooldown": 0.03}, "−{v}% КД вербовки"),
    S("drill", "Муштра", KIND_ECO, "discipline", 0, {"extras_training_cooldown": 0.03}, "−{v}% КД тренировки статистов"),
    S("bookkeeper", "Казначей", KIND_ECO, "money", 0, {"storage_hours": 1.0}, "+{v} ч к хранилищу дохода"),
    S("supply", "Снабжение", KIND_ECO, "money support", 0, {"contract_discount": 0.03}, "−{v}% цены контрактов статистов"),
    S("apothecary", "Аптекарь", KIND_ECO, "support", 1, {"potion_duration": 0.05}, "зелья действуют на {v}% дольше"),
    S("medic", "Полевой медик", KIND_AURA, "support endurance", 1, {"heal": 0.01}, "{v}% павших за раунд возвращаются в строй"),
    S("recruiter", "Вербовщик", KIND_ECO, "support leader", 1, {"recruit_rank_bonus": 0.4}, "+{v} ступени к потолку ранга вербовки (с округлением)"),
    S("accounting", "Учёт", KIND_ECO, "support", 1, {"dev_points": 0.02}, "+{v}% очков развития"),
    S("mediator", "Посредник", KIND_ECO, "money", 1, {"tax_relief": 0.03}, "−{v}% налога императора"),
    S("negotiator", "Переговорщик", KIND_DEF, "support", 1, {"accept_window": 0.06}, "+{v}% времени на принятие вызова"),
    S("reserve_squad", "Резервный отряд", KIND_TRIGGER, "support endurance", 1, {"when": WHEN_ROUND_3, "revive": 0.03}, "в 3-м раунде {v}% павших возвращаются в строй"),
    S("liaison", "Связной", KIND_META, "info dark", 1, {"spy_chance": 0.03}, "+{v} п.п. к шансу шпионских навыков банды"),
    S("bodyguard", "Охрана главы", KIND_META, "defense", 1, {"leader_guard": 0.1}, "{v}% шанс, что шпион не выведет Главу"),
    S("mobilize", "Мобилизация", KIND_DEF, "defense", 1, {"army_power": 0.025}, "+{v}% мощи лагеря защиты"),
    S("war_cry", "Клич", KIND_ATK, "power", 2, {"army_power": 0.025}, "+{v}% мощи лагеря атаки"),
    S("fire_support", "Поддержка огнём", KIND_TRIGGER, "power", 2, {"when": WHEN_ROUNDS_2_3, "attack": 0.05}, "во 2–3 раундах +{v}% атаки"),
    S("formation", "Строй", KIND_AURA, "defense discipline", 2, {"durability": 0.02}, "+{v}% ХП бойцов"),
    S("cohesion", "Сплочённость", KIND_AURA, "support discipline", 2, {"dodge": 0.004, "block": 0.004, "counter": 0.004}, "+{v} п.п. ко всем реакциям"),
    S("pillar", "Опора", KIND_AURA, "defense", 2, {"reduction": 0.012}, "{v}% входящего урона гасится"),
    S("cool_head", "Холодная голова", KIND_AURA, "discipline", 2, {"enemy_crit": -0.02}, "шанс крита противника −{v} п.п."),
    S("plan_b", "Второй план", KIND_TRIGGER, "support", 2, {"when": WHEN_ON_LOSS, "loss_save": 0.05}, "если бой проигран — ещё {v}% павших выживают"),
    S("veteran", "Ветеран", KIND_ECO, "discipline", 2, {"mastery_delay": 0.04}, "−{v}% ожидания этапов мастерства"),
    S("heir", "Наследник", KIND_META, "leader", 3, {"self_boost": 0.08}, "все навыки Заместителя сильнее на {v}%"),
    S("second_king", "Второй король", KIND_META, "leader power", 4, {"copy_leader": 0.06}, "копирует {v}% силы навыков Главы"),
]

# ───────────────────────── ТАКТИК: реакции и условия боя ─────────────────────────
POOLS[POS_TACTICIAN] = [
    S("evasion", "Уклонение", KIND_AURA, "speed", 0, {"dodge": 0.008}, "+{v} п.п. к уклонению"),
    S("guard", "Блок", KIND_AURA, "defense tech", 0, {"block": 0.008}, "+{v} п.п. к блоку"),
    S("riposte", "Контратака", KIND_AURA, "tech", 0, {"counter": 0.008}, "+{v} п.п. к контратаке"),
    S("retreat", "Отход", KIND_AURA, "speed", 0, {"flee": 0.008}, "+{v} п.п. к побегу из проигранной схватки"),
    S("read_fight", "Чтение боя", KIND_AURA, "tech info", 0, {"suppress": 0.015}, "реакции противника слабее на {v}%"),
    S("precision", "Точный удар", KIND_AURA, "tech", 0, {"sure_hit": 0.015}, "{v}% атаки проходит сквозь уклонение и блок"),
    S("weak_points", "Слабые места", KIND_AURA, "tech info", 0, {"crit_chance": 0.01}, "+{v} п.п. к шансу крита"),
    S("finisher", "Добивание", KIND_AURA, "power tech", 0, {"crit_power": 0.04}, "+{v}% к силе крита"),
    S("speed_crew", "Скорость", KIND_ECO, "speed", 0, {"battle_cooldown": 0.02, "dodge": 0.003}, "−{v}% КД сражений и +{v2} п.п. к уклонению"),
    S("tactical_retreat", "Тактическое отступление", KIND_AURA, "endurance", 0, {"loss_save": 0.015}, "{v}% павших выживают после боя"),
    S("ambush", "Засада", KIND_TRIGGER, "tech dark", 1, {"when": WHEN_ENEMY_STRONGER, "enemy_reactions_r1": -1.0, "attack": 0.03}, "если противник сильнее — в 1-м раунде у него нет реакций, а у тебя +{v2}% атаки"),
    S("feint", "Ложное отступление", KIND_TRIGGER, "tech", 1, {"when": WHEN_HEAVY_ROUND, "attack": 0.08}, "после раунда с потерей >25% армии — следующий раунд +{v}% атаки"),
    S("regroup", "Перегруппировка", KIND_TRIGGER, "discipline", 1, {"when": WHEN_BELOW_50, "dodge": 0.03, "block": 0.03}, "армия ниже половины — +{v} п.п. к уклонению и блоку"),
    S("pincer", "Клещи", KIND_AURA, "tech power", 1, {"cleave": 0.015}, "+{v}% урона по толпе"),
    S("attrition", "Изматывание", KIND_AURA, "endurance", 1, {"ramp": 0.008, "ramp_cap": 0.06}, "+{v}% атаки за раунд (до +{v2}%)"),
    S("quick_start", "Быстрый старт", KIND_AURA, "speed", 1, {"rush": 0.04, "rush_rounds": 2}, "+{v}% атаки в первые 2 раунда"),
    S("patience", "Терпение", KIND_TRIGGER, "discipline", 1, {"when": WHEN_ROUND_4_PLUS, "attack": 0.05}, "с 4-го раунда +{v}% атаки"),
    S("read_moves", "Читать движения", KIND_AURA, "info", 1, {"enemy_crit": -0.02}, "шанс крита противника −{v} п.п."),
    S("disperse", "Рассредоточение", KIND_AURA, "defense speed", 1, {"reduction": 0.01}, "{v}% входящего урона гасится"),
    S("flank", "Обход с фланга", KIND_AURA, "speed tech", 1, {"first_strike": 0.004}, "{v}% армии противника выбито до боя"),
    S("rhythm", "Ритм", KIND_TRIGGER, "tech", 2, {"when": WHEN_EVERY_3RD, "attack": 0.12}, "каждый 3-й раунд +{v}% атаки"),
    S("slow_burn", "Затяжной бой", KIND_TRIGGER, "endurance", 2, {"when": WHEN_WEAKER_ROUND_3, "enemy_attack": -0.06}, "если ты слабее — с 3-го раунда атака противника −{v}%"),
    S("adaptation", "Адаптация", KIND_AURA, "copy tech", 2, {"copy": 0.04}, "копирует {v}% боевых бафов противника"),
    S("foresight", "Предвидение", KIND_INTEL, "info", 2, {"field": F_FORECAST}, "в отчёте разведки — шанс победы над целью (точность растёт с редкостью)"),
    S("strategist", "Стратег", KIND_META, "tech leader", 2, {"warlord_defender_boost": 0.06}, "навыки Военачальника и Защитника сильнее на {v}%"),
    S("decoy", "Приманка", KIND_TRIGGER, "dark", 2, {"when": WHEN_ROUND_1, "reduction": 0.15}, "в 1-м раунде {v}% урона по тебе гасится"),
    S("analysis", "Разбор боя", KIND_AURA, "info", 2, {"crit_power": 0.03}, "+{v}% к силе крита"),
    S("speed_of_light", "Сверхскорость", KIND_AURA, "speed", 2, {"dodge": 0.012, "flee": 0.008}, "+{v} п.п. к уклонению и +{v2} п.п. к побегу"),
    S("tactical_genius", "Гений тактики", KIND_META, "tech", 3, {"triggers_boost": 0.14}, "условные навыки банды сильнее на {v}%"),
    S("perfect_tactics", "Совершенная тактика", KIND_TRIGGER, "tech", 4, {"when": WHEN_ROUND_1, "enemy_no_reactions": 1, "attack": 0.04}, "в 1-м раунде противник не уклоняется и не блокирует; +{v2}% атаки"),
]

# ───────────────────────── ВОЕНАЧАЛЬНИК: нападение ─────────────────────────
POOLS[POS_WARLORD] = [
    S("charge", "В атаку", KIND_ATK, "power", 0, {"army_power": 0.025}, "+{v}% мощи лагеря атаки"),
    S("opening_blow", "Первый удар", KIND_AURA, "power", 0, {"opening": 0.05}, "+{v}% атаки в первом раунде"),
    S("onslaught", "Натиск", KIND_AURA, "power speed", 0, {"rush": 0.04, "rush_rounds": 2}, "+{v}% атаки в первые 2 раунда"),
    S("momentum", "Разгон", KIND_AURA, "power", 0, {"ramp": 0.008, "ramp_cap": 0.06}, "+{v}% атаки за раунд (до +{v2}%)"),
    S("crushing", "Сокрушение", KIND_AURA, "power", 0, {"crit_chance": 0.01}, "+{v} п.п. к шансу крита"),
    S("heavy_hand", "Тяжёлая рука", KIND_AURA, "power", 0, {"crit_power": 0.05}, "+{v}% к силе крита"),
    S("rend", "Рассечение", KIND_AURA, "weapon", 0, {"bleed": 0.01}, "{v}% дошедшего урона бьёт ещё раз в следующем раунде"),
    S("sweep", "Сметающий", KIND_AURA, "power", 0, {"cleave": 0.015}, "+{v}% урона по толпе"),
    S("pierce", "Пробитие", KIND_AURA, "weapon tech", 0, {"pierce": 0.012}, "{v}% брони противника игнорируется"),
    S("no_miss", "Без промаха", KIND_AURA, "tech", 0, {"sure_hit": 0.015}, "{v}% атаки проходит сквозь уклонение и блок"),
    S("surprise", "Внезапность", KIND_AURA, "speed dark", 1, {"first_strike": 0.004}, "{v}% армии противника выбито до боя"),
    S("stormer", "Штурмовик", KIND_VS, "power", 1, {"vs": VS_DISTRICT, "attack": 0.05}, "+{v}% атаки в боях за районы"),
    S("siege", "Осада", KIND_VS, "power", 1, {"vs": VS_CITY, "attack": 0.05}, "+{v}% атаки против ботов городов"),
    S("duelist", "Дуэлянт", KIND_VS, "tech", 1, {"vs": VS_PVP, "attack": 0.05}, "+{v}% атаки в вызовах игрокам"),
    S("hunter", "Охотник", KIND_VS, "power", 1, {"vs": VS_BOSS, "attack": 0.06}, "+{v}% атаки против боссов"),
    S("conqueror", "Завоеватель", KIND_VS, "leader power", 1, {"vs": VS_WAR, "attack": 0.05}, "+{v}% атаки в войнах императоров"),
    S("rage", "Ярость", KIND_AURA, "rage power", 1, {"attack": 0.05, "durability": -0.02}, "+{v}% атаки, но −{v2}% ХП (берсерк)"),
    S("madness", "Безумие", KIND_AURA, "rage chaos", 1, {"chaos": 0.01}, "{v}% шанс хаоса в раунд: удар ×2 и сбой реакций врага"),
    S("bloodlust", "Жажда крови", KIND_AURA, "rage dark", 1, {"grow_on_kill": 0.02}, "атака растёт от доли убитых врагов (+{v}%)"),
    S("relentless", "Неудержимый", KIND_ECO, "speed", 1, {"no_cd_on_win": 0.03}, "{v}% шанс, что победа не ставит КД сражений"),
    S("march", "Марш", KIND_ECO, "speed", 2, {"battle_cooldown": 0.025}, "−{v}% КД сражений"),
    S("spoils", "Трофеи", KIND_ECO, "money", 2, {"influence": 2}, "+{v} влияния (выше потолок ранга вербовки)"),
    S("loot", "Добыча", KIND_ECO, "money", 2, {"fragment_bonus": 0.04}, "+{v}% фрагментов с боссов"),
    S("armed", "Вооружённый", KIND_AURA, "weapon", 2, {"attack": 0.02, "pierce": 0.01}, "+{v}% атаки и {v2}% пробития"),
    S("battle_brothers", "Боевое братство", KIND_ATK, "leader support", 2, {"per_filled_slot": 0.005}, "+{v}% мощи лагеря атаки за каждую занятую позицию"),
    S("battle_cry", "Боевой клич", KIND_TRIGGER, "power", 2, {"when": WHEN_ROUND_1, "enemy_reactions": -0.03}, "в 1-м раунде реакции противника −{v} п.п."),
    S("double_capture", "Двойной захват", KIND_ECO, "speed power", 2, {"no_cd_bots": 0.05}, "{v}% шанс, что бой с ботами не ставит КД"),
    S("no_mercy", "Без пощады", KIND_AURA, "dark", 2, {"enemy_loss_save": -0.03}, "спасение павших у противника −{v}%"),
    S("destroyer", "Разрушитель", KIND_AURA, "power weapon", 3, {"pierce": 0.025, "suppress": 0.025}, "{v}% пробития и реакции противника слабее на {v2}%"),
    S("war_god", "Бог войны", KIND_META, "power", 4, {"attack_skills": 0.05}, "все атакующие навыки банды сильнее на {v}%"),
]

# ───────────────────────── ЗАЩИТНИК: лагерь защиты ─────────────────────────
POOLS[POS_DEFENDER] = [
    S("wall", "Стена", KIND_DEF, "defense", 0, {"army_power": 0.025}, "+{v}% мощи лагеря защиты"),
    S("fortress", "Крепость", KIND_DEF, "defense endurance", 0, {"durability": 0.025}, "+{v}% ХП бойцов в защите"),
    S("armor", "Броня", KIND_DEF, "defense", 0, {"reduction": 0.012}, "{v}% входящего урона гасится в защите"),
    S("shield", "Щит", KIND_DEF, "defense", 0, {"block": 0.01}, "+{v} п.п. к блоку в защите"),
    S("sidestep", "Уход", KIND_DEF, "speed", 0, {"dodge": 0.01}, "+{v} п.п. к уклонению в защите"),
    S("counterblow", "Контрудар", KIND_DEF, "tech", 0, {"counter": 0.01}, "+{v} п.п. к контратаке в защите"),
    S("cover", "Укрытие", KIND_DEF, "endurance", 0, {"loss_save": 0.02}, "{v}% павших защитников выживают"),
    S("trenches", "Окопы", KIND_TRIGGER, "defense", 0, {"when": WHEN_DEF_ROUND_1, "enemy_attack": -0.05}, "в защите: в 1-м раунде атака нападающего −{v}%"),
    S("traps", "Ловушки", KIND_DEF, "dark tech", 0, {"first_strike": 0.004}, "в защите: {v}% нападающих выбито до боя"),
    S("barbed_wire", "Колючая проволока", KIND_DEF, "defense", 0, {"reflect": 0.02}, "в защите: {v}% дошедшего урона возвращается нападающему"),
    S("absorb", "Поглощение", KIND_DEF, "endurance tech", 1, {"absorb_store": 0.02, "absorb_return": 1.0}, "в защите: {v}% урона копится и возвращается в атаку"),
    S("endure", "Терпеть", KIND_DEF, "endurance", 1, {"adapt_threshold": 0.3, "adapt_bonus": 0.05, "adapt_guard": 0.02}, "пока не потеряно 30% — +{v3}% гашения, потом +{v2}% атаки"),
    S("medicine", "Перевязка", KIND_DEF, "support endurance", 1, {"heal": 0.012}, "в защите: {v}% павших за раунд возвращаются"),
    S("last_stand", "Последний рубеж", KIND_TRIGGER, "endurance defense", 1, {"when": WHEN_DEF_BELOW_30, "durability": 0.08, "block": 0.03}, "защита ниже 30% — +{v}% ХП и +{v2} п.п. блока"),
    S("home_walls", "Свои стены", KIND_DEF, "defense leader", 1, {"durability": 0.02, "block": 0.005}, "в защите +{v}% ХП и +{v2} п.п. блока"),
    S("reinforce", "Подкрепление", KIND_DEF, "support", 1, {"army_power": 0.02}, "+{v}% мощи лагеря защиты"),
    S("sentry", "Часовой", KIND_DEF, "info", 1, {"accept_window": 0.08}, "+{v}% времени на принятие вызова"),
    S("vigilance", "Бдительность", KIND_DEF, "info", 1, {"dodge": 0.01}, "+{v} п.п. к уклонению в защите"),
    S("impregnable", "Неприступность", KIND_DEF, "defense", 1, {"block": 0.01}, "+{v} п.п. к блоку в защите"),
    S("repulse", "Отпор", KIND_TRIGGER, "power defense", 1, {"when": WHEN_DEF_WIN, "enemy_extra_dead": 0.03}, "отбив атаку — нападающий теряет ещё {v}% выживших"),
    S("garrison", "Гарнизон", KIND_VS, "defense support", 2, {"vs": VS_CLAN_WAR, "army_power": 0.05}, "+{v}% мощи роты клана в защите земель"),
    S("militia", "Ополчение", KIND_VS, "defense", 2, {"vs": VS_WAR, "army_power": 0.05}, "+{v}% мощи в войнах императоров (в защите)"),
    S("steadfast", "Непоколебимость", KIND_DEF, "discipline", 2, {"anti_suppress": 0.05}, "ослабление твоих реакций противником −{v}%"),
    S("grit", "Стойкость", KIND_DEF, "endurance", 2, {"enemy_crit": -0.02}, "в защите шанс крита нападающего −{v} п.п."),
    S("iron_skin", "Железная кожа", KIND_DEF, "defense", 2, {"anti_pierce": 0.03}, "пробитие нападающего −{v}%"),
    S("clotting", "Свёртывание", KIND_DEF, "endurance", 2, {"anti_bleed": 0.05}, "кровотечение по тебе −{v}%"),
    S("composure", "Хладнокровие", KIND_DEF, "discipline", 2, {"anti_chaos": 0.05}, "шанс хаоса нападающего −{v}%"),
    S("counteroffensive", "Контрнаступление", KIND_DEF, "power", 2, {"counter": 0.01, "attack": 0.015}, "в защите +{v} п.п. контратаки и +{v2}% атаки"),
    S("bastion", "Бастион", KIND_TRIGGER, "defense", 3, {"when": WHEN_DEF_ROUNDS_1_2, "reduction": 0.03}, "в защите: в 1–2 раундах {v}% урона гасится"),
    S("unbreakable", "Несокрушимый", KIND_META, "defense endurance", 4, {"def_loss_cap": 0.6}, "лагерь защиты теряет не больше {v}% за бой"),
]

# ───────────────────────── БИЗНЕСМЕН: экономика ─────────────────────────
POOLS[POS_BUSINESSMAN] = [
    S("cashbox", "Касса", KIND_ECO, "money", 0, {"income": 0.02}, "+{v}% дохода всех зданий"),
    S("cafe_owner", "Своё кафе", KIND_ECO, "money", 0, {"income_cafe": 0.05}, "+{v}% дохода кафе"),
    S("shop_owner", "Сеть магазинов", KIND_ECO, "money", 0, {"income_shop": 0.05}, "+{v}% дохода магазинов"),
    S("gym_owner", "Спортзалы", KIND_ECO, "money power", 0, {"income_gym": 0.05}, "+{v}% дохода спортзалов"),
    S("dark_trade", "Тёмная торговля", KIND_ECO, "money dark", 0, {"income_black_market": 0.05}, "+{v}% дохода чёрных рынков"),
    S("lobby", "Лобби", KIND_ECO, "money leader", 0, {"income_parliament": 0.05}, "+{v}% дохода парламента"),
    S("warehouse", "Склад", KIND_ECO, "money", 0, {"storage_hours": 1.5}, "+{v} ч к хранилищу дохода"),
    S("developer", "Застройщик", KIND_ECO, "money", 0, {"build_discount": 0.03}, "−{v}% цены постройки"),
    S("renovation", "Ремонт", KIND_ECO, "money", 0, {"upgrade_discount": 0.03}, "−{v}% цены прокачки бизнеса"),
    S("tax_advisor", "Налоговый консультант", KIND_ECO, "money", 0, {"tax_relief": 0.04}, "−{v}% налога императора"),
    S("investor", "Инвестор", KIND_ECO, "money", 1, {"deposit_rate": 0.04}, "+{v}% к процентам вкладов"),
    S("broker", "Брокер", KIND_ECO, "money", 1, {"exchange_fee": 0.05}, "−{v}% комиссии биржи и аукциона"),
    S("purchaser", "Закупщик", KIND_ECO, "money support", 1, {"contract_discount": 0.03}, "−{v}% цены контрактов статистов"),
    S("pharmacist", "Фармацевт", KIND_ECO, "money support", 1, {"potion_discount": 0.03}, "−{v}% цены зелий"),
    S("lucky", "Везунчик", KIND_ECO, "money chaos", 1, {"gacha_free_roll": 0.01}, "{v}% шанс, что крутка не потратит тикет"),
    S("collector", "Коллекционер", KIND_ECO, "money", 1, {"gacha_luck": 0.008}, "{v}% шанс поднять редкость выпавшего уника"),
    S("ticket_dealer", "Перекупщик тикетов", KIND_ECO, "money speed", 1, {"ticket_regen": 0.03}, "тикеты копятся на {v}% быстрее"),
    S("sponsor", "Спонсор", KIND_ECO, "money leader", 1, {"income": 0.01}, "+{v}% дохода зданий"),
    S("cashback", "Откат", KIND_ECO, "money dark", 1, {"cashback": 0.02}, "{v}% NHCoin, потраченных на стройку и прокачку, возвращается"),
    S("double_shift", "Двойная смена", KIND_ECO, "money", 1, {"double_collect": 0.02}, "{v}% шанс удвоить доход при сборе"),
    S("network", "Сеть", KIND_ECO, "money", 2, {"income": 0.012, "storage_hours": 1.0}, "+{v}% дохода и +{v2} ч к хранилищу"),
    S("monopoly", "Монополия", KIND_ECO, "money dark", 2, {"income_shop": 0.04, "income_cafe": 0.04}, "+{v}% дохода магазинов и +{v2}% дохода кафе"),
    S("holdings", "Холдинг", KIND_ECO, "money leader", 2, {"income": 0.015}, "+{v}% дохода зданий"),
    S("mercenaries", "Наёмники", KIND_ECO, "money power", 2, {"contract_duration": 0.05}, "контракты статистов действуют на {v}% дольше"),
    S("logistics", "Логистика", KIND_ECO, "money", 2, {"storage_fee": 0.05}, "−{v}% платы за ячейки хранения статистов"),
    S("audit", "Аудит", KIND_HIDE, "money defense", 2, {"anti_treasury_theft": 0.05}, "шанс кражи казны саботажем −{v} п.п."),
    S("reserve_fund", "Резервный фонд", KIND_ECO, "money", 2, {"full_storage_bonus": 0.05}, "если хранилище было полным — сбор +{v}%"),
    S("market_maker", "Маркетмейкер", KIND_ECO, "money info", 2, {"exchange_fee": 0.05}, "−{v}% комиссии аукциона"),
    S("tycoon", "Магнат", KIND_ECO, "money leader", 3, {"income": 0.015, "build_discount": 0.01}, "+{v}% дохода и −{v2}% цены постройки"),
    S("money_king", "Король денег", KIND_ECO, "money", 4, {"income": 0.01, "storage_hours": 2.0}, "+{v}% дохода и +{v2} ч к хранилищу"),
]

# ───────────────────────── ШПИОН: перед твоей атакой, с шансом ─────────────────────────
# `p` — базовый шанс срабатывания (×GRADE, не выше 90%); контрразведка противника снижает.
POOLS[POS_SPY] = [
    S("poison", "Подмешать в еду", KIND_SPY, "dark", 0, {"p": 0.15, "pre_kill": 0.01}, "{p}% шанс: {v}% армии противника выбывает до боя"),
    S("bribe", "Подкуп", KIND_SPY, "dark money", 0, {"p": 0.15, "desert": 0.015}, "{p}% шанс: {v}% бойцов противника не выходят на бой (не гибнут)"),
    S("broken_clock", "Сбитые часы", KIND_SPY, "dark", 0, {"p": 0.2, "enemy_attack_r1": -0.06}, "{p}% шанс: в 1-м раунде атака противника −{v}%"),
    S("torn_bandages", "Порванные бинты", KIND_SPY, "dark", 0, {"p": 0.2, "enemy_durability": -0.03}, "{p}% шанс: ХП бойцов противника −{v}%"),
    S("rumor", "Слух", KIND_SPY, "info", 0, {"p": 0.2, "enemy_dodge": -0.01}, "{p}% шанс: уклонение противника −{v} п.п."),
    S("cut_straps", "Подрезанные ремни", KIND_SPY, "dark", 0, {"p": 0.2, "enemy_block": -0.01}, "{p}% шанс: блок противника −{v} п.п."),
    S("trip", "Подножка", KIND_SPY, "dark speed", 0, {"p": 0.2, "enemy_counter": -0.01}, "{p}% шанс: контратака противника −{v} п.п."),
    S("cut_off", "Отрезать путь", KIND_SPY, "dark tech", 0, {"p": 0.2, "enemy_flee": -0.01}, "{p}% шанс: побег противника −{v} п.п."),
    S("blind_scouts", "Ослепить разведку", KIND_SPY, "info", 0, {"p": 0.25, "enemy_crit": -0.015}, "{p}% шанс: противник бьёт вслепую — шанс его крита −{v} п.п."),
    S("silent_night", "Тихая ночь", KIND_SPY, "dark", 0, {"p": 0.25, "first_strike": 0.004}, "{p}% шанс: тихо снять часовых — {v}% армии противника выбито до боя"),
    S("behead", "Обезглавить", KIND_SPY, "dark", 1, {"p": 0.06, "disable": POS_LEADER}, "{p}% шанс: навыки Главы противника не работают в этом бою"),
    S("topple_deputy", "Сбить зама", KIND_SPY, "dark", 1, {"p": 0.08, "disable": POS_DEPUTY}, "{p}% шанс: отключить Заместителя противника"),
    S("steal_plan", "Украсть план", KIND_SPY, "info tech", 1, {"p": 0.08, "disable": POS_TACTICIAN}, "{p}% шанс: отключить Тактика противника"),
    S("disarm", "Разоружить", KIND_SPY, "dark weapon", 1, {"p": 0.08, "disable": POS_WARLORD}, "{p}% шанс: отключить Военачальника противника"),
    S("breach", "Вскрыть оборону", KIND_SPY, "dark", 1, {"p": 0.08, "disable": POS_DEFENDER}, "{p}% шанс: отключить Защитника противника"),
    S("steal_technique", "Украсть технику", KIND_SPY, "copy tech", 1, {"p": 0.12, "steal_technique": 0.1}, "{p}% шанс: забрать на бой {v}% бафов уникальной техники противника"),
    S("swap_potions", "Подменить зелья", KIND_SPY, "dark", 1, {"p": 0.12, "disable_potions": 1}, "{p}% шанс: зелья противника не действуют в этом бою"),
    S("demoralize", "Деморализация", KIND_SPY, "dark info", 1, {"p": 0.15, "enemy_loss_save": -0.04}, "{p}% шанс: спасение павших у противника −{v}%"),
    S("panic", "Паника", KIND_SPY, "dark", 1, {"p": 0.12, "enemy_flee_r1": 0.03}, "{p}% шанс: {v}% бойцов противника бегут в 1-м раунде"),
    S("backstab", "Удар в спину", KIND_SPY, "dark", 1, {"p": 0.12, "first_strike": 0.006}, "{p}% шанс: {v}% армии противника выбито до боя"),
    S("poisoned_blades", "Отравленные клинки", KIND_SPY, "dark weapon", 2, {"p": 0.15, "bleed": 0.02}, "{p}% шанс: твои удары вызывают кровотечение +{v}%"),
    S("weak_spot", "Слабая точка", KIND_SPY, "info", 2, {"p": 0.15, "crit_chance": 0.02}, "{p}% шанс: +{v} п.п. к криту в этом бою"),
    S("false_order", "Ложный приказ", KIND_SPY, "dark info", 2, {"p": 0.12, "enemy_attack_r12": -0.05}, "{p}% шанс: в 1–2 раундах атака противника −{v}%"),
    S("trophies", "Сбить прицел", KIND_SPY, "dark info", 2, {"p": 0.2, "enemy_crit": -0.02}, "{p}% шанс: шанс крита противника −{v} п.п."),
    S("forced_march", "Ускоренный марш", KIND_SPY, "speed dark", 2, {"p": 0.3, "enemy_accept_window": -0.1}, "{p}% шанс: у защитника −{v}% времени на принятие вызова"),
    S("double_game", "Двойная игра", KIND_META, "dark", 2, {"repeat": 0.08}, "{v}% шанс повторить каждый сработавший шпионский навык"),
    S("network", "Агентурная сеть", KIND_META, "info dark", 2, {"spy_chance": 0.04}, "+{v} п.п. к шансу всех шпионских навыков"),
    S("sleeper", "Спящий агент", KIND_SPY, "dark", 2, {"p": 0.1, "enemy_attack_camp_out": 0.03}, "{p}% шанс: {v}% бойцов противника не выходят на бой"),
    S("puppeteer", "Кукловод", KIND_SPY, "dark copy", 3, {"p": 0.15, "steal_skill": 1}, "{p}% шанс: один случайный навык противника работает на тебя"),
    S("kings_shadow", "Тень короля", KIND_META, "dark", 4, {"pierce_counterintel": 1}, "шпионские навыки не срываются контрразведкой ниже по уровню"),
]

# ───────────────────────── РАЗВЕДКА: атомарные данные о цели ─────────────────────────
# Разведка — ОТДЕЛЬНЫЙ ЭТАП (пользователь 2026-10-16): кнопка «Разведать» у района, города или
# игрока, без КД. Что попадёт в отчёт — решают навыки карты на позиции Разведки. Отчёт
# сохраняется (снимок на момент разведки) и открывается в любой момент, в т.ч. перед атакой.
# Уровень разведки = редкость карты (1…9). Поле открыто, если уровень разведки ВЫШЕ уровня
# сокрытия этого поля у цели; равенство — видна вилка («~120–150k»), ниже — «скрыто».
POOLS[POS_SCOUT] = [
    S("headcount", "Счёт голов", KIND_INTEL, "info", 0, {"field": F_HEADCOUNT}, "видно число статистов цели"),
    S("weigh_fists", "Взвесить кулаки", KIND_INTEL, "info power", 0, {"field": F_ATTACK_POWER}, "видна мощь лагеря атаки"),
    S("weigh_guard", "Оценить оборону", KIND_INTEL, "info defense", 0, {"field": F_DEFENSE_POWER}, "видна мощь лагеря защиты"),
    S("rank_grid", "Ранговая сетка", KIND_INTEL, "info", 0, {"field": F_RANKS}, "видна раскладка статистов по рангам"),
    S("top_squads", "Лучшие отряды", KIND_INTEL, "info power", 0, {"field": F_TOP_SQUADS}, "видны три сильнейших отряда"),
    S("faces", "Лица банды", KIND_INTEL, "info leader", 0, {"field": F_LINEUP}, "видно, кто стоит на позициях"),
    S("weak_link", "Слабое звено", KIND_INTEL, "info", 0, {"field": F_EMPTY_SLOTS}, "видно, какие позиции пустуют"),
    S("cooldown_watch", "Распорядок", KIND_INTEL, "info speed", 0, {"field": F_COOLDOWNS}, "видно, когда цель снова сможет атаковать"),
    S("connections", "Связи", KIND_INTEL, "info", 0, {"field": F_CLAN}, "виден клан цели и её ранг"),
    S("tail", "Хвост", KIND_INTEL, "info dark", 0, {"field": F_CHALLENGES}, "видны висящие вызовы цели"),
    S("read_skills", "Чтение навыков", KIND_INTEL, "info tech", 1, {"field": F_SKILLS}, "видны навыки позиций цели"),
    S("roots", "Корни", KIND_INTEL, "info", 1, {"field": F_BLOODLINE}, "видна родословная"),
    S("path_seer", "Путь", KIND_INTEL, "info", 1, {"field": F_PATH}, "виден путь"),
    S("style", "Стиль", KIND_INTEL, "info tech", 1, {"field": F_TECHNIQUE}, "видна уникальная техника"),
    S("talent", "Талант", KIND_INTEL, "info", 1, {"field": F_GENIUS}, "видна гениальность"),
    S("medkit", "Аптечка", KIND_INTEL, "info", 1, {"field": F_POTIONS}, "видны активные зелья"),
    S("wallet", "Кошелёк", KIND_INTEL, "info money", 1, {"field": F_WALLET}, "видны NHCoin и доход в минуту"),
    S("real_estate", "Недвижимость", KIND_INTEL, "info money", 1, {"field": F_BUSINESS}, "видны бизнесы цели по типам"),
    S("chronicle", "Хроника", KIND_INTEL, "info", 1, {"field": F_BATTLES}, "видны последние бои цели"),
    S("early_alarm", "Ранняя тревога", KIND_DEF, "info speed", 1, {"accept_window": 0.06}, "+{v}% времени на принятие вызова"),
    S("know_enemy", "Знай врага", KIND_ECO, "info power", 2, {"scouted_attack": 0.04}, "+{v}% атаки против цели, на которую у тебя есть отчёт разведки"),
    S("expose", "Вскрыть слабости", KIND_ECO, "info tech", 2, {"scouted_enemy_block": -0.02}, "цель из твоего отчёта разведки −{v} п.п. блока в бою с тобой"),
    S("terrain", "Знание местности", KIND_VS, "info", 2, {"vs": VS_BOTS, "dodge": 0.02}, "+{v} п.п. уклонения в боях с ботами"),
    S("forecast", "Расчёт исхода", KIND_INTEL, "info tech", 2, {"field": F_FORECAST}, "в отчёте разведки — прогноз боя с целью (точность растёт с редкостью)"),
    S("watcher", "Наблюдатель", KIND_ECO, "info", 2, {"marks": 1}, "+{v} слот метки на игроков"),
    S("informants", "Сеть информаторов", KIND_ECO, "info dark", 2, {"marks": 1}, "+{v} слот метки на игроков"),
    S("counter_read", "Встречная разведка", KIND_DEF, "info", 2, {"reduction": 0.01}, "зная ход врага, в защите гасит {v}% урона"),
    S("deep_cover", "Глубокое погружение", KIND_META, "info dark", 2, {"intel_level": 1}, "+{v} к уровню всех разведок"),
    S("god_eye", "Глаз бога", KIND_META, "info copy", 3, {"see_through_fakes": 1}, "видит настоящие данные сквозь дезинформацию"),
    S("all_seeing", "Всевидящий", KIND_META, "info", 4, {"intel_level": 2, "range_as_exact": 1}, "+2 к уровню разведок; вилка превращается в точное значение"),
]

# ───────────────────────── БЕЗОПАСНОСТЬ: прятать данные и ловить чужих ─────────────────────────
POOLS[POS_SECURITY] = [
    S("fog", "Туман", KIND_HIDE, "defense info", 0, {"field": F_HEADCOUNT}, "скрыто число статистов"),
    S("closed_fists", "Закрытые кулаки", KIND_HIDE, "defense", 0, {"field": F_ATTACK_POWER}, "скрыта мощь лагеря атаки"),
    S("blind_guard", "Глухая оборона", KIND_HIDE, "defense", 0, {"field": F_DEFENSE_POWER}, "скрыта мощь лагеря защиты"),
    S("mixed_ranks", "Смешанные ранги", KIND_HIDE, "defense", 0, {"field": F_RANKS}, "скрыта раскладка по рангам"),
    S("shadow_squads", "Тень отрядов", KIND_HIDE, "defense dark", 0, {"field": F_TOP_SQUADS}, "скрыты сильнейшие отряды"),
    S("masks", "Маски", KIND_HIDE, "defense dark", 0, {"field": F_LINEUP}, "скрыто, кто стоит на позициях"),
    S("full_house", "Полный состав", KIND_HIDE, "defense", 0, {"field": F_EMPTY_SLOTS}, "скрыты пустые позиции"),
    S("false_schedule", "Ложный распорядок", KIND_HIDE, "defense", 0, {"field": F_COOLDOWNS}, "скрыто, когда ты снова сможешь атаковать"),
    S("anonymity", "Анонимность", KIND_HIDE, "defense", 0, {"field": F_CLAN}, "скрыт клан"),
    S("clean_tail", "Чистый хвост", KIND_HIDE, "defense", 0, {"field": F_CHALLENGES}, "скрыты висящие вызовы"),
    S("muteness", "Немота", KIND_HIDE, "defense tech", 1, {"field": F_SKILLS}, "скрыты навыки позиций"),
    S("blood_secret", "Тайна крови", KIND_HIDE, "defense", 1, {"field": F_BLOODLINE}, "скрыта родословная"),
    S("hidden_path", "Скрытый путь", KIND_HIDE, "defense", 1, {"field": F_PATH}, "скрыт путь"),
    S("closed_style", "Закрытый стиль", KIND_HIDE, "defense tech", 1, {"field": F_TECHNIQUE}, "скрыта техника"),
    S("quiet_genius", "Тихий гений", KIND_HIDE, "defense", 1, {"field": F_GENIUS}, "скрыта гениальность"),
    S("no_trace", "Без следа", KIND_HIDE, "defense", 1, {"field": F_POTIONS}, "скрыты зелья"),
    S("offshore", "Офшор", KIND_HIDE, "defense money", 1, {"field": F_WALLET}, "скрыт кошелёк и доход"),
    S("fronts", "Подставные лица", KIND_HIDE, "defense money", 1, {"field": F_BUSINESS}, "скрыты бизнесы"),
    S("erased", "Стёртая хроника", KIND_HIDE, "defense", 1, {"field": F_BATTLES}, "скрыты последние бои"),
    S("disinformation", "Дезинформация", KIND_META, "dark info", 1, {"fake_numbers": 0.08}, "разведка видит числа с искажением до ±{v}%"),
    S("double_agent", "Двойной агент", KIND_ECO, "info dark", 2, {"reveal_scout": 1}, "когда тебя разведали — ты узнаёшь, кто"),
    S("counter_trap", "Ответный удар", KIND_ECO, "dark", 2, {"scout_trap": 0.01}, "разведавший тебя теряет {v}% статистов младшего ранга"),
    S("counterintel", "Контрразведка", KIND_META, "defense info", 2, {"anti_spy": 0.05}, "шанс шпионских навыков против тебя −{v} п.п."),
    S("hq_guard", "Охрана штаба", KIND_META, "defense", 2, {"anti_disable": 0.1}, "{v}% шанс, что шпион не отключит твою позицию"),
    S("quarantine", "Карантин", KIND_META, "defense endurance", 2, {"anti_poison": 0.2}, "яд и подкуп шпиона действуют на {v}% слабее"),
    S("clean_ranks", "Чистые ряды", KIND_META, "defense", 2, {"anti_sabotage": 0.05}, "шанс саботажа против тебя −{v} п.п."),
    S("cloak", "Скрытность", KIND_ECO, "dark", 2, {"stealth": 1}, "твоё имя скрыто в отчётах и списках"),
    S("alarm", "Тревога", KIND_ECO, "info", 2, {"scout_alert": 1}, "пуш, когда тебя разведали"),
    S("impenetrable", "Непроницаемость", KIND_META, "defense", 3, {"hide_level": 1}, "+1 к уровню сокрытия всех полей"),
    S("ghost", "Призрак", KIND_META, "dark defense", 4, {"unmarkable": 1, "hide_level": 1}, "тебя нельзя пометить; +1 к уровню сокрытия"),
]


SKILLS: dict[tuple[str, str], Skill] = {(pos, s.code): s for pos, pool in POOLS.items() for s in pool}

for _pos, _pool in POOLS.items():
    assert len(_pool) == 30 and len({s.code for s in _pool}) == 30, _pos
