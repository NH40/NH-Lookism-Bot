from aiogram.fsm.state import State, StatesGroup


class AdminReferralStates(StatesGroup):
    waiting_name = State()
