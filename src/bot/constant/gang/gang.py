"""Банда игрока — экран банды, распределение статистов по лагерям (константы)."""
from __future__ import annotations

CB_GANG_OPEN = "gang:open"
CB_GANG_BACK = "gang:back"  # возврат на экран банды редактированием, а не новым сообщением
CB_GANG_CAMP_MOVE_PREFIX = "gang:camp:"
"""f"{CB_GANG_CAMP_MOVE_PREFIX}{from_camp}:{to_camp}:{percent}" — быстрый перевод доли всей армии."""

# Ручная сборка лагерей по отрядам (отряд = стопка статистов одного ранга, звёзд и уровня
# тренировки — см. db/models/extra.py). Ранги не содержат ':' — безопасный разделитель.
CB_GANG_SQUADS_PREFIX = "gang:squads:"
"""f"{CB_GANG_SQUADS_PREFIX}{page}" — список отрядов."""
CB_GANG_SQUAD_PREFIX = "gang:squad:"
"""f"{CB_GANG_SQUAD_PREFIX}{rank}:{stars}:{training_level}" — экран одного отряда."""
CB_GANG_SQUAD_MOVE_PREFIX = "gang:sqmv:"
"""f"{CB_GANG_SQUAD_MOVE_PREFIX}{rank}:{stars}:{level}:{from_camp}:{amount}" — перенос части отряда."""
CB_GANG_SQUAD_CUSTOM_PREFIX = "gang:sqcustom:"
"""f"{CB_GANG_SQUAD_CUSTOM_PREFIX}{rank}:{stars}:{level}:{from_camp}" — ввести своё число."""

AMOUNT_HALF = "half"
AMOUNT_ALL = "all"

# Состав отряда — 9 позиций уников (raw-notes «Банда»).
CB_GANG_LINEUP = "gang:lineup"
CB_GANG_POSITION_PREFIX = "gang:pos:"
"""f"{CB_GANG_POSITION_PREFIX}{position}:{page}" — экран позиции со списком подходящих карт."""
CB_GANG_POSITION_SET_PREFIX = "gang:posset:"
"""f"{CB_GANG_POSITION_SET_PREFIX}{position}:{card_code}"."""
CB_GANG_POSITION_CLEAR_PREFIX = "gang:posclr:"
"""f"{CB_GANG_POSITION_CLEAR_PREFIX}{position}"."""

# Удаление банды (полный сброс) — экран подтверждения и сама кнопка «Да».
CB_GANG_DELETE_ASK = "gang:delask"
CB_GANG_DELETE_CONFIRM = "gang:delyes"
