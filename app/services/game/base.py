"""GameBase — базовый класс игровых сервисов.

Логика разбита на миксины:
  _queries_mixin.py    — запросы к городам/районам, КД
  _promotions_mixin.py — переходы между фазами (повышение/понижение)
  _districts_mixin.py  — выдача/изъятие fist/king-районов (fist — deprecated)
  _vassal_mixin.py     — битва за трон, вассалитет, городской налог, конкест страны (патч 1.3.1)
"""
from app.services.game._queries_mixin import CityQueriesMixin, ATTACK_CD
from app.services.game._promotions_mixin import PromotionsMixin, FIST_MIN_CITIES, FIST_CITY_SIZES, FIST_BOT_CONFIGS
from app.services.game._districts_mixin import DistrictsMixin
from app.services.game._vassal_mixin import VassalMixin

__all__ = ["GameBase", "ATTACK_CD", "FIST_MIN_CITIES", "FIST_CITY_SIZES", "FIST_BOT_CONFIGS"]


class GameBase(CityQueriesMixin, PromotionsMixin, DistrictsMixin, VassalMixin):
    """Агрегирует все миксины в единый базовый класс для GameGangService, GameKingService, GameKingChallengeService, GameEmperorService."""
    pass
