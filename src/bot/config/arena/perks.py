"""Перки онлайн-боя (реестр). Перк = эффект на раунд: свои модификаторы, модификаторы противнику, множители урона,
энергия, кулдаун. `minigame` у сильных перков: «self» — играет применивший (лучше сыграл — сильнее эффект),
«enemy» — навязано противнику (плохо сыграл — получает дебафф). Источники перков (техники по уровням, путь,
родословные, абсолюты, уники, мастерство) подключаются на этапе 2 — здесь базовый набор, доступный всем.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bot.services.combat.mods import CombatMods


@dataclass(frozen=True, slots=True)
class Perk:
    code: str
    name: str
    about: str
    cost: int
    cooldown: int  # раундов
    self_mods: CombatMods = field(default_factory=CombatMods)
    enemy_mods: CombatMods = field(default_factory=CombatMods)  # то, что накладывается на противника
    damage: float = 1.0  # множитель своего урона в раунде
    enemy_damage: float = 1.0  # множитель урона противника в раунде
    minigame: str | None = None  # "self" | "enemy"
    game: str | None = None  # код мини-игры (`config/minigame`)
    power: float = 0.0  # сила эффекта мини-игры: self — +урон за идеальную игру, enemy — −урон противнику за провал
    ai_weight: float = 1.0  # как охотно автоатака его жмёт
    first_round_damage: float = 0.0  # приём в первом раунде боя бьёт этим множителем вместо `damage` (Удар одного шага)
    copy_share: float = 0.0  # копирует на раунд эту долю бафов источников противника
    mirror: bool = False  # повторяет последний перк противника
    energy_gain: int = 0  # +⚡ после применения


CHAR_ACTION_NAMES = {"crush": "💥 Сокрушить", "dash": "⚡ Рывок вперёд", "evade": "🌀 Увернуться", "stand": "🛡 Стоять насмерть"}
CHAR_ACTION_ABOUT = {"crush": "Сила: урон ×{v}.", "dash": "Скорость: дополнительный удар {p}%.",
                     "evade": "Ловкость: уклонение +{p}%, свой урон ×0.8.", "stand": "Выносливость: гашение {p}%, прочность +10%, свой урон ×0.7."}


def char_action(code: str) -> Perk | None:
    """Действие характеристики `ch:<вид>:<ранг>` → перк-на-лету (сила — от ранга, ранг подставляет сервер)."""
    from bot.config.arena.arena import CHAR_ACTIONS

    parts = code.split(":")
    if len(parts) != 3 or parts[0] != "ch" or parts[1] not in CHAR_ACTIONS or not parts[2].isdigit():
        return None
    kind, rank = parts[1], int(parts[2])
    _, cost, cd, base, per, cap = CHAR_ACTIONS[kind]
    v = min(cap, base + per * rank)
    about = CHAR_ACTION_ABOUT[kind].format(v=f"{v:.2f}".rstrip("0").rstrip("."), p=round(v * 100))
    if kind == "crush":
        return Perk(code, CHAR_ACTION_NAMES[kind], about, cost, cd, damage=v, ai_weight=0.6)
    if kind == "dash":
        return Perk(code, CHAR_ACTION_NAMES[kind], about, cost, cd, self_mods=CombatMods(multi_hit=v), ai_weight=0.6)
    if kind == "evade":
        return Perk(code, CHAR_ACTION_NAMES[kind], about, cost, cd, self_mods=CombatMods(dodge=v), damage=0.8, ai_weight=0.3)
    return Perk(code, CHAR_ACTION_NAMES[kind], about, cost, cd, self_mods=CombatMods(reduction=v, durability=0.1), damage=0.7, ai_weight=0.3)


BASE_PERKS: dict[str, Perk] = {p.code: p for p in (
    Perk("rush", "Рывок", "Удар на полную: урон ×1.5 в этом раунде.", cost=3, cooldown=2, damage=1.5, ai_weight=1.2),
    Perk("guard_break", "Пробой", "Сквозь блок и уклонение: пробитие 40%, 30% атаки проходит наверняка.", cost=4, cooldown=3,
         self_mods=CombatMods(pierce=0.4, sure_hit=0.3)),
    Perk("second_wind", "Второе дыхание", "20% павших за раунд возвращаются в строй.", cost=5, cooldown=4,
         self_mods=CombatMods(heal=0.2), ai_weight=0.8),
    Perk("pressure", "Давление", "Противник проходит мини-игру: провал — его урон в раунде до −60%.", cost=4, cooldown=3,
         minigame="enemy", game="reaction", power=0.6),
    Perk("focus", "Концентрация", "Мини-игра на точность: чем лучше, тем сильнее удар (до ×2).", cost=5, cooldown=4,
         minigame="self", game="rhythm", power=1.0),
)}
