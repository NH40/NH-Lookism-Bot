from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BankStates(StatesGroup):
    take_amount = State()  # сумма кредита (данные: bank_id)
    repay_amount = State()  # сумма погашения (данные: loan_id)
    create_capital = State()
    create_terms = State()  # «процент мин макс» (данные: capital)
    deposit = State()
    withdraw = State()
    terms = State()
