"""Страны — статичный список: 7 стран, зафиксированных в дизайне (Россия/США/Китай/
Япония/Корея/Мексика/Казахстан, подтверждено пользователем 2026-09-21 — Северная и
Южная Корея объединены в одну страну, не как в LookismBattlePlanet 1.0, где они были
раздельными). Тот же паттерн, что `EVENT_DEFS` в Universe Anime Planet
(`config/event/event.py`) — код+контент одной статичной записью, а не БД-таблица
определений: список никогда не меняется через админку, добавление 8-й страны — это
правка кода, не рантайм-операция.

`code` — то, что реально сравнивается/хранится (`User.country_code`, `City.country_code`,
callback_data в `constant/start`) — сверяться по нему, не по `name`.
"""
from __future__ import annotations

# Переезд (пользователь 2026-11-06): смена страны — не чаще раза в час, меняется в админке.
COUNTRY_SWAP_COOLDOWN_SECONDS = 60 * 60
# Между любыми переездами — 15 минут (пользователь 2026-11-08: переездом сбрасывали вызов).
CITY_MOVE_COOLDOWN_SECONDS = 15 * 60

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CountryDef:
    code: str
    name: str


COUNTRIES: tuple[CountryDef, ...] = (
    CountryDef("RU", "Россия"),
    CountryDef("US", "США"),
    CountryDef("CN", "Китай"),
    CountryDef("JP", "Япония"),
    CountryDef("KR", "Корея"),
    CountryDef("MX", "Мексика"),
    CountryDef("KZ", "Казахстан"),
    # Пользователь 2026-11-05: страны, для которых есть картинки в `assets/map`.
    CountryDef("GB", "Англия"),
    CountryDef("FR", "Франция"),
    CountryDef("IT", "Италия"),
    CountryDef("ES", "Испания"),
)

COUNTRY_BY_CODE: dict[str, CountryDef] = {c.code: c for c in COUNTRIES}
