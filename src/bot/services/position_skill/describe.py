"""Описание навыков позиций с числами для конкретной карты (сервис для экранов бота и Mini App)."""
from __future__ import annotations

from dataclasses import dataclass

from bot.config.card import CardDef
from bot.config.position_skill import CARD_SKILLS, SKILLS, SPY_CHANCE_CAP, Skill, grade

# Значения, которые показываются как есть (не доли): ступени, часы, минуты, слоты, флаги.
_ABS = frozenset({
    "influence", "storage_hours", "extras_training", "recruit_rank_bonus", "shield_minutes", "blind_minutes", "marks",
    "intel_level", "absorb_return", "hide_level", "rush_rounds",
})
_NOSCALE = frozenset({"def_loss_cap", "adapt_threshold", "absorb_return", "hide_level", "intel_level", "marks", "rush_rounds"})
_SKIP = frozenset({"vs", "when", "field", "p", "disable"})


def _num(key: str, value: float, power: float) -> str:
    k = 1.0 if key in _NOSCALE else power
    if key in _ABS:
        x = value * k
        return f"{x:.1f}".rstrip("0").rstrip(".")
    return f"{abs(value) * k * 100:.1f}".rstrip("0").rstrip(".")


def describe(skill: Skill, power: float) -> str:
    vals = [(k, v) for k, v in skill.fx.items() if k not in _SKIP and isinstance(v, (int, float)) and not isinstance(v, bool)]
    kw = {name: _num(k, v, power) for name, (k, v) in zip(("v", "v2", "v3"), vals)}
    if "p" in skill.fx:
        kw["p"] = f"{min(SPY_CHANCE_CAP, skill.fx['p'] * power) * 100:.0f}"
    kw.setdefault("cap", "8")
    try:
        return skill.desc.format(**kw)
    except (KeyError, IndexError):
        return skill.desc


@dataclass(frozen=True, slots=True)
class SkillLine:
    code: str
    name: str
    kind: str
    text: str


def card_skill_lines(card: CardDef, position: str) -> list[SkillLine]:
    """Навыки карты на позиции с числами её редкости (без мета-усилений банды)."""
    power = grade(card.rarity)
    out = []
    for code in CARD_SKILLS.get(card.code, {}).get(position, ()):
        skill = SKILLS.get((position, code))
        if skill is not None:
            out.append(SkillLine(code, skill.name, skill.kind, describe(skill, power)))
    return out
