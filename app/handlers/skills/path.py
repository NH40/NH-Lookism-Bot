from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.skill_service import skill_service, _all_path_skills_map
from app.data.skills import PATH_SKILLS, PATH_SYNERGIES
from app.constants.raid import (
    PATH_SPIN_CRAFT_COST, PATH_LEVEL_MAX, PATH_LEVEL_BONUSES,
)
from app.utils.formatters import skill_path_label

router = Router()


@router.callback_query(F.data == "path_choose")
async def cb_path_choose(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.skill_path:
        await cb.answer("Путь уже выбран", show_alert=True)
        await cb_path_menu(cb, session, user)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💼 Бизнесмен", callback_data="choose_path:businessman"
    ))
    builder.row(InlineKeyboardButton(
        text="💝 Романтик", callback_data="choose_path:romantic"
    ))
    builder.row(InlineKeyboardButton(
        text="👹 Монстр", callback_data="choose_path:monster"
    ))
    builder.row(InlineKeyboardButton(
        text="🌑 Тень", callback_data="choose_path:shadow"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    await cb.message.edit_text(
        "🗺 <b>Выбор пути</b>\n\n"
        "💼 <b>Бизнесмен</b>\n+% доход, скидки на здания, множитель районов, рэкет\n\n"
        "💝 <b>Романтик</b>\n+слоты тикетов, +% шанс, двойная вербовка, народная любовь\n\n"
        "👹 <b>Монстр</b>\n+% тренировка, двойная тренировка, двойная атака, ярость\n\n"
        "🌑 <b>Тень</b>\n-% КД всего, скрытность, удар из засады, серия убийств\n\n"
        "<i>⚠️ Выбор нельзя изменить!</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("choose_path:"))
async def cb_choose_path(cb: CallbackQuery, session: AsyncSession, user: User):
    path = cb.data.split(":")[1]
    result = await skill_service.choose_path(session, user, path)
    if result["ok"]:
        await cb.answer(f"✅ Путь выбран!")
        await cb_path_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "path_menu")
async def cb_path_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.skill_path:
        await cb_path_choose(cb, session, user)
        return

    bought = await skill_service.get_path_skills_bought(session, user.id)
    skills = PATH_SKILLS.get(user.skill_path, [])
    extra_count = await skill_service.get_extra_path_skills_count(session, user)
    slots = getattr(user, "extra_path_skill_slots", 1)
    path_frags = getattr(user, "path_fragments", 0)
    path_level = getattr(user, "skill_path_level", 0)
    path_awakened = getattr(user, "path_awakened", False)

    path_emoji = {"businessman": "💼", "romantic": "💝", "monster": "👹", "shadow": "🌑"}.get(user.skill_path, "")
    path_name = skill_path_label(user.skill_path)

    bought_ids = set(bought)
    bought_count = sum(1 for s in skills if s.skill_id in bought_ids)
    total_count = len(skills)

    builder = InlineKeyboardBuilder()

    for skill in skills:
        if skill.skill_id not in bought_ids:
            req_lvl = getattr(skill, "min_path_level", 0)
            locked_by_level = path_level < req_lvl
            if locked_by_level:
                builder.button(
                    text=f"🔒 {skill.emoji} {skill.name} | ур. пути {req_lvl}",
                    callback_data="noop"
                )
            else:
                can = "✅" if user.skill_path_points >= skill.cost else "❌"
                builder.button(
                    text=f"{can} {skill.emoji} {skill.name} | 💎 {skill.cost}",
                    callback_data=f"buy_path_skill:{skill.skill_id}"
                )
    builder.adjust(1)

    # Кнопка скрытности — показываем всем у кого куплен навык (в т.ч. через слияние)
    if getattr(user, "path_unique_2", False):
        stealth_on = getattr(user, "shadow_stealth_active", False)
        stealth_label = "🫥 Скрытность: ВКЛ ✅" if stealth_on else "👁 Скрытность: ВЫКЛ ❌"
        builder.row(InlineKeyboardButton(
            text=stealth_label,
            callback_data="shadow_stealth_toggle"
        ))

    slots_full = extra_count >= slots
    merge_icon = "🔒" if slots_full else "🌐"
    builder.row(InlineKeyboardButton(
        text=f"{merge_icon} Слияние путей [{extra_count}/{slots}]",
        callback_data="extra_skills_menu"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    awakened_str = "⚡ <b>Пробуждён!</b>" if path_awakened else ""
    level_stars = "⭐" * path_level + "☆" * (PATH_LEVEL_MAX - path_level)
    level_bonus = PATH_LEVEL_BONUSES.get(user.skill_path, {})
    level_bonus_str = ""
    if level_bonus and path_level > 0:
        parts = [f"+{v * path_level} {k.replace('income_bonus_percent','% дохода').replace('ticket_chance','% тикета').replace('train_bonus_percent','% трен.')}" for k, v in level_bonus.items()]
        level_bonus_str = f" ({', '.join(parts)})"

    lines = [
        f"🗺 <b>Путь: {path_emoji} {path_name}</b>",
        f"",
        f"💎 Очков пути: <b>{user.skill_path_points}</b>",
        f"🔷 Фрагменты Пути: <b>{path_frags}</b>",
        f"⭐ Уровень пути: <b>{level_stars}</b>{level_bonus_str}",
    ]
    if awakened_str:
        lines.append(awakened_str)
    lines.append(f"")
    lines.append(f"<b>── Навыки пути [{bought_count}/{total_count}] ──</b>")
    lines.append(f"")
    for skill in skills:
        req_lvl = getattr(skill, "min_path_level", 0)
        if skill.skill_id in bought_ids:
            lines.append(f"✅ {skill.emoji} <b>{skill.name}</b>")
            lines.append(f"   └ {skill.description}")
        elif path_level < req_lvl:
            lines.append(f"🔒 {skill.emoji} {skill.name} — ур. пути {req_lvl}")
            lines.append(f"   └ <i>{skill.description}</i>")
        else:
            can = "✅" if user.skill_path_points >= skill.cost else "❌"
            lines.append(f"{can} {skill.emoji} {skill.name} — 💎 {skill.cost}")
            lines.append(f"   └ <i>{skill.description}</i>")

    lines.append(f"")
    lines.append(f"<b>── Слияние путей ──</b>")
    lines.append(f"")
    if slots_full:
        lines.append(f"🔒 Слоты заполнены: <b>{extra_count}/{slots}</b>")
        if slots == 1:
            lines.append(f"<i>Донат «Три пути» откроет ещё 2 слота</i>")
    else:
        lines.append(f"🌐 Использовано: <b>{extra_count}/{slots}</b>")
        lines.append(f"<i>Крути навык за {PATH_SPIN_CRAFT_COST} 🔷 в Рейды → Крафт → 🔷</i>")
        if slots > 1:
            lines.append(f"<i>Или купи навык за ×5 💎 в меню ниже</i>")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "extra_skills_menu")
async def cb_extra_skills_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.skill_path:
        await cb.answer("Сначала выбери путь!", show_alert=True)
        return

    slots = getattr(user, "extra_path_skill_slots", 1)
    extra_count = await skill_service.get_extra_path_skills_count(session, user)
    slots_full = extra_count >= slots
    can_buy_more = not slots_full and slots > 1

    bought = set(await skill_service.get_path_skills_bought(session, user.id))
    other_paths = [p for p in PATH_SKILLS if p != user.skill_path]
    path_emoji_map = {"businessman": "💼", "romantic": "💝", "monster": "👹", "shadow": "🌑"}

    all_map = _all_path_skills_map()
    active_foreign_paths = set()
    for sid in bought:
        skill_obj = all_map.get(sid)
        if skill_obj and skill_obj.path != user.skill_path:
            active_foreign_paths.add(skill_obj.path)

    builder = InlineKeyboardBuilder()

    if can_buy_more:
        for other_path in other_paths:
            for skill in PATH_SKILLS[other_path]:
                if skill.skill_id not in bought:
                    cost5 = skill.cost * 5
                    can = "✅" if user.skill_path_points >= cost5 else "❌"
                    builder.button(
                        text=f"{can} {skill.emoji} {skill.name} | 💎 {cost5}",
                        callback_data=f"buy_extra_skill:{skill.skill_id}"
                    )
        builder.adjust(1)

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="path_menu"))

    lines = [
        f"🌐 <b>Слияние путей</b>",
        f"",
        f"💎 Очков пути: <b>{user.skill_path_points}</b>",
        f"🌐 Слоты: <b>{extra_count}/{slots}</b>",
        f"",
    ]

    if slots_full:
        lines.append(f"🔒 <b>Все слоты заполнены</b>")
        if slots == 1:
            lines.append(f"<i>С донатом «Три пути» откроются ещё 2 слота</i>")
            lines.append(f"<i>и возможность выбирать навык за ×5 💎</i>")
    else:
        if slots == 1:
            lines.append(f"<i>Крути навык в Рейды → Крафт → 🔷 за фрагменты Пути</i>")
            lines.append(f"<i>Донат «Три пути»: 3 слота + выбор навыка за ×5 💎</i>")
        else:
            lines.append(f"<i>Выбери навык другого пути за ×5 от обычной цены</i>")
            lines.append(f"<i>Или крути рандомный навык в Рейды → Крафт → 🔷</i>")

    if active_foreign_paths:
        lines.append(f"")
        lines.append(f"<b>── Активные синергии ──</b>")
        for fp in active_foreign_paths:
            syn = PATH_SYNERGIES.get((user.skill_path, fp))
            if syn:
                effect_str = ", ".join(f"+{v} {k}" for k, v in syn["effect"].items())
                lines.append(f"  {syn['emoji']} <b>{syn['name']}</b>: {effect_str}")

    for other_path in other_paths:
        emoji = path_emoji_map.get(other_path, "❓")
        lines.append(f"\n{emoji} <b>{skill_path_label(other_path)}</b>")
        syn = PATH_SYNERGIES.get((user.skill_path, other_path))
        if syn:
            is_active = other_path in active_foreign_paths
            syn_marker = f"✨ Синергия: {syn['emoji']} {syn['name']}" if is_active else f"💤 Синергия при 1-м навыке: {syn['emoji']} {syn['name']}"
            lines.append(f"  <i>{syn_marker}</i>")
        for skill in PATH_SKILLS[other_path]:
            if skill.skill_id in bought:
                lines.append(f"  ✅ {skill.emoji} {skill.name}")
            elif can_buy_more:
                cost5 = skill.cost * 5
                can = "✅" if user.skill_path_points >= cost5 else "❌"
                lines.append(f"  {can} {skill.emoji} {skill.name} — 💎 {cost5}")
            else:
                lines.append(f"  🔒 {skill.emoji} {skill.name}")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy_extra_skill:"))
async def cb_buy_extra_skill(cb: CallbackQuery, session: AsyncSession, user: User):
    skill_id = cb.data.split(":")[1]
    result = await skill_service.buy_extra_path_skill(session, user, skill_id)
    if result["ok"]:
        synergy = result.get("synergy")
        text = f"✅ Навык «{result['skill']}» куплен за {result['cost']} 💎!"
        if synergy:
            text += f"\n\n✨ Синергия активирована: {synergy['emoji']} {synergy['name']}!"
        await cb.answer(text, show_alert=True)
        await cb_extra_skills_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data.startswith("buy_path_skill:"))
async def cb_buy_path_skill(cb: CallbackQuery, session: AsyncSession, user: User):
    skill_id = cb.data.split(":")[1]
    result = await skill_service.buy_path_skill(session, user, skill_id)
    if result["ok"]:
        if result.get("awakened"):
            await cb.answer(
                f"✅ Навык «{result['skill']}» куплен!\n\n⚡ ПУТЬ ПРОБУЖДЁН! Получен бонус пробуждения!",
                show_alert=True
            )
        else:
            await cb.answer(f"✅ Навык «{result['skill']}» куплен!")
        await cb_path_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "shadow_stealth_toggle")
async def cb_shadow_stealth_toggle(cb: CallbackQuery, session: AsyncSession, user: User):
    if not getattr(user, "path_unique_2", False):
        await cb.answer("Навык «Скрытность» не куплен", show_alert=True)
        return
    current = getattr(user, "shadow_stealth_active", False)
    user.shadow_stealth_active = not current
    await session.commit()
    state = "включена 🫥" if not current else "выключена 👁"
    await cb.answer(f"Скрытность {state}", show_alert=True)
    await cb_path_menu(cb, session, user)
