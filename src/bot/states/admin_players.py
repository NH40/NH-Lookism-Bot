from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminGiveStates(StatesGroup):
    # Данные: uid, kind (`GIVE_KIND_*`), code (для ресурса).
    waiting_input = State()


class AdminDevStates(StatesGroup):
    waiting_rank = State()  # данные: uid, stat


class AdminPunishStates(StatesGroup):
    waiting_reason = State()  # данные: uid, key (срок)
