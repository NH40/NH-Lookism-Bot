"""
Утилита управления ботом.
Запускать: python manager.py [команда]
"""
import asyncio
import sys
import os
from datetime import datetime

BACKUP_DIR = "./backups"


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
  backup              Создать бэкап
  restore <file>      Восстановить из файла
  list                Список бэкапов
  migrate             Создать таблицы в БД
  stats               Статистика игроков
  autobackup          Авто-бэкап (для Docker)
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
    elif args[0] == "autobackup":
        asyncio.run(auto_backup_loop())
    else:
        print_help()