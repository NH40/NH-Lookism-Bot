"""Казино — слоты и блэкджек (хендлеры). Вход — «🎰 Казино» в магазине; покер — свой домен."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.casino import (
    CASINO_STAKE_RESOURCES,
    CB_BJ_DOUBLE,
    CB_BJ_HIT,
    CB_BJ_STAND,
    CB_CASINO_GAME_PREFIX,
    CB_CASINO_OPEN,
    CB_CASINO_SQUAD_PREFIX,
    CB_CASINO_STAKE_PREFIX,
    CB_CASINO_STATISTS_PREFIX,
    CB_SLOTS_AGAIN_PREFIX,
    GAME_BLACKJACK,
    GAME_SLOTS,
    STAKE_RESOURCE,
    STAKE_STATIST,
)
from bot.keyboards.casino import (
    back_to_game,
    blackjack_done_menu,
    blackjack_menu,
    casino_menu,
    slots_result_menu,
    squads_menu,
    stake_menu,
)
from bot.services.casino import (
    OUTCOME_PAIR,
    OUTCOME_TRIPLE,
    BlackjackState,
    CasinoBusyError,
    HandInProgressError,
    HandNotFoundError,
    InvalidStakeError,
    NotEnoughError,
    SlotsResult,
    Stake,
    X3StrategyError,
    blackjack_deal,
    blackjack_double,
    blackjack_hit,
    blackjack_stand,
    current_hand,
    hand_value,
    play_slots,
)
from bot.services.extra import list_squads
from bot.services.gang import get_gang
from bot.services.resource import StatistKey, balance
from bot.states.casino import CasinoStates
from bot.texts.casino import (
    BJ_DOUBLED,
    BJ_HIDDEN,
    BJ_RESULT,
    BJ_TABLE,
    BJ_YOUR_MOVE,
    BUSY_ALERT,
    CASINO_SCREEN,
    GAME_NAMES,
    HAND_GONE_ALERT,
    HAND_IN_PROGRESS_ALERT,
    NOT_ENOUGH_ALERT,
    PICK_SQUAD,
    PICK_SQUAD_NONE,
    PICK_STAKE,
    SLOTS_LOSS,
    SLOTS_PAIR,
    SLOTS_RESULT,
    SLOTS_TRIPLE,
    STAKE_INVALID,
    STAKE_PROMPT,
    STATISTS_MIN_ALERT,
    X3_ALERT,
)
from bot.texts.gang import squad_title
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="casino")


def stake_label(stake: Stake, amount: int | None = None) -> str:
    value = stake.amount if amount is None else amount
    if stake.kind == STAKE_RESOURCE:
        return amount_label(stake.code, value)
    key = StatistKey.decode(stake.code)
    return f"{format_number(value)} 👥 {squad_title(key.rank, key.stars, key.training_level, key.school, key.school_level)}"


def _cards(cards: list[list]) -> str:
    return " ".join(f"{r}{s}" for r, s in cards)


def render_blackjack(state: BlackjackState):
    if state.finished:
        dealer, dealer_total = _cards(state.dealer), f"({state.dealer_total})"
        status = BJ_RESULT[state.outcome].format(payout=stake_label(state.stake, state.payout))
        markup = blackjack_done_menu()
    else:
        dealer, dealer_total = f"{_cards(state.dealer[:1])} {BJ_HIDDEN}", ""
        status = BJ_YOUR_MOVE
        markup = blackjack_menu(can_double=len(state.player) == 2 and not state.doubled)
    text = BJ_TABLE.format(
        stake=stake_label(state.stake), doubled=BJ_DOUBLED if state.doubled else "", dealer=dealer,
        dealer_total=dealer_total, player=_cards(state.player), player_total=hand_value(state.player), status=status,
    )
    return text, markup


def render_slots(result: SlotsResult):
    stake = stake_label(result.stake)
    if result.outcome == OUTCOME_TRIPLE:
        line = SLOTS_TRIPLE.format(stake=stake, payout=stake_label(result.stake, result.payout))
    elif result.outcome == OUTCOME_PAIR:
        line = SLOTS_PAIR.format(stake=stake)
    else:
        line = SLOTS_LOSS.format(stake=stake)
    return SLOTS_RESULT.format(reel=" | ".join(result.reel), line=line), slots_result_menu(result.stake.code, result.stake.amount)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


async def _squads(session: AsyncSession, user_id: int) -> list[tuple[str, str, int]]:
    return [
        (
            StatistKey(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level).encode(),
            squad_title(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level),
            sq.attack + sq.defense,
        )
        for sq in await list_squads(session, user_id)
        if sq.attack + sq.defense > 0
    ]


@router.callback_query(F.data == CB_CASINO_OPEN)
async def cb_casino_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    await safe_edit_text(callback.message, CASINO_SCREEN, reply_markup=casino_menu())


@router.callback_query(F.data.startswith(CB_CASINO_GAME_PREFIX))
async def cb_casino_game(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    await state.clear()
    game = callback.data.removeprefix(CB_CASINO_GAME_PREFIX)
    if game not in GAME_NAMES or not await _guard(callback, session):
        await callback.answer()
        return
    # Незаконченная раздача блэкджека — сразу к ней, а не к новой ставке.
    if game == GAME_BLACKJACK:
        hand = await current_hand(redis, callback.from_user.id)
        if hand is not None:
            await callback.answer()
            text, markup = render_blackjack(hand)
            await safe_edit_text(callback.message, text, reply_markup=markup)
            return
    await callback.answer()
    await safe_edit_text(callback.message, PICK_STAKE.format(game=GAME_NAMES[game]), reply_markup=stake_menu(game))


async def _ask_stake(callback: CallbackQuery, state: FSMContext, game: str, kind: str, code: str, item: str, have: int) -> None:
    await state.set_state(CasinoStates.waiting_stake)
    await state.update_data(game=game, kind=kind, code=code)
    await callback.answer()
    await safe_edit_text(
        callback.message, STAKE_PROMPT.format(game=GAME_NAMES[game], item=item, have=format_number(have)),
        reply_markup=back_to_game(game),
    )


@router.callback_query(F.data.startswith(CB_CASINO_STAKE_PREFIX))
async def cb_casino_stake(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    game, _, code = callback.data.removeprefix(CB_CASINO_STAKE_PREFIX).partition(":")
    if game not in GAME_NAMES or code not in CASINO_STAKE_RESOURCES or not await _guard(callback, session):
        await callback.answer()
        return
    have = await balance(session, callback.from_user.id, code)
    await _ask_stake(callback, state, game, STAKE_RESOURCE, code, resource_label(code), have)


@router.callback_query(F.data.startswith(CB_CASINO_STATISTS_PREFIX))
async def cb_casino_statists(callback: CallbackQuery, session: AsyncSession) -> None:
    game = callback.data.removeprefix(CB_CASINO_STATISTS_PREFIX)
    if game != GAME_BLACKJACK or not await _guard(callback, session):
        await callback.answer()
        return
    squads = await _squads(session, callback.from_user.id)
    if not squads:
        await callback.answer(PICK_SQUAD_NONE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, PICK_SQUAD.format(game=GAME_NAMES[game]), reply_markup=squads_menu(game, squads))


@router.callback_query(F.data.startswith(CB_CASINO_SQUAD_PREFIX))
async def cb_casino_squad(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    game, _, code = callback.data.removeprefix(CB_CASINO_SQUAD_PREFIX).partition(":")
    squad = next((s for s in await _squads(session, callback.from_user.id) if s[0] == code), None)
    if game != GAME_BLACKJACK or squad is None:
        await callback.answer()
        return
    await _ask_stake(callback, state, game, STAKE_STATIST, code, "👥 " + squad[1], squad[2])


async def _play(session: AsyncSession, redis: Redis, user_id: int, game: str, stake: Stake):
    """→ (текст, клавиатура) или popup-ошибка (строка)."""
    try:
        if game == GAME_SLOTS:
            return render_slots(await play_slots(session, redis, user_id, stake))
        return render_blackjack(await blackjack_deal(session, redis, user_id, stake))
    except CasinoBusyError:
        return BUSY_ALERT
    except X3StrategyError:
        return X3_ALERT
    except NotEnoughError:
        return NOT_ENOUGH_ALERT
    except HandInProgressError:
        return HAND_IN_PROGRESS_ALERT
    except InvalidStakeError:
        return STATISTS_MIN_ALERT if stake.kind == STAKE_STATIST else NOT_ENOUGH_ALERT


@router.message(CasinoStates.waiting_stake)
async def on_casino_stake(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    data = await state.get_data()
    game = data.get("game", "")
    raw = (message.text or "").replace(" ", "").replace("_", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(STAKE_INVALID, reply_markup=back_to_game(game))
        return
    result = await _play(session, redis, message.from_user.id, game, Stake(data["kind"], data["code"], int(raw)))
    if isinstance(result, str):
        await message.answer(result, reply_markup=back_to_game(game))
        return
    await state.clear()
    await message.answer(result[0], reply_markup=result[1])


@router.callback_query(F.data.startswith(CB_SLOTS_AGAIN_PREFIX))
async def cb_slots_again(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    code, _, raw = callback.data.removeprefix(CB_SLOTS_AGAIN_PREFIX).rpartition(":")
    if code not in CASINO_STAKE_RESOURCES or not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    result = await _play(session, redis, callback.from_user.id, GAME_SLOTS, Stake(STAKE_RESOURCE, code, int(raw)))
    if isinstance(result, str):
        await callback.answer(result, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, result[0], reply_markup=result[1])


async def _bj_action(callback: CallbackQuery, session: AsyncSession, redis: Redis, action) -> None:
    # Popup-тексты — без HTML.
    try:
        state = await action(session, redis, callback.from_user.id)
    except CasinoBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except HandNotFoundError:
        await callback.answer(HAND_GONE_ALERT, show_alert=True)
        return
    except NotEnoughError:
        await callback.answer(NOT_ENOUGH_ALERT, show_alert=True)
        return
    await callback.answer()
    text, markup = render_blackjack(state)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_BJ_HIT)
async def cb_bj_hit(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _bj_action(callback, session, redis, blackjack_hit)


@router.callback_query(F.data == CB_BJ_STAND)
async def cb_bj_stand(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _bj_action(callback, session, redis, blackjack_stand)


@router.callback_query(F.data == CB_BJ_DOUBLE)
async def cb_bj_double(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _bj_action(callback, session, redis, blackjack_double)
