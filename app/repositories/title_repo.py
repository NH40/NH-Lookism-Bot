from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.title import UserDonatTitle
from app.data.titles import DONAT_TITLE_MAP, DONAT_SET_MAP, DONAT_SETS, DONAT_TITLES


class TitleRepo:

    async def has_title(
        self, session: AsyncSession, user_id: int, title_id: str
    ) -> bool:
        result = await session.execute(
            select(UserDonatTitle).where(
                UserDonatTitle.user_id == user_id,
                UserDonatTitle.title_id == title_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_combat_power_mult(
        self, session: AsyncSession, user_id: int
    ) -> float:
        """Перемножает все combat_power_mult от активных донат-титулов."""
        result = await session.execute(
            select(UserDonatTitle.title_id).where(
                UserDonatTitle.user_id == user_id
            )
        )
        title_ids = result.scalars().all()

        mult = 1.0
        # Кулак: +20% мощи
        if "fist_power" in title_ids:
            mult *= 1.20
        # Гений оружия: +15%, с полным сетом genius_maker +18% (×1.20)
        if "genius_weapon" in title_ids:
            genius_titles = [t.title_id for t in DONAT_TITLES if t.set_id == "genius_maker"]
            if all(tid in title_ids for tid in genius_titles):
                mult *= 1.18
            else:
                mult *= 1.15
        # Монстр (сет целиком): +100%
        monster_titles = [t.title_id for t in DONAT_TITLES if t.set_id == "monster"]
        if all(tid in title_ids for tid in monster_titles):
            mult *= 2.0

        return mult

    async def get_user_titles(
        self, session: AsyncSession, user_id: int
    ) -> list[str]:
        result = await session.execute(
            select(UserDonatTitle.title_id).where(
                UserDonatTitle.user_id == user_id
            )
        )
        return result.scalars().all()

    async def has_set(
        self, session: AsyncSession, user_id: int, set_id: str
    ) -> bool:
        titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == set_id]
        if not titles_in_set:
            return False
        count = await session.scalar(
            select(func.count(UserDonatTitle.title_id)).where(
                UserDonatTitle.user_id == user_id,
                UserDonatTitle.title_id.in_(titles_in_set),
            )
        )
        return (count or 0) == len(titles_in_set)

    async def has_all_sets(self, session: AsyncSession, user_id: int) -> bool:
        """Проверяет наличие всех донатных сетов (VVIP) — 1 запрос вместо N."""
        owned = set(await self.get_user_titles(session, user_id))
        return all(
            all(t.title_id in owned for t in DONAT_TITLES if t.set_id == s.set_id)
            for s in DONAT_SETS
        )

    async def get_titles_display(
        self, session: AsyncSession, user_id: int
    ) -> str:
        """Строка с титулами для профиля."""
        result = await session.execute(
            select(UserDonatTitle.title_id).where(
                UserDonatTitle.user_id == user_id
            )
        )
        owned = set(result.scalars().all())
        if not owned:
            return "Нет титулов"

        lines = []
        shown_titles = set()

        # Сначала полные сеты
        for s in DONAT_SETS:
            titles_in_set = [t.title_id for t in DONAT_TITLES if t.set_id == s.set_id]
            if all(tid in owned for tid in titles_in_set):
                lines.append(f"✨ {s.name}")
                shown_titles.update(titles_in_set)

        # Отдельные титулы которые не вошли в полный сет
        for tid in owned:
            if tid not in shown_titles:
                cfg = DONAT_TITLE_MAP.get(tid)
                if cfg:
                    lines.append(f"{cfg.emoji} {cfg.name}")

        # VVIP если все сеты собраны
        all_set_ids = {s.set_id for s in DONAT_SETS}
        has_all = all(
            all(
                t.title_id in owned
                for t in DONAT_TITLES if t.set_id == sid
            )
            for sid in all_set_ids
        )
        if has_all:
            lines.insert(0, "👑 VVIP")

        return "\n".join(lines) if lines else "Нет титулов"


title_repo = TitleRepo()