"""Биржа (конфиг). Перенос из 1.0 («Рынок»: лоты по фиксированной цене в ресурсе на выбор
продавца, аукционы с антиснайпом и комиссией). Пользователь 2026-10-04: торговать «всеми
ресурсами, что есть в игре, включая донат», формат — лоты + аукционы + прямой обмен с
игроком. Числа — из 1.0, комиссия лотов — решение автора кода."""
from __future__ import annotations

EXCHANGE_MAX_LOTS = 5  # активных лотов у игрока (1.0)
EXCHANGE_MAX_AUCTIONS = 3  # активных аукционов у игрока (1.0)
EXCHANGE_MAX_TRADES = 5  # исходящих предложений обмена
EXCHANGE_LOT_COMMISSION = 0.05  # с продавца — уходит из экономики
EXCHANGE_AUCTION_COMMISSION = 0.10  # с выигрышной ставки (1.0)
EXCHANGE_AUCTION_MIN_STEP = 0.10  # следующая ставка — минимум +10% (1.0)
EXCHANGE_AUCTION_HOURS: tuple[int, ...] = (1, 3, 6, 12, 24)  # (1.0)
EXCHANGE_AUCTION_SOFT_CLOSE_SECONDS = 60  # ставка в последнюю минуту — продление (1.0)
EXCHANGE_AUCTION_EXTEND_SECONDS = 60
EXCHANGE_TRADE_HOURS = 24  # предложение обмена живёт сутки
EXCHANGE_PAGE = 8
EXCHANGE_SWEEP_SECONDS = 30
