from app.services.game.gang import GameGangService
from app.services.game.king import GameKingService
from app.services.game.king_challenge import GameKingChallengeService
from app.services.game.emperor import GameEmperorService


class GameService(GameGangService, GameKingService, GameKingChallengeService, GameEmperorService):
    """Главный сервис — объединяет все фазы. GameFistService убран (патч 1.3.1) —
    Кулак вынесен из прогрессии, King ведёт напрямую в Emperor."""

    async def gang_attack(self, session, user, district_id: int):
        return await self.gang_attack_district(session, user, district_id)

    async def gang_pvp_attack(self, session, attacker, defender_id):
        return await self.gang_attack_pvp(session, attacker, defender_id)


game_service = GameService()