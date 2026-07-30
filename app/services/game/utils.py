import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.formatters import fmt_num

# Слабейшие статисты гибнут первыми (реверс squad_service.py rank_order).
_STATIST_RANK_WEAKEST_FIRST = [
    "F", "E", "D", "C", "B", "A", "S", "SS", "SSS", "SR", "SSR",
    "UR", "LR", "MP", "X", "XX", "XXX", "DX", "ERROR",
]

# Слабейшие карточки гибнут первыми (реверс clan/exchange.py RANK_ORDER,
# см. app/data/characters.py CharacterRankConfig — member слабее perfection).
_CARD_RANK_WEAKEST_FIRST = [
    "member", "boss", "king", "strong_king", "gen_zero",
    "new_legend", "legend", "peak", "absolute", "perfection",
]


async def apply_battle_casualties(
    session: AsyncSession, attacker: User, defender: User, attacker_won: bool
) -> dict:
    """Потери статистов и карточек в PvP-бою (патч 1.3.1: король/трон/император
    больше не уничтожает проигравшего целиком — оба участника платят цену).

    Правила зависят от РОЛИ, не суммируются друг с другом:
      - Атакующий ВСЕГДА теряет 100% от количества защитника в каждой
        категории (статисты/карточки), не больше собственного запаса —
        независимо от исхода боя (даже проиграв, атакующий теряет ровно это,
        никакого дополнительного штрафа сверху).
      - Защитник, если он ПРОИГРАЛ, ДОПОЛНИТЕЛЬНО теряет
        PVP_LOSER_CASUALTY_PERCENT% своих собственных статистов/карточек.
        Победивший защитник по этой функции не теряет ничего.

    Победитель/трофеи (районы, города, монеты) эта функция не трогает —
    только живая сила."""
    from sqlalchemy import select, delete as sql_delete
    from app.models.squad_member import SquadMember
    from app.models.character import UserCharacter
    from app.models.card_deck import UserDeck
    from app.repositories.squad_repo import squad_repo
    from app.config.game_balance import PVP_LOSER_CASUALTY_PERCENT

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

    async def _card_rows(uid: int) -> list[tuple[int, str]]:
        return list((await session.execute(
            select(UserCharacter.id, UserCharacter.rank).where(UserCharacter.user_id == uid)
        )).all())

    async def _kill_cards(rows: list[tuple[int, str]], n: int) -> int:
        if n <= 0 or not rows:
            return 0
        by_rank: dict[str, list[int]] = {}
        for cid, rank in rows:
            by_rank.setdefault(rank, []).append(cid)
        chosen: list[int] = []
        remaining = n
        for rank in _CARD_RANK_WEAKEST_FIRST:
            if remaining <= 0:
                break
            pool = by_rank.pop(rank, [])
            if not pool:
                continue
            take = min(len(pool), remaining)
            chosen.extend(random.sample(pool, take))
            remaining -= take
        if remaining > 0 and by_rank:
            # Ранг вне списка (новый/неизвестный) — добираем что осталось.
            leftover = [cid for pool in by_rank.values() for cid in pool]
            take = min(len(leftover), remaining)
            chosen.extend(random.sample(leftover, take))
        if not chosen:
            return 0
        await session.execute(sql_delete(UserDeck).where(UserDeck.char_id.in_(chosen)))
        await session.execute(sql_delete(UserCharacter).where(UserCharacter.id.in_(chosen)))
        return len(chosen)

    def _loser_pct(total: int) -> int:
        if total <= 0:
            return 0
        return max(1, round(total * PVP_LOSER_CASUALTY_PERCENT / 100))

    atk_rows, atk_total = await _statist_rows(attacker.id)
    def_rows, def_total = await _statist_rows(defender.id)
    atk_cards = await _card_rows(attacker.id)
    def_cards = await _card_rows(defender.id)

    # Атакующий: 100% от количества защитника, не больше своего запаса —
    # всегда, независимо от исхода.
    atk_statists_lost = await _kill_statists(atk_rows, min(atk_total, def_total))
    atk_cards_lost = await _kill_cards(atk_cards, min(len(atk_cards), len(def_cards)))

    # Защитник: доп. 60% своих, только если проиграл.
    def_statists_lost = 0
    def_cards_lost = 0
    if attacker_won:
        def_statists_lost = await _kill_statists(def_rows, _loser_pct(def_total))
        def_cards_lost = await _kill_cards(def_cards, _loser_pct(len(def_cards)))

    await session.flush()
    await squad_repo.update_user_combat_power(session, attacker)
    await squad_repo.update_user_combat_power(session, defender)

    return {
        "attacker_statists_lost": atk_statists_lost, "defender_statists_lost": def_statists_lost,
        "attacker_cards_lost": atk_cards_lost, "defender_cards_lost": def_cards_lost,
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