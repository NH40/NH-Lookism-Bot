"""
Хэндлеры системы Походов.

Поток:
  campaigns_menu
    → campaigns_new              (выбор ресурса)
    → campaigns_res:{res}        (выбор ранга задания)
    → campaigns_rank:{res}:{tr}  (выбор длительности)
    → campaigns_dur:{res}:{tr}:{h}          (выбор ранга статистов)
    → campaigns_srank:{res}:{tr}:{h}:{sr}   (выбор количества)
    → campaigns_cnt:{res}:{tr}:{h}:{sr}:{n} (подтверждение)
    → campaigns_launch:{res}:{tr}:{h}:{sr}:{n} (запуск)
    → campaigns_collect:{camp_id}           (забрать результат)

  tr = task rank (ранг задания: E/D/C/B/A/S)
  sr = statist rank (ранг статистов: E/D/C/B/A/S)
"""
from datetime import timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.campaign_service import campaign_service
from app.constants.campaigns import (
    CAMPAIGN_DURATIONS_HOURS,
    CAMPAIGN_RANK_MAP,
    CAMPAIGN_RANKS,
    CAMPAIGN_RESOURCE_MAP,
    CAMPAIGN_RESOURCES,
    MAX_ACTIVE_CAMPAIGNS,
    STATIST_COUNT_OPTIONS,
    MAX_STATISTS_PER_CAMPAIGN,
)
from app.utils.formatters import fmt_num, fmt_ttl

router = Router()

# ── Константы ─────────────────────────────────────────────────────────────────

# Порядок рангов статистов от слабого к сильному (полный список)
STATIST_RANK_ORDER = [
    "F", "E", "D", "C", "B", "A", "S",
    "SS", "SSS", "SR", "SSR", "UR",
    "LR", "MP", "X", "XX", "XXX", "DX", "ERROR",
]

STATIST_RANK_EMOJI = {
    "F":  "⬛", "E":  "⬜", "D":  "🟦", "C":  "🟩",
    "B":  "🟨", "A":  "🟧", "S":  "🟥", "SS": "💠",
    "SSS":"🔷", "SR": "🌟", "SSR":"✨",  "UR": "💎",
    "LR": "👑", "MP": "🔱", "X":  "⚡",  "XX": "🌀",
    "XXX":"🔥", "DX": "💀", "ERROR":"❌",
}


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _duration_label(h: int) -> str:
    if h == 1:
        return "1 час"
    if h < 5:
        return f"{h} часа"
    return f"{h} часов"


def _resource_emoji(rid: str) -> str:
    cfg = CAMPAIGN_RESOURCE_MAP.get(rid)
    return cfg.emoji if cfg else "❓"


def _resource_label(rid: str) -> str:
    cfg = CAMPAIGN_RESOURCE_MAP.get(rid)
    return cfg.label if cfg else rid


def _rank_emoji(rank: str) -> str:
    """Эмодзи ранга задания (из констант кампании)."""
    cfg = CAMPAIGN_RANK_MAP.get(rank)
    return cfg.emoji if cfg else "❓"


def _sr_emoji(rank: str) -> str:
    """Эмодзи ранга статиста."""
    return STATIST_RANK_EMOJI.get(rank, "❓")


