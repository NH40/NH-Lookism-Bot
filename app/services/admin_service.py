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
        return {"total": total, "phases": phases}

    async def patch_reset_progress(self, session: AsyncSession, version: str) -> int:
        from app.services.prestige_service import prestige_service
        from app.models.clan import Clan, ClanMember
        from app.services.clan_service import clan_service

        result = await session.execute(select(User))
        users = result.scalars().all()

        # ── Топ-10 и топ-5 кланов ПЕРЕД сбросом ─────────────────────────────────
        top_players = sorted(users, key=lambda u: u.combat_power, reverse=True)[:10]
        top_rewards = {0: 10, 1: 9, 2: 8, 3: 7, 4: 6, 5: 5, 6: 4, 7: 4, 8: 3, 9: 3}

        top_clans_r = await session.execute(
            select(Clan).order_by(Clan.combat_power.desc()).limit(5)
        )
        top_clans = top_clans_r.scalars().all()
        clan_rewards = {0: 8, 1: 6, 2: 5, 3: 4, 4: 3}

        # Собираем bonus_tickets ДО сброса
        bonus_tickets: dict[int, int] = {}
        for i, u in enumerate(top_players):
            bonus_tickets[u.id] = top_rewards.get(i, 3)

        for i, clan in enumerate(top_clans):
            tickets = clan_rewards.get(i, 3)
            members_r = await session.execute(
                select(ClanMember).where(ClanMember.clan_id == clan.id)
            )
            for member in members_r.scalars().all():
                existing = bonus_tickets.get(member.user_id, 0)
                bonus_tickets[member.user_id] = max(existing, tickets)
            # Обнуляем казну
            clan.treasury = 0

        # ── Сброс прогресса ───────────────────────────────────────────────────────
        for user in users:
            await prestige_service._reset_progress(session, user, keep_ui=False)

        # ── Применяем бонусные тикеты ПОСЛЕ сброса ───────────────────────────────
        for user in users:
            extra = bonus_tickets.get(user.id, 0)
            if extra > 0:
                user.tickets = min(user.tickets + extra, user.max_tickets)

        # ── Пересчёт боевой мощи кланов ПОСЛЕ сброса ─────────────────────────────
        # После сброса у всех игроков combat_power = 0 (нет статистов)
        # Поэтому мощь клана тоже = 0, это корректно
        all_clans_r = await session.execute(select(Clan))
        all_clans = all_clans_r.scalars().all()
        for clan in all_clans:
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
            user.ticket_chance = min(95, user.ticket_chance + 1)
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