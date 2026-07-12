"""Общее для всех игр казино: ресурсы ставок, баланс, детектор стратегии x3."""
import logging
from app.models.user import User
from app.constants.bank import CASINO_HISTORY_TTL, CASINO_X3_RATIO_MIN, CASINO_X3_RATIO_MAX

logger = logging.getLogger(__name__)

# ── Допустимые ресурсы ────────────────────────────────────────────────────────
CASINO_RESOURCES: dict[str, str] = {
    "nh_coins":           "💰 NHCoin",
    "tickets":            "🎟 Тикеты",
    "card_dust":          "🌫 Пыль карт",
    "ui_fragments":       "🔮 Фрагменты УИ",
    "alchemy_fragments":  "🧪 Фрагменты алхимии",
    "path_fragments":     "🩺 Фрагменты пути",
    "business_fragments": "🏢 Фрагменты бизнеса",
    "war_points":         "⚔️ Очки войны",
    "mastery_points":     "🎯 Очки мастерства",
}
CASINO_RESOURCE_LABELS = CASINO_RESOURCES  # алиас

_HISTORY_KEY = "casino:bets:{game}:{uid}:{res}"
_HISTORY_TTL = CASINO_HISTORY_TTL


def get_balance(user: User, resource: str) -> int:
    return getattr(user, resource, 0)


def set_balance(user: User, resource: str, value: int) -> None:
    setattr(user, resource, value)


def _redis():
    from app.services.cooldown_service import cooldown_service
    return cooldown_service.redis


async def detect_x3(game: str, user_id: int, resource: str, amount: int) -> bool:
    """
    Возвращает True если ставка является частью паттерна x3 (3 подряд).
    Паттерн: ставка[i] ≈ 3 × ставка[i-1] (±10% допуск).
    """
    redis = _redis()
    key = _HISTORY_KEY.format(game=game, uid=user_id, res=resource)
    try:
        history = await redis.lrange(key, 0, -1)
        bets = [int(v) for v in history]
        bets.append(amount)

        def is_triple(a: int, b: int) -> bool:
            if a == 0:
                return False
            ratio = b / a
            return CASINO_X3_RATIO_MIN <= ratio <= CASINO_X3_RATIO_MAX

        if len(bets) >= 3:
            if is_triple(bets[-3], bets[-2]) and is_triple(bets[-2], bets[-1]):
                return True
    except Exception as e:
        logger.warning(f"casino x3 detect error: {e}")
    return False


async def record_bet(game: str, user_id: int, resource: str, amount: int) -> None:
    """Записать ставку в историю (Redis список, 3 последних)."""
    redis = _redis()
    key = _HISTORY_KEY.format(game=game, uid=user_id, res=resource)
    try:
        await redis.rpush(key, str(amount))
        await redis.ltrim(key, -3, -1)
        await redis.expire(key, _HISTORY_TTL)
    except Exception as e:
        logger.warning(f"casino record_bet error: {e}")


X3_WARN_MSG = (
    "🎰 <b>Казино просит вас остановиться!</b>\n\n"
    "Мы заметили, что вы каждый раз ставите в 3 раза больше.\n"
    "Пожалуйста, измените размер ставки.\n\n"
    "<i>Казино оставляет за собой право отклонить ставку.</i>"
)


def add_weekly_casino_profit(user: User, resource: str, net_change: int) -> None:
    """Учитывает чистую прибыль/убыток в недельном рейтинге казино (только NHCoin)."""
    if resource == "nh_coins":
        user.casino_weekly_coins_won = (user.casino_weekly_coins_won or 0) + net_change
