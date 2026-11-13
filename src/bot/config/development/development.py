"""Системы развития — общие числа (`docs/design/development_systems.md`).

Формат уровней у всех систем один: `tuple` из `MAX_LEVEL` словарей, уровень N — прибавка к
уровням 1..N-1 (эффект уровня L = сумма первых L записей):

    {"combat": {поле CombatMods: значение}, "eco": {поле EconomyMods: значение},
     "special": {особые механики Build: копирование, память противников, ротация…}}

Поля проверяются при сборке Build (`CombatMods.of` / `EconomyMods.of`) — опечатка в конфиге
падает сразу, а не тихо не работает.
"""
from __future__ import annotations

MAX_LEVEL = 10

# Множитель пробуждения ко всем бафам систем развития (не к характеристикам и мастерству —
# пользователь). Пробуждение реализуется после систем; уровень 0 — ×1.
AWAKENING_BUFF_MULTIPLIER_PER_LEVEL = 0.08  # 10 пробуждений → ×1.8


def awakening_multiplier(level: int) -> float:
    return 1.0 + AWAKENING_BUFF_MULTIPLIER_PER_LEVEL * max(0, level)


# «Три камня» Преодоления (пользователь: путь, УТ и родословная Ким Гапрена должны идеально
# стыковаться): бонус к нарастанию за 2 и за 3 совпавших источника.
OVERCOME_RESONANCE: dict[int, dict[str, dict[str, float]]] = {
    2: {"combat": {"overcome": 0.15, "durability": 0.10}},
    3: {"combat": {"overcome": 0.40, "durability": 0.25, "attack": 0.10}},
}

# Пути Копирования / Бесконечной техники — память последних противников (PvP).
PATH_MEMORY_SIZE = 5
# Доля способностей противника из памяти по свежести: прошлый — 3/5, позапрошлый — 2/5 …
PATH_MEMORY_WEIGHTS: tuple[float, ...] = (0.6, 0.4, 0.3, 0.2, 0.1)


# Боевые поля, которые задают не силу, а порог/потолок/длительность, — множители баланса их не трогают.
_UNSCALED = frozenset({
    "rush_rounds", "overcome_gap_cap", "ramp_cap", "rapid_cap", "adapt_threshold", "reflect_burst_at", "reflect_every", "no_dodge",
})


def scale_levels(levels: dict[str, tuple[dict, ...]], scales: dict[str, float]) -> dict[str, tuple[dict, ...]]:
    """Множители баланса (подобраны симуляцией) к боевым числам уровней: `{код: множитель}`. Применяются при
    загрузке конфига, поэтому тексты уровней и бой видят одни и те же числа."""
    out = dict(levels)
    for code, k in scales.items():
        if code not in out or k == 1:
            continue
        out[code] = tuple(
            {**spec, "combat": {f: (round(v * k, 4) if isinstance(v, float) and f not in _UNSCALED else v)
                                for f, v in spec.get("combat", {}).items()}} if spec.get("combat") else spec
            for spec in out[code]
        )
    return out
