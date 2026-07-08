"""
Утилита управления ботом.
Запускать: python manager.py [команда]
"""
import asyncio
import sys
import os
from datetime import datetime

BACKUP_DIR = "./backups"
# Сколько последних бэкапов хранить — auto_backup_loop копит их каждые 6ч
# бесконечно, без чистки диск через пару месяцев забивается дампами.
# ~650МБ на дамп, 5 держит ~30ч истории при ~3.2ГБ на диске.
BACKUP_KEEP = 5


def prune_backups(keep: int = BACKUP_KEEP) -> None:
    """Удаляет старые бэкапы, оставляя последние `keep` файлов."""
    if not os.path.isdir(BACKUP_DIR):
        return
    files = sorted(
        (f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_") and f.endswith(".sql")),
        reverse=True,
    )
    for f in files[keep:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
            print(f"🗑 Старый бэкап удалён: {f}")
        except OSError:
            pass


async def backup():
    """Создаёт бэкап PostgreSQL."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    from app.config import settings
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{BACKUP_DIR}/backup_{ts}.sql"
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
    if ret == 0:
        size = os.path.getsize(filename) // 1024
        print(f"✅ Бэкап создан: {filename} ({size} KB)")
        prune_backups()
    else:
        print(f"❌ Ошибка создания бэкапа (код {ret})")


async def restore(filename: str):
    """Восстанавливает из бэкапа."""
    from app.config import settings
    if not os.path.exists(filename):
        print(f"❌ Файл не найден: {filename}")
        return

    # Фильтруем проблемные строки
    clean_file = filename + ".clean.sql"
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    filtered = [
        l for l in lines
        if "transaction_timeout" not in l
    ]
    with open(clean_file, "w") as f:
        f.writelines(filtered)

    cmd = (
        f"PGPASSWORD='{settings.POSTGRES_PASSWORD}' "
        f"psql "
        f"-h {settings.POSTGRES_HOST} "
        f"-p {settings.POSTGRES_PORT} "
        f"-U {settings.POSTGRES_USER} "
        f"-d {settings.POSTGRES_DB} "
        f"-v ON_ERROR_STOP=0 "
        f"-f '{clean_file}'"
    )
    ret = os.system(cmd)
    try:
        os.remove(clean_file)
    except Exception:
        pass
    if ret == 0:
        print(f"✅ Восстановлено из: {filename}")
    else:
        print(f"⚠️ Восстановлено с предупреждениями из: {filename}")


async def list_backups():
    """Показывает список бэкапов."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = sorted([
        f for f in os.listdir(BACKUP_DIR)
        if f.endswith(".sql") and ".clean" not in f
    ], reverse=True)
    if not files:
        print("Бэкапов нет")
        return
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        size = os.path.getsize(path) // 1024
        print(f"  {f} — {size} KB")


async def migrate():
    """Создаёт таблицы в БД."""
    from app.database import init_db
    await init_db()
    print("✅ Таблицы созданы")


async def stats():
    """Выводит статистику игроков."""
    from app.database import AsyncSessionFactory
    from app.services.admin_service import admin_service
    async with AsyncSessionFactory() as session:
        async with session.begin():
            s = await admin_service.get_stats(session)
            print(f"Всего игроков: {s['total']}")
            for phase, count in s['phases'].items():
                print(f"  {phase}: {count}")


async def set_clan_leader(clan_name: str, tg_id: int):
    """Принудительно меняет лидера клана."""
    from app.database import AsyncSessionFactory
    from sqlalchemy import select
    from app.models.clan import Clan, ClanMember
    from app.models.user import User

    async with AsyncSessionFactory() as session:
        async with session.begin():
            clan = await session.scalar(select(Clan).where(Clan.name == clan_name))
            if not clan:
                print(f"❌ Клан '{clan_name}' не найден")
                return

            user = await session.scalar(select(User).where(User.tg_id == tg_id))
            if not user:
                print(f"❌ Игрок с tg_id {tg_id} не найден")
                return

            member = await session.scalar(
                select(ClanMember).where(
                    ClanMember.clan_id == clan.id,
                    ClanMember.user_id == user.id,
                )
            )
            if not member:
                print(f"❌ Игрок {tg_id} не состоит в клане '{clan_name}'")
                return

            old_owner = await session.scalar(select(User).where(User.id == clan.owner_id))
            clan.owner_id = user.id
            print(
                f"✅ Лидер клана '{clan_name}' сменён: "
                f"{old_owner.tg_id if old_owner else '?'} → {tg_id}"
            )


async def add_king_cities():
    """Добавляет 10 пустых king-городов каждого типа в каждый сектор."""
    from app.database import AsyncSessionFactory
    from app.models.city import City
    from app.data.cities import SECTORS, CITY_TYPES, CITY_NAMES_BY_SECTOR
    from sqlalchemy import select, func

    async with AsyncSessionFactory() as session:
        async with session.begin():
            total = 0
            for sector in SECTORS:
                names = CITY_NAMES_BY_SECTOR.get(sector, [])
                for city_type in CITY_TYPES:
                    existing = await session.scalar(
                        select(func.count(City.id)).where(
                            City.sector == sector,
                            City.phase == "king",
                            City.type_id == city_type.type_id,
                        )
                    )
                    offset = existing or 0
                    for i in range(10):
                        base_name = names[(offset + i) % len(names)] if names else "Город"
                        city = City(
                            sector=sector,
                            phase="king",
                            type_id=city_type.type_id,
                            name=f"{base_name} К{city_type.type_id}-{offset + i + 1}",
                            total_districts=city_type.total_districts,
                        )
                        session.add(city)
                        total += 1
            print(f"✅ Добавлено {total} king-городов")


