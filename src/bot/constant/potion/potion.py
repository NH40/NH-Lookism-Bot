"""Зелья (константы): виды и callback'и экрана «🧪 Зелья» в магазине."""
from __future__ import annotations

POTION_POWER = "power"  # сила армии
POTION_GUARD = "guard"  # стойкость (выживание)
POTION_WEALTH = "wealth"  # доход бизнеса
POTION_TRAINING = "training"  # тренировки
POTION_RECRUIT = "recruit"  # вербовка
POTION_LUCK = "luck"  # удача в крутке уников
POTION_HUNTER = "hunter"  # фрагменты с боссов

POTIONS: tuple[str, ...] = (
    POTION_POWER, POTION_GUARD, POTION_WEALTH, POTION_TRAINING, POTION_RECRUIT, POTION_LUCK, POTION_HUNTER,
)

CB_POTION_OPEN = "potion:open"
CB_POTION_KIND_PREFIX = "potion:kind:"  # f"{...}{kind}" — тиры одного зелья
CB_POTION_BUY_PREFIX = "potion:buy:"  # f"{...}{kind}:{tier}" — купить и выпить
CB_POTION_AUTO_PREFIX = "potion:auto:"  # f"{...}{kind}:{tier}" — авто-зелье (0 — выключить)
# Правило 2: покупка тратит NHCoin — Redis-лок на клик.
LOCK_ACTION_POTION = "potion"
