"""Build — сумма бафов четырёх систем развития игрока (сервис).

Единственная точка, где складываются родословная, активный путь, активная уникальная
техника и активная гениальность (`docs/design/development_systems.md`, «Архитектура»). Бой
получает `Build.battle` через профиль бойца (`services/characteristic.get_combat_profile`),
экономика, вербовка, тренировка, тикеты и саботаж читают `Build.eco`. Пробуждение умножает
всё собранное здесь (`awakening_multiplier`) — на характеристики и мастерство множитель не
действует (они считаются отдельно, в профиле бойца).

Особые механики, которые не сводятся к сумме чисел, тоже собираются здесь:
- «три камня» Преодоления — резонанс пути, УТ и родословной Ким Гапрена;
- путь Копирования — слияние способностей путей последних противников (память PvP);
- Бесконечная техника — те же копии, но переключаемые по раундам (`BattleBuild.rotation`);
- родословная Джинена — копирование источников текущего противника в бою и усиление
  пути Копирования.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.absolute import HASBULLA_SHOP_DISCOUNT
from bot.constant.absolute import ABS_HASBULLA
from bot.config.potion import POTION_EFFECTS, POTION_TIERS
from bot.constant.potion import POTION_WEALTH
from bot.db.repositories import potion as potion_repo
from bot.db.repositories import clan as clan_repo
from bot.config.clan import CLAN_BUILDINGS, CLAN_DONATE_LEVELS

from bot.config.awakening import LEVELS as AWAKENING_LEVELS
from bot.config.bloodline import LEVELS as BLOODLINE_LEVELS
from bot.config.development import (
    OVERCOME_RESONANCE,
    PATH_MEMORY_SIZE,
    PATH_MEMORY_WEIGHTS,
    awakening_multiplier,
)
from bot.config.genius import LEVELS as GENIUS_LEVELS
from bot.config.unique_path import LEVELS as PATH_LEVELS
from bot.config.unique_technique import LEVELS as TECHNIQUE_LEVELS
from bot.constant.bloodline import BLOODLINE_GAPRYONG
from bot.constant.build import SOURCE_BLOODLINE, SOURCE_BLOODLINE2, SOURCE_PATH2, SOURCE_GENIUS, SOURCE_PATH, SOURCE_TECHNIQUE
from bot.constant.unique_path import COPYING_PATHS, PATH_OVERCOME
from bot.constant.unique_technique import TECH_OVERCOME
from bot.db.repositories import build as build_repo
from bot.db.repositories.build import BuildRow
from bot.services.build.mods import NO_ECO, EconomyMods
from bot.services.combat.mods import NO_BUILD, NO_MODS, BattleBuild, CombatMods, sum_mods

if TYPE_CHECKING:
    from bot.services.position_skill.position_skill import PositionEffects


@dataclass(frozen=True, slots=True)
class LevelEffect:
    """Накопленный эффект уровня L одной системы: сумма записей 1..L конфига."""

    combat: CombatMods = NO_MODS
    eco: EconomyMods = NO_ECO
    special: dict = field(default_factory=dict)


def level_effect(table: dict[str, tuple[dict, ...]], code: str | None, level: int) -> LevelEffect:
    if not code or level <= 0 or code not in table:
        return LevelEffect()
    combat, eco, special = NO_MODS, NO_ECO, {}
    for spec in table[code][:level]:
        combat = combat + CombatMods.of(spec.get("combat", {}))
        eco = eco + EconomyMods.of(spec.get("eco", {}))
        for key, value in spec.get("special", {}).items():
            # Числа копятся по уровням, кортежи/флаги — последний уровень перекрывает.
            special[key] = special.get(key, 0) + value if isinstance(value, (int, float)) and not isinstance(value, bool) else value
    return LevelEffect(combat=combat, eco=eco, special=special)


async def _potion_mods(session: AsyncSession, user_id: int, power: float) -> tuple[CombatMods, EconomyMods]:
    combat, eco = NO_MODS, NO_ECO
    for kind, tier in await potion_repo.active_for_user(session, user_id):
        if kind == POTION_WEALTH or kind not in POTION_EFFECTS or not 0 < tier <= POTION_TIERS:
            continue
        spec = POTION_EFFECTS[kind][1][tier - 1]
        combat = combat + CombatMods.of(spec.get("combat", {}))
        eco = eco + EconomyMods.of(spec.get("eco", {}))
    if power:
        combat, eco = combat.scale(1 + power), eco.scale(1 + power)
    return combat, eco


async def _clan_eco(session: AsyncSession, user_id: int) -> EconomyMods:
    found = await clan_repo.buildings_of_user(session, user_id)
    if found is None:
        return NO_ECO
    donate_level, built = found
    eco = NO_ECO
    for kind, count in built.items():
        spec = CLAN_BUILDINGS.get(kind, (0, 0, {}))[2].get("eco", {})
        if spec and count:
            eco = eco + EconomyMods.of(spec).scale(count)
    for spec in CLAN_DONATE_LEVELS[:donate_level]:
        eco = eco + EconomyMods.of(spec.get("eco", {}))
    return eco


@dataclass(frozen=True, slots=True)
class Build:
    battle: BattleBuild = NO_BUILD
    eco: EconomyMods = NO_ECO
    awakening: float = 1.0  # применённый множитель пробуждения
    resonance: int = 0  # сколько «камней» Преодоления сошлось (0, 2, 3)
    # Особые возможности-флаги систем (например, `sabotage_marked` пути Сенсорики).
    flags: frozenset[str] = frozenset()
    # Навыки позиций банды (`services/position_skill`): боевые — по контексту боя в
    # `CombatProfile.chances`, небоевые уже сложены в `eco`. Пробуждение на них не действует.
    positions: "PositionEffects | None" = None  # None — навыков нет (импорт ленивый: цикл build ↔ position_skill)
    # Боевые бафы действующих зелий отдельно — шпион «Подменить зелья» снимает их на бой.
    potion_combat: CombatMods = NO_MODS
    # Действующие абсолютные карты (`services/absolute.active`) — перки за обладание.
    absolutes: frozenset[str] = frozenset()
    # КПД Пути тренировок (0…0.5): тренировки быстрее и результативнее, очки пути — быстрее.
    training_kpd: float = 0.0


EMPTY_BUILD = Build()


def _resonance(row: BuildRow) -> int:
    stones = sum((row.path == PATH_OVERCOME, row.technique == TECH_OVERCOME, row.bloodline == BLOODLINE_GAPRYONG))
    return stones if stones >= 2 else 0


async def _memory_copies(session: AsyncSession, user_id: int) -> list[CombatMods]:
    """Боевые способности путей последних противников (без копирующих путей — без рекурсии)."""
    copies = []
    for code, level in await build_repo.list_memory(session, user_id, PATH_MEMORY_SIZE):
        if code in COPYING_PATHS:
            continue
        copies.append(level_effect(PATH_LEVELS, code, level).combat)
    return copies


async def get_build(session: AsyncSession, user_id: int) -> Build:
    row = await build_repo.get_row(session, user_id)
    if row is None:
        return EMPTY_BUILD
    effects = {
        SOURCE_BLOODLINE: level_effect(BLOODLINE_LEVELS, row.bloodline, row.bloodline_level),
        SOURCE_PATH: level_effect(PATH_LEVELS, row.path, row.path_level),
        SOURCE_TECHNIQUE: level_effect(TECHNIQUE_LEVELS, row.technique, row.technique_level),
        SOURCE_GENIUS: level_effect(GENIUS_LEVELS, row.genius, row.genius_level),
    }
    # Второе тело (донат): второй путь и вторая родословная действуют одновременно с первыми.
    if row.path2:
        effects[SOURCE_PATH2] = level_effect(PATH_LEVELS, row.path2, row.path2_level)
    if row.bloodline2:
        effects[SOURCE_BLOODLINE2] = level_effect(BLOODLINE_LEVELS, row.bloodline2, row.bloodline2_level)
    special: dict = {}
    for effect in effects.values():
        for key, value in effect.special.items():
            special[key] = special.get(key, 0) + value if isinstance(value, (int, float)) and not isinstance(value, bool) else value

    # Путь Бесконечной техники: ещё N изученных техник (самые прокачанные) вполсилы.
    extra_n = None if special.get("all_techniques") else int(special.get("extra_techniques", 0))
    if (extra_n is None or extra_n) and row.technique:
        from bot.config.unique_path import INFINITE_EXTRA_TECHNIQUE_POWER
        from bot.db.repositories import unique_technique as tech_repo

        others = sorted(((c, lv) for c, lv in await tech_repo.list_owned(session, user_id) if c != row.technique), key=lambda x: -x[1])
        extra_combat_t, extra_eco_t = NO_MODS, NO_ECO
        for code, level in others[:extra_n]:
            e = level_effect(TECHNIQUE_LEVELS, code, level)
            extra_combat_t = extra_combat_t + e.combat.scale(INFINITE_EXTRA_TECHNIQUE_POWER)
            extra_eco_t = extra_eco_t + e.eco.scale(INFINITE_EXTRA_TECHNIQUE_POWER)
        base_t = effects[SOURCE_TECHNIQUE]
        effects[SOURCE_TECHNIQUE] = LevelEffect(combat=base_t.combat + extra_combat_t, eco=base_t.eco + extra_eco_t, special=base_t.special)

    combat_parts = {source: e.combat for source, e in effects.items()}
    # Гений оружия «нацелен на уникальные техники»: усиливает именно их боевые бафы.
    technique_power = sum(e.eco.technique_power for e in effects.values())
    if technique_power:
        combat_parts[SOURCE_TECHNIQUE] = combat_parts[SOURCE_TECHNIQUE].scale(1 + technique_power)
    resonance = _resonance(row)
    # Родословная Гапрена усиливает сам резонанс «трёх камней» (`resonance_bonus`).
    extra_combat = (
        CombatMods.of(OVERCOME_RESONANCE[resonance].get("combat", {})).scale(1 + special.get("resonance_bonus", 0.0))
        if resonance
        else NO_MODS
    )

    # Удар одного шага (Гансоп): первый удар растёт от ступеней мастерства Скорости и Силы.
    if special.get("opening_per_mastery"):
        tiers = row.mastery_speed + row.mastery_strength
        extra_combat = extra_combat + CombatMods(opening=special["opening_per_mastery"] * tiers)

    rotation: tuple[CombatMods, ...] = ()
    memory_copy = special.get("memory_copy", 0.0)
    memory_rotation = special.get("memory_rotation", 0.0)
    if memory_copy or memory_rotation:
        # Родословная Джинена усиливает путь Копирования (пользователь).
        boost = 1 + special.get("copy_path_boost", 0.0)
        copies = await _memory_copies(session, user_id)
        if memory_copy and copies:
            merged = sum_mods(c.scale(w) for c, w in zip(copies, PATH_MEMORY_WEIGHTS))
            extra_combat = extra_combat + merged.scale(memory_copy * boost)
        if memory_rotation and copies:
            rotation = tuple(c.scale(memory_rotation * boost) for c in copies)

    multiplier = awakening_multiplier(row.awakening_level)
    total = (sum_mods(combat_parts.values()) + extra_combat).scale(multiplier)
    battle = BattleBuild(
        total=total,
        by_source=tuple((source, mods.scale(multiplier)) for source, mods in combat_parts.items() if mods != NO_MODS),
        copy_sources=tuple(special.get("copy_sources", ())),
        copy_strength=special.get("copy_strength", 0.0) * multiplier,
        rotation=tuple(r.scale(multiplier) for r in rotation),
    )
    eco = NO_ECO
    for e in effects.values():
        eco = eco + e.eco
    eco = eco.scale(multiplier)
    # Собственные бафы этапов пробуждения — сверх множителя, сам множитель на них не действует.
    own = level_effect({"awakening": AWAKENING_LEVELS}, "awakening", row.awakening_level)
    battle = battle.with_total(battle.total + own.combat)
    eco = eco + own.eco
    # Зелья (магазин): действующие эффекты, усиленные гением медицины. Зелье богатства сюда
    # не входит — доход ленивый, оно считается по пересечению окон (`services/potion`).
    potion_combat, potion_eco = await _potion_mods(session, user_id, eco.potion_power)
    if potion_combat != NO_MODS:
        battle = battle.with_total(battle.total + potion_combat)
    eco = eco + potion_eco
    # Клан: здания на землях клана и донат-уровень — небоевые бафы участникам (боевые бафы
    # донат-уровня работают только у клановой роты в войне, `services/clan/war`).
    eco = eco + await _clan_eco(session, user_id)
    positions = await _positions(session, user_id)
    eco = eco + positions.eco
    training_kpd = await _training_kpd(session, user_id, row)
    if training_kpd:
        from bot.config.unique_path import TRAINING_KPD_EXTRAS_PP

        eco = eco + EconomyMods(
            dev_points=training_kpd, personal_cooldown=training_kpd / 2,
            extras_training=training_kpd * TRAINING_KPD_EXTRAS_PP, extras_training_cooldown=training_kpd / 2,
        )
    from bot.services.absolute import active as active_absolutes

    absolutes = await active_absolutes(session, user_id)
    if ABS_HASBULLA in absolutes:  # Хасбула: скидка в магазине (контракты, зелья; ячейки — в `services/storage`)
        eco = eco + EconomyMods(contract_discount=HASBULLA_SHOP_DISCOUNT, potion_discount=HASBULLA_SHOP_DISCOUNT)
    flags = frozenset(key for key, value in special.items() if value is True)
    return Build(
        battle=battle, eco=eco, awakening=multiplier, resonance=resonance, flags=flags, positions=positions,
        potion_combat=potion_combat, absolutes=absolutes, training_kpd=training_kpd,
    )


async def _training_kpd(session: AsyncSession, user_id: int, row: BuildRow) -> float:
    """КПД Пути тренировок: дни на пути × % + тренировки на пути × %, не выше потолка уровня."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from bot.config.unique_path import TRAINING_KPD_CAP_PER_LEVEL, TRAINING_KPD_PER_DAY, TRAINING_KPD_PER_REP
    from bot.constant.unique_path import PATH_TRAINING
    from bot.db.models.development import UserPath
    from bot.db.models.user import User

    level = row.path_level if row.path == PATH_TRAINING else row.path2_level if row.path2 == PATH_TRAINING else 0
    if not level:
        return 0.0
    since = await session.scalar(select(UserPath.obtained_at).where(UserPath.user_id == user_id, UserPath.code == PATH_TRAINING))
    reps = await session.scalar(select(User.training_path_reps).where(User.id == user_id)) or 0
    days = (datetime.now(timezone.utc) - since).total_seconds() / 86400 if since else 0.0
    return min(level * TRAINING_KPD_CAP_PER_LEVEL, days * TRAINING_KPD_PER_DAY + reps * TRAINING_KPD_PER_REP)


async def _positions(session: AsyncSession, user_id: int) -> "PositionEffects":
    """Эффекты навыков позиций по текущему составу банды."""
    from bot.config.card import CARD_BY_CODE
    from bot.db.repositories import card as card_repo
    from bot.services.position_skill.position_skill import NO_EFFECTS
    from bot.services.position_skill.position_skill import compute as compute_positions

    lineup = {p.position: CARD_BY_CODE.get(p.card_code) for p in await card_repo.list_positions(session, user_id)}
    return compute_positions(lineup) if any(lineup.values()) else NO_EFFECTS
