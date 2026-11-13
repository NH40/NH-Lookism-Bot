"""Небоевые модификаторы систем развития — экономика, вербовка, тренировка, тикеты,
саботаж, скрытность, автоматика (`docs/design/development_systems.md`).

Складываются между системами (`+`), масштабируются пробуждением (`scale`). Нулевой
`EconomyMods()` — игра ровно как без систем развития: каждое место, которое их читает,
обязано давать прежний результат при нулях.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

# Поля-уровни, которые не складываются, а берутся по максимуму (два источника «разведки 2»
# не дают «разведку 4»).
_MAX_FIELDS = frozenset({"stat_floor", "scout", "foresight", "logs", "potion_tier", "potion_auto"})
# Поля, которые не масштабируются пробуждением (ступени, уровни, флаги).
_UNSCALED = _MAX_FIELDS | frozenset({
    "recruit_rank_bonus", "ticket_cap", "marks", "business_cap", "recruit_cap", "security", "security_pierce",
    "teacher_quest_cut", "auto_tech_task",
})


@dataclass(frozen=True, slots=True)
class EconomyMods:
    # Армия.
    army_power: float = 0.0  # +доля мощи каждого бойца (атака и ХП) — родословная Муджина
    # Бизнес.
    income: float = 0.0  # +доля дохода зданий
    build_discount: float = 0.0  # скидка на постройку
    upgrade_discount: float = 0.0  # скидка на прокачку уровня/вместимости
    storage_hours: float = 0.0  # +часов к хранилищу (базово 24)
    tax_relief: float = 0.0  # доля налога императора, которую игрок не платит (гений бизнеса)
    business_cap: int = 0  # +к потолку прокачки бизнеса (Элита: до 15)
    passive_income: float = 0.0  # NHCoin в час сверх зданий (путь Бизнесмена)
    battle_loot: float = 0.0  # победа над игроком: эта доля его NHCoin переходит победителю (Элита)
    coin_protect: float = 0.0  # у проигравшего эта доля защищена от чужой добычи (путь Отчаяния)
    # Вербовка статистов.
    recruit_cooldown: float = 0.0  # −доля КД вербовки
    recruit_rank_bonus: int = 0  # +ступеней к потолку ранга вербовки
    recruit_double: float = 0.0  # шанс завербовать сразу вдвое больше
    recruit_quantity: float = 0.0  # +доля бойцов за нажатие
    recruit_influence_cut: float = 0.0  # −доля требования к влиянию на бойца и на ступень ранга
    recruit_cap: int = 0  # +к потолку бойцов за нажатие
    influence_bonus: float = 0.0  # +доля влияния
    influence_rank_cut: float = 0.0  # −доля влияния на ступень ранга вербовки и контрактов
    # Тренировка.
    extras_training: float = 0.0  # +п.п. к шансам тренировки статистов
    extras_training_cooldown: float = 0.0  # −доля КД тренировки статистов
    extras_extra_roll: float = 0.0  # не прошедшие 1-й этап пробуют ещё раз (путь тренировок)
    extras_coverage: float = 0.0  # +п.п. к доле статистов, попадающих в тренировку
    training_cap_mult: float = 0.0  # кап уровня тренировки выше на эту долю (Самдак, до ×2)
    rank_hold: bool = False  # можно запретить статистам переходить на следующий ранг (Самдак)
    school_cooldown: float = 0.0  # −доля КД занятий школ (Хансу)
    dev_points: float = 0.0  # +доля очков развития с личной тренировки
    personal_cooldown: float = 0.0  # −доля КД личной тренировки
    mastery_delay: float = 0.0  # −доля ожидания этапа мастерства
    stat_cost_discount: float = 0.0  # скидка на ранги характеристик
    stat_floor: int = 0  # пол рангов характеристик (индекс в RANK_LADDER; Ким Гапрен)
    # Уники и тикеты.
    ticket_regen: float = 0.0  # −доля интервала регена тикетов
    ticket_cap: int = 0  # +к потолку регена
    gacha_luck: float = 0.0  # шанс поднять редкость выпавшего уника на ступень
    gacha_free_roll: float = 0.0  # шанс, что крутка не потратит тикет
    # Бои и война.
    battle_cooldown: float = 0.0  # −доля КД сражений
    # Саботаж, шпионаж, скрытность.
    sabotage_chance: float = 0.0  # +п.п. к шансу саботажа
    sabotage_cooldown: float = 0.0  # −доля КД саботажа
    sabotage_loot: float = 0.0  # +доля добычи саботажа
    stealth: bool = False  # имя скрыто в отчётах и списках (Курода)
    silent_sabotage: bool = False  # император не узнаёт даже о попытке
    scout: int = 0  # разведка: 1 — мощь цели перед боем, 2 — состав лагерей, 3 — её билд
    foresight: int = 0  # предвидение: 1 — шанс победы, 2 — ожидаемые потери, 3 — точный прогноз
    marks: int = 0  # сколько игроков можно держать под метками (Сенсорика)
    logs: int = 0  # наблюдение: 1 — последние бои цели, 2 — её действия, 3 — всё
    security: int = 0  # безопасность: +ступени сокрытия всех полей от чужой разведки
    security_pierce: int = 0  # разведка не замечает столько ступеней чужой безопасности
    false_intel: float = 0.0  # чужая разведка видит числа с такой ошибкой (Курода)
    spy_chance: float = 0.0  # +к шансу своих шпионов
    spy_resist: float = 0.0  # −к шансу чужих шпионов
    # Магазин (контракты статистов, Джинчоль).
    contract_discount: float = 0.0
    contract_duration: float = 0.0
    contract_power: float = 0.0  # Пеньгуан: наёмники сильнее
    contract_bonus: float = 0.0  # вместе с контрактом бесплатно приходит ещё эта доля бойцов
    contract_retain: float = 0.0  # эта доля выживших остаётся навсегда, когда контракт кончается
    # Системы развития.
    fragment_bonus: float = 0.0  # +доля фрагментов с боссов
    tech_fragment_discount: float = 0.0  # уровни техник дешевле во фрагментах (Хансу)
    technique_quest_speed: float = 0.0  # задания учителей меньше на эту долю (Хансу)
    auto_tech_task: int = 0  # столько заданий учителя засчитывается сразу (Хансу)
    teacher_quest_cut: int = 0  # столько же для пути Бесконечной техники (Джинен)
    blood_bonus: float = 0.0  # +доля капель крови
    medicine_discount: float = 0.0  # скидка на уровни гения медицины (Джинен)
    # Зелья (гений медицины, `config/potion`).
    potion_tier: int = 0  # открытый тир зелий (I–IV доступны всем, `POTION_BASE_MAX_TIER`)
    potion_discount: float = 0.0  # зелья дешевле
    potion_duration: float = 0.0  # зелья действуют дольше
    potion_power: float = 0.0  # эффекты зелий сильнее
    potion_auto: int = 0  # слоты авто-зелий
    potion_heal: float = 0.0  # каждое действующее зелье: столько павших за раунд возвращается (Джинен)
    technique_power: float = 0.0  # усиление боевых бафов активной УТ (гений оружия)
    # Автоматика (Ультра инстинкт Ямадзаки).
    auto_recruit: bool = False
    auto_train: bool = False
    auto_roll: bool = False
    auto_school: bool = False
    auto_boss: bool = False

    def __add__(self, other: "EconomyMods") -> "EconomyMods":
        values = {}
        for f in fields(self):
            a, b = getattr(self, f.name), getattr(other, f.name)
            if isinstance(a, bool):
                values[f.name] = a or b
            elif f.name in _MAX_FIELDS:
                values[f.name] = max(a, b)
            else:
                values[f.name] = a + b
        return EconomyMods(**values)

    def scale(self, k: float) -> "EconomyMods":
        if k == 1:
            return self
        values = {}
        for f in fields(self):
            v = getattr(self, f.name)
            values[f.name] = v if isinstance(v, bool) or f.name in _UNSCALED else v * k
        return EconomyMods(**values)

    @classmethod
    def of(cls, values: dict) -> "EconomyMods":
        unknown = set(values) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown economy mods: {sorted(unknown)}")
        return cls(**values)


NO_ECO = EconomyMods()


def capped(value: float, cap: float = 0.9) -> float:
    """Скидки и сокращения времени режутся потолком — ни одно действие не становится
    бесплатным или мгновенным."""
    return max(0.0, min(cap, value))
