"""Быстрое меню — обрабатывает нажатия постоянной reply-клавиатуры
(app/utils/keyboards/reply_menu.py). Каждая кнопка открывает тот же экран,
что и соответствующая inline-кнопка главного меню, но отправляет НОВОЕ
сообщение (у reply-кнопки нет "своего" сообщения для редактирования).

Роутер регистрируется ПЕРВЫМ в main.py — точное совпадение текста кнопки
должно перехватывать нажатие раньше любого активного FSM-хэндлера (например,
если игрок как раз вводит сумму рейза в покере и тут же жмёт "🏦 Банк" —
это должно увести его в Банк, а не попытаться распарсить текст кнопки как
число)."""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.keyboards.reply_menu import quick_menu_kb

router = Router()


@router.message(F.text == "👤 Профиль")
async def qm_profile(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    import html
    from app.repositories.title_repo import title_repo
    from app.repositories.city_repo import city_repo
    from app.services.business_service import business_service
    from app.utils.formatters import fmt_num, phase_label, progress_bar
    from app.utils.keyboards.common import back_kb
    from app.data.cities import COUNTRY_BY_CODE
    from app.handlers.common._common import _phase_emoji

    titles_str = await title_repo.get_titles_display(session, user.id)
    districts = await city_repo.get_user_district_count(session, user.id)
    info = await business_service.get_income_breakdown(session, user)

    prestige_str = ""
    if user.prestige_level > 0:
        prestige_str = (
            f"\n━━━ 🌟 Пробуждение ━━━\n"
            f"{progress_bar(user.prestige_level, 10)} {user.prestige_level}/10\n"
            f"  +{user.prestige_level * 5}% мощь | "
            f"+{user.prestige_income_bonus}% доход | "
            f"+{user.prestige_ticket_bonus}% тикет"
        )

    text = (
        f"📊 <b>Профиль</b>\n\n"
        f"👤 {html.escape(user.full_name)}"
        + (f"\n🏴 Банда: {html.escape(user.gang_name)}" if user.gang_name else "")
        + f"\n{_phase_emoji(user.phase)} {phase_label(user.phase)}"
        + (f" | 🌐 {COUNTRY_BY_CODE[user.country].label}" if user.country and user.country in COUNTRY_BY_CODE else "")
        + f"\n\n━━━ 💰 Финансы ━━━\n"
        f"NHCoin: {fmt_num(user.nh_coins)}\n"
        f"Доход: {fmt_num(info['base_income'])}/мин"
        + (f" → {fmt_num(info['final_income'])}/мин" if info['final_income'] != info['base_income'] else "")
        + f"\n\n━━━ ⚔️ Боевые ━━━\n"
        f"Мощь: {fmt_num(user.combat_power)}\n"
        f"Влияние: {fmt_num(user.influence)}\n\n"
        f"━━━ 🏙 Территория ━━━\n"
        f"Районов: {districts} | Городов: {user.king_cities_count}"
        + prestige_str
        + f"\n\n━━━ 💎 Титулы ━━━\n"
        + titles_str
    )
    await message.answer(text, reply_markup=back_kb("settings"), parse_mode="HTML")


@router.message(F.text == "⚔️ Атака")
async def qm_attack(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.services.bank.credits_service import credits_service
    from app.utils.keyboards.common import back_kb
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        await message.answer(block_msg, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    from app.handlers.attack import build_attack_menu
    text, kb, photo = await build_attack_menu(session, user)
    if photo:
        await message.answer_photo(photo, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "⚔️ Рейд")
async def qm_raid(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.services.bank.credits_service import credits_service
    from app.utils.keyboards.common import back_kb
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        await message.answer(block_msg, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    from app.handlers.raid.menu import build_raid_menu_view
    text, kb = await build_raid_menu_view(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏢 Бизнес")
async def qm_business(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    if not user.business_building_id:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
        await message.answer(
            "🏢 <b>Бизнес</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Сначала захвати хотя бы один район (Атака), затем сможешь"
            " выбрать своё дело здесь.",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
        return

    from app.handlers.business._common import _build_business_main
    text, kb = await _build_business_main(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏦 Банк")
async def qm_bank(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.bank.menu import _bank_menu_text, bank_menu_kb
    text = await _bank_menu_text(session, user)
    await message.answer(text, reply_markup=bank_menu_kb(), parse_mode="HTML")


@router.message(F.text == "👥 Группировка")
async def qm_squad(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.squad import build_squad_view
    text, kb = await build_squad_view(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏯 Кланы")
async def qm_clans(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.services.clan import clan_service
    clan = await clan_service.get_user_clan(session, user.id)
    if not clan:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🏯 Создать клан", callback_data="clan_create"))
        builder.row(InlineKeyboardButton(text="🔍 Найти клан", callback_data="clan_search:0"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
        await message.answer(
            "🏯 <b>Кланы</b>\n\nВы не состоите в клане.\nСоздайте свой или вступите в существующий!",
            reply_markup=builder.as_markup(), parse_mode="HTML",
        )
        return

    from app.handlers.clan.main import _build_clan_main
    text, kb = await _build_clan_main(session, user, clan)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🛒 Магазин")
async def qm_shop(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.utils.keyboards.shop import shop_kb
    from app.utils.formatters import fmt_num
    await message.answer(
        f"🛒 <b>Магазин</b>\n\n"
        f"💰 Баланс: {fmt_num(user.nh_coins)} NHCoin\n\n"
        f"Выберите раздел:",
        reply_markup=shop_kb(), parse_mode="HTML",
    )


@router.message(F.text == "👹 Боссы")
async def qm_bosses(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.bosses.menu import _boss_main_screen, _boss_photo
    text, kb, boss_id = await _boss_main_screen(session, user)
    photo = _boss_photo(boss_id) if boss_id else None
    if photo:
        await message.answer_photo(photo, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🗺 Походы")
async def qm_campaigns(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.campaigns.menu import _campaigns_text_kb
    text, kb = await _campaigns_text_kb(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏪 Биржа")
async def qm_market(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from app.utils.formatters import fmt_num
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Покупатель", callback_data="market_buyer"))
    builder.row(InlineKeyboardButton(text="💰 Продавец", callback_data="market_seller"))
    builder.row(InlineKeyboardButton(text="🔨 Аукционы", callback_data="market_auction_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    await message.answer(
        f"🏪 <b>Биржа</b>\n\n"
        f"💰 NHCoin: <b>{fmt_num(user.nh_coins)}</b>\n"
        f"Выбери роль:",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.message(F.text == "🏛 Аукцион")
async def qm_auction(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.auction import _build_auction_view
    text, kb = await _build_auction_view(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🃏 Колода")
async def qm_deck(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.cards.menu import build_deck_view
    text, kb = await build_deck_view(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏆 Титулы")
async def qm_titles(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🥇 Достижения", callback_data="achievements_menu"))
    builder.row(InlineKeyboardButton(text="💎 Донатные сеты", callback_data="donat_sets_menu"))
    builder.row(InlineKeyboardButton(text="🎮 Игровые титулы", callback_data="game_titles_menu"))
    builder.row(InlineKeyboardButton(text="🌟 Слава", callback_data="fame_titles_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    await message.answer(
        "🏆 <b>Титулы</b>\n\n"
        "🥇 Достижения — выполняй задачи и получай бонусы\n\n"
        "💎 Донатные сеты — особые привилегии за поддержку проекта\n\n"
        "🎮 Игровые титулы — за топ рейтинга казино\n\n"
        "🌟 Слава — уникальные сеты Кузницы славы",
        reply_markup=builder.as_markup(), parse_mode="HTML",
    )


@router.message(F.text == "⚡ Навыки")
async def qm_skills(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.skills.menu import build_skills_view
    text, kb = await build_skills_view(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🏋 Тренировка")
async def qm_training(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.services.bank.credits_service import credits_service
    from app.utils.keyboards.common import back_kb
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        await message.answer(block_msg, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        return

    from app.handlers.training import build_training_menu_view
    text, kb = await build_training_menu_view(session, user)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "📋 Задания")
async def qm_quests(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.handlers.quests import quest_service, _build_quest_page, _time_to_reset
    quests = await quest_service.get_or_create_quests(session, user)
    swap_count = await quest_service.get_swap_count(user.id)
    reroll_used = await quest_service.is_reroll_used(user.id)
    h, m = _time_to_reset()
    text, kb = _build_quest_page(quests, 0, h, m, swap_count, reroll_used)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "⚙️ Прочее")
async def qm_other(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    from app.repositories.title_repo import title_repo
    from app.utils.keyboards.common import menu_other_kb
    has_vvip = await title_repo.has_all_sets(session, user.id)
    await message.answer(
        "⚙️ <b>Прочее</b>\n\nВыбери раздел:",
        reply_markup=menu_other_kb(has_vvip=has_vvip), parse_mode="HTML",
    )
