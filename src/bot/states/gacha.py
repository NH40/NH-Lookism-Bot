from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class GachaStates(StatesGroup):
    waiting_count = State()  # сколько тикетов открыть разом
