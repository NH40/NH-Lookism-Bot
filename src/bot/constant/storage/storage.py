"""Ячейки хранения (константы)."""
from __future__ import annotations

STORAGE_ITEM_EMPTY = ""
STORAGE_ITEM_RESOURCE = "res"  # ресурс (`constant/resource`), item_code — код ресурса
STORAGE_ITEM_STATIST = "statist"  # отряд статистов, item_code — `StatistKey.encode()`

CB_STORAGE_OPEN = "storage:open"
CB_STORAGE_CELL_PREFIX = "storage:cell:"  # f"{...}{slot}"
CB_STORAGE_UNLOCK_PREFIX = "storage:unlock:"  # f"{...}{slot}" — купить ячейку
CB_STORAGE_PUT_RES_PREFIX = "storage:putr:"  # f"{...}{slot}:{resource}"
CB_STORAGE_PUT_STATISTS_PREFIX = "storage:puts:"  # f"{...}{slot}" — выбрать отряд
CB_STORAGE_PUT_SQUAD_PREFIX = "storage:sq:"  # f"{...}{slot}:{StatistKey}"
CB_STORAGE_TAKE_ALL_PREFIX = "storage:all:"  # f"{...}{slot}"
CB_STORAGE_TAKE_PART_PREFIX = "storage:take:"  # f"{...}{slot}" — ввод количества
CB_STORAGE_TOPUP_PREFIX = "storage:more:"  # f"{...}{slot}" — доложить то же самое
# Правило 2: открытие, вклад и выемка тратят ресурсы — Redis-лок на клик.
LOCK_ACTION_STORAGE = "storage"
