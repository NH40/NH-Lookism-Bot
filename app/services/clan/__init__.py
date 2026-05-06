from app.services.clan.base import ClanBaseService
from app.services.clan.invite import ClanInviteService
from app.services.clan.war import ClanWarService
from app.services.clan.exchange import ClanExchangeService
from app.services.clan.shop import ClanShopService
from app.services.clan.auction import ClanAuctionService
from app.services.clan.treasury import ClanTreasuryService
from app.services.clan.upgrades import ClanUpgradesService


class ClanService(
    ClanInviteService,
    ClanWarService,
    ClanExchangeService,
    ClanShopService,
    ClanAuctionService,
    ClanTreasuryService,
    ClanUpgradesService,
):
    """Единый сервис кланов."""
    pass


clan_service = ClanService()