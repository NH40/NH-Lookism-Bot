"""Кланы (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.clan import CLAN_BUILDINGS, CLAN_CREATE_COST, CLAN_SHOP_POTION_TIERS
from bot.constant.clan import (
    CB_CLAN_GAR_REVOKE_PREFIX,
    CB_CLAN_LEVEL_BUY,
    BUILDINGS,
    CB_CLAN_ACCEPT_INVITE_PREFIX,
    CB_CLAN_ACCEPT_PREFIX,
    CB_CLAN_APPLY_PREFIX,
    CB_CLAN_BUILD_DOWN_PREFIX,
    CB_CLAN_BUILD_PREFIX,
    CB_CLAN_BUILD_UP_PREFIX,
    CB_CLAN_BUY_LAND,
    CB_CLAN_CANCEL_APP_PREFIX,
    CB_CLAN_CREATE,
    CB_CLAN_DECLINE_INVITE_PREFIX,
    CB_CLAN_DELETE,
    CB_CLAN_DELETE_CONFIRM,
    CB_CLAN_DONATE_COINS,
    CB_CLAN_EDIT,
    CB_CLAN_EDIT_DESCRIPTION,
    CB_CLAN_EDIT_IMAGE,
    CB_CLAN_EDIT_NAME,
    CB_CLAN_EXCHANGE,
    CB_CLAN_EXCHANGE_MEMBER_PREFIX,
    CB_CLAN_EXCHANGE_RES_PREFIX,
    CB_CLAN_FIND_PREFIX,
    CB_CLAN_GAR_ACCESS,
    CB_CLAN_GAR_APPROVE_PREFIX,
    CB_CLAN_GAR_PUT,
    CB_CLAN_GAR_PUT_CARD_PREFIX,
    CB_CLAN_GAR_PUT_CARDS,
    CB_CLAN_GAR_PUT_SQUAD_PREFIX,
    CB_CLAN_GAR_REQUEST,
    CB_CLAN_GAR_TAKE,
    CB_CLAN_GAR_TAKE_CARD_PREFIX,
    CB_CLAN_GAR_TAKE_SQUAD_PREFIX,
    CB_CLAN_GARRISON,
    CB_CLAN_INVITE,
    CB_CLAN_KICK,
    CB_CLAN_KICK_PREFIX,
    CB_CLAN_LANDS,
    CB_CLAN_LEAVE,
    CB_CLAN_LEAVE_CONFIRM,
    CB_CLAN_LEVELS,
    CB_CLAN_LOG,
    CB_CLAN_STATS_PREFIX,
    CB_CLAN_MEMBERS,
    CB_CLAN_MY_INVITES,
    CB_CLAN_OPEN,
    CB_CLAN_RANK_PREFIX,
    CB_CLAN_RANKS,
    CB_CLAN_REJECT_PREFIX,
    CB_CLAN_REQUESTS,
    CB_CLAN_SHOP,
    CB_CLAN_SHOP_MERCS,
    CB_CLAN_SHOP_MERCS_PREFIX,
    CB_CLAN_SHOP_POTION_PREFIX,
    CB_CLAN_SHOP_TICKETS,
    CB_CLAN_TOP_PREFIX,
    CB_CLAN_TRANSFER,
    CB_CLAN_TRANSFER_PREFIX,
    CB_CLAN_TREASURY,
    CB_CLAN_VIEW_PREFIX,
    CB_CLAN_WAR,
    CB_CLAN_WAR_ATTACK_PREFIX,
    CB_CLAN_WAR_TARGETS_PREFIX,
    KICK_RANKS,
    MANAGER_RANKS,
    RANK_CAPTAIN,
    RANK_DEPUTY,
    RANK_MEMBER,
    RANK_OWNER,
)
from bot.constant.profile import CB_PROFILE_OPEN
from bot.constant.potion import POTION_WEALTH, POTIONS
from bot.constant.resource import RESOURCES
from bot.texts.clan import (
    BTN_GAR_ACCESS_OFF,
    BTN_GAR_ACCESS_ON,
    BTN_GAR_ACCESS_PLAIN,
    BTN_BUY_LEVEL,
    BTN_ACCEPT,
    BTN_ACCEPT_INVITE,
    BTN_APPLY,
    BTN_ATTACK,
    BTN_BUILD,
    BTN_BUILDING,
    BTN_BUY_LAND,
    BTN_CANCEL_APP,
    BTN_CONFIRM,
    BTN_CREATE,
    BTN_DECLINE_INVITE,
    BTN_DELETE,
    BTN_DEMOLISH,
    BTN_DONATE,
    BTN_EDIT,
    BTN_EDIT_DESCRIPTION,
    BTN_EDIT_IMAGE,
    BTN_EDIT_NAME,
    BTN_EXCHANGE,
    BTN_FIND,
    BTN_GAR_ACCESS,
    BTN_GAR_PUT,
    BTN_GAR_PUT_CARDS,
    BTN_GAR_PUT_STATISTS,
    BTN_GAR_REQUEST,
    BTN_GAR_TAKE,
    BTN_GARRISON,
    BTN_INVITE,
    BTN_ITEM,
    BTN_KICK,
    BTN_LANDS,
    BTN_LEAVE,
    BTN_LEVELS,
    BTN_LOG,
    BTN_STATS,
    BTN_MEMBERS,
    BTN_MERCS_RANK,
    BTN_MY_INVITES,
    BTN_NEXT,
    BTN_PREV,
    BTN_RANKS,
    BTN_REJECT,
    BTN_REQUESTS,
    BTN_SHOP,
    BTN_SHOP_MERCS,
    BTN_SHOP_POTION,
    BTN_SHOP_TICKETS,
    BTN_TARGET,
    BTN_TOP,
    BTN_TRANSFER,
    BTN_TREASURY,
    BTN_WAR,
    BTN_WAR_TARGETS,
    BUILDING_NAMES,
    RANK_NAME,
)
from bot.texts.common import BTN_BACK, BTN_BACK_TO_PROFILE
from bot.texts.potion import POTION_NAMES, ROMAN
from bot.texts.resource import resource_label
from bot.utils.formatting import format_number


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _back(data: str = CB_CLAN_OPEN) -> list[InlineKeyboardButton]:
    return [_btn(BTN_BACK, data)]


def _pages(prefix: str, page: int, pages: int) -> list[InlineKeyboardButton]:
    nav = []
    if page > 0:
        nav.append(_btn(BTN_PREV, f"{prefix}{page - 1}"))
    if page < pages - 1:
        nav.append(_btn(BTN_NEXT, f"{prefix}{page + 1}"))
    return nav


def no_clan_menu(invites: int) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_CREATE.format(cost=format_number(CLAN_CREATE_COST)), CB_CLAN_CREATE)],
        [_btn(BTN_FIND, f"{CB_CLAN_FIND_PREFIX}0"), _btn(BTN_TOP, f"{CB_CLAN_TOP_PREFIX}0")],
    ]
    if invites:
        rows.append([_btn(BTN_MY_INVITES.format(count=invites), CB_CLAN_MY_INVITES)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clan_menu(rank: str, requests: int, access_requests: int = 0) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_MEMBERS, CB_CLAN_MEMBERS), _btn(BTN_GARRISON, CB_CLAN_GARRISON)],
        [_btn(BTN_LANDS, CB_CLAN_LANDS), _btn(BTN_TREASURY, CB_CLAN_TREASURY)],
        [_btn(BTN_SHOP, CB_CLAN_SHOP), _btn(BTN_WAR, CB_CLAN_WAR)],
        [_btn(BTN_EXCHANGE, CB_CLAN_EXCHANGE), _btn(BTN_LOG, CB_CLAN_LOG)],
        [_btn(BTN_LEVELS, CB_CLAN_LEVELS), _btn(BTN_TOP, f"{CB_CLAN_TOP_PREFIX}0")],
        [_btn(BTN_STATS, f"{CB_CLAN_STATS_PREFIX}treasury")],
    ]
    if rank in MANAGER_RANKS:
        rows.append([_btn(BTN_REQUESTS.format(count=requests), CB_CLAN_REQUESTS), _btn(BTN_INVITE, CB_CLAN_INVITE)])
    if rank == RANK_OWNER:
        label = BTN_GAR_ACCESS.format(count=access_requests) if access_requests else BTN_GAR_ACCESS_PLAIN
        rows.append([_btn(label, CB_CLAN_GAR_ACCESS)])
    if rank in MANAGER_RANKS:
        rows.append([_btn(BTN_EDIT, CB_CLAN_EDIT)])
    manage = []
    if rank == RANK_OWNER:
        manage.append(_btn(BTN_RANKS, CB_CLAN_RANKS))
    if rank in KICK_RANKS:
        manage.append(_btn(BTN_KICK, CB_CLAN_KICK))
    if manage:
        rows.append(manage)
    rows.append([_btn(BTN_LEAVE, CB_CLAN_LEAVE)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clans_list_menu(rows_data: list, prefix: str, page: int, pages: int, back: str) -> InlineKeyboardMarkup:
    rows = [[_btn(clan.name, f"{CB_CLAN_VIEW_PREFIX}{clan.id}")] for clan, _ in rows_data]
    nav = _pages(prefix, page, pages)
    if nav:
        rows.append(nav)
    rows.append(_back(back))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clan_view_menu(clan_id: int, can_apply: bool, applied: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_apply:
        rows.append([_btn(BTN_CANCEL_APP, f"{CB_CLAN_CANCEL_APP_PREFIX}{clan_id}") if applied else _btn(BTN_APPLY, f"{CB_CLAN_APPLY_PREFIX}{clan_id}")])
    rows.append(_back(f"{CB_CLAN_FIND_PREFIX}0"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def levels_menu(next_level: int | None, price: int | None) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_BUY_LEVEL.format(n=next_level, price=price), CB_CLAN_LEVEL_BUY)]] if next_level else []
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_menu(data: str = CB_CLAN_OPEN) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_back(data)])


def requests_menu(requests: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_ACCEPT.format(name=name), f"{CB_CLAN_ACCEPT_PREFIX}{uid}"), _btn(BTN_REJECT.format(name=name), f"{CB_CLAN_REJECT_PREFIX}{uid}")]
        for uid, name in requests
    ]
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def invites_menu(invites: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_ACCEPT_INVITE.format(name=name), f"{CB_CLAN_ACCEPT_INVITE_PREFIX}{cid}"), _btn(BTN_DECLINE_INVITE.format(name=name), f"{CB_CLAN_DECLINE_INVITE_PREFIX}{cid}")]
        for cid, name in invites
    ]
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def members_pick_menu(members: list[tuple[int, str]], prefix: str, back: str = CB_CLAN_OPEN, extra: list | None = None) -> InlineKeyboardMarkup:
    rows = [[_btn(name, f"{prefix}{uid}")] for uid, name in members]
    rows.extend(extra or [])
    rows.append(_back(back))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ranks_menu(members: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    return members_pick_menu(members, CB_CLAN_RANK_PREFIX, extra=[[_btn(BTN_TRANSFER, CB_CLAN_TRANSFER)], [_btn(BTN_DELETE, CB_CLAN_DELETE)]])


def rank_set_menu(user_id: int) -> InlineKeyboardMarkup:
    rows = [[_btn(RANK_NAME[r], f"{CB_CLAN_RANK_PREFIX}{user_id}:{r}")] for r in (RANK_DEPUTY, RANK_CAPTAIN, RANK_MEMBER)]
    rows.append(_back(CB_CLAN_RANKS))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_menu(confirm_data: str, back: str = CB_CLAN_OPEN) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_CONFIRM, confirm_data)], _back(back)])


def transfer_confirm_menu(user_id: int) -> InlineKeyboardMarkup:
    return confirm_menu(f"{CB_CLAN_TRANSFER_PREFIX}{user_id}:ok", CB_CLAN_TRANSFER)


def delete_confirm_menu() -> InlineKeyboardMarkup:
    return confirm_menu(CB_CLAN_DELETE_CONFIRM, CB_CLAN_RANKS)


def kick_confirm_menu(user_id: int) -> InlineKeyboardMarkup:
    return confirm_menu(f"{CB_CLAN_KICK_PREFIX}{user_id}:ok", CB_CLAN_KICK)


def leave_confirm_menu() -> InlineKeyboardMarkup:
    return confirm_menu(CB_CLAN_LEAVE_CONFIRM)


def edit_menu(can_image: bool) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_EDIT_NAME, CB_CLAN_EDIT_NAME), _btn(BTN_EDIT_DESCRIPTION, CB_CLAN_EDIT_DESCRIPTION)]]
    if can_image:
        rows.append([_btn(BTN_EDIT_IMAGE, CB_CLAN_EDIT_IMAGE)])
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lands_menu(built: dict[str, int], land_price: int | None, manager: bool) -> InlineKeyboardMarkup:
    rows = []
    if manager and land_price is not None:
        rows.append([_btn(BTN_BUY_LAND.format(price=format_number(land_price)), CB_CLAN_BUY_LAND)])
    buttons = [_btn(BTN_BUILDING.format(name=BUILDING_NAMES[k], count=built.get(k, 0), max=CLAN_BUILDINGS[k][0]), f"{CB_CLAN_BUILD_PREFIX}{k}") for k in BUILDINGS]
    rows.extend(buttons[i:i + 2] for i in range(0, len(buttons), 2))
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def building_menu(kind: str, price: int | None, refund: int | None, manager: bool) -> InlineKeyboardMarkup:
    rows = []
    if manager and price is not None:
        rows.append([_btn(BTN_BUILD.format(price=format_number(price)), f"{CB_CLAN_BUILD_UP_PREFIX}{kind}")])
    if manager and refund is not None:
        rows.append([_btn(BTN_DEMOLISH.format(refund=format_number(refund)), f"{CB_CLAN_BUILD_DOWN_PREFIX}{kind}")])
    rows.append(_back(CB_CLAN_LANDS))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def treasury_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_DONATE, CB_CLAN_DONATE_COINS)], _back()])


def shop_menu(members: int, tickets_price, potion_price, bought_today: int = 0) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_SHOP_TICKETS.format(price=format_number(tickets_price(1, members, bought_today))), CB_CLAN_SHOP_TICKETS)]]
    for kind in POTIONS:
        if kind == POTION_WEALTH:
            continue
        row = [
            _btn(BTN_SHOP_POTION.format(name=POTION_NAMES[kind].split(" ", 1)[0], roman=ROMAN[tier], price=format_number(potion_price(tier, members))),
                 f"{CB_CLAN_SHOP_POTION_PREFIX}{kind}:{tier}")
            for tier in CLAN_SHOP_POTION_TIERS
        ]
        rows.append(row)
    rows.append([_btn(BTN_SHOP_MERCS, CB_CLAN_SHOP_MERCS)])
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mercs_menu(ranks: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    buttons = [_btn(BTN_MERCS_RANK.format(rank=r, price=format_number(p)), f"{CB_CLAN_SHOP_MERCS_PREFIX}{r}") for r, p in ranks]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append(_back(CB_CLAN_SHOP))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def garrison_menu(can_request: bool = False) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_GAR_PUT, CB_CLAN_GAR_PUT), _btn(BTN_GAR_TAKE, CB_CLAN_GAR_TAKE)]]
    if can_request:
        rows.append([_btn(BTN_GAR_REQUEST, CB_CLAN_GAR_REQUEST)])
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def access_menu(members: list[tuple[int, str, bool, bool]]) -> InlineKeyboardMarkup:
    """(user_id, имя, есть право, просит доступ) — кнопка на участника: выдать / отнять."""
    rows = []
    for uid, name, allowed, requested in members:
        if allowed:
            rows.append([_btn(BTN_GAR_ACCESS_ON.format(name=name), f"{CB_CLAN_GAR_REVOKE_PREFIX}{uid}")])
        else:
            rows.append([_btn(BTN_GAR_ACCESS_OFF.format(name=name, bell="🔔 " if requested else ""), f"{CB_CLAN_GAR_APPROVE_PREFIX}{uid}")])
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def garrison_put_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn(BTN_GAR_PUT_STATISTS, f"{CB_CLAN_GAR_PUT_SQUAD_PREFIX}"), _btn(BTN_GAR_PUT_CARDS, CB_CLAN_GAR_PUT_CARDS)],
        _back(CB_CLAN_GARRISON),
    ])


def items_menu(items: list[tuple[str, str, int]], prefix: str, back: str = CB_CLAN_GARRISON) -> InlineKeyboardMarkup:
    """(код для callback, подпись, количество)."""
    rows = [[_btn(BTN_ITEM.format(name=name, quantity=format_number(q)), f"{prefix}{code}")] for code, name, q in items]
    rows.append(_back(back))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def take_menu(statists: list[tuple[str, str, int]], cards: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_ITEM.format(name=n, quantity=format_number(q)), f"{CB_CLAN_GAR_TAKE_SQUAD_PREFIX}{c}")] for c, n, q in statists]
    rows += [[_btn(BTN_ITEM.format(name=n, quantity=format_number(q)), f"{CB_CLAN_GAR_TAKE_CARD_PREFIX}{c}")] for c, n, q in cards]
    rows.append(_back(CB_CLAN_GARRISON))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def war_menu(can_attack: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_attack:
        rows.append([_btn(BTN_WAR_TARGETS, f"{CB_CLAN_WAR_TARGETS_PREFIX}0")])
    rows.append(_back())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def war_targets_menu(targets: list, page: int, pages: int) -> InlineKeyboardMarkup:
    rows = [
        [_btn(BTN_TARGET.format(shield="🛡 " if t.shielded else "", name=t.name, lands=t.lands, members=t.members), f"{CB_CLAN_WAR_ATTACK_PREFIX}{t.clan_id}")]
        for t in targets
    ]
    nav = _pages(CB_CLAN_WAR_TARGETS_PREFIX, page, pages)
    if nav:
        rows.append(nav)
    rows.append(_back(CB_CLAN_WAR))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def war_confirm_menu(clan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_ATTACK, f"{CB_CLAN_WAR_ATTACK_PREFIX}{clan_id}:ok")], _back(f"{CB_CLAN_WAR_TARGETS_PREFIX}0")])


def exchange_res_menu(user_id: int) -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_CLAN_EXCHANGE_RES_PREFIX}{user_id}:{code}") for code in RESOURCES]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append(_back(CB_CLAN_EXCHANGE))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def exchange_members_menu(members: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    return members_pick_menu(members, CB_CLAN_EXCHANGE_MEMBER_PREFIX)


def stats_menu(current: str) -> InlineKeyboardMarkup:
    from bot.constant.clan import STATS_SORTS
    from bot.texts.clan import STATS_SORT_LABELS

    buttons = [_btn(("• " if s == current else "") + STATS_SORT_LABELS[s], f"{CB_CLAN_STATS_PREFIX}{s}") for s in STATS_SORTS]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:3], buttons[3:], _back()])
