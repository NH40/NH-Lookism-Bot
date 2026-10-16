from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminClansStates(StatesGroup):
    waiting_clan = State()  # название или id клана
    waiting_value = State()  # число для поля (clan_id и field в FSM-данных)
