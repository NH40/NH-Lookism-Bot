from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CasinoStates(StatesGroup):
    # Размер ставки; игра и валюта ставки — в данных состояния (game, kind, code).
    waiting_stake = State()
