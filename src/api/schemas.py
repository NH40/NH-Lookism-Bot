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


class ProfileOut(BaseModel):
    user_id: int
    username: str | None
    display_name: str | None
    is_onboarded: bool
    country: CountryOut | None
    city: CityOut | None
    phase: str
    gang_name: str | None
