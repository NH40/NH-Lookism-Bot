"""Лиги (константы): статусы заявок на районы после перехода и callback кнопки «Отбить район»."""
from __future__ import annotations

CLAIM_OPEN = "open"  # ждёт вызова (или идёт вызов)
CLAIM_WON = "won"  # район отбит, здания поставлены
CLAIM_LOST = "lost"  # вызов проигран — здания возвращены NHCoin
CLAIM_EXPIRED = "expired"  # 24 часа прошли без победы — здания возвращены NHCoin

CB_LEAGUE_CLAIM_PREFIX = "lg:claim:"  # + id заявки
