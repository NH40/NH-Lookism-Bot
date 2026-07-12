ITEM_TYPES = {
    "squad_member":       "👥 Статисты",
    "character":          "⭐ Персонажи",
    "tickets":            "🎟 Тикеты",
    "card_dust":          "🌫 Пыль карт",
    "path_points":        "🔷 Очки пути",
    "mastery_points":     "⭐ Очки мастерства",
    "ui_fragments":       "🔮 Фрагменты УИ",
    "alchemy_fragments":  "🧪 Фрагменты алхимии",
    "path_fragments":     "🔷 Фрагменты Пути",
    "business_fragments": "🏢 Фрагменты бизнеса",
    "war_points":         "⚔️ Очки войны",
}

MAX_LISTINGS_PER_USER = 5

# ── Аукционы на бирже ─────────────────────────────────────────────────────────
MARKET_AUCTION_COMMISSION_PCT = 0.10          # комиссия системы с выигрышной ставки (sink)
MARKET_AUCTION_MIN_BID_INCREMENT_PCT = 0.10   # минимальный шаг следующей ставки
MARKET_AUCTION_DURATION_OPTIONS = [3600, 3 * 3600, 6 * 3600, 12 * 3600, 24 * 3600]  # 1/3/6/12/24ч
MARKET_AUCTION_SOFT_CLOSE_SECONDS = 60        # анти-снайп: если ставка в последние N секунд
MARKET_AUCTION_EXTEND_SECONDS = 60            # ...продлить аукцион на столько
MARKET_AUCTION_MAX_PER_USER = 3               # отдельный кап от MAX_LISTINGS_PER_USER