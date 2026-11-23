"""Перки из систем развития (2026-11-19, этап 2 онлайн-боёв).

Пользователь: перк строится на основной, понятной функции источника. Функция уже записана в уровнях: техника,
путь и родословная — это наборы боевых модификаторов. Перк ступени — это «вспышка» накопленных к этой ступени
модификаторов на один раунд (поверх пассивных бафов, которые остаются) плюс немного урона. Ступени — уровни
1 / 4 / 7 / 10; на 10-м («Предел») у техники мини-игра себе, у пути и родословной — мини-игра противнику.
Абсолюты, позиции банды и техники мастерства — перки по их смыслу (ниже). Цифры выровняет этап баланса.
"""
from __future__ import annotations

from bot.config.arena.perks import Perk
from bot.config.bloodline import LEVELS as BLOODLINE_LEVELS
from bot.config.mastery.techniques import MASTERY_TREES
from bot.config.unique_path import LEVELS as PATH_LEVELS
from bot.config.arena.moves import BLOOD_MOVES, TECH_MOVES
from bot.config.unique_technique import LEVELS as TECH_LEVELS
from bot.services.combat.mods import CombatMods

TIER_LEVELS: tuple[int, ...] = (1, 4, 7, 10)
TIER_NAMES: tuple[str, ...] = ("Приём", "Связка", "Коронный", "Предел")
_SELF_GAMES = ("rhythm", "charge", "combo", "aim")  # мини-игра «Предела» техники (по кругу)
_ENEMY_GAMES = ("reaction", "dodge", "gonogo", "parry")  # навязанная противнику


def _cum(table: dict, code: str, level: int) -> CombatMods:
    mods = CombatMods()
    for spec in table.get(code, ())[:level]:
        mods = mods + CombatMods.of(spec.get("combat", {}))
    return mods


# Усиление перков источника (этап 6, баланс симуляцией): пути и родословные с особыми механиками (не боевыми
# модификаторами) не выравниваются множителем уровней — их уравнивает сила перков. Ключ «вид:код».
PERK_BOOST: dict[str, float] = {}


def _tier_perks(kind: str, table: dict, code: str, name: str, idx: int) -> list[Perk]:
    out = []
    boost = PERK_BOOST.get(f"{kind}:{code}", 1.0)
    for t, level in enumerate(TIER_LEVELS):
        if level > len(table.get(code, ())):
            break
        mods = _cum(table, code, level).scale((1.0 + 0.25 * t) * boost)
        has_mods = mods != CombatMods()
        top = t == len(TIER_LEVELS) - 1
        game = minigame = None
        if top:
            minigame = "self" if kind == "tech" else "enemy"
            game = (_SELF_GAMES if kind == "tech" else _ENEMY_GAMES)[idx % 4]
        out.append(Perk(
            code=f"{kind}:{code}:{t + 1}", name=f"{name} · {TIER_NAMES[t]}",
            about=("Вспышка силы источника на раунд" if has_mods else "Удар в стиле источника") + (" + мини-игра." if top else "."),
            cost=2 + t, cooldown=2 + t // 2, self_mods=mods, damage=1.0 + (0.1 * t + (0 if has_mods else 0.15)) * boost,
            minigame=minigame, game=game, power=(0.8 if kind == "tech" else 0.5) if top else 0.0,
        ))
    return out


def _move_perks(kind: str, table: dict, code: str, idx: int) -> list[Perk]:
    """Свои приёмы источника (`config/arena/moves`, 2026-11-23) — на тех же ступенях и кодах, что шаблонные перки."""
    from bot.config.arena.moves import BLOOD_MOVES, MOVE_COOLDOWN, MOVE_COST, TECH_MOVES

    moves = (TECH_MOVES if kind == "tech" else BLOOD_MOVES)[code]
    mini = "self" if kind == "tech" else "enemy"
    games = _SELF_GAMES if kind == "tech" else _ENEMY_GAMES
    out = []
    for t, level in enumerate(TIER_LEVELS):
        if level > len(table.get(code, ())):
            break
        mv = moves[t]
        top = t == len(TIER_LEVELS) - 1
        out.append(Perk(
            code=f"{kind}:{code}:{t + 1}", name=mv.name, about=mv.about, cost=MOVE_COST[t], cooldown=MOVE_COOLDOWN[t],
            self_mods=mv.mods, enemy_mods=mv.enemy, damage=mv.damage, enemy_damage=mv.enemy_damage,
            minigame=mini if top else None, game=games[idx % 4] if top else None, power=mv.power if top else 0.0,
            first_round_damage=mv.first_round_damage, copy_share=mv.copy_share, mirror=mv.mirror, energy_gain=mv.energy_gain,
        ))
    return out


def build_source_perks() -> dict[str, Perk]:
    from bot.texts.bloodline import BLOODLINE_NAMES
    from bot.texts.unique_path import PATH_NAMES
    from bot.texts.unique_technique import TECHNIQUE_NAMES

    perks: list[Perk] = []
    for i, code in enumerate(TECH_LEVELS):
        perks += _move_perks("tech", TECH_LEVELS, code, i) if code in TECH_MOVES else _tier_perks("tech", TECH_LEVELS, code, TECHNIQUE_NAMES.get(code, code), i)
    for i, code in enumerate(PATH_LEVELS):
        perks += _tier_perks("path", PATH_LEVELS, code, PATH_NAMES.get(code, code), i)
    for i, code in enumerate(BLOODLINE_LEVELS):
        perks += _move_perks("blood", BLOODLINE_LEVELS, code, i) if code in BLOOD_MOVES else _tier_perks("blood", BLOODLINE_LEVELS, code, BLOODLINE_NAMES.get(code, code), i)
    perks += ABSOLUTE_PERKS + POSITION_PERKS + mastery_perks()
    return {p.code: p for p in perks}


