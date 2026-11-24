"""Приёмы ветвей v3 — родословные и пути (пользователь 2026-11-24, `docs/design/paths_bloodlines_v3.md`).

Было: у каждой ветки 4 перка-ступени (уровни 1/4/7/10), у путей — безымянные «вспышки». Стало: 2–3 своих приёма,
1-й с 1-го уровня, 2-й с 4-го, 3-й (коронный) с 7-го; **сила приёма растёт с уровнем ветки** — числа в таблицах
ниже даны для 10-го уровня, на 1-м приём работает на `LEVEL_FACTOR_MIN` (40%), дальше линейно. На 10-м у коронного
приёма «Предел» — мини-игра (если у приёма задана `power`). Цена и КД от уровня не зависят.

Коды перков: `<вид>:<ветка>:<номер приёма>@<уровень>` (`blood:elite:2@7`). В наборе в бой хранится код без
уровня — прокачка ветки ничего не сбивает (`perk_base`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bot.config.arena.perks import Perk
from bot.services.combat.mods import CombatMods

M = CombatMods

BRANCH_UNLOCK: tuple[int, ...] = (1, 4, 7)  # с какого уровня ветки открывается приём 1/2/3
BRANCH_COST: tuple[int, ...] = (3, 4, 5)
BRANCH_COOLDOWN: tuple[int, ...] = (2, 3, 3)
BRANCH_MAX_LEVEL = 10
LEVEL_FACTOR_MIN = 0.4  # сила приёма на 1-м уровне ветки (на 10-м — 1.0)


def level_factor(level: int) -> float:
    level = max(1, min(BRANCH_MAX_LEVEL, level))
    return LEVEL_FACTOR_MIN + (1 - LEVEL_FACTOR_MIN) * (level - 1) / (BRANCH_MAX_LEVEL - 1)


def perk_base(code: str) -> str:
    """Код приёма без уровня (`blood:elite:2@7` → `blood:elite:2`) — для набора в бой."""
    return code.partition("@")[0]


@dataclass(frozen=True, slots=True)
class BranchMove:
    """Приём ветки — числа для 10-го уровня."""
    name: str
    mods: CombatMods = field(default_factory=CombatMods)
    enemy: CombatMods = field(default_factory=CombatMods)
    damage: float = 1.0
    enemy_damage: float = 1.0
    power: float = 0.0  # Предел (10-й уровень, только коронный): сила мини-игры
    minigame_self: bool = False  # мини-игра себе (по умолчанию — противнику)
    first_round_damage: float = 0.0
    copy_share: float = 0.0
    copy_path_share: float = 0.0
    mirror: bool = False
    energy_gain: int = 0
    lasting: int = 0
    vs_perk_enemy_damage: float = 1.0
    revenge: float = 0.0
    per_round: float = 0.0
    lesson: float = 0.0
    repeat_tech: bool = False
    clean_round_damage: float = 1.0
    reveal: int = 0


B = BranchMove

# --- Родословные -------------------------------------------------------------------------------------------------
# Ямадзаки, Ким Гапрён и Джинён не переделывались (популярные): их 4 прежних приёма сведены в 3 с той же силой на
# 10-м уровне (2-й и 3-й прежние слиты в один).
BLOOD_BRANCHES: dict[str, tuple[BranchMove, ...]] = {
    "elite": (
        B("Приказ элиты", damage=1.9),
        B("Строй элиты", M(reduction=0.35, durability=0.25)),
        B("Гордость элиты", damage=2.2, power=0.4),
    ),
    "mujin": (
        B("Удар до боя", M(first_strike=0.20)),
        B("Быстрый шаг", damage=2.0),
        B("Король Сеула", damage=3.0, power=0.5),
    ),
    "samdak": (
        B("Железная выучка", M(durability=0.45, reduction=0.20)),
        B("Перегрузка", damage=2.0),
        B("Выпуск", M(heal=0.35)),
    ),
    "sophia": (
        B("Контрудар", M(counter=0.7, counter_power=0.3)),
        B("Терпение", enemy_damage=0.45),
        B("Возмездие", damage=1.2, revenge=3.0, power=0.4),
    ),
    "kuroda": (
        B("Тень", M(dodge=0.45, first_strike=0.05)),
        B("Ложный след", M(suppress=0.55)),
        B("Удар из тени", damage=1.2, clean_round_damage=2.2, power=0.5),
    ),
    "jincheol": (
        B("Подкрепление", M(heal=0.30)),
        B("Наёмный удар", damage=2.0),
        B("Армия Джинчоля", M(attack=0.6, durability=0.6)),
    ),
    "hansu": (
        B("Урок", M(block=0.10, counter=0.10), lesson=0.8),
        B("Разбор ошибок", enemy_damage=0.55),
        B("Ученик превзошёл", repeat_tech=True, power=0.5),
    ),
    "penguan": (
        B("Деньги — сила", damage=1.8),
        B("Подкуп", enemy_damage=0.5),
        B("Монополия", damage=2.4, power=0.5),
    ),
    # нетронутые (прежние приёмы)
    "yamazaki": (
        B("Щит клана", M(first_hit_ward=0.5)),
        B("Тело Ямадзаки", M(durability=0.3, reduction=0.25)),
        B("Глава клана", energy_gain=2, power=0.5),
    ),
    "gapryong": (
        B("Кулак легенды", damage=1.4),
        B("Несломленный", M(durability=0.3, overcome=0.5)),
        B("Первое поколение", damage=2.2, power=0.5),
    ),
    "jinyeong": (
        B("Чужая сила", M(attack=0.3)),
        B("Гений копии", copy_share=0.35),
        B("Абсолютная копия", mirror=True, power=0.4),
    ),
}

# --- Пути --------------------------------------------------------------------------------------------------------
# Преодоление, Отчаяние и Бесконечная техника не переделывались: их приёмы — прежние «вспышки» ступеней 4/7/10
# (накопленные модификаторы пути × 1.25/1.5/1.75), см. `_kept_path_moves`.
PATH_BRANCHES: dict[str, tuple[BranchMove, ...]] = {
    "reflection": (
        B("Зеркальный блок", M(reduction=0.45, reflect=0.45)),
        B("Разбитое зеркало", M(reflect_burst_power=0.5), damage=2.0),
        B("Отражение судьбы", M(reflect=0.7), vs_perk_enemy_damage=0.3, power=0.4),
    ),
    "absorption": (
        B("Впитать", M(absorb_store=0.6)),
        B("Выплеснуть", M(absorb_return=0.5, absorb_power=0.3), damage=1.8),
        B("Насыщение", M(heal=0.4, absorb_store=0.2)),
    ),
    "copy": (
        B("Копия", mirror=True),  # открывает шкала копирования (`COPY_PERK_GAUGE`), а не уровень
        B("Чужая сила", copy_share=0.4),
        B("Слепок", copy_path_share=0.6, power=0.4),
    ),
    "foresight": (
        B("Прочитать удар", M(dodge=0.5), vs_perk_enemy_damage=0.4),
        B("Контрудар", M(counter=0.7)),
        B("Видение исхода", enemy_damage=0.6, lasting=2, reveal=3, power=0.4),
    ),
    "sensory": (
        B("Метка", M(attack=0.35), lasting=2),
        B("Слабое место", M(pierce=0.6, crit_chance=0.3)),
        B("Сенсорная волна", M(suppress=0.6), power=0.5),
    ),
    "sure_hit": (
        B("Неотвратимый", M(sure_hit=0.8)),
        B("Пробой брони", M(pierce=0.6), damage=1.5),
        B("Удар без промаха", M(sure_hit=1.0), damage=2.4, power=0.8, minigame_self=True),
    ),
    "adaptation": (
        B("Привыкание", enemy_damage=0.55),
        B("Опыт боя", per_round=0.06),
        B("Полная адаптация", M(attack=0.25, durability=0.25), lasting=99),
    ),
    "training": (
        B("Выучка", M(attack=0.35, durability=0.35)),
        B("Второе дыхание", M(heal=0.35)),
        B("Отработанный удар", damage=2.0, power=0.8, minigame_self=True),
    ),
    "evasion": (
        B("Уход", M(dodge=0.6)),
        B("Ответ из уклона", M(dodge_counter=0.7)),
        B("Призрак", enemy_damage=0.3, lasting=1, power=0.4),
    ),
    "business": (
        B("Подкуп", enemy_damage=0.6),
        B("Наёмники на час", M(heal=0.25)),
        B("Инвестиция в победу", damage=2.0, power=0.4),
    ),
}

KEPT_PATH_NAMES: dict[str, tuple[str, str, str]] = {
    "overcome": ("Шаг через стену", "Против сильного", "Преодоление предела"),
    "despair": ("Добить слабого", "Холодный расчёт", "Бездна отчаяния"),
    "infinite": ("Смена стоек", "Поток техник", "Бесконечность"),
}

# Сила приёмов ветки (подбирается симуляцией): множитель всех эффектов приёма. Ключ «вид:код».
# Нетронутые родословные — прежние множители их приёмов.
BRANCH_BOOST: dict[str, float] = {
    "blood:yamazaki": 1.8, "blood:gapryong": 0.85, "blood:jinyeong": 2.11,
    # v3 (2026-11-24): экономические ветки — приёмы сильнее (×1.6). Симуляция просила ×3, но это «урон ×4» и лечение
    # >100% — выглядит багом; их главная сила — доход, контракты, КПД и метки, которых симуляция не видит.
    "path:sensory": 1.6, "path:training": 1.6, "path:business": 1.6,
    "blood:samdak": 1.6, "blood:jincheol": 1.6, "blood:hansu": 1.6, "blood:penguan": 1.6,
}
# Потолки приёма после всех множителей — чтобы ни одна ветка не дала абсурдных чисел.
CAP_DAMAGE = 3.0
CAP_ENEMY_DAMAGE = 0.35  # урон противника не ниже ×0.35
CAP_MINIGAME_POWER = 0.6
CAP_HEAL = 0.6
CAP_MOD = 0.6  # любая доля приёма (уклонение, пробитие, подавление…)
CAP_MOD_BIG = 0.8  # атака и прочность


def _kept_path_moves(levels: dict, code: str) -> tuple[BranchMove, ...]:
    """Прежние «вспышки» ступеней 4/7/10 у нетронутых путей: накопленные модификаторы × 1.25/1.5/1.75, урон
    ×1.1/1.2/1.3, мини-игра на 10-м."""
    out = []
    for i, (lvl, name) in enumerate(zip((4, 7, 10), KEPT_PATH_NAMES[code])):
        mods = CombatMods()
        for spec in levels.get(code, ())[:lvl]:
            mods = mods + CombatMods.of(spec.get("combat", {}))
        out.append(B(name, mods.scale(1.25 + 0.25 * i), damage=1.1 + 0.1 * i, power=0.5 if i == 2 else 0.0))
    return tuple(out)


def _cap_mods(mods: CombatMods) -> CombatMods:
    """Любая доля в приёме — не выше 60% (атака и прочность — 80%): иначе усиление ветки даёт «реакции −96%»."""
    from dataclasses import fields, replace

    capped = {}
    for f in fields(mods):
        v = getattr(mods, f.name)
        if isinstance(v, float):
            cap = CAP_MOD_BIG if f.name in ("attack", "durability") else CAP_HEAL if f.name == "heal" else CAP_MOD
            if v > cap:
                capped[f.name] = cap
    return replace(mods, **capped) if capped else mods


def _up(x: float, k: float) -> float:
    return 1 + (x - 1) * k


def _down(x: float, k: float) -> float:
    return max(0.1, 1 - (1 - x) * k)


_ENEMY_GAMES = ("reaction", "dodge", "gonogo", "parry")
_SELF_GAMES = ("rhythm", "charge", "combo", "aim")


def _extra_about(p: Perk) -> list[str]:
    parts = []
    if p.lasting:
        parts.append("до конца боя" if p.lasting >= 99 else f"действует {p.lasting + 1} раунда")
    if p.vs_perk_enemy_damage < 1:
        parts.append(f"если противник жмёт приём — его урон ×{p.vs_perk_enemy_damage:.2f}".rstrip("0").rstrip("."))
    if p.revenge:
        parts.append(f"сильнее от потерь: +{round(p.revenge * 100)}% урона за всю потерянную армию")
    if p.per_round:
        parts.append(f"урон +{round(p.per_round * 100)}% за каждый прошедший раунд")
    if p.lesson:
        parts.append(f"следующий приём техники ×{1 + p.lesson:.2f}".rstrip("0").rstrip("."))
    if p.repeat_tech:
        parts.append("повтор твоего последнего приёма техники")
    if p.clean_round_damage > 1:
        parts.append(f"если в прошлом раунде ты не потерял бойцов — урон ещё ×{p.clean_round_damage:.2f}".rstrip("0").rstrip("."))
    if p.copy_path_share:
        parts.append(f"копия {round(p.copy_path_share * 100)}% пассивок путей противника")
    if p.reveal:
        parts.append(f"{p.reveal} раунда видишь энергию и готовые приёмы противника")
    return parts


def _perk(kind: str, code: str, n: int, mv: BranchMove, level: int, idx: int, boost: float) -> Perk:
    from bot.config.arena.moves import describe

    k = level_factor(level) * boost
    top = n == 3 and level >= BRANCH_MAX_LEVEL and mv.power > 0
    minigame = ("self" if mv.minigame_self else "enemy") if top else None
    game = ((_SELF_GAMES if mv.minigame_self else _ENEMY_GAMES)[idx % 4]) if top else None
    p = Perk(
        code=f"{kind}:{code}:{n}@{level}", name=mv.name, about="", cost=BRANCH_COST[n - 1], cooldown=BRANCH_COOLDOWN[n - 1],
        self_mods=_cap_mods(mv.mods.scale(k)), enemy_mods=_cap_mods(mv.enemy.scale(k)), damage=min(CAP_DAMAGE, _up(mv.damage, k)),
        enemy_damage=max(CAP_ENEMY_DAMAGE, _down(mv.enemy_damage, k)),
        minigame=minigame, game=game, power=min(CAP_MINIGAME_POWER, mv.power * boost) if top else 0.0,
        first_round_damage=_up(mv.first_round_damage, k) if mv.first_round_damage else 0.0,
        copy_share=mv.copy_share * k, mirror=mv.mirror, energy_gain=mv.energy_gain,
        lasting=mv.lasting, vs_perk_enemy_damage=max(CAP_ENEMY_DAMAGE, _down(mv.vs_perk_enemy_damage, k)), revenge=mv.revenge * k,
        per_round=mv.per_round * k, lesson=mv.lesson * k, repeat_tech=mv.repeat_tech,
        clean_round_damage=_up(mv.clean_round_damage, k), copy_path_share=mv.copy_path_share * k, reveal=mv.reveal,
    )
    base = describe(p.self_mods, p.damage, p.enemy_damage, p.power, p.copy_share, p.minigame, p.first_round_damage,
                    p.energy_gain, p.mirror).rstrip(".")
    extra = _extra_about(p)
    if base == "Удар в стиле источника" and extra:
        base = ""
    text = ", ".join(x for x in [base] + extra if x)
    text = (text[0].upper() + text[1:]) if text else "Удар в стиле источника"
    from dataclasses import replace

    return replace(p, about=f"{text}. Сила {round(k / boost * 100) if boost else 0}% (ур. {level}).")


def branch_moves(kind: str, code: str) -> tuple[BranchMove, ...]:
    if kind == "blood":
        return BLOOD_BRANCHES.get(code, ())
    if code in KEPT_PATH_NAMES:
        from bot.config.unique_path import LEVELS as PATH_LEVELS

        return _kept_path_moves(PATH_LEVELS, code)
    return PATH_BRANCHES.get(code, ())


def build_branch_perks(kind: str, codes) -> list[Perk]:
    """Все приёмы ветвей вида `kind` («blood»/«path») на всех уровнях — для реестра."""
    out = []
    for idx, code in enumerate(codes):
        boost = BRANCH_BOOST.get(f"{kind}:{code}", 1.0)
        for n, mv in enumerate(branch_moves(kind, code), 1):
            for level in range(BRANCH_UNLOCK[n - 1], BRANCH_MAX_LEVEL + 1):
                out.append(_perk(kind, code, n, mv, level, idx, boost))
    return out


def branch_codes(kind: str, code: str | None, level: int) -> list[str]:
    """Коды открытых приёмов ветки на её уровне `level`."""
    if not code or level <= 0:
        return []
    level = min(level, BRANCH_MAX_LEVEL)
    return [f"{kind}:{code}:{n}@{level}" for n, _ in enumerate(branch_moves(kind, code), 1) if level >= BRANCH_UNLOCK[n - 1]]
