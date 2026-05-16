from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OrderCheckoutStates(StatesGroup):
    waiting_contacts = State()
    waiting_date = State()
    waiting_time = State()
    waiting_payment = State()
    waiting_confirm = State()
