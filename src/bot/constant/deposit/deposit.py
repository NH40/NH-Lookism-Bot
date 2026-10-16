"""Вклады (константы)."""
from __future__ import annotations

CB_DEPOSIT_OPEN = "deposit:open"
CB_DEPOSIT_NEW = "deposit:new"  # выбрать ресурс
CB_DEPOSIT_RES_PREFIX = "deposit:res:"  # f"{...}{resource}" — выбрать срок
CB_DEPOSIT_TERM_PREFIX = "deposit:term:"  # f"{...}{resource}:{hours}" — ввод суммы
CB_DEPOSIT_CLAIM_PREFIX = "deposit:claim:"  # f"{...}{id}" — забрать (созрел — с процентами, нет — только тело)
# Правило 2: вклад и выемка двигают ресурсы — Redis-лок на клик.
LOCK_ACTION_DEPOSIT = "deposit"
