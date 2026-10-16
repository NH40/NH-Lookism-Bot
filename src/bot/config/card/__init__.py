"""Публичное API card-конфига: каталог уников и справочники поиска по нему."""
from bot.config.card.card import ASSETS_DIR, RARITY_CHANCE_PERCENT, CardDef  # noqa: F401
from bot.config.card.cards_data import CARDS  # noqa: F401

CARD_BY_CODE: dict[str, CardDef] = {c.code: c for c in CARDS}
CARDS_BY_RARITY: dict[str, tuple[CardDef, ...]] = {
    rarity: tuple(c for c in CARDS if c.rarity == rarity) for rarity in RARITY_CHANCE_PERCENT
}
