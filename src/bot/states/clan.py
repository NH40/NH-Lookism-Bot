from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ClanStates(StatesGroup):
    waiting_name = State()  # название нового клана
    waiting_edit_name = State()
    waiting_edit_description = State()
    waiting_image = State()  # аватарка (фото)
    waiting_invite = State()  # @юзернейм приглашённого
    waiting_donate = State()  # взнос в казну
    waiting_exchange = State()  # сумма обменника (кому и что — в данных)
    waiting_garrison = State()  # сколько внести/забрать (что — в данных)
    waiting_mercs = State()  # сколько наёмников в роту (ранг — в данных)
    waiting_shop_tickets = State()  # сколько тикетов каждому участнику
