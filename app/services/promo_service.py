from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.promo import PromoCode, PromoUse

REWARD_LABELS = {
    "tickets":            "🎟 Тикеты",
    "coins":              "💰 NHCoin",
    "ui_fragments":       "🔮 Фрагменты УИ",
    "alchemy_fragments":  "🧪 Фрагменты алхимии",
    "path_points":        "🔷 Очки пути",
    "mastery_points":     "⭐ Очки мастерства",
}


class PromoService:

    async def create_promo(
        self, session: AsyncSession,
        code: str, reward_type: str,
        reward_amount: int, max_uses: int = 1
    ) -> dict:
        if reward_type not in REWARD_LABELS:
            return {"ok": False, "reason": "Неизвестный тип награды"}
        if not code or len(code) > 32:
            return {"ok": False, "reason": "Неверный код"}

        existing = await session.scalar(
            select(PromoCode).where(PromoCode.code == code.upper())
        )
        if existing:
            return {"ok": False, "reason": "Код уже существует"}

        promo = PromoCode(
            code=code.upper(),
            reward_type=reward_type,
            reward_amount=reward_amount,
            max_uses=max_uses,
        )
        session.add(promo)
        await session.flush()
        return {"ok": True, "promo_id": promo.id}

    async def use_promo(
        self, session: AsyncSession, user: User, code: str
    ) -> dict:
        promo = await session.scalar(
            select(PromoCode).where(
                PromoCode.code == code.upper(),
                PromoCode.is_active == True,
            )
        )
        if not promo:
            return {"ok": False, "reason": "Промокод не найден или неактивен"}

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

        # Выдаём награду
        self._apply_reward(user, promo.reward_type, promo.reward_amount)

        promo.used_count += 1
        if promo.used_count >= promo.max_uses:
            promo.is_active = False

        session.add(PromoUse(promo_id=promo.id, user_id=user.id))
        await session.flush()

        label = REWARD_LABELS.get(promo.reward_type, promo.reward_type)
        return {
            "ok": True,
            "reward_type": promo.reward_type,
            "reward_amount": promo.reward_amount,
            "label": label,
        }

    def _apply_reward(self, user: User, reward_type: str, amount: int) -> None:
        if reward_type == "tickets":
            user.tickets += amount  
        elif reward_type == "coins":
            user.nh_coins += amount
        elif reward_type == "ui_fragments":
            user.ui_fragments += amount
        elif reward_type == "alchemy_fragments":
            user.alchemy_fragments += amount
        elif reward_type == "path_points":
            user.skill_path_points += amount
        elif reward_type == "mastery_points":
            user.mastery_points += amount

    async def get_all_promos(self, session: AsyncSession) -> list[PromoCode]:
        result = await session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc()).limit(20)
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


promo_service = PromoService()