from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class DonateStates(StatesGroup):
    waiting_amount = State()  # своя сумма пополнения
