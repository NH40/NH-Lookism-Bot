from app.models.user import User
from app.utils.formatters import fmt_num


async def notify_pvp_attack(
    attacker: User, defender: User,
    win: bool, phase: str
) -> None:
    try:
        if not defender.notifications_enabled:
            return
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        phase_names = {"gang": "банды", "king": "королей", "fist": "кулаков"}
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