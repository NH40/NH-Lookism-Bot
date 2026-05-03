import json
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.clan import Clan, ClanMember, ClanInvite, ClanWar, ClanAuction
from app.constants.clan import CLAN_SHOP_MAP, CLAN_AUCTION_REWARDS, CLAN_UPGRADES_MAP

class ClanService:

    async def get_user_clan(self, session: AsyncSession, user_id: int) -> Clan | None:
        member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user_id)
        )
        if not member:
            return None
        return await session.scalar(
            select(Clan).where(Clan.id == member.clan_id)
        )

    async def get_clan_members(self, session: AsyncSession, clan_id: int) -> list:
        result = await session.execute(
            select(ClanMember).where(ClanMember.clan_id == clan_id)
        )
        return result.scalars().all()

    async def recalc_power(self, session: AsyncSession, clan: Clan) -> None:
        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        if not user_ids:
            clan.combat_power = 0
            await session.flush()
            return
        total = await session.scalar(
            select(func.sum(User.combat_power)).where(User.id.in_(user_ids))
        )
        clan.combat_power = total or 0
        await session.flush()

    async def create_clan(self, session: AsyncSession, user: User, name: str) -> dict:
        existing_member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user.id)
        )
        if existing_member:
            return {"ok": False, "reason": "Вы уже состоите в клане"}

        name = name.strip()
        if len(name) < 2 or len(name) > 32:
            return {"ok": False, "reason": "Название от 2 до 32 символов"}

        existing = await session.scalar(
            select(Clan).where(Clan.name == name)
        )
        if existing:
            return {"ok": False, "reason": "Клан с таким названием уже существует"}

        clan = Clan(name=name, owner_id=user.id, combat_power=user.combat_power)
        session.add(clan)
        await session.flush()

        member = ClanMember(clan_id=clan.id, user_id=user.id)
        session.add(member)
        await session.flush()

        return {"ok": True, "clan_id": clan.id, "name": name}

    async def invite_user(
        self, session: AsyncSession, clan: Clan, from_user: User, to_username: str
    ) -> dict:
        members = await self.get_clan_members(session, clan.id)
        if len(members) >= clan.max_members:
            return {"ok": False, "reason": f"Клан уже заполнен ({clan.max_members} чел.)"}

        to_user = await session.scalar(
            select(User).where(User.username == to_username.lstrip("@"))
        )
        if not to_user:
            return {"ok": False, "reason": "Игрок не найден"}
        if to_user.id == from_user.id:
            return {"ok": False, "reason": "Нельзя пригласить себя"}

        # Проверяем уже в клане
        existing_member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == to_user.id)
        )
        if existing_member:
            return {"ok": False, "reason": "Игрок уже в клане"}

        # Проверяем что нет активного приглашения
        existing_invite = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.clan_id == clan.id,
                ClanInvite.to_user_id == to_user.id,
                ClanInvite.is_pending == True,
            )
        )
        if existing_invite:
            return {"ok": False, "reason": "Приглашение уже отправлено"}

        invite = ClanInvite(
            clan_id=clan.id,
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            invite_type="invite",
        )
        session.add(invite)
        await session.flush()

        return {"ok": True, "invite_id": invite.id, "to_user": to_user}

    async def request_join(
        self, session: AsyncSession, clan: Clan, user: User
    ) -> dict:
        existing_member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user.id)
        )
        if existing_member:
            return {"ok": False, "reason": "Вы уже состоите в клане"}

        members = await self.get_clan_members(session, clan.id)
        if len(members) >= clan.max_members:
            return {"ok": False, "reason": "Клан уже заполнен"}

        # Проверяем что нет активного запроса или приглашения в ЛЮБОЙ клан
        existing_request = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.to_user_id == user.id,
                ClanInvite.is_pending == True,
            )
        )
        if existing_request:
            return {"ok": False, "reason": "У вас уже есть активный запрос или приглашение"}

        request = ClanInvite(
            clan_id=clan.id,
            from_user_id=user.id,
            to_user_id=user.id,
            invite_type="request",
        )
        session.add(request)
        await session.flush()

        return {"ok": True, "request_id": request.id}

    async def accept_invite(
        self, session: AsyncSession, invite_id: int, user: User
    ) -> dict:
        invite = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.id == invite_id,
                ClanInvite.is_pending == True,
            )
        )
        if not invite:
            return {"ok": False, "reason": "Приглашение не найдено или истекло"}

        # Проверяем что игрок не в клане
        existing = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user.id)
        )
        if existing:
            invite.is_pending = False
            await session.flush()
            return {"ok": False, "reason": "Вы уже состоите в клане"}

        clan = await session.scalar(
            select(Clan).where(Clan.id == invite.clan_id)
        )
        if not clan:
            return {"ok": False, "reason": "Клан не найден"}

        members = await self.get_clan_members(session, clan.id)
        if len(members) >= clan.max_members:
            invite.is_pending = False
            await session.flush()
            return {"ok": False, "reason": "Клан уже заполнен"}

        # Отменяем все другие приглашения/запросы игрока
        other_invites = await session.execute(
            select(ClanInvite).where(
                ClanInvite.to_user_id == user.id,
                ClanInvite.is_pending == True,
                ClanInvite.id != invite_id,
            )
        )
        for other in other_invites.scalars().all():
            other.is_pending = False

        invite.is_pending = False
        member = ClanMember(clan_id=clan.id, user_id=user.id)
        session.add(member)

        await self.recalc_power(session, clan)
        await self._add_clan_bonuses_to_user(session, clan, user)
        await session.flush()

        return {"ok": True, "clan": clan}

    async def decline_invite(self, session: AsyncSession, invite_id: int) -> dict:
        invite = await session.scalar(
            select(ClanInvite).where(
                ClanInvite.id == invite_id,
                ClanInvite.is_pending == True,
            )
        )
        if not invite:
            return {"ok": False, "reason": "Приглашение не найдено"}
        invite.is_pending = False
        await session.flush()
        return {"ok": True}

    async def leave_clan(
        self, session: AsyncSession, user: User, transfer_to_id: int | None = None
    ) -> dict:
        member = await session.scalar(
            select(ClanMember).where(ClanMember.user_id == user.id)
        )
        if not member:
            return {"ok": False, "reason": "Вы не в клане"}

        clan = await session.scalar(
            select(Clan).where(Clan.id == member.clan_id)
        )

        if clan.owner_id == user.id:
            members = await self.get_clan_members(session, clan.id)
            other_members = [m for m in members if m.user_id != user.id]

            if other_members and not transfer_to_id:
                return {
                    "ok": False,
                    "reason": "Вы владелец — сначала передайте права",
                    "need_transfer": True,
                    "members": other_members,
                }

            if transfer_to_id:
                clan.owner_id = transfer_to_id

            if not other_members:
                # Удаляем клан
                await session.delete(clan)
                await session.delete(member)
                await session.flush()
                return {"ok": True, "clan_deleted": True}

        await session.delete(member)
        await self._remove_clan_bonuses_from_user(session, user)
        await self.recalc_power(session, clan)
        await session.flush()
        return {"ok": True, "clan_deleted": False}

    async def kick_member(
        self, session: AsyncSession, clan: Clan, owner: User, target_user_id: int
    ) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может выгонять"}
        if target_user_id == owner.id:
            return {"ok": False, "reason": "Нельзя выгнать себя"}

        member = await session.scalar(
            select(ClanMember).where(
                ClanMember.clan_id == clan.id,
                ClanMember.user_id == target_user_id,
            )
        )
        if not member:
            return {"ok": False, "reason": "Игрок не в клане"}

        await session.delete(member)
        kicked_user = await session.scalar(select(User).where(User.id == target_user_id))
        if kicked_user:
            await self._remove_clan_bonuses_from_user(session, kicked_user)
        await self.recalc_power(session, clan)
        await session.flush()
        return {"ok": True}

    async def rename_clan(
        self, session: AsyncSession, clan: Clan, owner: User, new_name: str
    ) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может переименовать"}

        new_name = new_name.strip()
        if len(new_name) < 2 or len(new_name) > 32:
            return {"ok": False, "reason": "Название от 2 до 32 символов"}

        existing = await session.scalar(
            select(Clan).where(Clan.name == new_name)
        )
        if existing:
            return {"ok": False, "reason": "Такое название уже занято"}

        clan.name = new_name
        await session.flush()
        return {"ok": True}

    async def delete_clan(
        self, session: AsyncSession, clan: Clan, owner: User
    ) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может удалить клан"}

        members = await self.get_clan_members(session, clan.id)
        for m in members:
            await session.delete(m)

        await session.delete(clan)
        await session.flush()
        return {"ok": True}

    async def deposit_treasury(
        self, session: AsyncSession, clan: Clan, user: User, amount: int
    ) -> dict:
        if amount <= 0:
            return {"ok": False, "reason": "Сумма должна быть больше 0"}
        if user.nh_coins < amount:
            return {"ok": False, "reason": f"Недостаточно NHCoin (есть {user.nh_coins:,})"}

        user.nh_coins -= amount
        clan.treasury += amount
        await session.flush()
        return {"ok": True}

    async def buy_clan_shop(
        self, session: AsyncSession, clan: Clan, buyer: User, item_id: str
    ) -> dict:
        item = CLAN_SHOP_MAP.get(item_id)
        if not item:
            return {"ok": False, "reason": "Товар не найден"}
        if clan.treasury < item.price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {item.price:,})"}

        clan.treasury -= item.price
        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        from app.models.user import User as UserModel
        users = (await session.execute(
            select(UserModel).where(UserModel.id.in_(user_ids))
        )).scalars().all()

        if item.item_type == "tickets":
            for u in users:
                u.tickets = min(u.tickets + item.value, u.max_tickets)

        elif item.item_type == "potion":
            from app.services.potion_service import potion_service
            for u in users:
                await potion_service.activate(session, u, item.value)

        elif item.item_type == "squad":
            val = item.value
            from app.models.squad_member import SquadMember
            from app.data.squad import RANKS_BY_ID
            rank_cfg = RANKS_BY_ID.get(val["rank"])
            for u in users:
                for _ in range(val["amount"]):
                    session.add(SquadMember(
                        user_id=u.id,
                        rank=val["rank"],
                        base_power=rank_cfg.base_power if rank_cfg else 1000,
                    ))
            from app.repositories.squad_repo import squad_repo
            for u in users:
                await squad_repo.update_user_combat_power(session, u)
            await self.recalc_power(session, clan)

        elif item.item_type == "character":
            from app.data.characters import CHARACTERS
            rank_filter = item.value
            pool = [c for c in CHARACTERS if c["rank"] == rank_filter]
            if not pool:
                pool = [c for c in CHARACTERS if c["rank"] == "member"]
            from app.models.character import UserCharacter
            for u in users:
                char = random.choice(pool)
                session.add(UserCharacter(
                    user_id=u.id,
                    character_id=char["name"],
                    rank=char["rank"],
                    power=char["power"],
                ))

        elif item.item_type == "auction":
            tier = item.value
            rewards = CLAN_AUCTION_REWARDS.get(tier, CLAN_AUCTION_REWARDS["common"])
            reward = random.choice(rewards)
            ends_at = datetime.now(timezone.utc) + timedelta(minutes=30)
            auction = ClanAuction(
                clan_id=clan.id,
                reward_type=tier,
                reward_data=json.dumps(reward),
                ends_at=ends_at,
            )
            session.add(auction)

        await session.flush()
        return {"ok": True, "item": item}

    async def give_auction_reward(
        self, session: AsyncSession, auction: ClanAuction
    ) -> None:
        """Выдаём награду победителю аукциона."""
        if not auction.leader_id:
            return

        winner = await session.scalar(
            select(User).where(User.id == auction.leader_id)
        )
        if not winner:
            return

        try:
            reward = json.loads(auction.reward_data) if auction.reward_data else {}
        except Exception:
            return

        rtype = reward.get("type")

        if rtype == "coins":
            winner.nh_coins += reward.get("amount", 0)

        elif rtype == "tickets":
            winner.tickets = min(
                winner.tickets + reward.get("amount", 0), winner.max_tickets
            )

        elif rtype == "potion":
            from app.services.potion_service import potion_service
            await potion_service.activate(session, winner, reward.get("potion_id"))

        elif rtype == "squad":
            from app.models.squad_member import SquadMember
            from app.data.squad import RANKS_BY_ID
            rank = reward.get("rank", "S")
            amount = reward.get("amount", 1)
            rank_cfg = RANKS_BY_ID.get(rank)
            for _ in range(amount):
                session.add(SquadMember(
                    user_id=winner.id,
                    rank=rank,
                    base_power=rank_cfg.base_power if rank_cfg else 1000,
                ))
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, winner)

        elif rtype == "character":
            from app.data.characters import CHARACTERS
            rank_filter = reward.get("rank", "king")
            pool = [c for c in CHARACTERS if c["rank"] == rank_filter]
            if pool:
                char = random.choice(pool)
                from app.models.character import UserCharacter
                session.add(UserCharacter(
                    user_id=winner.id,
                    character_id=char["name"],
                    rank=char["rank"],
                    power=char["power"],
                ))

        auction.is_finished = True
        await session.flush()

    async def get_active_auction(
        self, session: AsyncSession, clan_id: int
    ) -> ClanAuction | None:
        return await session.scalar(
            select(ClanAuction).where(
                ClanAuction.clan_id == clan_id,
                ClanAuction.is_finished == False,
            )
        )

    async def bid_auction(
        self, session: AsyncSession, auction: ClanAuction,
        user: User, amount: int
    ) -> dict:
        now = datetime.now(timezone.utc)
        if now >= auction.ends_at:
            return {"ok": False, "reason": "Аукцион завершён"}
        if amount <= auction.current_bid:
            return {"ok": False, "reason": f"Ставка должна быть больше {auction.current_bid:,}"}
        if user.nh_coins < amount:
            return {"ok": False, "reason": "Недостаточно NHCoin"}

        # Возвращаем предыдущему лидеру
        if auction.leader_id and auction.leader_id != user.id:
            prev = await session.scalar(
                select(User).where(User.id == auction.leader_id)
            )
            if prev:
                prev.nh_coins += auction.current_bid

        user.nh_coins -= amount
        auction.current_bid = amount
        auction.leader_id = user.id
        await session.flush()
        return {"ok": True}

    async def start_war(
        self, session: AsyncSession,
        attacker_clan: Clan, defender_clan: Clan,
        war_type: str, owner: User
    ) -> dict:
        if attacker_clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может начать войну"}
        if attacker_clan.id == defender_clan.id:
            return {"ok": False, "reason": "Нельзя воевать с собой"}

        # Проверяем нет ли активной войны
        active = await session.scalar(
            select(ClanWar).where(
                ClanWar.is_finished == False,
                (ClanWar.clan1_id == attacker_clan.id) | (ClanWar.clan2_id == attacker_clan.id)
            )
        )
        if active:
            return {"ok": False, "reason": "Клан уже участвует в войне"}

        hours = 6 if war_type == "power" else 4
        now = datetime.now(timezone.utc)

        start1 = attacker_clan.combat_power if war_type == "power" else attacker_clan.treasury
        start2 = defender_clan.combat_power if war_type == "power" else defender_clan.treasury

        war = ClanWar(
            clan1_id=attacker_clan.id,
            clan2_id=defender_clan.id,
            war_type=war_type,
            clan1_start=start1,
            clan2_start=start2,
            ends_at=now + timedelta(hours=hours),
        )
        session.add(war)
        await session.flush()
        return {"ok": True, "war_id": war.id, "ends_at": war.ends_at}

    async def get_top_clans(
        self, session: AsyncSession, limit: int = 10
    ) -> list[Clan]:
        result = await session.execute(
            select(Clan).order_by(Clan.combat_power.desc()).limit(limit)
        )
        return result.scalars().all()

    async def transfer_ownership(
        self, session: AsyncSession, clan: Clan, owner: User, new_owner_id: int
    ) -> dict:
        if clan.owner_id != owner.id:
            return {"ok": False, "reason": "Только владелец может передать права"}

        member = await session.scalar(
            select(ClanMember).where(
                ClanMember.clan_id == clan.id,
                ClanMember.user_id == new_owner_id,
            )
        )
        if not member:
            return {"ok": False, "reason": "Игрок не в клане"}

        clan.owner_id = new_owner_id
        await session.flush()
        return {"ok": True}

    async def exchange_resource(
        self, session: AsyncSession,
        from_user: User, to_user: User,
        resource_type: str, amount: int, meta: dict | None = None
    ) -> dict:
        if amount <= 0:
            return {"ok": False, "reason": "Количество должно быть больше 0"}

        if resource_type == "coins":
            if from_user.nh_coins < amount:
                return {"ok": False, "reason": "Недостаточно NHCoin"}
            from_user.nh_coins -= amount
            to_user.nh_coins += amount

        elif resource_type == "tickets":
            if from_user.tickets < amount:
                return {"ok": False, "reason": f"Недостаточно тикетов (есть {from_user.tickets})"}
            from_user.tickets -= amount
            to_user.tickets = min(to_user.tickets + amount, to_user.max_tickets)

        elif resource_type == "mastery_points":
            if from_user.mastery_points < amount:
                return {"ok": False, "reason": "Недостаточно очков мастерства"}
            from_user.mastery_points -= amount
            to_user.mastery_points += amount

        elif resource_type == "ui_fragments":
            if from_user.ui_fragments < amount:
                return {"ok": False, "reason": "Недостаточно фрагментов УИ"}
            from_user.ui_fragments -= amount
            to_user.ui_fragments += amount

        elif resource_type == "path_points":
            if from_user.skill_path_points < amount:
                return {"ok": False, "reason": "Недостаточно очков пути"}
            from_user.skill_path_points -= amount
            to_user.skill_path_points += amount

        elif resource_type == "squad":
            rank = meta.get("rank") if meta else None
            from app.models.squad_member import SquadMember
            q = select(SquadMember).where(SquadMember.user_id == from_user.id)
            if rank:
                q = q.where(SquadMember.rank == rank)
            q = q.limit(amount)
            result = await session.execute(q)
            members = result.scalars().all()
            if len(members) < amount:
                return {"ok": False, "reason": f"Недостаточно статистов (есть {len(members)})"}
            for m in members:
                m.user_id = to_user.id
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, from_user)
            await squad_repo.update_user_combat_power(session, to_user)

        elif resource_type == "character":
            char_id = meta.get("char_id") if meta else None
            from app.models.character import UserCharacter
            char = await session.scalar(
                select(UserCharacter).where(
                    UserCharacter.id == char_id,
                    UserCharacter.user_id == from_user.id,
                )
            )
            if not char:
                return {"ok": False, "reason": "Персонаж не найден"}
            char.user_id = to_user.id
            from app.repositories.squad_repo import squad_repo
            await squad_repo.update_user_combat_power(session, from_user)
            await squad_repo.update_user_combat_power(session, to_user)

        await session.flush()
        return {"ok": True}

    async def buy_upgrade(
        self, session: AsyncSession, clan: Clan, user: User, upgrade_id: str
    ) -> dict:
        upgrade = CLAN_UPGRADES_MAP.get(upgrade_id)
        if not upgrade:
            return {"ok": False, "reason": "Улучшение не найдено"}
        if clan.treasury < upgrade.price:
            return {"ok": False, "reason": f"Недостаточно в казне (нужно {upgrade.price:,})"}

        # Проверяем лимиты
        if upgrade.upgrade_type == "slots":
            current = clan.bonus_max_members
            if current + upgrade.value > upgrade.max_total:
                remaining = upgrade.max_total - current
                return {"ok": False, "reason": f"Можно добавить максимум ещё {remaining} мест (лимит 25)"}
            clan.bonus_max_members += upgrade.value
            clan.max_members = 5 + clan.bonus_max_members

        elif upgrade.upgrade_type == "income":
            if clan.bonus_income_pct >= upgrade.max_total * upgrade.value:
                return {"ok": False, "reason": "Уже куплено"}
            clan.bonus_income_pct += upgrade.value

        elif upgrade.upgrade_type == "ticket":
            if clan.bonus_ticket_pct >= upgrade.max_total * upgrade.value:
                return {"ok": False, "reason": "Уже куплено"}
            clan.bonus_ticket_pct += upgrade.value

        elif upgrade.upgrade_type == "train":
            if clan.bonus_train_pct >= upgrade.max_total * upgrade.value:
                return {"ok": False, "reason": "Уже куплено"}
            clan.bonus_train_pct += upgrade.value

        clan.treasury -= upgrade.price

        # Применяем бонусы всем участникам
        await self._apply_clan_bonuses(session, clan)
        await session.flush()
        return {"ok": True, "upgrade": upgrade}

    async def _apply_clan_bonuses(self, session: AsyncSession, clan: Clan) -> None:
        """Применяет бонусы клана всем участникам."""
        members = await self.get_clan_members(session, clan.id)
        user_ids = [m.user_id for m in members]
        from app.models.user import User as UserModel
        users = (await session.execute(
            select(UserModel).where(UserModel.id.in_(user_ids))
        )).scalars().all()

        for u in users:
            u.clan_income_bonus = clan.bonus_income_pct
            u.clan_ticket_bonus = clan.bonus_ticket_pct
            u.clan_train_bonus = clan.bonus_train_pct

    async def _remove_clan_bonuses_from_user(self, session: AsyncSession, user: User) -> None:
        """Убирает клановые бонусы с игрока при выходе."""
        user.clan_income_bonus = 0
        user.clan_ticket_bonus = 0
        user.clan_train_bonus = 0

    async def _add_clan_bonuses_to_user(self, session: AsyncSession, clan: Clan, user: User) -> None:
        """Добавляет клановые бонусы игроку при вступлении."""
        user.clan_income_bonus = clan.bonus_income_pct
        user.clan_ticket_bonus = clan.bonus_ticket_pct
        user.clan_train_bonus = clan.bonus_train_pct

clan_service = ClanService()