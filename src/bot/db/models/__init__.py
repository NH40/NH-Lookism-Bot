"""Импортировать все модели здесь, чтобы Base.metadata видел их (нужно для Alembic
autogenerate) — та же плоская структура db/models, что в Universe Anime Planet: каждая
модель уже сама по себе один домен, без соседних файлов (см. CLAUDE.md UAP).

Наполняется по мере переноса доменов из LookismBattlePlanet 1.0. Порядок импорта здесь
не влияет на порядок создания таблиц (Alembic/`Base.metadata.create_all` сортируют по
FK-зависимостям сами), но `Country`/`City` идут раньше `User` для читаемости — на них
ссылается `User.country_code`/`city_id`.
"""

from bot.db.models.country import Country  # noqa: F401
from bot.db.models.city import City  # noqa: F401
from bot.db.models.user import User  # noqa: F401
from bot.db.models.gang import Gang  # noqa: F401
from bot.db.models.extra import Extra  # noqa: F401
from bot.db.models.district import District  # noqa: F401
from bot.db.models.district_challenge import DistrictChallenge  # noqa: F401
from bot.db.models.business import Business  # noqa: F401
from bot.db.models.card_stack import CardStack  # noqa: F401
from bot.db.models.card_position import CardPosition  # noqa: F401
from bot.db.models.mastery_quest import MasteryQuest  # noqa: F401
from bot.db.models.emperor_tax import EmperorTaxOverride  # noqa: F401
from bot.db.models.sabotage_log import SabotageLog  # noqa: F401
from bot.db.models.emperor_war import EmperorWar  # noqa: F401
from bot.db.models.development import BattleMemory, UserGenius, UserPath, UserSchool, UserTechnique  # noqa: F401
from bot.db.models.map_event import MapEvent, MapEventEntry  # noqa: F401
from bot.db.models.activity import ActivityLog, PlayerMark  # noqa: F401
from bot.db.models.dev_quest import DevQuest  # noqa: F401
from bot.db.models.contract import StatistContract  # noqa: F401
from bot.db.models.potion import UserPotion  # noqa: F401
from bot.db.models.storage_cell import StorageCell  # noqa: F401
from bot.db.models.deposit import Deposit  # noqa: F401
from bot.db.models.poker import PokerPlayer, PokerTable  # noqa: F401
from bot.db.models.exchange import ExchangeAuction, ExchangeLot, ExchangeTrade  # noqa: F401
from bot.db.models.clan import Clan, ClanBuilding, ClanContract, ClanDonatePurchase, ClanGarrisonCard, ClanGarrisonExtra, ClanIncomeShare, ClanJoinRequest, ClanLog, ClanMember, ClanMemberStat, ClanWar  # noqa: F401
from bot.db.models.quest import DailyQuest, DailyQuestState  # noqa: F401
from bot.db.models.battle_pass import BattlePass, BattlePassClaim, BpSeason  # noqa: F401
from bot.db.models.donate import DonateUnlock, Lbp1Donation, Payment, SbpPayment  # noqa: F401
from bot.db.models.admin import AdminAudit, GameSetting  # noqa: F401
from bot.db.models.promo import PromoCode, PromoRedemption  # noqa: F401
from bot.db.models.referral import ReferralLink, ReferralVisit  # noqa: F401
from bot.db.models.top import SeasonTopPayout  # noqa: F401
from bot.db.models.scout_report import ScoutReport  # noqa: F401
