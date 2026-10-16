"""Ежедневные задания (константы) — callback'и и локи."""
from __future__ import annotations

LOCK_ACTION_QUEST = "quest"

CB_QUEST_REROLL_ALL = "q:rr"  # полный реролл невыполненных
CB_QUEST_SWAP_MENU = "q:sw"  # выбор задания на замену
CB_QUEST_SWAP_PREFIX = "q:sw:"  # q:sw:<слот>
CB_QUEST_ADMIN_COMPLETE = "q:adm"  # тест: выполнить все свои задания (только админ)
CB_QUEST_SCROLL = "q:sc"  # список заданий развития для свитка пропуска
CB_QUEST_SCROLL_PREFIX = "q:sc:"  # q:sc:<id квеста развития>
