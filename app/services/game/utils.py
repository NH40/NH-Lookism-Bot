from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.formatters import fmt_num


async def notify_pvp_attack(
    attacker: User, defender: User,
    win: bool, phase: str
) -> None:
    try:
        if not defender.notifications_enabled or not getattr(defender, "notif_pvp", True):
            return
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        phase_names = {
            "gang": "банды", "king": "королей",
            "king_challenge": "за трон", "emperor_pvp": "императоров",
        }
        phase_str = phase_names.get(phase, "")
        if win:
            text = (
                f"⚔️ <b>На вас напали!</b>\n\n"
                f"<b>{attacker.full_name}</b> атаковал вас "
                f"в PvP {phase_str} и победил!\n\n"
                f"💪 Его мощь: {fmt_num(attacker.combat_power)}\n"
                f"⚔️ Ваша мощь: {fmt_num(defender.combat_power)}"
            )
        else:
            text = (
                f"🛡 <b>Атака отражена!</b>\n\n"
                f"<b>{attacker.full_name}</b> атаковал вас "
                f"в PvP {phase_str} и проиграл!\n\n"
                f"💪 Его мощь: {fmt_num(attacker.combat_power)}\n"
                f"⚔️ Ваша мощь: {fmt_num(defender.combat_power)}"
            )
        await bot.send_message(defender.tg_id, text, parse_mode="HTML")
    except Exception:
        pass


async def notify_country_city_loss(
    session: AsyncSession, country: str, defender: User,
    attacker: User, city_names: list[str],
) -> None:
    """Рассылка всем игрокам проигравшей страны — их император уступил
    города в PvP Императоров. Не шлёт самому defender — он уже получает
    личное DM через notify_pvp_attack."""
    if not city_names:
        return
    try:
        from app.bot_instance import get_bot
        from sqlalchemy import select
        bot = get_bot()
        if not bot:
            return

        cities_str = ", ".join(city_names)
        text = (
            f"🏛 <b>Ваша страна потеряла территорию!</b>\n\n"
            f"Император <b>{defender.full_name}</b> проиграл в PvP Императоров "
            f"императору <b>{attacker.full_name}</b> и уступил {len(city_names)} "
            f"{'город' if len(city_names) == 1 else 'города/городов'}: {cities_str}.\n\n"
            f"Короли и банды в этих городах теперь платят городской налог "
            f"новому владельцу."
        )
        rows = (await session.execute(
            select(User.tg_id, User.notifications_enabled).where(
                User.country == country,
                User.id != defender.id,
            )
        )).all()
        for tg_id, notif_enabled in rows:
            if not notif_enabled:
                continue
            try:
                await bot.send_message(tg_id, text, parse_mode="HTML")
            except Exception:
                pass
    except Exception:
        pass