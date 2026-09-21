"""Фазы игрока — банда -> круг -> кулак (константы).

Значения сравниваются (`User.phase == ...`, ветвление по КД на сражения — 5м/30м/1ч в
зависимости от фазы, см. raw-notes «Фазы») — именованные константы, не строковые литералы
в репозитории/сервисе (см. CLAUDE.md, правило про `constant/`).
"""
from __future__ import annotations

PHASE_GANG = "gang"
PHASE_CIRCLE = "circle"
PHASE_FIST = "fist"

PHASE_ORDER: tuple[str, ...] = (PHASE_GANG, PHASE_CIRCLE, PHASE_FIST)
