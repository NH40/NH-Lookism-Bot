"""GameBase — базовый класс игровых сервисов.

Логика разбита на три миксина:
  _queries_mixin.py    — запросы к городам/районам, КД
  _promotions_mixin.py — переходы между фазами (повышение/понижение)
  _districts_mixin.py  — выдача/изъятие fist/king-районов
"""
from app.services.game._queries_mixin import CityQueriesMixin, ATTACK_CD
from app.services.game._promotions_mixin import PromotionsMixin, FIST_MIN_CITIES, FIST_CITY_SIZES, FIST_BOT_CONFIGS
from app.services.game._districts_mixin import DistrictsMixin

__all__ = ["GameBase", "ATTACK_CD", "FIST_MIN_CITIES", "FIST_CITY_SIZES", "FIST_BOT_CONFIGS"]


class GameBase(CityQueriesMixin, PromotionsMixin, DistrictsMixin):
    """Агрегирует все три миксина в единый базовый класс для GameGangService, GameKingService, GameFistService."""
    pass
