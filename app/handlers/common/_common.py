import json
from types import SimpleNamespace

from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User

_TOP_TTL = 30      # секунды
_PAGE_TTL = 30

PAGE_SIZE = 10


def _redis():
    from app.services.cooldown_service import cooldown_service
    return cooldown_service.redis


async def _get_top_cached(session: AsyncSession) -> list:
    r = _redis()
    raw = await r.get("cache:top10")
    if raw:
        return [SimpleNamespace(**d) for d in json.loads(raw)]
    result = await session.execute(
        select(User.full_name, User.combat_power, User.phase, User.ultra_instinct)
        .order_by(User.combat_power.desc())
        .limit(10)
    )
    data = [
        {"full_name": row.full_name, "combat_power": row.combat_power,
         "phase": row.phase, "ultra_instinct": row.ultra_instinct}
        for row in result.all()
    ]
    await r.setex("cache:top10", _TOP_TTL, json.dumps(data, ensure_ascii=False))
    return [SimpleNamespace(**d) for d in data]


async def _get_players_page_cached(session: AsyncSession, page: int) -> tuple[list, int]:
    r = _redis()
    count_key = "cache:players:count"
    page_key = f"cache:players:page:{page}"
    cached_count = await r.get(count_key)
    cached_page = await r.get(page_key)
    if cached_count and cached_page:
        return [SimpleNamespace(**d) for d in json.loads(cached_page)], int(cached_count)
    total = await session.scalar(select(func.count(User.id))) or 0
    result = await session.execute(
        select(User.id, User.full_name, User.combat_power, User.phase, User.ultra_instinct)
        .order_by(User.combat_power.desc())
        .offset(page * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    data = [
        {"id": row.id, "full_name": row.full_name, "combat_power": row.combat_power,
         "phase": row.phase, "ultra_instinct": row.ultra_instinct}
        for row in result.all()
    ]
    await r.setex(count_key, 60, str(total))
    await r.setex(page_key, _PAGE_TTL, json.dumps(data, ensure_ascii=False))
    return [SimpleNamespace(**d) for d in data], total


class CommonFSM(StatesGroup):
    waiting_promo = State()


def _phase_emoji(phase: str) -> str:
    return {
        "gang":    "🏴",
        "king":    "👑",
        "fist":    "✊",
        "emperor": "🏛",
    }.get(phase, "🏴")


async def _main_menu_text(session: AsyncSession, user: User) -> str:
    from app.models.skill import UserMastery
    from app.services.potion_service import potion_service
    from datetime import datetime, timezone

    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}

    mastery_lines = []
    if mastery:
        if mastery.strength > 0:
            mastery_lines.append(f"  💪 Сила {mastery.strength}/4 (+{bonus_map[mastery.strength]}% мощи)")
        if mastery.speed > 0:
            mastery_lines.append(f"  ⚡ Скорость {mastery.speed}/4 (-{speed_map[mastery.speed]}% КД)")
        if mastery.endurance > 0:
            mastery_lines.append(f"  🛡 Выносливость {mastery.endurance}/4 (+{speed_map[mastery.endurance]}% порог)")
        if mastery.technique > 0:
            mastery_lines.append(f"  🏋 Техника {mastery.technique}/4 (+{bonus_map[mastery.technique]}% трен./доход)")

    path_emoji = {"businessman": "💼", "romantic": "💝", "monster": "👹"}
    path_name  = {"businessman": "Бизнесмен", "romantic": "Романтик", "monster": "Монстр"}
    path_line = ""
    if user.skill_path:
        emoji = path_emoji.get(user.skill_path, "🛤")
        name  = path_name.get(user.skill_path, user.skill_path)
        path_line = f"  {emoji} Путь: {name}"

    potions = await potion_service.get_active(session, user.id)
    now = datetime.now(timezone.utc)
    potion_lines = []
    potion_emoji_map = {"power": "⚔️", "wealth": "💰", "influence": "⚡", "training": "🏋", "luck": "🍀"}
    potion_name_map  = {"power": "Сила", "wealth": "Богатство", "influence": "Влияние", "training": "Тренировка", "luck": "Удача"}
    for p in potions:
        remaining = max(0, int((p.expires_at - now).total_seconds()))
        m, s = divmod(remaining, 60)
        time_str = f"{m}м {s}с" if m else f"{s}с"
        emoji = potion_emoji_map.get(p.potion_type, "🧪")
        name  = potion_name_map.get(p.potion_type, p.potion_type)
        potion_lines.append(f"  {emoji} {name} +{p.bonus_value}% ({time_str})")

    ui_line = ""
    if user.ui_is_donat:
        ui_line = f"  👁 УИ Донат (макс) активен"
    elif user.ui_level > 0:
        ui_line = f"  👁 УИ {user.ui_level} уровень активен"
    elif user.ultra_instinct or user.true_ultra_instinct:
        tui = " TUI" if user.true_ultra_instinct else ""
        ui_line = f"  🤖 УИ{tui} активен"

    buff_lines = []
    if mastery_lines:
        buff_lines.append("━━━ ⚔️ Мастерство ━━━")
        buff_lines.extend(mastery_lines)
    if path_line or ui_line:
        buff_lines.append("━━━ 🛤 Развитие ━━━")
        if path_line:
            buff_lines.append(path_line)
        if ui_line:
            buff_lines.append(ui_line)
    if potion_lines:
        buff_lines.append("━━━ 🧪 Активные зелья ━━━")
        buff_lines.extend(potion_lines)

    buff_section = ("\n" + "\n".join(buff_lines)) if buff_lines else ""
    import html
    full_name = html.escape(user.full_name)
    gang_name = html.escape(user.gang_name) if user.gang_name else None

    from app.utils.formatters import fmt_num, phase_label
    return (
        f"👤 {full_name}\n"
        + (f"🏴 Банда: {gang_name}\n" if gang_name else "")
        + f"{'─' * 20}\n"
        f"{_phase_emoji(user.phase)} Фаза: {phase_label(user.phase)}\n"
        f"💰 NHCoin: {fmt_num(user.nh_coins)}\n"
        f"⚡ Влияние: {fmt_num(user.influence)}\n"
        f"💪 Боевая мощь: {fmt_num(user.combat_power)}"
        + buff_section
        + "\n\nВыбери раздел:"
    )
