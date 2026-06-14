from sqlalchemy.ext.asyncio import AsyncSession


class AdminBackupMixin:

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

    async def patch_reset_progress(self, session: AsyncSession, version: str) -> int:
        from app.services.prestige_service import prestige_service
        from app.models.clan import Clan, ClanMember
        from app.models.market import MarketListing
        from app.services.clan import clan_service
        from sqlalchemy import select, update, delete as sa_delete, update as sa_update, func
        from app.models.user import User

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

        # ── Глобальная очистка таблиц (быстрее, чем по одному в цикле) ─────────
        from app.models.building import UserBuilding
        from app.models.potion import ActivePotion
        from app.models.squad_member import SquadMember
        from app.models.character import UserCharacter
        from app.models.skill import UserPathSkills
        from app.models.king_bot import KingBot
        from app.models.city import District, FistBot
        from app.models.bank import StorageCell, Investment
        from app.models.emperor_gang import EmperorGangRecord
        await session.execute(sa_delete(UserBuilding))
        await session.execute(sa_delete(ActivePotion))
        await session.execute(sa_delete(SquadMember))
        await session.execute(sa_delete(UserCharacter))
        await session.execute(sa_delete(UserPathSkills))
        await session.execute(sa_delete(KingBot))
        await session.execute(sa_delete(EmperorGangRecord))
        await session.execute(sa_update(District).values(owner_id=None, is_captured=False))
        await session.execute(sa_update(FistBot).values(challenger_id=None))
        # Ячейки хранилища: очищаем содержимое, закрываем слоты
        await session.execute(
            sa_update(StorageCell).values(
                is_open=False,
                item_type=None,
                item_data=None,
                fee_debt=0,
                last_fee_at=None,
            )
        )
        # Вклады: удаляем чтобы планировщик не выплатил NHCoin после патча
        await session.execute(sa_delete(Investment))
        await session.flush()

        # ── Сброс прогресса ───────────────────────────────────────────────────────
        import logging as _logging
        _patch_log = _logging.getLogger(__name__)
        for user in users:
            try:
                async with session.begin_nested():
                    await prestige_service._reset_progress(session, user, keep_ui=False)
            except Exception as _e:
                _patch_log.error("patch_reset_progress: failed for user %s: %s", user.id, _e)
                session.expunge(user)

        # ── Применяем бонусные тикеты ПОСЛЕ сброса ───────────────────────────────
        for user in users:
            extra = bonus_tickets.get(user.id, 0)
            if extra > 0:
                user.tickets = min(user.tickets + extra, user.max_tickets)

        # ── Сброс казны и улучшений кланов (кроме доната) ПОСЛЕ сброса ───────────
        from app.models.clan_building import ClanRegionBuilding
        from app.models.clan_region import KoreanRegion

        # Удаляем все здания регионов
        await session.execute(sa_delete(ClanRegionBuilding))

        # Снимаем владение регионами
        await session.execute(sa_update(KoreanRegion).values(owner_clan_id=None))

        all_clans_r = await session.execute(select(Clan))
        all_clans = all_clans_r.scalars().all()
        clans_to_delete = []
        for clan in all_clans:
            member_count = await session.scalar(
                select(func.count(ClanMember.user_id)).where(ClanMember.clan_id == clan.id)
            )
            if member_count == 0:
                clans_to_delete.append(clan.id)
                continue
            clan.treasury = 0
            clan.treasury_ap = 0
            clan.bonus_max_members = 0
            clan.bonus_income_pct = 0
            clan.bonus_ticket_pct = 0
            clan.bonus_train_pct = 0
            clan.ap_income_circles = 0
            clan.ap_train_circles = 0
            clan.ap_ticket_circles = 0
            clan.max_members = 5
            await clan_service.recalc_power(session, clan)

        if clans_to_delete:
            await session.execute(sa_delete(Clan).where(Clan.id.in_(clans_to_delete)))

        # ── Сброс всех кредитов банка (патч очищает долги) ───────────────────────
        from app.services.bank.credits_service import credits_service as bank_credits
        await bank_credits.wipe_all_credits(session)

        # ── Версия ────────────────────────────────────────────────────────────────
        from app.models.game_version import GameVersion
        gv = GameVersion(version=version, patch_notes=f"Патч {version}")
        session.add(gv)
        await session.flush()

        return len(users)
