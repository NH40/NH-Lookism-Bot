import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.formatters import fmt_num

# Слабейшие статисты гибнут первыми (реверс squad_service.py rank_order).
_STATIST_RANK_WEAKEST_FIRST = [
    "F", "E", "D", "C", "B", "A", "S", "SS", "SSS", "SR", "SSR",
    "UR", "LR", "MP", "X", "XX", "XXX", "DX", "ERROR",
]


async def apply_battle_casualties(
    session: AsyncSession, side_a: User, side_b: User
) -> dict:
    """Взаимные потери статистов и карточек в PvP-бою (патч 1.3.1: король/трон/
    император больше не уничтожает проигравшего целиком — оба участника несут
    потери). С каждой стороны гибнет min(общее_число_статистов_a, ...b) —
    как в примере НХ (10 против 15 -> 10 гибнет с каждой стороны, у 15-й
    остаётся 5). Та же пропорция (потери/общее число) применяется к
    карточкам. Победитель/трофеи (районы, города, монеты) эта функция не
    трогает — только живая сила."""
    from sqlalchemy import select, delete as sql_delete
    from app.models.squad_member import SquadMember
    from app.models.character import UserCharacter
    from app.models.card_deck import UserDeck
    from app.repositories.squad_repo import squad_repo

    async def _statist_rows(uid: int):
        rows = (await session.execute(
            select(SquadMember).where(SquadMember.user_id == uid)
        )).scalars().all()
        return rows, sum(r.count for r in rows)

    async def _kill_statists(rows: list, n: int) -> int:
        if n <= 0:
            return 0
        by_rank: dict[str, list] = {}
        for r in rows:
            by_rank.setdefault(r.rank, []).append(r)
        killed = 0
        for rank in _STATIST_RANK_WEAKEST_FIRST:
            if killed >= n:
                break
            for r in by_rank.get(rank, []):
                if killed >= n:
                    break
                take = min(r.count, n - killed)
                r.count -= take
                killed += take
                if r.count <= 0:
                    await session.delete(r)
        return killed

    async def _card_ids(uid: int) -> list[int]:
        return list((await session.execute(
            select(UserCharacter.id).where(UserCharacter.user_id == uid)
        )).scalars().all())

    async def _kill_cards(ids: list[int], n: int) -> int:
        if n <= 0 or not ids:
            return 0
        chosen = random.sample(ids, min(n, len(ids)))
        await session.execute(sql_delete(UserDeck).where(UserDeck.char_id.in_(chosen)))
        await session.execute(sql_delete(UserCharacter).where(UserCharacter.id.in_(chosen)))
        return len(chosen)

    rows_a, total_a = await _statist_rows(side_a.id)
    rows_b, total_b = await _statist_rows(side_b.id)
    statist_casualties = min(total_a, total_b)

    lost_a = await _kill_statists(rows_a, statist_casualties)
    lost_b = await _kill_statists(rows_b, statist_casualties)

    cards_a = await _card_ids(side_a.id)
    cards_b = await _card_ids(side_b.id)
    card_casualties = min(len(cards_a), len(cards_b))

    cards_lost_a = await _kill_cards(cards_a, card_casualties)
    cards_lost_b = await _kill_cards(cards_b, card_casualties)

    await session.flush()
    await squad_repo.update_user_combat_power(session, side_a)
    await squad_repo.update_user_combat_power(session, side_b)

    return {
        "statists_lost_a": lost_a, "statists_lost_b": lost_b,
        "cards_lost_a": cards_lost_a, "cards_lost_b": cards_lost_b,
    }


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