async def _campaigns_text_kb(session: AsyncSession, user: User):
    """Собирает текст и клавиатуру главного экрана походов."""
    active = await campaign_service.get_active_campaigns(session, user.id)
    finished = await campaign_service.get_finished_campaigns(session, user.id)

    from datetime import datetime
    now = datetime.now(timezone.utc)

    lines = ["🗺 <b>Походы</b>\n"]

    # Завершённые (ждут сбора)
    if finished:
        lines.append("🎁 <b>Готово к сбору:</b>")
        for c in finished:
            res_emoji = _resource_emoji(c.resource_type)
            res_label = _resource_label(c.resource_type)
            result_str = "✅ Успех" if c.success else "❌ Провал"
            lines.append(
                f"  {_rank_emoji(c.rank)} Ранг {c.rank} — {_duration_label(c.duration_hours)}\n"
                f"  {result_str} | {res_emoji} +{fmt_num(c.resource_gained)} {res_label}\n"
                f"  👥 Вернулось: {c.statists_returned}/{c.statist_count}"
            )
        lines.append("")

    # Активные
    if active:
        lines.append("⏳ <b>Активные походы:</b>")
        for c in active:
            secs = max(0, int((c.ends_at - now).total_seconds()))
            res_emoji = _resource_emoji(c.resource_type)
            sr_em = _sr_emoji(getattr(c, "statist_rank", "?") or "?")
            lines.append(
                f"  {_rank_emoji(c.rank)} Ранг {c.rank} | {_duration_label(c.duration_hours)} | "
                f"{res_emoji} {_resource_label(c.resource_type)}\n"
                f"  {sr_em} {c.statist_count} статистов | ⏱ {fmt_ttl(secs)}"
            )
        lines.append("")
    elif not finished:
        lines.append("Нет активных походов.\nОтправляй статистов за ресурсами!")

    # Доступные статисты
    available = await campaign_service.get_available_statists(session, user.id)
    lines.append(f"\n👥 Свободных статистов: <b>{len(available)}</b>")
    lines.append(f"💪 Боевая мощь: <b>{fmt_num(user.combat_power)}</b>")

    builder = InlineKeyboardBuilder()

    # Кнопки «Забрать» для завершённых
    for c in finished:
        res_emoji = _resource_emoji(c.resource_type)
        builder.row(InlineKeyboardButton(
            text=f"🎁 Забрать: Ранг {c.rank} {res_emoji} +{fmt_num(c.resource_gained)}",
            callback_data=f"campaigns_collect:{c.id}",
        ))

    # Кнопка нового похода
    if len(active) < MAX_ACTIVE_CAMPAIGNS:
        builder.row(InlineKeyboardButton(
            text="➕ Новый поход",
            callback_data="campaigns_new",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"🔒 Все слоты заняты ({MAX_ACTIVE_CAMPAIGNS}/{MAX_ACTIVE_CAMPAIGNS})",
            callback_data="campaigns_full",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    return "\n".join(lines), builder.as_markup()


# ── Главный экран ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "campaigns_menu")
async def cb_campaigns_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    text, kb = await _campaigns_text_kb(session, user)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "campaigns_full")
async def cb_campaigns_full(cb: CallbackQuery):
    await cb.answer(
        f"Уже {MAX_ACTIVE_CAMPAIGNS} активных похода — сначала дождись завершения!",
        show_alert=True,
    )


# ── Шаг 1: выбор ресурса ─────────────────────────────────────────────────────

@router.callback_query(F.data == "campaigns_new")
async def cb_campaigns_new(cb: CallbackQuery, session: AsyncSession, user: User):
    ok, reason = await campaign_service.can_start(session, user.id)
    if not ok:
        await cb.answer(reason, show_alert=True)
        return

    available = await campaign_service.get_available_statists(session, user.id)
    if not available:
        await cb.answer("Нет свободных статистов для похода!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for res in CAMPAIGN_RESOURCES:
        builder.row(InlineKeyboardButton(
            text=f"{res.emoji} {res.label}",
            callback_data=f"campaigns_res:{res.resource_id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="campaigns_menu"))

    text = (
        "🗺 <b>Новый поход</b> — выбери ресурс\n\n"
        "Статисты принесут выбранный ресурс,\n"
        "если поход окажется успешным.\n\n"
        + "\n".join(
            f"{r.emoji} <b>{r.label}</b> — {r.base_per_statist_per_hour}/статист/час (базово)"
            for r in CAMPAIGN_RESOURCES
        )
    )
    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 2: выбор ранга задания ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_res:"))
async def cb_campaigns_res(cb: CallbackQuery, session: AsyncSession, user: User):
    resource_id = cb.data.split(":")[1]
    if resource_id not in CAMPAIGN_RESOURCE_MAP:
        await cb.answer("Ошибка: неизвестный ресурс", show_alert=True)
        return

    available = await campaign_service.get_available_statists(session, user.id)
    avg_all = int(sum(m.base_power for m in available) / len(available)) if available else 0

    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_id]
    builder = InlineKeyboardBuilder()

    lines = [
        f"🗺 <b>Новый поход</b> — {res_cfg.emoji} {res_cfg.label}\n",
        f"👥 Доступно статистов: <b>{len(available)}</b>",
        f"💪 Средняя мощь: <b>{fmt_num(avg_all)}</b>\n",
        "Выбери ранг задания:\n",
        "─" * 20,
    ]

    for rc in CAMPAIGN_RANKS:
        chance = campaign_service.calc_preview(avg_all, rc.rank, resource_id, 1, 1)["success_chance"]
        icon = "✅" if chance >= 50 else ("⚠️" if chance >= 20 else "❌")
        lines.append(
            f"{rc.emoji} Ранг <b>{rc.rank}</b> — шанс {chance}% {icon} | ×{rc.reward_multiplier:.1f} наград"
        )
        builder.row(InlineKeyboardButton(
            text=f"{rc.emoji} Ранг {rc.rank}  {chance}%  ×{rc.reward_multiplier:.1f}",
            callback_data=f"campaigns_rank:{resource_id}:{rc.rank}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="campaigns_new"))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 3: выбор длительности ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_rank:"))
async def cb_campaigns_rank(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("Ошибка", show_alert=True)
        return
    resource_id, task_rank = parts[1], parts[2]

    if resource_id not in CAMPAIGN_RESOURCE_MAP or task_rank not in CAMPAIGN_RANK_MAP:
        await cb.answer("Ошибка параметров", show_alert=True)
        return

    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_id]
    rank_cfg = CAMPAIGN_RANK_MAP[task_rank]
    available = await campaign_service.get_available_statists(session, user.id)
    avg_all = int(sum(m.base_power for m in available) / len(available)) if available else 0

    builder = InlineKeyboardBuilder()
    lines = [
        f"🗺 <b>Поход</b> — {res_cfg.emoji} {res_cfg.label} | {rank_cfg.emoji} Ранг {task_rank}\n",
        "Выбери длительность:\n",
        "─" * 20,
    ]

    for h in CAMPAIGN_DURATIONS_HOURS:
        preview = campaign_service.calc_preview(avg_all, task_rank, resource_id, h, len(available) or 1)
        max_res = preview["resource_max"]
        builder.row(InlineKeyboardButton(
            text=f"⏱ {_duration_label(h)}  →  до {fmt_num(max_res)} {res_cfg.emoji}",
            callback_data=f"campaigns_dur:{resource_id}:{task_rank}:{h}",
        ))
        lines.append(
            f"⏱ <b>{_duration_label(h)}</b> — до {fmt_num(max_res)} {res_cfg.emoji} {res_cfg.label}"
        )

    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"campaigns_res:{resource_id}",
    ))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 4: выбор ранга статистов ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_dur:"))
async def cb_campaigns_dur(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    if len(parts) < 4:
        await cb.answer("Ошибка", show_alert=True)
        return
    resource_id, task_rank, hours_str = parts[1], parts[2], parts[3]
    try:
        hours = int(hours_str)
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    if resource_id not in CAMPAIGN_RESOURCE_MAP or task_rank not in CAMPAIGN_RANK_MAP:
        await cb.answer("Ошибка параметров", show_alert=True)
        return
    if hours not in CAMPAIGN_DURATIONS_HOURS:
        await cb.answer("Ошибка длительности", show_alert=True)
        return

    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_id]
    rank_cfg = CAMPAIGN_RANK_MAP[task_rank]

    # Группируем доступных статистов по рангу
    by_rank = await campaign_service.get_available_by_rank(session, user.id)
    total_available = sum(len(v) for v in by_rank.values())

    if total_available == 0:
        await cb.answer("Нет свободных статистов!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    lines = [
        f"🗺 <b>Поход</b> — {res_cfg.emoji} {res_cfg.label}",
        f"{rank_cfg.emoji} Ранг {task_rank} | ⏱ {_duration_label(hours)}\n",
        "Выбери ранг статистов для отправки:\n",
        "─" * 22,
    ]

    for sr in STATIST_RANK_ORDER:
        members = by_rank.get(sr, [])
        if not members:
            continue
        count = len(members)
        avg_p = int(sum(m.base_power for m in members) / count)
        prev = campaign_service.calc_preview(avg_p, task_rank, resource_id, hours, count)
        chance = prev["success_chance"]
        icon = "✅" if chance >= 50 else ("⚠️" if chance >= 20 else "❌")
        lines.append(
            f"{_sr_emoji(sr)} Ранг <b>{sr}</b> — {count} ст. | "
            f"avg {fmt_num(avg_p)} 💪 | {chance}% успех {icon}"
        )
        builder.row(InlineKeyboardButton(
            text=f"{_sr_emoji(sr)} {sr}  {count} бойцов  {chance}% успех",
            callback_data=f"campaigns_srank:{resource_id}:{task_rank}:{hours}:{sr}",
        ))

    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"campaigns_rank:{resource_id}:{task_rank}",
    ))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 5: выбор количества ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_srank:"))
