"""Журнал действий игроков (константы) — виды записей. Уровень наблюдения решает, какие
виды видны (`config/activity.LOG_KINDS_BY_LEVEL`)."""
from __future__ import annotations

ACT_BATTLE = "battle"  # PvE/PvP/босс/война/трон
ACT_CAPTURE = "capture"  # захват районов/городов
ACT_BUSINESS = "business"  # постройки
ACT_DEVELOPMENT = "dev"  # развитие (уровни, новые гениальности/техники/пути)
