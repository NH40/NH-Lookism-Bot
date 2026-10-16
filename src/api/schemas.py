"""Pydantic-схемы ответов Mini App API — по одному классу на домен, наполняется по
мере переноса (тот же паттерн, что `api/schemas.py` в Universe Anime Planet)."""
from __future__ import annotations

from pydantic import BaseModel


class CountryOut(BaseModel):
    code: str
    name: str


class CityOut(BaseModel):
    id: int
    name: str
    district_count: int


class StatOut(BaseModel):
    code: str
    label: str
    rank: str


class PhaseProgressOut(BaseModel):
    target_label: str
    scope_label: str
    current: int
    total: int


class DevItemOut(BaseModel):
    label: str
    level: int
    kind: str  # bloodline | path | technique | genius


class ActivePotionOut(BaseModel):
    name: str
    tier: str
    left_seconds: int
    effect: str


class AbsoluteOut(BaseModel):
    code: str
    name: str
    perk: str
    via_stylist: bool  # перк взят Стилистом, самой карты нет


class AbsolutesOut(BaseModel):
    items: list[AbsoluteOut]
    blocked_seconds: int  # Ариан противника заблокировал абсолюты (0 — нет)


class ProfileOut(BaseModel):
    user_id: int
    username: str | None
    display_name: str | None
    is_onboarded: bool
    country: CountryOut | None
    city: CityOut | None
    phase: str
    phase_label: str
    potential_label: str
    gang_name: str | None
    army_power: int
    attack_power: int
    defense_power: int
    districts: int
    influence: int
    nh_coins: int
    nh_coins_pending: int
    donate_balance: int
    tickets: int
    tickets_cap: int
    online: int
    avatar: str | None
    stats: list[StatOut]
    dev_points: int
    phase_progress: PhaseProgressOut | None
    development: list[DevItemOut]
    second_body: bool
    potions: list[ActivePotionOut] = []
    absolutes: AbsolutesOut | None = None  # абсолюты — пассивки за обладание
    clan_name: str | None = None