async def spawn_boss(boss_id: str | None = None):
    """Вызывает глобального босса немедленно."""
    from app.database import AsyncSessionFactory, init_db
    from app.repositories.boss_repo import boss_repo
    from app.services.boss_service import boss_service
    from app.constants.bosses import BOSS_MAP, BOSS_ROTATION

    await init_db()

    # Проверяем boss_id
    if boss_id and boss_id not in BOSS_MAP:
        print(f"❌ Неизвестный boss_id: '{boss_id}'")
        print(f"   Доступные: {', '.join(BOSS_ROTATION)}")
        return

    async with AsyncSessionFactory() as session:
        async with session.begin():
            current = await boss_repo.get_current_boss(session)
            if current:
                cfg = BOSS_MAP.get(current.boss_id)
                print(f"❌ Уже есть активный босс: {cfg.emoji} {cfg.name} (id={current.boss_id})")
                print(f"   Сначала дождись конца или убей его.")
                return

            # Если указан конкретный boss_id — подменяем ротацию через last_boss
            if boss_id:
                # Ставим "предыдущим" босса, который идёт ДО нужного в ротации
                idx = BOSS_ROTATION.index(boss_id)
                fake_last = BOSS_ROTATION[(idx - 1) % len(BOSS_ROTATION)]

                # Временно патчим get_last_boss через прямой вызов create_boss
                from datetime import datetime, timedelta, timezone
                from app.constants.bosses import BOSS_DURATION_HOURS

                cfg = BOSS_MAP[boss_id]
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(hours=BOSS_DURATION_HOURS)

                if boss_id == "nikita":
                    state = {"despair_scale": 0.0, "nikita_base": cfg.base_hp, "heal_count": 0}
                elif boss_id == "archangel":
                    state = {"shield_hp": 0, "debuff_attacks": 0}
                elif boss_id == "manager":
                    state = {"healed": False}
                else:
                    state = {}

                boss = await boss_repo.create_boss(
                    session=session,
                    boss_id=boss_id,
                    hp=cfg.base_hp,
                    started_at=now,
                    expires_at=expires_at,
                    state=state,
                )
            else:
                boss = await boss_service.spawn_boss(session)

    cfg = BOSS_MAP[boss.boss_id]
    print(f"✅ Босс вызван: {cfg.emoji} {cfg.name} (boss_id={boss.boss_id})")
    print(f"   HP: {cfg.base_hp:,}")
    print(f"   Активен до: {boss.expires_at.strftime('%H:%M UTC')}")


async def reset_emperor(tg_id: int | None = None):
    """Сбрасывает записи группировок Императора. Без аргументов — для всех игроков."""
    from app.database import AsyncSessionFactory, init_db
    from app.models.emperor_gang import EmperorGangRecord
    from sqlalchemy import delete, select
    from app.models.user import User

    await init_db()
    async with AsyncSessionFactory() as session:
        async with session.begin():
            if tg_id is not None:
                user = await session.scalar(select(User).where(User.tg_id == tg_id))
                if not user:
                    print(f"❌ Игрок с tg_id {tg_id} не найден")
                    return
                result = await session.execute(
                    delete(EmperorGangRecord).where(EmperorGangRecord.user_id == user.id)
                )
                print(f"✅ Сброшено {result.rowcount} записей для {user.full_name} (tg_id={tg_id})")
            else:
                result = await session.execute(delete(EmperorGangRecord))
                print(f"✅ Сброшено {result.rowcount} записей группировок Императора (все игроки)")


async def auto_backup_loop():
    """Авто-бэкап каждые 6 часов."""
    print("🔄 Запущен авто-бэкап каждые 6 часов")
    while True:
        await backup()
        await asyncio.sleep(6 * 3600)


def print_help():
    print("""
Lookism Battle Planet — Manager

Команды:
  backup                        Создать бэкап
  restore <file>                Восстановить из файла
  list                          Список бэкапов
  migrate                       Создать таблицы в БД
  stats                         Статистика игроков
  set_clan_leader <clan> <tg>   Сменить лидера клана
  add_king_cities               Добавить 10 king-городов каждого типа в каждый сектор
  autobackup                    Авто-бэкап (для Docker)
  spawnboss                     Вызвать следующего босса по ротации
  spawnboss <boss_id>           Вызвать конкретного босса (nikita/archangel/manager/brothers)
  reset_emperor                 Сбросить группировки Императора для всех игроков
  reset_emperor <tg_id>         Сбросить группировки Императора для одного игрока
    """)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        asyncio.run(auto_backup_loop())
    elif args[0] == "backup":
        asyncio.run(backup())
    elif args[0] == "restore" and len(args) > 1:
        asyncio.run(restore(args[1]))
    elif args[0] == "list":
        asyncio.run(list_backups())
    elif args[0] == "migrate":
        asyncio.run(migrate())
    elif args[0] == "stats":
        asyncio.run(stats())
    elif args[0] == "set_clan_leader" and len(args) == 3:
        asyncio.run(set_clan_leader(args[1], int(args[2])))
    elif args[0] == "add_king_cities":
        asyncio.run(add_king_cities())
    elif args[0] == "autobackup":
        asyncio.run(auto_backup_loop())
    elif args[0] == "spawnboss":
        boss_id = args[1] if len(args) > 1 else None
        asyncio.run(spawn_boss(boss_id))
    elif args[0] == "reset_emperor":
        tg_id = int(args[1]) if len(args) > 1 else None
        asyncio.run(reset_emperor(tg_id))
    else:
        print_help()