async def cb_campaigns_srank(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    if len(parts) < 5:
        await cb.answer("Ошибка", show_alert=True)
        return
    resource_id, task_rank, hours_str, statist_rank = parts[1], parts[2], parts[3], parts[4]
    try:
        hours = int(hours_str)
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    if resource_id not in CAMPAIGN_RESOURCE_MAP or task_rank not in CAMPAIGN_RANK_MAP:
        await cb.answer("Ошибка параметров", show_alert=True)
        return
    if statist_rank not in STATIST_RANK_ORDER:
        await cb.answer("Неизвестный ранг статистов", show_alert=True)
        return

    # Статисты выбранного ранга
    available = await campaign_service.get_available_statists(session, user.id, statist_rank)
    avail_count = len(available)

    if avail_count == 0:
        await cb.answer(f"Нет свободных статистов ранга {statist_rank}!", show_alert=True)
        return

    avg_power = int(sum(m.base_power for m in available) / avail_count)
    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_id]
    rank_cfg = CAMPAIGN_RANK_MAP[task_rank]

    builder = InlineKeyboardBuilder()
    lines = [
        f"🗺 <b>Поход</b> — {res_cfg.emoji} {res_cfg.label}",
        f"{rank_cfg.emoji} Ранг {task_rank} | ⏱ {_duration_label(hours)}",
        f"{_sr_emoji(statist_rank)} Статисты: ранг <b>{statist_rank}</b> | "
        f"доступно <b>{avail_count}</b> | avg {fmt_num(avg_power)} 💪\n",
        "Выбери количество статистов:\n",
        "─" * 22,
    ]

    # Варианты из конфига, ограниченные доступными
    options = [n for n in STATIST_COUNT_OPTIONS if n <= avail_count]
    if avail_count not in options and avail_count <= MAX_STATISTS_PER_CAMPAIGN:
        options.append(avail_count)
    if not options:
        options = [avail_count]

    for n in options:
        n_cap = min(n, avail_count, MAX_STATISTS_PER_CAMPAIGN)
        prev = campaign_service.calc_preview(avg_power, task_rank, resource_id, hours, n_cap)
        label = f"Все ({n_cap})" if n_cap == avail_count else str(n_cap)
        lines.append(
            f"👤 <b>{label}</b> — {prev['success_chance']}% успех | "
            f"выжив. ✅{prev['survival_on_success']}% / ❌{prev['survival_on_fail']}%\n"
            f"  Макс. награда: {fmt_num(prev['resource_max'])} {res_cfg.emoji}"
        )
        builder.row(InlineKeyboardButton(
            text=(
                f"👤 {label}  |  {prev['success_chance']}% успех  "
                f"|  до {fmt_num(prev['resource_max'])} {res_cfg.emoji}"
            ),
            callback_data=f"campaigns_cnt:{resource_id}:{task_rank}:{hours}:{statist_rank}:{n_cap}",
        ))

    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"campaigns_dur:{resource_id}:{task_rank}:{hours}",
    ))

    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 6: подтверждение ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_cnt:"))
