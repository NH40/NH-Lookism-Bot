"""Админка — статистика (тексты)."""
from __future__ import annotations

from bot.utils.formatting import esc, format_number as n

SEP = "━━━━━━━━━━━━━━━━━━"
BTN_OVERVIEW = "👥 Игроки"
BTN_DONATE = "💎 Донат"
BTN_ECONOMY = "💰 Экономика"
BTN_SERVER = "🖥 Сервер"
BTN_BACK = "◀️ К статистике"
MENU = f"📊 <b>Статистика</b>\n{SEP}\n<i>Выбери срез:</i>"
PSUTIL_MISSING = "psutil не установлен"


def _pct(a: int, b: int) -> str:
    return f"{a / b * 100:.1f}%" if b else "—"


def overview(d: dict) -> str:
    return (
        f"👥 <b>Игроки</b>\n{SEP}\n"
        f"Всего: <b>{n(d['total'])}</b>\n"
        f"Регистраций: сегодня <b>{n(d['reg_today'])}</b> · 7 дн <b>{n(d['reg_7d'])}</b>\n"
        f"Онлайн: 24ч <b>{n(d['online_24h'])}</b> · 7 дн <b>{n(d['online_7d'])}</b>\n"
        f"Удержание D1: <b>{_pct(d['d1_kept'], d['d1_cohort'])}</b> ({d['d1_kept']}/{d['d1_cohort']})\n"
        f"Удержание D7: <b>{_pct(d['d7_kept'], d['d7_cohort'])}</b> ({d['d7_kept']}/{d['d7_cohort']})\n"
        f"Забанено: <b>{n(d['banned'])}</b>\n"
        f"Банд: <b>{n(d['gangs'])}</b>\n{SEP}\n<i>Онлайн = была активность за период.</i>"
    )


def donate(d: dict) -> str:
    donors = d["donors"]
    arppu = n(round(d["total"] / donors)) if donors else "—"
    top = "\n".join(
        f"{i}. {('@' + esc(u)) if u else uid} (<code>{uid}</code>) — <b>{n(t)} ₽</b>"
        for i, (uid, u, t) in enumerate(d["top"], 1)
    ) or "—"
    return (
        f"💎 <b>Донат</b>\n{SEP}\n"
        f"Всего: <b>{n(d['total'])} ₽</b>\n"
        f"Сегодня <b>{n(d['today'])}</b> · 7 дн <b>{n(d['d7'])}</b> · 30 дн <b>{n(d['d30'])}</b> ₽\n"
        f"Донатеров: <b>{n(donors)}</b> · ARPPU: <b>{arppu} ₽</b>\n"
        f"Чёрный рынок (покупок): <b>{n(d['unlocks'])}</b>\n"
        f"Клан-донат (покупок): <b>{n(d['clan_purchases'])}</b>\n"
        f"Донат-коинов в обороте: <b>{n(d['circulation'])}</b>\n"
        f"Премиум-пасс (сезон): <b>{n(d['bp_premium'])}</b>\n{SEP}\n"
        f"🏆 <b>Топ-10 донатеров</b>\n{top}"
    )


_RES_LABELS = [
    ("coins", "🪙 NHCoin"), ("tickets", "🎫 Тикеты"), ("dev_pts", "🌀 Очки развития"), ("path_pts", "🛤 Очки пути"),
    ("path_fr", "🧩 Фрагменты пути"), ("tech_fr", "🧩 Фрагменты техник"), ("gen_fr", "🧩 Фрагменты гениев"),
    ("blood", "🩸 Кровь"), ("donate", "💎 Донат-коины"),
]


def economy(d: dict) -> str:
    res = "\n".join(f"{label}: <b>{n(d['res'][k])}</b>" for k, label in _RES_LABELS)
    biz = ", ".join(f"{esc(t)} <b>{n(c)}</b>" for t, c in d["biz"]) or "—"
    return (
        f"💰 <b>Экономика</b>\n{SEP}\n{res}\n{SEP}\n"
        f"Статистов: <b>{n(d['extras'])}</b>\n"
        f"Бизнесы: {biz}\n"
        f"Районы: у игроков <b>{n(d['owned'])}</b> · у ботов <b>{n(d['bots'])}</b>\n"
        f"Кланов: <b>{n(d['clans'])}</b>\n"
        f"Средний уровень пасса: <b>{float(d['bp_avg']):.1f}</b>"
    )


def _mb(b: int) -> str:
    return f"{b / 1024 ** 3:.2f} ГБ" if b >= 1024 ** 3 else f"{b / 1024 ** 2:.0f} МБ"


def server(d: dict) -> str:
    s = d["srv"]
    if s.available:
        sys_part = (
            f"CPU: <b>{s.cpu:.0f}%</b>\nRAM: <b>{_mb(s.ram_used)}</b> / {_mb(s.ram_total)}\n"
            f"Диск: <b>{_mb(s.disk_used)}</b> / {_mb(s.disk_total)}\n"
        )
    else:
        sys_part = f"<i>{PSUTIL_MISSING}</i>\n"
    h, rem = divmod(d["uptime"], 3600)
    return (
        f"🖥 <b>Сервер</b>\n{SEP}\n{sys_part}"
        f"БД: <b>{_mb(d['db_size'])}</b>\nRedis: <b>{d['redis_mem'] or '—'}</b>\n"
        f"Аптайм бота: <b>{h // 24}д {h % 24}ч {rem // 60}м</b>"
    )
