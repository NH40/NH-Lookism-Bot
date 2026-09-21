"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (тексты)."""
from __future__ import annotations

from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST, PHASE_GANG

PHASE_LABELS: dict[str, str] = {
    PHASE_GANG: "Банда",
    PHASE_CIRCLE: "Круг",
    PHASE_FIST: "Кулак",
}

PROFILE_CARD = (
    "👤 <b>{display_name}</b>\n"
    "Юзернейм: {username}\n\n"
    "🏴 Банда: {gang_name}\n"
    "🌍 Страна: {country}\n"
    "🏙 Город: {city}\n"
    "🚦 Фаза: {phase_label}\n\n"
    "Остальные разделы профиля (характеристики, мастерство, уникальные системы, клан) "
    "появятся по мере реализации соответствующих доменов."
)

NOT_ONBOARDED = "Сначала пройди регистрацию — набери /start."
