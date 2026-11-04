"""Ультра инстинкт — действия и ключи настроек (константы)."""
from __future__ import annotations

ACTION_RECRUIT = "recruit"
ACTION_TRAIN = "train"
ACTION_EXTRAS = "extras"
ACTION_SCHOOL = "school"
ACTION_ROLL = "roll"
ACTIONS: tuple[str, ...] = (ACTION_RECRUIT, ACTION_TRAIN, ACTION_EXTRAS, ACTION_SCHOOL, ACTION_ROLL)

KEY_BOSSES = "bosses"  # коды боссов, которых бить автоматически
KEY_MAX_LOSS = "max_loss"  # потолок ожидаемых потерь, %
KEY_OFF = "off"  # выключенные действия

CB_ULTRA_OPEN = "ultra:open"
CB_ULTRA_ACTION_PREFIX = "ultra:act:"
CB_ULTRA_BOSS_PREFIX = "ultra:boss:"
CB_ULTRA_LOSS_PREFIX = "ultra:loss:"
