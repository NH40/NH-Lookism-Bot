"""Казино (константы)."""
from __future__ import annotations

from bot.constant.resource import NO_MINT_RESOURCES, RES_BLOOD, RESOURCES

GAME_SLOTS = "slots"
GAME_BLACKJACK = "bj"

STAKE_RESOURCE = "res"
STAKE_STATIST = "statist"

# Чем можно ставить. Донат-коины — нельзя (казино не печатает донат); кровь — нельзя
# (пользователь 2026-10-28: «убери кровь из казино» — игроки качали ею уровень крови).
CASINO_STAKE_RESOURCES: tuple[str, ...] = tuple(c for c in RESOURCES if c not in NO_MINT_RESOURCES and c != RES_BLOOD)

CB_CASINO_OPEN = "casino:open"
CB_CASINO_GAME_PREFIX = "casino:game:"  # f"{...}{game}" — выбор валюты ставки
CB_CASINO_STAKE_PREFIX = "casino:stake:"  # f"{...}{game}:{resource}" — ввод ставки
CB_CASINO_STATISTS_PREFIX = "casino:sts:"  # f"{...}{game}" — выбор отряда для ставки
CB_CASINO_SQUAD_PREFIX = "casino:sq:"  # f"{...}{game}:{StatistKey}" — ввод числа бойцов
CB_SLOTS_AGAIN_PREFIX = "casino:again:"  # f"{...}{resource}:{amount}" — та же ставка ещё раз
CB_BJ_HIT = "casino:bj:hit"
CB_BJ_STAND = "casino:bj:stand"
CB_BJ_DOUBLE = "casino:bj:double"
# Правило 2: ставка тратит ресурс — Redis-лок на клик.
LOCK_ACTION_CASINO = "casino"
