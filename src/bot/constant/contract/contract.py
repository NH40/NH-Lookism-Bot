"""Контракты статистов (константы): callback'и экрана найма."""
from __future__ import annotations

CB_CONTRACT_OPEN = "contract:open"
CB_CONTRACT_PAGE_PREFIX = "contract:page:"  # f"{...}{page}" — страница рангов
CB_CONTRACT_RANK_PREFIX = "contract:rank:"  # f"{...}{rank}" — выбрать ранг → ввод количества
CB_CONTRACT_BUY_PREFIX = "contract:buy:"  # f"{...}{rank}:{quantity}" — подтвердить найм
