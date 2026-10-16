from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminSeasonStates(StatesGroup):
    waiting_player = State()  # @ник/id игрока
    waiting_xp = State()  # количество опыта пасса (user_id в FSM-данных)
