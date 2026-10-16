"""Тренировки — личная (характеристики, КД 10 минут) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (константы)."""
from __future__ import annotations

CB_TRAIN_EXTRAS_OPEN = "training:open"
CB_TRAIN_EXTRAS_RUN = "training:run"
CB_TRAIN_PERSONAL = "training:personal"

# Тренировка техники (2026-10-12): список техник → экран техники (оплата / квест / уровень).
CB_TRAIN_TECH_OPEN = "training:tech"
CB_TRAIN_TECH_VIEW_PREFIX = "training:tv:"  # f"{...}{код техники}"
CB_TRAIN_TECH_PAY_PREFIX = "training:tp:"  # f"{...}{код техники}" — оплатить тренировку у учителя
CB_TRAIN_TECH_LEVEL_PREFIX = "training:tl:"  # f"{...}{код техники}" — поднять уровень за фрагменты

# Школы статистов (2026-10-13: занятия переехали из магазина в тренировки).
CB_TRAIN_SCHOOLS_OPEN = "training:schools"
CB_TRAIN_SCHOOL_LESSON_PREFIX = "training:sl:"  # f"{...}{школа}" — занятие у купленного учителя
