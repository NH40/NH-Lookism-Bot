"""Тикеты в поддержку (бот, 2026-11-20): игрок — /support и кнопка в настройках; сотрудники — раздел админки
«🆘 Поддержка» (саппорт, модераторы, админы): очередь, переписка, ответ (пуш игроку), закрытие."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_SUPPORT
from bot.services import support as svc
from bot.services.admin import roles
from bot.utils.formatting import esc
from bot.utils.notify import notify

router = Router(name="support")
CB_SUP_OPEN = "sup:open"
CB_SUP_WRITE = "sup:w"
CB_ADM_TICKET = "adm:sup:t:"  # + id
CB_ADM_REPLY = "adm:sup:r:"  # + id
CB_ADM_CLOSE = "adm:sup:c:"  # + id
SEP = "━━━━━━━━━━━━━━━━━━"
_ADMIN_LIST = f"{CB_ADMIN_SECTION_PREFIX}{SECTION_SUPPORT}"


class SupportStates(StatesGroup):
    waiting_text = State()
    waiting_reply = State()


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _thread_text(th: svc.Thread | None, *, staff_view: bool) -> str:
    if th is None:
        return f"🆘 <b>Поддержка</b>\n{SEP}\nОбращений пока нет. Опиши проблему — ответят модераторы или админы."
    status = {svc.OPEN: "⏳ ждёт ответа", svc.ANSWERED: "✅ есть ответ", svc.CLOSED: "🔒 закрыто"}[th.ticket.status]
    lines = [f"🆘 <b>Обращение #{th.ticket.id}</b> · {status}" + (f" · игрок {th.ticket.user_id}" if staff_view else ""), SEP]
    for m in th.messages[-12:]:
        who = "🛡 Поддержка" if m.staff else ("👤 Игрок" if staff_view else "👤 Ты")
        lines.append(f"<b>{who}:</b> {esc(m.text)}")
    return "\n".join(lines)[-3900:]


async def _show_mine(target: Message, session: AsyncSession, user_id: int, edit: bool = False) -> None:
    th = await svc.my_thread(session, user_id)
    markup = InlineKeyboardMarkup(inline_keyboard=[[_b("✍️ Написать", CB_SUP_WRITE)]])
    text = _thread_text(th, staff_view=False)
    if edit:
        try:
            await target.edit_text(text, reply_markup=markup)
            return
        except Exception:  # noqa: BLE001
            pass
    await target.answer(text, reply_markup=markup)


@router.message(Command("support"))
async def cmd_support(message: Message, session: AsyncSession) -> None:
    await _show_mine(message, session, message.from_user.id)


@router.callback_query(F.data == CB_SUP_OPEN)
async def cb_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _show_mine(callback.message, session, callback.from_user.id, edit=True)


@router.callback_query(F.data == CB_SUP_WRITE)
async def cb_write(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportStates.waiting_text)
    await callback.answer()
    await callback.message.answer(f"✍️ Напиши сообщение в поддержку одним сообщением (до {svc.MAX_TEXT} символов).")


@router.message(StateFilter(SupportStates.waiting_text), F.text)
async def on_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    try:
        ticket = await svc.write(session, message.from_user.id, message.text)
    except svc.SupportError:
        await message.answer(f"Сообщение — от 1 до {svc.MAX_TEXT} символов. Попробуй ещё раз.")
        return
    await state.clear()
    await message.answer(f"✅ Отправлено в поддержку (обращение #{ticket.id}). Ответ придёт сюда пушем.")


# --- сотрудники ---

async def _staff(callback: CallbackQuery, session: AsyncSession) -> bool:
    if not await roles.can(session, callback.from_user.id, SECTION_SUPPORT):
        await callback.answer("Нет доступа.", show_alert=True)
        return False
    return True


@router.callback_query(F.data == _ADMIN_LIST)
async def cb_queue(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await _staff(callback, session):
        return
    await state.clear()
    items, waiting = await svc.queue(session)
    rows = [[_b(f"#{t.id} · {preview or '…'}", f"{CB_ADM_TICKET}{t.id}")] for t, preview in items]
    rows.append([_b("◀️ Назад", CB_ADMIN_OPEN)])
    await callback.answer()
    await callback.message.edit_text(f"🆘 <b>Поддержка</b>\n{SEP}\nЖдут ответа: <b>{waiting}</b>" + ("" if items else "\nОчередь пуста."),
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith(CB_ADM_TICKET))
async def cb_ticket(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _staff(callback, session):
        return
    tid = int(callback.data.removeprefix(CB_ADM_TICKET))
    th = await svc.thread(session, tid)
    rows = [[_b("✍️ Ответить", f"{CB_ADM_REPLY}{tid}"), _b("🔒 Закрыть", f"{CB_ADM_CLOSE}{tid}")], [_b("◀️ К очереди", _ADMIN_LIST)]]
    await callback.answer()
    await callback.message.edit_text(_thread_text(th, staff_view=True), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith(CB_ADM_REPLY))
async def cb_reply(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await _staff(callback, session):
        return
    await state.set_state(SupportStates.waiting_reply)
    await state.update_data(ticket=int(callback.data.removeprefix(CB_ADM_REPLY)))
    await callback.answer()
    await callback.message.answer("✍️ Напиши ответ игроку одним сообщением.")


@router.message(StateFilter(SupportStates.waiting_reply), F.text)
async def on_reply(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_SUPPORT):
        return
    tid = (await state.get_data()).get("ticket")
    try:
        user_id = await svc.reply(session, message.from_user.id, tid, message.text)
    except svc.SupportError:
        await message.answer("Не получилось — обращение пропало или текст пустой.")
        return
    await state.clear()
    await notify(message.bot, user_id, f"🛡 <b>Ответ поддержки</b> (обращение #{tid}):\n{esc(message.text)}\n\nОтветить — /support")
    await message.answer("✅ Ответ отправлен.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_b("◀️ К очереди", _ADMIN_LIST)]]))


@router.callback_query(F.data.startswith(CB_ADM_CLOSE))
async def cb_close(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _staff(callback, session):
        return
    tid = int(callback.data.removeprefix(CB_ADM_CLOSE))
    user_id = await svc.close(session, tid)
    await callback.answer("Закрыто.")
    if user_id:
        await notify(callback.bot, user_id, f"🔒 Обращение #{tid} закрыто. Если вопрос остался — напиши снова: /support")
    items, waiting = await svc.queue(session)
    rows = [[_b(f"#{t.id} · {preview or '…'}", f"{CB_ADM_TICKET}{t.id}")] for t, preview in items] + [[_b("◀️ Назад", CB_ADMIN_OPEN)]]
    await callback.message.edit_text(f"🆘 <b>Поддержка</b>\n{SEP}\nЖдут ответа: <b>{waiting}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