async def cb_campaigns_cnt(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    if len(parts) < 6:
        await cb.answer("Ошибка", show_alert=True)
        return
    resource_id, task_rank, hours_str, statist_rank, cnt_str = (
        parts[1], parts[2], parts[3], parts[4], parts[5]
    )
    try:
        hours = int(hours_str)
        cnt = int(cnt_str)
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    if resource_id not in CAMPAIGN_RESOURCE_MAP or task_rank not in CAMPAIGN_RANK_MAP:
        await cb.answer("Ошибка параметров", show_alert=True)
        return
    if statist_rank not in STATIST_RANK_ORDER:
        await cb.answer("Неизвестный ранг статистов", show_alert=True)
        return

    available = await campaign_service.get_available_statists(session, user.id, statist_rank)
    avail_count = len(available)
    if cnt > avail_count:
        await cb.answer(
            f"Недостаточно статистов {statist_rank}: только {avail_count}", show_alert=True
        )
        return

    # Средняя мощь слабейших из выбранного ранга
    chosen = sorted(available, key=lambda m: m.base_power)[:cnt]
    avg_power = int(sum(m.base_power for m in chosen) / cnt) if cnt else 0

    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_id]
    rank_cfg = CAMPAIGN_RANK_MAP[task_rank]
    prev = campaign_service.calc_preview(avg_power, task_rank, resource_id, hours, cnt)

    text = (
        f"🗺 <b>Подтверждение похода</b>\n\n"
        f"{res_cfg.emoji} Ресурс: <b>{res_cfg.label}</b>\n"
        f"{rank_cfg.emoji} Ранг задания: <b>{task_rank}</b>\n"
        f"⏱ Длительность: <b>{_duration_label(hours)}</b>\n"
        f"{_sr_emoji(statist_rank)} Статисты: ранг <b>{statist_rank}</b> — {cnt} бойцов\n"
        f"💪 Их средняя мощь: <b>{fmt_num(avg_power)}</b>\n\n"
        f"─────────────────────\n"
        f"📊 Прогноз:\n"
        f"  🎯 Шанс успеха: <b>{prev['success_chance']}%</b>\n"
        f"  🏆 Макс. награда: <b>{fmt_num(prev['resource_max'])} {res_cfg.emoji}</b>\n"
        f"  👥 Выживут при успехе: ~{prev['survival_on_success']}%\n"
        f"  💀 Выживут при провале: ~{prev['survival_on_fail']}%\n"
        f"─────────────────────\n"
        f"⚠️ Статисты уйдут в поход и вернутся\n"
        f"   только по завершении (часть может погибнуть)."
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Отправить",
            callback_data=f"campaigns_launch:{resource_id}:{task_rank}:{hours}:{statist_rank}:{cnt}",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="campaigns_menu",
        ),
    )

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


