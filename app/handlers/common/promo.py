from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.keyboards.common import back_kb
from ._common import CommonFSM

router = Router()


# ── Промокод ─────────────────────────────────────────────────────────────────

@router.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext):
    await state.set_state(CommonFSM.waiting_promo)
    await message.answer(
        "🎁 Введите промокод:",
        reply_markup=back_kb("main_menu"),
    )


@router.message(CommonFSM.waiting_promo)
async def msg_promo(message: Message, session: AsyncSession, user: User, state: FSMContext):
    from app.services.promo_service import promo_service
    from app.services.cooldown_service import cooldown_service
    await state.clear()
    code = message.text.strip()

    lock_key = cooldown_service.promo_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await message.answer("❌ Подожди...", reply_markup=back_kb("main_menu"))
        return

    result = await promo_service.use_promo(session, user, code)
    if result["ok"]:
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"🎁 Получено:\n{result['summary']}",
            parse_mode="HTML",
            reply_markup=back_kb("main_menu"),
        )
    else:
        await message.answer(
            f"❌ {result['reason']}",
            reply_markup=back_kb("main_menu"),
            parse_mode="HTML",
        )
