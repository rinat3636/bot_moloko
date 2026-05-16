from aiogram.fsm.state import State, StatesGroup


class AdminBroadcastStates(StatesGroup):
    waiting_body = State()
    waiting_confirm = State()


class AdminCategoryStates(StatesGroup):
    waiting_name = State()


class AdminProductStates(StatesGroup):
    choosing_category = State()
    waiting_name = State()
    waiting_price = State()
    waiting_description = State()
    waiting_photo = State()
    waiting_edit_price = State()
    waiting_edit_name = State()
    waiting_edit_description = State()
    waiting_edit_photo = State()
