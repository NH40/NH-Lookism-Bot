from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    # Кодовое слово беты; что с ним делать (включить / сменить) — в FSM-данных
    # (`constant/admin.BETA_CODE_MODE_KEY`).
    waiting_beta_code = State()
    waiting_player_query = State()  # поиск игрока: @ник или id
