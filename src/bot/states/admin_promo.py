from aiogram.fsm.state import State, StatesGroup


class AdminPromoStates(StatesGroup):
    waiting_create = State()
