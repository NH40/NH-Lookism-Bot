from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update as sa_update, case
from app.models.user import User
from app.models.squad_member import SquadMember
from app.models.character import UserCharacter
from app.data.squad import RANKS_BY_ID


class SquadRepo:

    async def update_user_combat_power(
        self, session: AsyncSession, user: User
    ) -> int:
        """Единственное место расчёта боевой мощи."""

        # 1. Мощь отряда — один агрегирующий запрос вместо загрузки всех строк
        star_mult = case(
            (SquadMember.stars == 1, 1.10),
            (SquadMember.stars == 2, 1.20),
            (SquadMember.stars == 3, 1.30),
            (SquadMember.stars == 4, 1.40),
            (SquadMember.stars == 5, 1.50),
            else_=1.0,
        )
        squad_power_raw = await session.scalar(
            select(func.sum(SquadMember.base_power * star_mult))
            .where(SquadMember.user_id == user.id)
        )
        squad_power = int(squad_power_raw or 0)

        # 2. Мощь персонажей
        char_r = await session.execute(
            select(func.sum(UserCharacter.power)).where(
                UserCharacter.user_id == user.id
            )
        )
        char_power = char_r.scalar() or 0

        # 3. Бонус от учителя (обновляется scheduler'ом каждые 30 мин)
        teacher_bonus = user.teacher_power_bonus if user.referred_by else 0

        total = squad_power + char_power + teacher_bonus

        # Бонус мастерства силы — только колонка strength
        from app.models.skill import UserMastery
        strength = await session.scalar(
            select(UserMastery.strength).where(UserMastery.user_id == user.id)
        )
        if strength:
            strength_bonus = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
            raw = strength_bonus.get(strength, 0)
            effective = raw * user.skill_path_bonus_multiplier
            total = int(total * (1 + effective / 100))

        # Бонус навыков пути (squad_power_bonus): mon_power_1 / mon_power_2
        if user.squad_power_bonus > 0:
            total = int(total * (1 + user.squad_power_bonus / 100))

        # 4. Донат-множители
        from app.repositories.title_repo import title_repo
        mult = await title_repo.get_combat_power_mult(session, user.id)
        total = int(total * mult)

        # 5. Пробуждение (+5% за уровень)
        if user.prestige_level > 0:
            prestige_mult = 1 + (user.prestige_level * 5 / 100)
            total = int(total * prestige_mult)

        # Зелье боевой мощи
        try:
            from app.services.potion_service import potion_service
            potion_bonus = await potion_service.get_power_bonus(session, user.id)
            if potion_bonus > 0:
                total = int(total * (1 + potion_bonus / 100))
        except Exception:
            pass

        # Ограничиваем разумным максимумом (BIGINT safe)
        total = min(total, 9_000_000_000_000)
        user.combat_power = total

        try:
            from app.models.clan import ClanMember, Clan
            clan_id = await session.scalar(
                select(ClanMember.clan_id).where(ClanMember.user_id == user.id)
            )
            if clan_id:
                # Single JOIN query — no extra loads for Clan object or member list
                total_power = await session.scalar(
                    select(func.sum(User.combat_power))
                    .join(ClanMember, ClanMember.user_id == User.id)
                    .where(ClanMember.clan_id == clan_id)
                )
                await session.execute(
                    sa_update(Clan)
                    .where(Clan.id == clan_id)
                    .values(combat_power=total_power or 0)
                )
        except Exception:
            pass

        await session.flush()
        return total

    async def get_squad_count(
        self, session: AsyncSession, user_id: int
    ) -> int:
        result = await session.scalar(
            select(func.count(SquadMember.id)).where(
                SquadMember.user_id == user_id
            )
        )
        return result or 0

    async def get_members_by_rank(
        self, session: AsyncSession, user_id: int
    ) -> dict[str, list[SquadMember]]:
        result = await session.execute(
            select(SquadMember).where(
                SquadMember.user_id == user_id
            ).order_by(SquadMember.rank, SquadMember.stars.desc())
        )
        members = result.scalars().all()
        grouped: dict[str, list] = {}
        for m in members:
            grouped.setdefault(m.rank, []).append(m)
        return grouped


squad_repo = SquadRepo()