import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.clan import ClanMember
from app.services.clan import clan_service
from app.services.clan.base import RANK_LABELS

router = Router()


async def _reply(cb: CallbackQuery, text: str, markup) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")


# ── Управление рангами (только для владельца/заместителя) ──────────────────────

@router.callback_query(F.data == "clan_manage_ranks")
async def cb_manage_ranks(cb: CallbackQuery, session: AsyncSession, user: User):
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    my_member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    my_rank = my_member.rank if my_member else "member"
    is_owner = clan.owner_id == user.id

    if not is_owner and my_rank != "deputy":
        await cb.answer("Только владелец или заместитель может управлять рангами", show_alert=True)
        return

    members = await clan_service.get_clan_members(session, clan.id)
    # Deputy не может менять ранг владельца — исключаем его из списка
    other_member_ids = [
        m.user_id for m in members
        if m.user_id != user.id and (is_owner or m.user_id != clan.owner_id)
    ]
    if other_member_ids:
        users_map = {u.id: u for u in (await session.execute(
            select(User.id, User.full_name).where(User.id.in_(other_member_ids))
        )).all()}
    else:
        users_map = {}
    rank_by_uid = {m.user_id: m.rank for m in members}

    builder = InlineKeyboardBuilder()
    for uid in other_member_ids:
        u_row = users_map.get(uid)
        if not u_row:
            continue
        rank_label = RANK_LABELS.get(rank_by_uid.get(uid, "member"), rank_by_uid.get(uid, "member"))
        builder.row(InlineKeyboardButton(
            text=f"{rank_label} — {html.escape(u_row.full_name)}",
            callback_data=f"clan_rank_menu:{uid}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clans_menu"))

    await _reply(
        cb,
        f"👥 <b>Управление рангами — {html.escape(clan.name)}</b>\n\nВыберите участника для изменения ранга:",
        builder.as_markup(),
    )


@router.callback_query(F.data.startswith("clan_rank_menu:"))
async def cb_rank_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    target_id = int(cb.data.split(":")[1])
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return
    my_member = await session.scalar(
        select(ClanMember).where(ClanMember.clan_id == clan.id, ClanMember.user_id == user.id)
    )
    my_rank = my_member.rank if my_member else "member"
    if clan.owner_id != user.id and my_rank != "deputy":
        await cb.answer("Только владелец или заместитель может управлять рангами", show_alert=True)
        return

    target = await session.scalar(select(User).where(User.id == target_id))
    if not target:
        await cb.answer("Игрок не найден", show_alert=True)
        return

    member = await session.scalar(
        select(ClanMember).where(
            ClanMember.clan_id == clan.id,
            ClanMember.user_id == target_id,
        )
    )
    if not member:
        await cb.answer("Игрок не в вашем клане", show_alert=True)
        return

    current_rank = RANK_LABELS.get(member.rank, member.rank)

    rank_order = {"owner": 0, "deputy": 1, "captain": 2, "member": 3}
    current_order = rank_order.get(member.rank, 3)

    builder = InlineKeyboardBuilder()
    for rank_key, rank_name in [("deputy", "🛡 Заместитель"), ("captain", "⚔️ Капитан"), ("member", "👤 Участник")]:
        if member.rank != rank_key:
            arrow = "⬆️" if rank_order[rank_key] < current_order else "⬇️"
            builder.row(InlineKeyboardButton(
                text=f"{arrow} {rank_name}",
                callback_data=f"clan_set_rank:{target_id}:{rank_key}",
            ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="clan_manage_ranks"))

    await _reply(
        cb,
        f"👤 <b>{html.escape(target.full_name)}</b>\nТекущий ранг: {current_rank}\n\nВыберите новый ранг:",
        builder.as_markup(),
    )


@router.callback_query(F.data.startswith("clan_set_rank:"))
async def cb_set_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    target_id = int(parts[1])
    new_rank = parts[2]

    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        await cb.answer("Вы не в клане", show_alert=True)
        return

    result = await clan_service.set_member_rank(session, clan, user.id, target_id, new_rank)
    if not result["ok"]:
        await cb.answer(f"❌ {result['reason']}", show_alert=True)
        return

    await session.commit()
    rank_name = RANK_LABELS.get(new_rank, new_rank)
    await cb.answer(f"✅ Ранг изменён на {rank_name}", show_alert=True)
    await cb_manage_ranks(cb, session, user)
