from aiogram.fsm.state import State, StatesGroup


class ProductQtyStates(StatesGroup):
    picking = State()