def _p(code: str, name: str, about: str, cost: int, cd: int, **kw) -> Perk:
    return Perk(code=code, name=name, about=about, cost=cost, cooldown=cd, **kw)


# Абсолюты — по их смыслу.
ABSOLUTE_PERKS: list[Perk] = [
    _p("abs:hasbulla_horse", "Копыто Коня", "Лихой удар: урон ×1.4.", 3, 3, damage=1.4),
    _p("abs:kuropatkaa_hopeful", "Надежда Куропатки", "30% павших за раунд встают обратно.", 4, 4, self_mods=CombatMods(heal=0.3)),
    _p("abs:marise_boosty", "Клоны Мариз", "Клоны в строю: лечение 20% и +10% атаки.", 4, 4, self_mods=CombatMods(heal=0.2, attack=0.1)),
    _p("abs:tabasko_unlucky", "Неудача Табаско", "Противнику не везёт: реакции −30% и мини-игра.", 4, 3,
       enemy_mods=CombatMods(suppress=0.3), minigame="enemy", game="gonogo", power=0.4),
    _p("abs:malosolny_ogurchik_emperor", "Вайбик Огурчика", "+30% атаки и +5 п.п. к уклонению и блоку.", 3, 3,
       self_mods=CombatMods(attack=0.3, dodge=0.05, block=0.05)),
    _p("abs:quande_manchester_100m", "Стометровка Кванде", "Серия ударов: дополнительный удар 50%.", 4, 3, self_mods=CombatMods(multi_hit=0.5)),
    _p("abs:manager_fair", "Честность Менеджера", "Пробитие 50%, треть атаки — наверняка.", 4, 3, self_mods=CombatMods(pierce=0.5, sure_hit=0.33)),
    _p("abs:nikita_despair", "Отчаяние Никиты", "Чем сильнее враг, тем злее удар.", 4, 3, self_mods=CombatMods(despair=0.5)),
    _p("abs:arkhangel_wwip", "Крыло Архангела", "Гашение урона 30% и лечение 10%.", 4, 4, self_mods=CombatMods(reduction=0.3, heal=0.1)),
    _p("abs:some_thing_stylist", "Стиль", "Крит: шанс +30%, сила +50%.", 4, 3, self_mods=CombatMods(crit_chance=0.3, crit_power=0.5)),
    _p("abs:arian_absolute", "Абсолют Ариана", "Глушит противника: его урон ×0.75 и мини-игра.", 5, 4,
       enemy_damage=0.75, minigame="enemy", game="parry", power=0.4),
]

# Позиции банды: уник на позиции даёт перк своей роли.
POSITION_PERKS: list[Perk] = [
    _p("pos:leader", "Приказ лидера", "+25% атаки всей армии.", 3, 3, self_mods=CombatMods(attack=0.25)),
    _p("pos:deputy", "Прикрытие зама", "Гашение 15% и +10% атаки.", 3, 3, self_mods=CombatMods(reduction=0.15, attack=0.1)),
    _p("pos:tactician", "Тактика", "Реакции противника −30%.", 3, 3, enemy_mods=CombatMods(suppress=0.3)),
    _p("pos:warlord", "Натиск военачальника", "Урон ×1.3.", 3, 3, damage=1.3),
    _p("pos:businessman", "Подкуп", "Урон противника ×0.85.", 3, 3, enemy_damage=0.85),
    _p("pos:spy", "Шпионаж", "Противник проходит мини-игру: провал — урон −40%.", 3, 3, minigame="enemy", game="arrows", power=0.4),
    _p("pos:scout", "Разведка боем", "+15% уклонения, 15% атаки наверняка.", 3, 3, self_mods=CombatMods(dodge=0.15, sure_hit=0.15)),
    _p("pos:security", "Охрана", "Гашение урона 30%.", 3, 3, self_mods=CombatMods(reduction=0.3)),
    _p("pos:defender", "Стена защитника", "+15% блока, +20% прочности.", 3, 3, self_mods=CombatMods(block=0.15, durability=0.2)),
]


# Техники мастерства: функция мастерства × ступень (сила — мощь удара, скорость — серия и уклонение,
# выносливость — гашение и прочность, техника — пробитие, точность и крит).
def _mastery_mods(mastery: str, tier: int) -> tuple[CombatMods, float]:
    k = 0.1 * tier
    if mastery == "strength":
        return CombatMods(attack=1.5 * k), 1.0 + k
    if mastery == "speed":
        return CombatMods(multi_hit=1.5 * k, dodge=0.5 * k), 1.0
    if mastery == "endurance":
        return CombatMods(reduction=k, durability=1.5 * k), 1.0
    return CombatMods(pierce=k, sure_hit=k, crit_chance=0.5 * k), 1.0


def mastery_perks() -> list[Perk]:
    out = []
    for mastery, tiers in MASTERY_TREES.items():
        for tier, techs in enumerate(tiers, 1):
            mods, dmg = _mastery_mods(mastery, tier)
            for t in techs:
                out.append(_p(f"mt:{t.code}", t.name, t.about, 2 + tier, 2 + tier // 2, self_mods=mods, damage=dmg))
    return out
