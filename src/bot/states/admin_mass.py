from aiogram.fsm.state import State, StatesGroup


class AdminMassStates(StatesGroup):
    waiting_clan = State()
    waiting_content = State()
    waiting_button = State()
    waiting_amount = State()
