from app.services.game.gang import GameGangService
from app.services.game.king import GameKingService
from app.services.game.fist import GameFistService


class GameService(GameGangService, GameKingService, GameFistService):
    """Главный сервис — объединяет все фазы."""

    async def gang_attack(self, session, user):
        return await self.gang_attack_bot(session, user)

    async def gang_pvp_attack(self, session, attacker, defender_id):
        return await self.gang_attack_pvp(session, attacker, defender_id)


game_service = GameService()