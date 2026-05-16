from aiogram.fsm.state import State, StatesGroup


class AdminBroadcastStates(StatesGroup):
    waiting_body = State()
    waiting_confirm = State()


class AdminProductStates(StatesGroup):
    waiting_edit_price = State()


class AdminContactReplyStates(StatesGroup):
    waiting_text = State()
