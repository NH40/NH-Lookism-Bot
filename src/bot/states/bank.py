from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BankStates(StatesGroup):
    take_amount = State()  # сумма заявки (данные: bank_id, kind)
    repay_amount = State()  # сумма погашения (данные: loan_id)
    create_capital = State()
    create_terms = State()  # «фикс почас пеня мин макс» (данные: capital)
    deposit = State()
    withdraw = State()
    terms = State()
    member = State()  # @ник участника
    approve_terms = State()  # условия банкира к договору (данные: loan_id)
