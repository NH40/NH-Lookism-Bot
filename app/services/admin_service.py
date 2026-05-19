from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.services.title_service import title_service


class AdminService:

    async def find_user(self, session: AsyncSession, query: str) -> User | None:
        if query.lstrip("-").isdigit():
            r = await session.execute(select(User).where(User.tg_id == int(query)))
            u = r.scalar_one_or_none()
            if u:
                return u
        uname = query.lstrip("@")
        r = await session.execute(select(User).where(User.username == uname))
        u = r.scalar_one_or_none()
        if u:
            return u
        r = await session.execute(select(User).where(User.gang_name.ilike(f"%{query}%")))
        return r.scalar_one_or_none()

    async def give_coins(self, session: AsyncSession, user: User, amount: int) -> None:
        user.nh_coins += amount
        await session.flush()

    async def give_tickets(self, session: AsyncSession, user: User, count: int) -> None:
        user.tickets += count
        await session.flush()

    async def give_tui(self, session: AsyncSession, user: User) -> None:
        user.ultra_instinct = True
        user.true_ultra_instinct = True
        user.max_tickets = 999999
        await session.flush()

    async def remove_tui(self, session: AsyncSession, user: User) -> None:
        user.true_ultra_instinct = False
        user.max_tickets = 3
        await session.flush()

    async def give_all_titles(self, session: AsyncSession, user: User, admin_tg_id: int) -> int:
        return await title_service.grant_all_titles(session, user, admin_tg_id)

    async def remove_all_titles(self, session: AsyncSession, user: User) -> None:
        await title_service.revoke_all_titles(session, user)

    async def get_stats(self, session: AsyncSession) -> dict:
        total = await session.scalar(select(func.count(User.id)))
        phases = {}
        for phase in ["gang", "king", "fist", "emperor"]:
            count = await session.scalar(
                select(func.count(User.id)).where(User.phase == phase)
            )
            phases[phase] = count
        with_power = await session.scalar(
            select(func.count(User.id)).where(User.combat_power > 0)
        )
        return {"total": total, "phases": phases, "with_power": with_power}

    async def patch_reset_progress(self, session: AsyncSession, version: str) -> int:
        from app.services.prestige_service import prestige_service
        from app.models.clan import Clan, ClanMember
        from app.models.market import MarketListing
        from app.services.clan import clan_service
        from sqlalchemy import update

        result = await session.execute(select(User))
        users = result.scalars().all()

        # ── Топ-10 и топ-5 кланов ПЕРЕД сбросом ─────────────────────────────────
        top_players = sorted(users, key=lambda u: u.combat_power, reverse=True)[:10]
        top_rewards = {0: 20, 1: 18, 2: 16, 3: 14, 4: 12, 5: 10, 6: 8, 7: 8, 8: 6, 9: 6}

        top_clans_r = await session.execute(
            select(Clan).order_by(Clan.combat_power.desc()).limit(5)
        )
        top_clans = top_clans_r.scalars().all()
        clan_rewards = {0: 16, 1: 12, 2: 10, 3: 8, 4: 6}

        # Собираем bonus_tickets ДО сброса
        bonus_tickets: dict[int, int] = {}
        for i, u in enumerate(top_players):
            bonus_tickets[u.id] = top_rewards.get(i, 6)

        for i, clan in enumerate(top_clans):
            tickets = clan_rewards.get(i, 6)
            members_r = await session.execute(
                select(ClanMember).where(ClanMember.clan_id == clan.id)
            )
            for member in members_r.scalars().all():
                existing = bonus_tickets.get(member.user_id, 0)
                bonus_tickets[member.user_id] = max(existing, tickets)

        # ── Сброс биржи ───────────────────────────────────────────────────────────
        await session.execute(
            update(MarketListing)
            .where(
                MarketListing.is_sold == False,
                MarketListing.is_cancelled == False,
            )
            .values(is_cancelled=True)
        )

        # ── Предварительная очистка зданий глобально (гарантирует 0 зданий после вайпа) ──
        from app.models.building import UserBuilding
        from sqlalchemy import delete as sa_delete
        await session.execute(sa_delete(UserBuilding))
        await session.flush()

        # ── Сброс прогресса ───────────────────────────────────────────────────────
        for user in users:
            await prestige_service._reset_progress(session, user, keep_ui=False)

        # ── Применяем бонусные тикеты ПОСЛЕ сброса ───────────────────────────────
        for user in users:
            extra = bonus_tickets.get(user.id, 0)
            if extra > 0:
                user.tickets = min(user.tickets + extra, user.max_tickets)

        # ── Сброс казны и улучшений кланов (кроме доната) ПОСЛЕ сброса ───────────
        all_clans_r = await session.execute(select(Clan))
        all_clans = all_clans_r.scalars().all()
        for clan in all_clans:
            clan.treasury = 0
            clan.bonus_max_members = 0
            clan.bonus_income_pct = 0
            clan.bonus_ticket_pct = 0
            clan.bonus_train_pct = 0
            clan.max_members = 5
            await clan_service.recalc_power(session, clan)

        # ── Версия ────────────────────────────────────────────────────────────────
        from app.models.game_version import GameVersion
        gv = GameVersion(version=version, patch_notes=f"Патч {version}")
        session.add(gv)
        await session.flush()

        return len(users)

    async def create_backup(self) -> dict:
        import os
        from datetime import datetime
        from app.config import settings

        os.makedirs("/app/backups", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/app/backups/backup_{ts}.sql"

        # Используем --no-privileges --no-owner для совместимости
        cmd = (
            f"PGPASSWORD='{settings.POSTGRES_PASSWORD}' "
            f"pg_dump "
            f"-h {settings.POSTGRES_HOST} "
            f"-p {settings.POSTGRES_PORT} "
            f"-U {settings.POSTGRES_USER} "
            f"--no-privileges "
            f"--no-owner "
            f"--clean "
            f"--if-exists "
            f"-F p "
            f"-f '{filename}' "
            f"{settings.POSTGRES_DB}"
        )
        ret = os.system(cmd)
        if ret == 0 and os.path.exists(filename):
            size = os.path.getsize(filename) // 1024
            return {"ok": True, "filename": filename, "size_kb": size}
        return {"ok": False, "filename": filename}

    async def list_backups(self) -> list[dict]:
        import os
        backup_dir = "/app/backups"
        os.makedirs(backup_dir, exist_ok=True)
        files = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".sql") and ".clean" not in f:
                path = os.path.join(backup_dir, f)
                try:
                    size = os.path.getsize(path) // 1024
                except Exception:
                    size = 0
                files.append({"name": f, "path": path, "size_kb": size})
        return files

    async def give_mastery_points(self, session: AsyncSession, user: User, amount: int) -> None:
        user.mastery_points += amount
        await session.flush()

    async def give_path_points(self, session: AsyncSession, user: User, amount: int) -> None:
        user.skill_path_points += amount
        await session.flush()

    async def give_ui_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.ui_fragments += amount
        await session.flush()

    async def give_alchemy_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.alchemy_fragments = getattr(user, "alchemy_fragments", 0) + amount
        await session.flush()

    async def give_path_fragments(self, session: AsyncSession, user: User, amount: int) -> None:
        user.path_fragments = getattr(user, "path_fragments", 0) + amount
        await session.flush()

    async def delete_user(self, session: AsyncSession, user: User) -> None:
        from app.services.prestige_service import prestige_service
        from app.models.title import UserAchievement, UserDonatTitle
        from app.models.skill import UserMastery
        from app.models.clan import ClanMember
        from sqlalchemy import delete as sa_delete

        await prestige_service._reset_progress(session, user, keep_ui=False)

        await session.execute(sa_delete(UserAchievement).where(UserAchievement.user_id == user.id))
        await session.execute(sa_delete(UserDonatTitle).where(UserDonatTitle.user_id == user.id))
        await session.execute(sa_delete(UserMastery).where(UserMastery.user_id == user.id))
        await session.execute(sa_delete(ClanMember).where(ClanMember.user_id == user.id))
        await session.delete(user)
        await session.flush()

    async def give_prestige(self, session: AsyncSession, user: User, amount: int = 1) -> None:
        """Добавляет пробуждения игроку с бонусами как при обычном пробуждении."""
        from app.models.game_version import GameVersion
        for _ in range(amount):
            if user.prestige_level >= 10:
                break
            user.prestige_level += 1
            user.prestige_income_bonus += 5
            user.prestige_recruit_bonus += 5
            user.prestige_train_bonus += 5
            user.prestige_ticket_bonus += 1
            user.ticket_chance = min(getattr(user, "max_ticket_chance", 70), user.ticket_chance + 1)
        await session.flush()

    async def remove_prestige(self, session: AsyncSession, user: User, amount: int = 1) -> None:
        """Убирает пробуждения с откатом бонусов."""
        for _ in range(amount):
            if user.prestige_level <= 0:
                break
            user.prestige_level -= 1
            user.prestige_income_bonus = max(0, user.prestige_income_bonus - 5)
            user.prestige_recruit_bonus = max(0, user.prestige_recruit_bonus - 5)
            user.prestige_train_bonus = max(0, user.prestige_train_bonus - 5)
            user.prestige_ticket_bonus = max(0, user.prestige_ticket_bonus - 1)
            user.ticket_chance = max(25, user.ticket_chance - 1)
        await session.flush()
    
    async def give_character(self, session: AsyncSession, user: User, char_name: str) -> dict:
        from app.data.characters import CHARACTERS, RANK_CONFIG_MAP
        from app.models.character import UserCharacter

        char_data = next((c for c in CHARACTERS if c["name"] == char_name), None)
        if not char_data:
            return {"ok": False, "reason": "Персонаж не найден"}

        char = UserCharacter(
            user_id=user.id,
            character_id=char_data["name"],
            rank=char_data["rank"],
            power=char_data["power"],
        )
        session.add(char)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "character": char_data}

    async def give_absolute_character(self, session: AsyncSession, user: User, char_name: str) -> dict:
        from app.data.characters import CHARACTERS
        from app.models.character import UserCharacter

        char_data = next((c for c in CHARACTERS if c["name"] == char_name and c["rank"] == "absolute"), None)
        if not char_data:
            return {"ok": False, "reason": "Абсолютный персонаж не найден"}

        char = UserCharacter(
            user_id=user.id,
            character_id=char_data["name"],
            rank=char_data["rank"],
            power=char_data["power"],
        )
        session.add(char)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        return {"ok": True, "character": char_data}

    async def take_absolute_characters(self, session: AsyncSession, user: User) -> dict:
        from app.models.character import UserCharacter
        from sqlalchemy import delete as sa_delete

        result = await session.execute(
            sa_delete(UserCharacter).where(
                UserCharacter.user_id == user.id,
                UserCharacter.rank == "absolute",
            )
        )
        count = result.rowcount
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        return {"ok": True, "removed": count}

    async def give_king_city(self, session: AsyncSession, user: User) -> dict:
        import random
        from app.models.city import City, District
        from app.repositories.city_repo import city_repo
        from sqlalchemy import select, func

        sector = user.sector or "Н"

        result = await session.execute(
            select(City).where(
                City.sector == sector,
                City.phase.in_(["gang", "king"]),
                City.total_districts == 16,
            ).order_by(City.id)
        )
        all_cities = result.scalars().all()

        target_city = None
        for city in all_cities:
            my_count = await session.scalar(
                select(func.count(District.id)).where(
                    District.owner_id == user.id,
                    District.city_id == city.id,
                    District.is_captured == True,
                )
            ) or 0
            if my_count == 0:
                target_city = city
                break

        if not target_city:
            from app.data.cities import CITY_NAMES_BY_SECTOR
            names = CITY_NAMES_BY_SECTOR.get(sector, [])
            used_names = {c.name for c in all_cities}
            available = [n for n in names if n not in used_names]
            name = random.choice(available) if available else f"Адм-{sector}-{len(all_cities)+1}"
            target_city = City(
                sector=sector, phase="king", type_id=3, name=name,
                total_districts=16, captured_districts=0,
                is_fully_captured=False, district_power_multiplier=1.0,
            )
            session.add(target_city)
            await session.flush()

        await city_repo.init_city_districts(session, target_city)
        await session.flush()

        districts_r = await session.execute(
            select(District).where(District.city_id == target_city.id)
        )
        districts = districts_r.scalars().all()
        for d in districts:
            d.owner_id = user.id
            d.is_captured = True

        target_city.captured_districts = len(districts)
        target_city.owner_id = user.id
        target_city.is_fully_captured = True

        cities_r = await session.execute(
            select(District.city_id)
            .join(City, City.id == District.city_id)
            .where(
                District.owner_id == user.id,
                District.is_captured == True,
                City.phase != "fist",
            ).distinct()
        )
        user.king_cities_count = len(cities_r.scalars().all())
        await session.flush()
        return {"ok": True, "cities_count": user.king_cities_count, "city_name": target_city.name}

    async def take_all_cities(self, session: AsyncSession, user: User) -> dict:
        from app.models.city import City, District
        from sqlalchemy import update as sa_update

        districts_result = await session.execute(
            sa_update(District)
            .where(District.owner_id == user.id)
            .values(owner_id=None, is_captured=False)
        )
        await session.execute(
            sa_update(City)
            .where(City.owner_id == user.id)
            .values(owner_id=None, is_fully_captured=False, captured_districts=0)
        )
        user.king_cities_count = 0
        user.fist_cities_count = 0
        await session.flush()

        from app.services.business_service import business_service
        await business_service._recalc_income(session, user)
        return {"ok": True, "removed": districts_result.rowcount}

    async def give_squad_member(self, session: AsyncSession, user: User, rank: str, count: int = 1) -> dict:
        from app.data.squad import RANKS_BY_ID
        from app.models.squad_member import SquadMember

        rank_cfg = RANKS_BY_ID.get(rank)
        if not rank_cfg:
            return {"ok": False, "reason": "Ранг не найден"}

        for _ in range(count):
            member = SquadMember(
                user_id=user.id,
                rank=rank,
                stars=0,
                base_power=rank_cfg.base_power,
            )
            session.add(member)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "rank": rank, "count": count}

    async def restore_backup(self, filename: str) -> dict:
        import os
        from app.config import settings

        if not os.path.exists(filename):
            return {"ok": False, "reason": "Файл не найден"}

        # Фильтруем проблемные строки
        clean_file = filename + ".clean.sql"
        try:
            with open(filename, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            filtered = [
                l for l in lines
                if "transaction_timeout" not in l
                and "idle_in_transaction_session_timeout" not in l
            ]
            with open(clean_file, "w", encoding="utf-8") as f:
                f.writelines(filtered)
        except Exception as e:
            return {"ok": False, "reason": f"Ошибка фильтрации: {e}"}

        cmd = (
            f"PGPASSWORD='{settings.POSTGRES_PASSWORD}' "
            f"psql "
            f"-h {settings.POSTGRES_HOST} "
            f"-p {settings.POSTGRES_PORT} "
            f"-U {settings.POSTGRES_USER} "
            f"-d {settings.POSTGRES_DB} "
            f"-v ON_ERROR_STOP=0 "
            f"-q "
            f"-f '{clean_file}' "
            f"2>/dev/null"
        )
        os.system(cmd)

        try:
            os.remove(clean_file)
        except Exception:
            pass

        return {"ok": True}


admin_service = AdminService()