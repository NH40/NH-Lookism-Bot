"""Навыки позиций банды — сборка эффектов из состава (сервис).

Уник на позиции даёт навыки своей позиции (`config/position_skill.CARD_SKILLS`), их сила —
`GRADE` редкости карты × мета-усиления других позиций (`_powers`). Результат — `PositionEffects`:
- боевые эффекты по контексту (всегда / нападение / защита / тип боя), дебафы противнику,
  условные навыки (`TriggerSpec`), потолок потерь — забирает `CombatProfile.chances`;
- небоевые (`EconomyMods`) — складываются в `Build.eco` (`services/build`);
- уровни разведки и сокрытия по полям — `services/position_skill.intel`;
- шпионские навыки — бросаются перед атакой (`resolve_spy`).

Шпион противника может отключить позицию на бой: `PositionEffects.without(...)` пересобирает
эффекты без неё (мета-усиления тоже пересчитываются).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from random import Random

from bot.config.card import CardDef
from bot.config.position_skill import CARD_SKILLS, SKILLS, SPY_CHANCE_CAP, Skill, grade
from bot.constant.card import (
    POS_DEFENDER,
    POS_DEPUTY,
    POS_LEADER,
    POS_SCOUT,
    POS_WARLORD,
    POSITIONS,
    RARITY_INDEX,
)
from bot.constant.position_skill import (
    F_ATTACK_POWER,
    F_DEFENSE_POWER,
    F_HEADCOUNT,
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
    ROLE_ATTACK,
    ROLE_DEFENSE,
    VS_BOTS,
    VS_CITY,
    VS_DISTRICT,
    WHEN_DEF_BELOW_30,
    WHEN_DEF_ROUND_1,
    WHEN_DEF_ROUNDS_1_2,
    WHEN_DEF_WIN,
    WHEN_ROUND_1,
)
from bot.services.build.mods import NO_ECO, EconomyMods
from bot.services.combat.combat import TriggerSpec
from bot.services.combat.mods import NO_MODS, CombatMods

_COMBAT = frozenset(f.name for f in fields(CombatMods))
_ECO = frozenset(f.name for f in fields(EconomyMods))
_ECO_TYPES = {f.name: type(f.default) for f in fields(EconomyMods)}


def _eco(values: dict[str, float]) -> EconomyMods:
    """Числа навыков → `EconomyMods` с типами полей: флаги — bool, ступени/слоты — int."""
    out = {}
    for k, v in values.items():
        t = _ECO_TYPES[k]
        out[k] = bool(v) if t is bool else int(round(v)) if t is int else float(v)
    return EconomyMods.of(out)
# Не масштабируются силой навыка: счётчики, пороги, уровни, флаги.
_NOSCALE = frozenset({"rush_rounds", "adapt_threshold", "absorb_return", "def_loss_cap", "hide_level", "intel_level",
                      "marks", "reflect_every"})
_DEF_TRIGGERS = frozenset({WHEN_DEF_ROUND_1, WHEN_DEF_ROUNDS_1_2, WHEN_DEF_BELOW_30, WHEN_DEF_WIN})
_BOT_VS = frozenset({VS_DISTRICT, VS_CITY})


@dataclass(frozen=True, slots=True)
class ActiveSkill:
    position: str
    card: CardDef
    skill: Skill
    power: float  # GRADE редкости × мета-усиления

    def value(self, key: str) -> float:
        v = self.skill.fx[key]
        if isinstance(v, bool) or key in _NOSCALE or not isinstance(v, (int, float)):
            return v
        return v * self.power

    @property
    def label(self) -> str:
        return self.skill.name


def _army(x: float) -> CombatMods:
    """«Мощь лагеря» в бою — и удар, и стойкость бойцов."""
    return CombatMods(attack=x, durability=x)


def _split(s: ActiveSkill) -> tuple[CombatMods, CombatMods, dict[str, float]]:
    """Эффекты навыка → (себе в бою, противнику в бою, особые числа)."""
    own, enemy, special = {}, {}, {}
    for key in s.skill.fx:
        if key in ("vs", "when", "field", "p", "disable"):
            continue
        v = s.value(key)
        if key in _COMBAT:
            own[key] = own.get(key, 0) + v
        elif key == "army_power":
            own["attack"] = own.get("attack", 0) + v
            own["durability"] = own.get("durability", 0) + v
        elif key == "enemy_attack":
            enemy["attack"] = enemy.get("attack", 0) + v
        elif key == "enemy_crit":
            enemy["crit_chance"] = enemy.get("crit_chance", 0) + v
        elif key == "enemy_loss_save":
            enemy["loss_save"] = enemy.get("loss_save", 0) + v
        elif key == "enemy_reactions":
            for r in ("dodge", "block", "counter", "flee"):
                enemy[r] = enemy.get(r, 0) + v
        elif key in ("anti_suppress", "anti_pierce", "anti_bleed", "anti_chaos"):
            target = key.removeprefix("anti_")
            enemy[target] = enemy.get(target, 0) - v  # ослабляет соответствующий бафф противника
        else:
            special[key] = special.get(key, 0) + (v if not isinstance(v, bool) else 1)
    return CombatMods(**own), CombatMods(**enemy), special


@dataclass(frozen=True)
class PositionEffects:
    lineup: tuple[tuple[str, CardDef], ...] = ()
    skills: tuple[ActiveSkill, ...] = ()
    disabled: frozenset[str] = frozenset()
    aura: CombatMods = NO_MODS
    attack: CombatMods = NO_MODS  # только в нападении
    defense: CombatMods = NO_MODS  # только в защите
    vs: tuple[tuple[str, CombatMods], ...] = ()
    enemy: CombatMods = NO_MODS  # дебафы противнику на весь бой
    eco: EconomyMods = NO_ECO
    special: Mapping[str, float] = field(default_factory=dict)
    triggers: tuple[TriggerSpec, ...] = ()
    def_triggers: tuple[TriggerSpec, ...] = ()
    intel: Mapping[str, int] = field(default_factory=dict)  # поле → уровень разведки
    hide: Mapping[str, int] = field(default_factory=dict)  # поле → уровень сокрытия

    @property
    def spies(self) -> tuple[ActiveSkill, ...]:
        return tuple(s for s in self.skills if s.skill.kind == KIND_SPY)

    def combat(self, role: str | None, vs: tuple[str, ...]) -> CombatMods:
        """Бафы стороны в бою с этой ролью и типом цели (`VS_*`; бои с ботами — ещё и `VS_BOTS`)."""
        total = self.aura
        if role == ROLE_ATTACK:
            total = total + self.attack
        elif role == ROLE_DEFENSE:
            total = total + self.defense
        tags = set(vs) | ({VS_BOTS} if _BOT_VS & set(vs) else set())
        for code, mods in self.vs:
            if code in tags:
                total = total + mods
        return total

    def triggers_for(self, role: str | None) -> tuple[TriggerSpec, ...]:
        return self.triggers + (self.def_triggers if role == ROLE_DEFENSE else ())

    def without(self, positions: frozenset[str]) -> "PositionEffects":
        if not positions:
            return self
        return compute(dict(self.lineup), disabled=self.disabled | positions)

    def get(self, key: str, default: float = 0.0) -> float:
        return self.special.get(key, default)


NO_EFFECTS = PositionEffects()


def _powers(lineup: Mapping[str, CardDef], disabled: frozenset[str]) -> list[ActiveSkill]:
    """Активные навыки со силой: редкость карты × мета-усиления (сами мета-навыки не усиливаются)."""
    raw: list[ActiveSkill] = []
    for pos in POSITIONS:
        card = lineup.get(pos)
        if card is None or pos in disabled:
            continue
        for code in CARD_SKILLS.get(card.code, {}).get(pos, ()):
            skill = SKILLS.get((pos, code))
            if skill is not None:
                raw.append(ActiveSkill(pos, card, skill, grade(card.rarity)))
    meta: dict[str, float] = {}
    for s in raw:
        if s.skill.kind == KIND_META:
            for key in s.skill.fx:
                meta[key] = meta.get(key, 0) + s.value(key)
    leader_missing = lineup.get(POS_LEADER) is None or POS_LEADER in disabled
    boost = {pos: 1 + meta.get("all_skills", 0) for pos in POSITIONS}
    boost[POS_LEADER] += meta.get("leader_boost", 0)
    boost[POS_DEPUTY] += meta.get("deputy_boost", 0) + meta.get("self_boost", 0) + (meta.get("stand_in", 0) if leader_missing else 0)
    boost[POS_WARLORD] += meta.get("attack_skills", 0) + meta.get("warlord_defender_boost", 0)
    boost[POS_DEFENDER] += meta.get("warlord_defender_boost", 0)
    trig_boost = 1 + meta.get("triggers_boost", 0)
    out = []
    for s in raw:
        if s.skill.kind == KIND_META:
            out.append(s)
            continue
        k = boost[s.position] * (trig_boost if s.skill.kind == KIND_TRIGGER else 1)
        out.append(ActiveSkill(s.position, s.card, s.skill, s.power * k))
    # «Второй король»: Заместитель копирует долю силы навыков Главы.
    copy = meta.get("copy_leader", 0)
    if copy and not leader_missing:
        deputy_card = lineup.get(POS_DEPUTY)
        out += [ActiveSkill(POS_DEPUTY, deputy_card, s.skill, s.power * copy)
                for s in list(out) if s.position == POS_LEADER and s.skill.kind not in (KIND_META, KIND_INTEL, KIND_HIDE)]
    return out


def compute(lineup: Mapping[str, CardDef | None], *, disabled: frozenset[str] = frozenset()) -> PositionEffects:
    cards = {pos: card for pos, card in lineup.items() if card is not None}
    skills = _powers(cards, disabled)
    filled = sum(1 for pos in cards if pos not in disabled)
    aura = attack = defense = enemy = NO_MODS
    vs: dict[str, CombatMods] = {}
    eco = NO_ECO
    special: dict[str, float] = {}
    triggers: list[TriggerSpec] = []
    def_triggers: list[TriggerSpec] = []
    intel: dict[str, int] = {}
    hide: dict[str, int] = {}

    def add_special(d: dict[str, float]) -> None:
        for k, v in d.items():
            special[k] = max(special.get(k, 0), v) if k in _NOSCALE else special.get(k, 0) + v

    for s in skills:
        kind, fx = s.skill.kind, s.skill.fx
        level = RARITY_INDEX[s.card.rarity] + 1
        own, foe, extra = _split(s)
        if kind in (KIND_INTEL, KIND_HIDE):
            target = intel if kind == KIND_INTEL else hide
            if "field" in fx:
                target[fx["field"]] = max(target.get(fx["field"], 0), level)
            add_special(extra)
            continue
        if kind == KIND_SPY:
            continue  # бросаются перед атакой (`resolve_spy`)
        if kind == KIND_TRIGGER:
            spec = TriggerSpec(
                name=s.skill.name, when=fx["when"], mods=own, enemy_mods=foe,
                no_enemy_reactions=bool(extra.get("enemy_reactions_r1") or extra.get("enemy_no_reactions")),
                revive=extra.get("revive", 0.0),
                loss_save=own.loss_save if fx["when"] == "on_loss" else 0.0,
                enemy_extra_dead=extra.get("enemy_extra_dead", 0.0),
            )
            if fx["when"] == "on_loss":
                spec = TriggerSpec(name=spec.name, when=spec.when, loss_save=spec.loss_save)
            (def_triggers if fx["when"] in _DEF_TRIGGERS else triggers).append(spec)
            continue
        if kind == KIND_ECO:
            eco_part = {k: v for k, v in extra.items() if k in _ECO}
            eco = eco + _eco(eco_part) if eco_part else eco
            add_special({k: v for k, v in extra.items() if k not in _ECO})
            # «Скорость» тактика: у ECO-навыка могут быть и боевые поля.
            aura = aura + own
            enemy = enemy + foe
            continue
        if kind == KIND_META:
            add_special(extra)
            continue
        # Боевые: «за каждую занятую позицию» превращается в мощь.
        if "per_filled_slot" in extra:
            own = own + _army(extra.pop("per_filled_slot") * filled)
        if kind == KIND_AURA:
            aura, enemy = aura + own, enemy + foe
        elif kind == KIND_ATK:
            attack = attack + own
        elif kind == KIND_DEF:
            defense, enemy = defense + own, enemy + foe  # дебафы защиты — только нападающему
        elif kind == KIND_VS:
            vs[fx["vs"]] = vs.get(fx["vs"], NO_MODS) + own
        add_special(extra)

    scout_card = cards.get(POS_SCOUT) if POS_SCOUT not in disabled else None
    if scout_card is not None:  # базовые поля — у любого разведчика (пользователь 2026-10-16)
        base_level = RARITY_INDEX[scout_card.rarity] + 1
        for f in (F_HEADCOUNT, F_ATTACK_POWER, F_DEFENSE_POWER):
            intel[f] = max(intel.get(f, 0), base_level)
    bump = int(special.get("intel_level", 0))
    if bump:
        intel = {k: v + bump for k, v in intel.items()}
    hbump = int(special.get("hide_level", 0))
    if hbump:
        hide = {k: v + hbump for k, v in hide.items()}
    return PositionEffects(
        lineup=tuple(cards.items()), skills=tuple(skills), disabled=disabled, aura=aura, attack=attack, defense=defense,
        vs=tuple(vs.items()), enemy=enemy, eco=eco, special=special, triggers=tuple(triggers),
        def_triggers=tuple(def_triggers), intel=intel, hide=hide,
    )


# --- Шпион перед атакой ---


@dataclass(frozen=True, slots=True)
class SpyEvent:
    name: str
    card_name: str
    success: bool
    blocked: bool  # сорван контрразведкой (иначе — просто не повезло)


@dataclass(frozen=True)
class SpyOutcome:
    events: tuple[SpyEvent, ...] = ()
    disable: frozenset[str] = frozenset()  # позиции цели, отключённые на бой
    attacker_mods: CombatMods = NO_MODS  # бафы нападающему на бой
    enemy_mods: CombatMods = NO_MODS  # дебафы цели на бой
    withheld: float = 0.0  # доля бойцов цели, не вышедших на бой
    triggers: tuple[TriggerSpec, ...] = ()  # раундовые дебафы цели (1-й / 1–2 раунды) — у нападающего
    special: Mapping[str, float] = field(default_factory=dict)  # steal_technique, disable_potions, …


NO_SPY = SpyOutcome()


def resolve_spy(attacker: PositionEffects, defender: PositionEffects, rng: Random | None = None) -> SpyOutcome:
    """Шпионские навыки нападающего: бросок шанса каждого (+«Агентурная сеть»/«Связной»),
    контрразведка цели снижает шанс; «Тень короля» — контрразведка ниже по уровню не мешает.
    «Двойная игра» — шанс повторить сработавший навык (эффект ещё раз)."""
    spies = attacker.spies
    if not spies:
        return NO_SPY
    rng = rng or Random()
    bonus = attacker.get("spy_chance")
    anti = defender.get("anti_spy")
    pierce = attacker.get("pierce_counterintel")
    repeat = attacker.get("repeat")
    guard_disable = defender.get("anti_disable")
    guard_leader = defender.get("leader_guard")
    quarantine = min(0.8, defender.get("anti_poison"))
    events: list[SpyEvent] = []
    disable: set[str] = set()
    own, foe, special = NO_MODS, NO_MODS, {}
    withheld = 0.0
    triggers: list[TriggerSpec] = []
    for s in spies:
        fx = s.skill.fx
        base = min(SPY_CHANCE_CAP, fx.get("p", 0) * s.power + bonus)
        chance = base if pierce else max(0.0, base - anti)
        hit = rng.random() < chance
        events.append(SpyEvent(s.skill.name, s.card.name, hit, blocked=not hit and rng.random() < base - chance if base else False))
        if not hit:
            continue
        times = 2 if repeat and rng.random() < repeat else 1
        for _ in range(times):
            if "disable" in fx:
                guard = guard_disable + (guard_leader if fx["disable"] == POS_LEADER else 0)
                if rng.random() >= guard:
                    disable.add(fx["disable"])
                continue
            for key in fx:
                if key in ("p", "disable"):
                    continue
                v = s.value(key)
                if key in ("pre_kill", "first_strike"):
                    own = own + CombatMods(first_strike=v * (1 - quarantine if key == "pre_kill" else 1))
                elif key in ("desert", "enemy_flee_r1", "enemy_attack_camp_out"):
                    withheld += v * (1 - quarantine if key == "desert" else 1)
                elif key in ("enemy_attack_r1", "enemy_attack_r12"):
                    when = WHEN_ROUND_1 if key == "enemy_attack_r1" else WHEN_DEF_ROUNDS_1_2  # «1–2 раунды»
                    triggers.append(TriggerSpec(name=s.skill.name, when=when, enemy_mods=CombatMods(attack=v)))
                elif key.startswith("enemy_") and key != "enemy_accept_window":
                    target = {"enemy_durability": "durability", "enemy_dodge": "dodge", "enemy_block": "block",
                              "enemy_counter": "counter", "enemy_flee": "flee", "enemy_loss_save": "loss_save",
                              "enemy_crit": "crit_chance"}.get(key)
                    if target:
                        foe = foe + CombatMods(**{target: v})
                elif key in _COMBAT:
                    own = own + CombatMods(**{key: v})
                else:
                    special[key] = special.get(key, 0) + (v if not isinstance(v, bool) else 1)
    return SpyOutcome(events=tuple(events), disable=frozenset(disable), attacker_mods=own, enemy_mods=foe,
                      withheld=min(0.5, withheld), triggers=tuple(triggers), special=special)
