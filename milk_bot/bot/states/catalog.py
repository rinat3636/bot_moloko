from aiogram.fsm.state import State, StatesGroup


class ProductQtyStates(StatesGroup):
    picking = State()


class SearchStates(StatesGroup):
    waiting_query = State()
    browsing = State()
