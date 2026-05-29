import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.user import User
from app.models.promo import PromoCode, PromoUse

REWARD_LABELS = {
    "tickets":            "🎟 Тикеты",
    "coins":              "💰 NHCoin",
    "ui_fragments":       "🔮 Фрагменты УИ",
    "alchemy_fragments":  "🧪 Фрагменты алхимии",
    "path_fragments":     "🔷 Фрагменты Пути",
    "path_points":        "💎 Очки пути",
    "mastery_points":     "⭐ Очки мастерства",
}


def _parse_rewards(promo: PromoCode) -> list[dict]:
    """Возвращает список наград промокода в едином формате."""
    if promo.rewards_json:
        try:
            return json.loads(promo.rewards_json)
        except Exception:
            pass
    # Legacy поддержка старых промокодов
    if promo.reward_type and promo.reward_amount is not None:
        return [{"type": promo.reward_type, "amount": promo.reward_amount}]
    return []


def _rewards_summary(rewards: list[dict]) -> str:
    """Красивая строка со всеми наградами."""
    parts = []
    for r in rewards:
        label = REWARD_LABELS.get(r["type"], r["type"])
        parts.append(f"{label}: +{r['amount']:,}".replace(",", " "))
    return "\n".join(parts)


class PromoService:

    async def create_promo(
        self,
        session: AsyncSession,
        code: str,
        rewards: list[dict],
        limit_type: str = "uses",
        max_uses: int = 1,
        expires_at: datetime | None = None,
    ) -> dict:
        """
        Создаёт промокод.
        rewards — список [{type, amount}, ...]
        limit_type — "uses" (по кол-ву) или "time" (по времени)
        max_uses — макс. использований (для limit_type="uses")
        expires_at — когда истекает (для limit_type="time")
        """
        if not rewards:
            return {"ok": False, "reason": "Нет наград"}
        for r in rewards:
            if r.get("type") not in REWARD_LABELS:
                return {"ok": False, "reason": f"Неизвестный тип награды: {r.get('type')}"}
            if not isinstance(r.get("amount"), int) or r["amount"] <= 0:
                return {"ok": False, "reason": f"Неверное количество для {r.get('type')}"}

        if limit_type not in ("uses", "time"):
            return {"ok": False, "reason": "Тип ограничения: uses или time"}

        if not code or len(code) > 32:
            return {"ok": False, "reason": "Неверный код (макс. 32 символа)"}

        existing = await session.scalar(
            select(PromoCode).where(PromoCode.code == code.upper())
        )
        if existing:
            return {"ok": False, "reason": "Код уже существует"}

        promo = PromoCode(
            code=code.upper(),
            limit_type=limit_type,
            rewards_json=json.dumps(rewards, ensure_ascii=False),
            max_uses=max_uses if limit_type == "uses" else 999_999_999,
            expires_at=expires_at if limit_type == "time" else None,
        )
        session.add(promo)
        await session.flush()
        return {"ok": True, "promo_id": promo.id}

    async def use_promo(
        self, session: AsyncSession, user: User, code: str
    ) -> dict:
        from app.services.cooldown_service import cooldown_service
        code_upper = code.upper()
        code_lock = f"lock:promo_code:{code_upper}"
        if not await cooldown_service.acquire_lock(code_lock, ttl=5):
            return {"ok": False, "reason": "Подожди..."}

        promo = await session.scalar(
            select(PromoCode).where(
                PromoCode.code == code_upper,
                PromoCode.is_active == True,
            )
        )
        if not promo:
            return {"ok": False, "reason": "Промокод не найден или неактивен"}

        # Проверка по времени
        if promo.limit_type == "time":
            if promo.expires_at and datetime.now(timezone.utc) > promo.expires_at:
                promo.is_active = False
                await session.flush()
                return {"ok": False, "reason": "Срок действия промокода истёк"}
        else:
            # Проверка по кол-ву использований
            if promo.used_count >= promo.max_uses:
                return {"ok": False, "reason": "Промокод уже использован максимальное количество раз"}

        # Проверяем использовал ли уже этот игрок
        already = await session.scalar(
            select(PromoUse).where(
                PromoUse.promo_id == promo.id,
                PromoUse.user_id == user.id,
            )
        )
        if already:
            return {"ok": False, "reason": "Вы уже использовали этот промокод"}

        rewards = _parse_rewards(promo)
        if not rewards:
            return {"ok": False, "reason": "Промокод повреждён, обратитесь к администратору"}

        # Выдаём все награды
        for r in rewards:
            self._apply_reward(user, r["type"], r["amount"])

        promo.used_count += 1
        if promo.limit_type == "uses" and promo.used_count >= promo.max_uses:
            promo.is_active = False

        session.add(PromoUse(promo_id=promo.id, user_id=user.id))
        await session.flush()

        return {
            "ok": True,
            "rewards": rewards,
            "summary": _rewards_summary(rewards),
        }

    def _apply_reward(self, user: User, reward_type: str, amount: int) -> None:
        if reward_type == "tickets":
            from app.config.game_balance import ticket_hard_cap
            user.tickets = min(user.tickets + amount, ticket_hard_cap(user))
        elif reward_type == "coins":
            user.nh_coins += amount
        elif reward_type == "ui_fragments":
            user.ui_fragments += amount
        elif reward_type == "alchemy_fragments":
            user.alchemy_fragments += amount
        elif reward_type == "path_fragments":
            user.path_fragments += amount
        elif reward_type == "path_points":
            user.skill_path_points += amount
        elif reward_type == "mastery_points":
            user.mastery_points += amount

    async def get_all_promos(self, session: AsyncSession) -> list[PromoCode]:
        result = await session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc()).limit(30)
        )
        return result.scalars().all()

    async def deactivate_promo(self, session: AsyncSession, promo_id: int) -> dict:
        promo = await session.scalar(
            select(PromoCode).where(PromoCode.id == promo_id)
        )
        if not promo:
            return {"ok": False, "reason": "Промокод не найден"}
        promo.is_active = False
        await session.flush()
        return {"ok": True}

    async def delete_promo(self, session: AsyncSession, promo_id: int) -> dict:
        promo = await session.scalar(
            select(PromoCode).where(PromoCode.id == promo_id)
        )
        if not promo:
            return {"ok": False, "reason": "Промокод не найден"}
        await session.execute(delete(PromoUse).where(PromoUse.promo_id == promo_id))
        await session.delete(promo)
        await session.flush()
        return {"ok": True}


promo_service = PromoService()