# ── Шаг 7: запуск ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_launch:"))
async def cb_campaigns_launch(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    if len(parts) < 6:
        await cb.answer("Ошибка", show_alert=True)
        return
    resource_id, task_rank, hours_str, statist_rank, cnt_str = (
        parts[1], parts[2], parts[3], parts[4], parts[5]
    )
    try:
        hours = int(hours_str)
        cnt = int(cnt_str)
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    if statist_rank not in STATIST_RANK_ORDER:
        await cb.answer("Неизвестный ранг статистов", show_alert=True)
        return

    # Redis-лок: предотвращает параллельный запуск нескольких походов.
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.campaign_launch_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    result = await campaign_service.start_campaign(
        session=session,
        user=user,
        resource_type=resource_id,
        rank=task_rank,
        duration_hours=hours,
        statist_count=cnt,
        statist_rank=statist_rank,
    )

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    camp = result["campaign"]
    res_cfg = CAMPAIGN_RESOURCE_MAP[resource_id]
    rank_cfg = CAMPAIGN_RANK_MAP[task_rank]

    text = (
        f"🚀 <b>Поход начался!</b>\n\n"
        f"{rank_cfg.emoji} Ранг {task_rank} | {res_cfg.emoji} {res_cfg.label}\n"
        f"⏱ Длительность: {_duration_label(hours)}\n"
        f"{_sr_emoji(statist_rank)} Отправлено: <b>{camp.statist_count}</b> бойцов ранга {statist_rank}\n"
        f"💪 Средняя мощь: <b>{fmt_num(camp.avg_power)}</b>\n\n"
        f"Возвращайся, когда истечёт время, и забери результат!"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗺 К походам", callback_data="campaigns_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("Поход начался! 🚀")


# ── Сбор результата ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("campaigns_collect:"))
async def cb_campaigns_collect(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        campaign_id = int(cb.data.split(":")[1])
    except (IndexError, ValueError):
        await cb.answer("Ошибка", show_alert=True)
        return

    # Redis-лок по ID похода: предотвращает двойной сбор наград.
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.campaign_collect_lock_key(campaign_id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("⏳ Подождите...", show_alert=False)
        return

    result = await campaign_service.collect_campaign(session, user, campaign_id)

    if not result["ok"]:
        await cb.answer(result.get("reason", "Ошибка"), show_alert=True)
        return

    res_cfg = CAMPAIGN_RESOURCE_MAP.get(result["resource_type"])
    rank_cfg = CAMPAIGN_RANK_MAP.get(result["rank"])

    if result["success"]:
        outcome_icon = "✅"
        outcome_text = "Успех!"
    else:
        outcome_icon = "❌"
        outcome_text = "Провал"

    res_line = ""
    if result["resource_gained"] > 0 and res_cfg:
        res_line = f"\n{res_cfg.emoji} Получено: <b>{fmt_num(result['resource_gained'])} {res_cfg.label}</b>"

    rank_line = f"{rank_cfg.emoji} Ранг {result['rank']}" if rank_cfg else f"Ранг {result['rank']}"

    text = (
        f"{outcome_icon} <b>Поход завершён — {outcome_text}</b>\n\n"
        f"{rank_line} | ⏱ {_duration_label(result['duration_hours'])}"
        f"{res_line}\n\n"
        f"👥 Отправлено: {result['statists_sent']}\n"
        f"👤 Вернулось:  <b>{result['statists_returned']}</b>\n"
        f"💀 Погибло:    <b>{result['statists_lost']}</b>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗺 К походам", callback_data="campaigns_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer("Результат получен!")


