from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from milk_bot.bot.config import get_admin_ids
from milk_bot.bot.keyboards.inline import admin_main_keyboard
from milk_bot.bot.keyboards.reply import main_menu_keyboard


async def clear_fsm_with_menu(message: Message, state: FSMContext, *, notice: str | None = None) -> None:
    await state.clear()
    text = notice or "Действие отменено."
    await message.answer(text, reply_markup=main_menu_keyboard())
    uid = message.from_user.id if message.from_user else 0
    if uid in get_admin_ids():
        await message.answer(
            "Панель администратора:",
            reply_markup=admin_main_keyboard(),
        )


def is_checkout_state(state_str: str | None) -> bool:
    if not state_str:
        return False
    return state_str.startswith("OrderCheckoutStates:")


def is_admin_fsm_state(state_str: str | None) -> bool:
    if not state_str:
        return False
    return state_str.startswith("AdminProductStates:") or state_str.startswith(
        "AdminBroadcastStates:"
    )
