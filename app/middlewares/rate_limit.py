import logging
from typing import Callable, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery

from app.config import settings

logger = logging.getLogger(__name__)

# Per-user limits: max REQUESTS actions per WINDOW seconds.
# After MAX_VIOLATIONS windows where limit is exceeded → temp ban.
REQUESTS = 8
WINDOW = 3          # seconds
MAX_VIOLATIONS = 5  # violations before ban
BAN_SECONDS = 300   # 5 minutes

# Lua script: atomic INCR + EXPIRE-only-on-first-call.
# Avoids two round-trips to Redis per request.
_INCR_EXPIRE_LUA = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RateLimitMiddleware(BaseMiddleware):
    """
    Redis-backed sliding window rate limiter with escalating auto-ban.

    Keys:
      rl:cnt:{uid}  — request counter, TTL = WINDOW seconds
      rl:vio:{uid}  — violation counter, TTL = 1 hour
      rl:ban:{uid}  — ban flag, TTL = BAN_SECONDS
    """

    def __init__(
        self,
        limit: float = 0.5,          # kept for backwards compat, unused
        requests: int = REQUESTS,
        window: int = WINDOW,
        max_violations: int = MAX_VIOLATIONS,
        ban_seconds: int = BAN_SECONDS,
    ):
        self.requests = requests
        self.window = window
        self.max_violations = max_violations
        self.ban_seconds = ban_seconds
        # Reuse the shared Redis client — no extra connection pool
        from app.services.cooldown_service import cooldown_service
        self._redis = cooldown_service.redis

    # ── Redis helpers ────────────────────────────────────────────────────────

    async def _is_banned(self, uid: int) -> bool:
        return await self._redis.exists(f"rl:ban:{uid}") == 1

    async def _record_request(self, uid: int) -> int:
        return int(await self._redis.eval(
            _INCR_EXPIRE_LUA, 1, f"rl:cnt:{uid}", self.window
        ))

    async def _record_violation(self, uid: int) -> int:
        return int(await self._redis.eval(
            _INCR_EXPIRE_LUA, 1, f"rl:vio:{uid}", 3600
        ))

    async def _ban(self, uid: int) -> None:
        await self._redis.setex(f"rl:ban:{uid}", self.ban_seconds, "1")
        logger.warning(
            "[RateLimit] user %d auto-banned for %ds (script abuse)",
            uid, self.ban_seconds,
        )

    # ── Middleware entry ─────────────────────────────────────────────────────

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        uid: int | None = None
        if hasattr(event, "from_user") and event.from_user:
            uid = event.from_user.id

        if not uid:
            return await handler(event, data)

        if uid in settings.admin_ids_list:
            return await handler(event, data)

        if await self._is_banned(uid):
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        "⛔ Вы временно заблокированы за использование скриптов.\n"
                        "Попробуйте через несколько минут.",
                        show_alert=True,
                    )
                except Exception:
                    pass
            return None

        count = await self._record_request(uid)
        if count > self.requests:
            violations = await self._record_violation(uid)
            logger.info(
                "[RateLimit] user %d: %d req/%ds, violations=%d",
                uid, count, self.window, violations,
            )
            if violations >= self.max_violations:
                await self._ban(uid)
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass
            return None

        return await handler(event, data)
