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
        user.true_ultra_instinct = True
        await session.flush()

    async def remove_tui(self, session: AsyncSession, user: User) -> None:
        user.true_ultra_instinct = False
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
        result = await session.execute(select(User))
        users = result.scalars().all()
        for user in users:
            await prestige_service._reset_progress(session, user)
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
        """Добавляет пробуждения игроку и применяет бонусы."""
        from app.services.prestige_service import prestige_service
        for _ in range(amount):
            user.prestige_level += 1
            await prestige_service._reapply_achievement_bonuses(session, user)
        await session.flush()

    async def remove_prestige(self, session: AsyncSession, user: User, amount: int = 1) -> None:
        """Убирает пробуждения игроку."""
        user.prestige_level = max(0, user.prestige_level - amount)
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