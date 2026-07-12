import json
from types import SimpleNamespace

from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User

_TOP_TTL = 30      # секунды
_PAGE_TTL = 30
_SLAVA_TTL = 60
_FAME_TTL = 60

PAGE_SIZE = 10


def _redis():
    from app.services.cooldown_service import cooldown_service
    return cooldown_service.redis


async def _get_top_cached(session: AsyncSession) -> list:
    r = _redis()
    raw = await r.get("cache:top10")
    if raw:
        return [SimpleNamespace(**d) for d in json.loads(raw)]
    # shadow_stealth_active = скрытность включена (навык Тени): скрыть из топа
    result = await session.execute(
        select(User.full_name, User.combat_power, User.phase, User.ultra_instinct)
        .where(User.shadow_stealth_active.is_(False))
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


async def _get_slava_top_cached(session: AsyncSession) -> list:
    r = _redis()
    raw = await r.get("cache:slava10")
    if raw:
        return [SimpleNamespace(**d) for d in json.loads(raw)]
    from app.repositories.user_repo import user_repo
    rows = await user_repo.get_top_by_all_time_power(session, limit=10)
    data = [
        {
            "full_name": row.full_name,
            "total_power": row.total_power,
            "prestige_level": row.prestige_level,
            "phase": row.phase,
            "ultra_instinct": row.ultra_instinct,
        }
        for row in rows
    ]
    await r.setex("cache:slava10", _SLAVA_TTL, json.dumps(data, ensure_ascii=False))
    return [SimpleNamespace(**d) for d in data]


async def _get_fame_alltime_top_cached(session: AsyncSession) -> list:
    r = _redis()
    raw = await r.get("cache:fame_alltime10")
    if raw:
        return [SimpleNamespace(**d) for d in json.loads(raw)]
    from app.repositories.user_repo import user_repo
    rows = await user_repo.get_top_by_fame_alltime(session, limit=10)
    data = [
        {
            "full_name": row.full_name,
            "fame_alltime_points": row.fame_alltime_points,
            "phase": row.phase,
            "ultra_instinct": row.ultra_instinct,
        }
        for row in rows
    ]
    await r.setex("cache:fame_alltime10", _FAME_TTL, json.dumps(data, ensure_ascii=False))
    return [SimpleNamespace(**d) for d in data]


async def _get_fame_patch_top_cached(session: AsyncSession) -> list:
    r = _redis()
    raw = await r.get("cache:fame_patch10")
    if raw:
        return [SimpleNamespace(**d) for d in json.loads(raw)]
    from app.repositories.user_repo import user_repo
    rows = await user_repo.get_top_by_fame_patch(session, limit=10)
    data = [
        {
            "full_name": row.full_name,
            "fame_patch_points": row.fame_patch_points,
            "phase": row.phase,
            "ultra_instinct": row.ultra_instinct,
        }
        for row in rows
    ]
    await r.setex("cache:fame_patch10", _FAME_TTL, json.dumps(data, ensure_ascii=False))
    return [SimpleNamespace(**d) for d in data]


async def _get_players_page_cached(session: AsyncSession, page: int) -> tuple[list, int]:
    r = _redis()
    count_key = "cache:players:count"
    page_key = f"cache:players:page:{page}"
    cached_count = await r.get(count_key)
    cached_page = await r.get(page_key)
    if cached_count and cached_page:
        return [SimpleNamespace(**d) for d in json.loads(cached_page)], int(cached_count)
    # shadow_stealth_active = скрытность включена: скрыть из общего списка
    total = await session.scalar(
        select(func.count(User.id)).where(User.shadow_stealth_active.is_(False))
    ) or 0
    result = await session.execute(
        select(User.id, User.full_name, User.combat_power, User.phase, User.ultra_instinct)
        .where(User.shadow_stealth_active.is_(False))
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

    from app.utils.formatters import progress_bar as _pbar

    land_power_bonus = getattr(user, "clan_land_power_mastery_bonus", 0)
    land_speed_bonus = getattr(user, "clan_land_speed_mastery_bonus", 0)
    eff_strength = min(4, (mastery.strength if mastery else 0) + land_power_bonus)
    eff_speed = min(4, (mastery.speed if mastery else 0) + land_speed_bonus)

    mastery_lines = []
    if eff_strength > 0:
        land_str = f" 🏰+{land_power_bonus}" if land_power_bonus else ""
        mastery_lines.append(f"  💪 Сила {_pbar(eff_strength, 4)} {eff_strength}/4{land_str} (+{bonus_map[eff_strength]}% мощи)")
    if eff_speed > 0:
        land_str = f" 🏰+{land_speed_bonus}" if land_speed_bonus else ""
        mastery_lines.append(f"  ⚡ Скорость {_pbar(eff_speed, 4)} {eff_speed}/4{land_str} (-{speed_map[eff_speed]}% КД)")
    if mastery and mastery.endurance > 0:
        mastery_lines.append(f"  🛡 Выносливость {_pbar(mastery.endurance, 4)} {mastery.endurance}/4 (+{speed_map[mastery.endurance]}% порог)")
    if mastery and mastery.technique > 0:
        mastery_lines.append(f"  🏋 Техника {_pbar(mastery.technique, 4)} {mastery.technique}/4 (+{bonus_map[mastery.technique]}% трен./доход)")

    path_emoji = {"businessman": "💼", "romantic": "💝", "monster": "👹", "shadow": "🌑"}
    path_name  = {"businessman": "Бизнесмен", "romantic": "Романтик", "monster": "Монстр", "shadow": "Тень"}
    path_line = ""
    if user.skill_path:
        emoji = path_emoji.get(user.skill_path, "🛤")
        name  = path_name.get(user.skill_path, user.skill_path)
        path_line = f"  {emoji} Путь: {name}"

    potions = await potion_service.get_active(session, user.id)
    now = datetime.now(timezone.utc)
    potion_lines = []
    potion_emoji_map = {"power": "⚔️", "income": "💰", "influence": "⚡", "training": "🏋", "luck": "🍀", "raid_drop": "💠"}
    potion_name_map  = {"power": "Сила", "income": "Богатство", "influence": "Влияние", "training": "Тренировка", "luck": "Удача", "raid_drop": "Охотник"}
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

    war_points = getattr(user, "war_points", 0)
    war_genius = getattr(user, "war_genius_level", 0)
    war_line = f"  ⚔️ Очки войны: {war_points} | Гений войны: {war_genius}/5" if (war_points or war_genius) else ""

    buff_lines = []
    if mastery_lines or war_line:
        buff_lines.append("━━━ ⚔️ Мастерство ━━━")
        buff_lines.extend(mastery_lines)
        if war_line:
            buff_lines.append(war_line)
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
