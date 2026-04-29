AUCTION_ROUND_SECONDS = 90
BID_EXTEND_SECONDS = 15
NEXT_AUCTION_KEY = "next_auction_at"

AUCTION_PAUSE_MIN = 10
AUCTION_PAUSE_MAX = 20

TIER_WEIGHTS = {
    1: 50,
    2: 30,
    3: 15,
    4: 4,
    5: 1,
}

AUCTION_TIERS = {
    1: {"name": "Бронзовый",   "emoji": "🟫", "rounds": 2, "min_bid": 500,   "reward_type": "tickets"},
    2: {"name": "Серебряный",  "emoji": "⬜", "rounds": 2, "min_bid": 2000,  "reward_type": "potion"},
    3: {"name": "Золотой",     "emoji": "🟨", "rounds": 3, "min_bid": 5000,  "reward_type": "character"},
    4: {"name": "Платиновый",  "emoji": "🟦", "rounds": 3, "min_bid": 15000, "reward_type": "character"},
    5: {"name": "Королевский", "emoji": "🟧", "rounds": 4, "min_bid": 50000, "reward_type": "character"},
}

RANK_BY_TIER = {
    3: ["king", "strong_king"],
    4: ["gen_zero", "new_legend"],
    5: ["gen_zero", "new_legend"],
}