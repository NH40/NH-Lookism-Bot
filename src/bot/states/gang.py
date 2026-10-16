from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class GangStates(StatesGroup):
    waiting_name = State()
    # Своё число бойцов для переноса части отряда; в FSM-данных — rank/stars/level/from_camp.
    waiting_squad_amount = State()
