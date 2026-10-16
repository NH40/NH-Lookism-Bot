"""Кланы — главный экран, создание, поиск, топ, заявки, участники, приглашения, выход
(хендлеры). Вход — «Кланы» в меню профиля. Ядро — как в Universe Anime Planet; карточка клана
— фото с подписью, если есть аватарка, иначе текст (тип сообщения не конвертируется: старое
удаляем и шлём новое — правило 12 UAP)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.clan import CLAN_CREATE_COST, CLAN_MAX_MEMBERS, CLAN_NAME_MAX, CLAN_NAME_MIN, CLAN_PAGE
from bot.constant.clan import (
    CB_CLAN_ACCEPT_INVITE_PREFIX,
    CB_CLAN_APPLY_PREFIX,
    CB_CLAN_CANCEL_APP_PREFIX,
    CB_CLAN_CREATE,
    CB_CLAN_DECLINE_INVITE_PREFIX,
    CB_CLAN_FIND_PREFIX,
    CB_CLAN_LEAVE,
    CB_CLAN_LEAVE_CONFIRM,
    CB_CLAN_MEMBERS,
    CB_CLAN_MY_INVITES,
    CB_CLAN_OPEN,
    CB_CLAN_TOP_PREFIX,
    CB_CLAN_VIEW_PREFIX,
    MANAGER_RANKS,
    RANK_OWNER,
)
from bot.constant.common import CB_MENU_CLANS
from bot.constant.settings import NOTIFY_CLAN
from bot.db.repositories import clan as clan_repo
from bot.keyboards.clan import back_menu, clan_menu, clan_view_menu, clans_list_menu, invites_menu, leave_confirm_menu, no_clan_menu
from bot.services import clan as clan_service
from bot.services.gang import get_gang
from bot.services.settings import notify_player
from bot.states.clan import ClanStates
from bot.texts.clan import (
    CARD_ME,
    CARD_SHARE,
    CLAN_CARD,
    CLAN_LINE,
    CLANS_EMPTY,
    CREATE_PROMPT,
    CREATED,
    ERRORS,
    FIND_HEADER,
    LEAVE_CONFIRM,
    LEFT_ALERT,
    MEMBER_LINE,
    MEMBERS_HEADER,
    MY_INVITES_EMPTY,
    MY_INVITES_HEADER,
    NAME_INVALID,
    NO_CLAN,
    NO_DESCRIPTION,
    PUSH_APPLICATION,
    RANK_EMOJI,
    RANK_NAME,
    TOP_HEADER,
    ACCEPTED_ALERT,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import esc, format_number

router = Router(name="clan")


def error_text(exc: clan_service.ClanError) -> str:
    value = format_number(exc.value) if isinstance(exc.value, int) else exc.value
    return ERRORS.get(exc.code, exc.code).format(value=value)


async def send_screen(bot: Bot, chat_id: int, old: Message | None, text: str, markup: InlineKeyboardMarkup, photo: str | None = None) -> None:
    """Экран, который бывает и текстом, и фото: удалить старое сообщение и прислать новое."""
    if old is not None:
        try:
            await old.delete()
        except TelegramAPIError:
            pass
    if photo:
        await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)


async def _card_text(session: AsyncSession, clan_id: int, viewer_rank: str | None = None, viewer_id: int | None = None) -> tuple[str, str | None]:
    v = await clan_service.view(session, clan_id)
    clan = v.clan
    built = await clan_repo.buildings(session, clan.id)
    me = ""
    if viewer_rank:
        me = CARD_ME.format(rank=f"{RANK_EMOJI[viewer_rank]} {RANK_NAME[viewer_rank]}")
        if viewer_rank in MANAGER_RANKS and viewer_id:
            share = await clan_repo.pending_share(session, viewer_id)
            if share:
                me += CARD_SHARE.format(share=format_number(share))
    text = CLAN_CARD.format(
        name=esc(clan.name), crown=" 👑" if v.top10 else "",
        description=(esc(clan.description) + "\n") if clan.description else NO_DESCRIPTION,
        members=v.members, max_members=CLAN_MAX_MEMBERS, owner=esc(v.owner_label),
        lands=clan.lands, max_lands=clan_service.max_lands(clan), used=sum(built.values()),
        treasury=format_number(clan.treasury), power=format_number(await clan_service.clan_power(session, clan.id)),
        donate_level=clan.donate_level, me=me,
    )
    return text, clan.image_file_id


async def render_clan(bot: Bot, chat_id: int, session: AsyncSession, user_id: int, old: Message | None = None) -> None:
    """Главный экран клана игрока (или экран «без клана»)."""
    member = await clan_service.member_of(session, user_id)
    if member is None:
        invites = len(await clan_repo.invites_of(session, user_id))
        await send_screen(bot, chat_id, old, NO_CLAN.format(cost=format_number(CLAN_CREATE_COST)), no_clan_menu(invites))
        return
    text, photo = await _card_text(session, member.clan_id, member.rank, user_id)
    requests = access = 0
    if member.rank in MANAGER_RANKS:
        requests = len(await clan_repo.list_requests(session, member.clan_id, False))
    if member.rank == "owner":
        access = len(await clan_repo.garrison_requests(session, member.clan_id))
    await send_screen(bot, chat_id, old, text, clan_menu(member.rank, requests, access), photo)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data.in_({CB_MENU_CLANS, CB_CLAN_OPEN}))
async def cb_clan_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    # Точка возврата «Назад» для всех ожиданий ввода домена.
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)


# --- создание ---

@router.callback_query(F.data == CB_CLAN_CREATE)
async def cb_clan_create(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await state.set_state(ClanStates.waiting_name)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, CREATE_PROMPT.format(min=CLAN_NAME_MIN, max=CLAN_NAME_MAX), back_menu())


def valid_name(name: str) -> bool:
    return CLAN_NAME_MIN <= len(name) <= CLAN_NAME_MAX and "\n" not in name


@router.message(ClanStates.waiting_name)
async def on_clan_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if not valid_name(name):
        await message.answer(NAME_INVALID.format(min=CLAN_NAME_MIN, max=CLAN_NAME_MAX), reply_markup=back_menu())
        return
    try:
        clan = await clan_service.create(session, message.from_user.id, name)
    except clan_service.ClanError as exc:
        if exc.code != "name_taken":
            await state.clear()
        await message.answer(error_text(exc), reply_markup=back_menu())
        return
    await state.clear()
    await message.answer(CREATED.format(name=esc(name), lands=clan.lands))
    await render_clan(message.bot, message.chat.id, session, message.from_user.id)


# --- поиск, топ, просмотр, заявка ---

async def _clans_page(session: AsyncSession, page: int, header: str, prefix: str, back: str):
    rows, page, pages = await clan_service.browse(session, page, CLAN_PAGE)
    lines = "".join(
        CLAN_LINE.format(place=page * CLAN_PAGE + i + 1, name=esc(c.name), lands=c.lands, members=n) for i, (c, n) in enumerate(rows)
    ) or CLANS_EMPTY
    return header.format(page=page + 1, pages=pages) + lines, clans_list_menu(rows, prefix, page, pages, back)


@router.callback_query(F.data.startswith(CB_CLAN_FIND_PREFIX))
async def cb_clan_find(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_FIND_PREFIX)
    await callback.answer()
    text, markup = await _clans_page(session, int(raw) if raw.isdigit() else 0, FIND_HEADER, CB_CLAN_FIND_PREFIX, CB_CLAN_OPEN)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


@router.callback_query(F.data.startswith(CB_CLAN_TOP_PREFIX))
async def cb_clan_top(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_TOP_PREFIX)
    await callback.answer()
    text, markup = await _clans_page(session, int(raw) if raw.isdigit() else 0, TOP_HEADER, CB_CLAN_TOP_PREFIX, CB_CLAN_OPEN)
    await send_screen(callback.bot, callback.message.chat.id, callback.message, text, markup)


async def render_view(bot: Bot, chat_id: int, old: Message | None, session: AsyncSession, clan_id: int, viewer_id: int) -> bool:
    if await clan_repo.get(session, clan_id) is None:
        return False
    text, photo = await _card_text(session, clan_id)
    can_apply = await clan_service.member_of(session, viewer_id) is None
    request = await clan_repo.get_request(session, clan_id, viewer_id) if can_apply else None
    await send_screen(bot, chat_id, old, text, clan_view_menu(clan_id, can_apply, bool(request and not request.is_invite)), photo)
    return True


@router.callback_query(F.data.startswith(CB_CLAN_VIEW_PREFIX))
async def cb_clan_view(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_VIEW_PREFIX)
    await callback.answer()
    if raw.isdigit():
        await render_view(callback.bot, callback.message.chat.id, callback.message, session, int(raw), callback.from_user.id)


@router.callback_query(F.data.startswith(CB_CLAN_APPLY_PREFIX))
async def cb_clan_apply(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_APPLY_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    clan_id, user_id = int(raw), callback.from_user.id
    try:
        await clan_service.apply(session, user_id, clan_id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await render_view(callback.bot, callback.message.chat.id, callback.message, session, clan_id, user_id)
    clan = await clan_repo.get(session, clan_id)
    name = (await clan_repo.member_labels(session, [user_id]))[user_id][0]
    for officer in (await clan_repo.officers(session, clan_id)).values():
        await notify_player(callback.bot, session, officer, NOTIFY_CLAN, PUSH_APPLICATION.format(name=esc(name), clan=esc(clan.name)))


@router.callback_query(F.data.startswith(CB_CLAN_CANCEL_APP_PREFIX))
async def cb_clan_cancel_app(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_CANCEL_APP_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    await clan_service.cancel_application(session, callback.from_user.id, int(raw))
    await callback.answer()
    await render_view(callback.bot, callback.message.chat.id, callback.message, session, int(raw), callback.from_user.id)


# --- участники ---

@router.callback_query(F.data == CB_CLAN_MEMBERS)
async def cb_clan_members(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await clan_service.member_of(session, callback.from_user.id)
    if member is None:
        await callback.answer(ERRORS["not_in_clan"], show_alert=True)
        return
    members = await clan_repo.list_members(session, member.clan_id)
    labels = await clan_repo.member_labels(session, [m.user_id for m in members])
    order = {RANK_OWNER: 0, "deputy": 1, "captain": 2, "member": 3}
    lines = "".join(
        MEMBER_LINE.format(
            emoji=RANK_EMOJI[m.rank], name=esc(labels[m.user_id][0]),
            username=f" (@{esc(labels[m.user_id][1])})" if labels[m.user_id][1] else "", rank=RANK_NAME[m.rank],
        )
        for m in sorted(members, key=lambda m: (order[m.rank], m.joined_at))
    )
    clan = await clan_repo.get(session, member.clan_id)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, MEMBERS_HEADER.format(name=esc(clan.name)) + lines, back_menu())


# --- приглашения (игрок) ---

@router.callback_query(F.data == CB_CLAN_MY_INVITES)
async def cb_clan_my_invites(callback: CallbackQuery, session: AsyncSession) -> None:
    invites = await clan_repo.invites_of(session, callback.from_user.id)
    names = await clan_repo.names(session, [i.clan_id for i in invites])
    items = [(i.clan_id, names.get(i.clan_id, "—")) for i in invites]
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, MY_INVITES_HEADER + ("" if items else MY_INVITES_EMPTY), invites_menu(items))


@router.callback_query(F.data.startswith(CB_CLAN_ACCEPT_INVITE_PREFIX))
async def cb_clan_accept_invite(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_ACCEPT_INVITE_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    try:
        await clan_service.accept_invite(session, callback.from_user.id, int(raw))
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(ACCEPTED_ALERT)
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)


@router.callback_query(F.data.startswith(CB_CLAN_DECLINE_INVITE_PREFIX))
async def cb_clan_decline_invite(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_DECLINE_INVITE_PREFIX)
    if raw.isdigit():
        await clan_service.decline_invite(session, callback.from_user.id, int(raw))
    await callback.answer()
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)


# --- выход ---

@router.callback_query(F.data == CB_CLAN_LEAVE)
async def cb_clan_leave(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await clan_service.member_of(session, callback.from_user.id)
    if member is None:
        await callback.answer(ERRORS["not_in_clan"], show_alert=True)
        return
    if member.rank == RANK_OWNER:
        await callback.answer(ERRORS["owner_must_transfer"], show_alert=True)
        return
    clan = await clan_repo.get(session, member.clan_id)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, LEAVE_CONFIRM.format(clan=esc(clan.name)), leave_confirm_menu())


@router.callback_query(F.data == CB_CLAN_LEAVE_CONFIRM)
async def cb_clan_leave_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await clan_service.leave(session, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(LEFT_ALERT, show_alert=True)
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)

