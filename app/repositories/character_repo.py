from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.character import UserCharacter
from app.data.characters import RANK_CONFIG_MAP, RANK_EMOJI


class CharacterRepo:

    async def get_total_power(
        self, session: AsyncSession, user_id: int
    ) -> int:
        result = await session.scalar(
            select(func.sum(UserCharacter.power)).where(
                UserCharacter.user_id == user_id
            )
        )
        return result or 0

    async def get_collection(
        self, session: AsyncSession, user_id: int
    ) -> list[UserCharacter]:
        result = await session.execute(
            select(UserCharacter).where(
                UserCharacter.user_id == user_id
            ).order_by(UserCharacter.power.desc())
        )
        return result.scalars().all()

    async def get_collection_display(
        self, session: AsyncSession, user_id: int
    ) -> str:
        chars = await self.get_collection(session, user_id)
        if not chars:
            return "Коллекция пуста"

        from collections import Counter
        counts = Counter((c.character_id, c.rank) for c in chars)
        rank_order = [
            "absolute", "peak", "legend", "new_legend",
            "gen_zero", "strong_king", "king", "boss", "member"
        ]

        # Сортируем по рангу
        sorted_chars = sorted(
            counts.items(),
            key=lambda x: rank_order.index(x[0][1])
            if x[0][1] in rank_order else 99
        )

        lines = []
        for (name, rank), count in sorted_chars:
            emoji = RANK_EMOJI.get(rank, "❓")
            cfg = RANK_CONFIG_MAP.get(rank)
            rank_label = cfg.label if cfg else rank
            cnt_str = f" ×{count}" if count > 1 else ""
            lines.append(f"{emoji} {name}{cnt_str} [{rank_label}]")

        total = sum(c.power for c in chars)
        lines.append(f"\n💥 Суммарная мощь: {total:,}")
        return "\n".join(lines)


character_repo = CharacterRepo()