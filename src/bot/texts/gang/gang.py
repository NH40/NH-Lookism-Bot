"""Банда игрока — название, состав (9 позиций), статисты (лагеря) (тексты)."""
from __future__ import annotations

from bot.config.game import GANG_NAME_MAX_LENGTH, GANG_NAME_MIN_LENGTH

NAME_PROMPT = "🏴 Придумай название для своей банды (от {min} до {max} символов):".format(
    min=GANG_NAME_MIN_LENGTH, max=GANG_NAME_MAX_LENGTH
)

NAME_TOO_SHORT = f"Слишком коротко — минимум {GANG_NAME_MIN_LENGTH} символа. Попробуй ещё раз:"
NAME_TOO_LONG = f"Слишком длинно — максимум {GANG_NAME_MAX_LENGTH} символов. Попробуй ещё раз:"

NAME_CONFIRMED = "✅ Банда «{name}» создана!"
