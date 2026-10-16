from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ExchangeStates(StatesGroup):
    # Мастер предложения: количество предмета, цена/мин. ставка, юзернейм для обмена — шаг и
    # собранные поля в данных состояния. Своя ставка на аукционе — отдельно.
    waiting_amount = State()
    waiting_price = State()
    waiting_username = State()
    waiting_bid = State()
