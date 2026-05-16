from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

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


def is_catalog_qty_state(state_str: str | None) -> bool:
    if not state_str:
        return False
    return state_str.startswith("ProductQtyStates:")


def is_admin_fsm_state(state_str: str | None) -> bool:
    if not state_str:
        return False
    return state_str.startswith("AdminProductStates:") or state_str.startswith(
        "AdminBroadcastStates:"
    )


def is_checkout_callback(data: str | None) -> bool:
    if not data:
        return False
    return data.startswith(("dl:", "sl:", "pay:", "ord:"))


async def block_if_busy_fsm(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    allow_checkout_callbacks: bool = False,
) -> bool:
    """True — можно обрабатывать действие (не занят оформлением / админ-вводом)."""
    current = await state.get_state()
    if not current:
        return True

    if allow_checkout_callbacks and isinstance(event, CallbackQuery):
        if is_checkout_callback(event.data):
            return True

    busy_notice: str | None = None
    if is_checkout_state(current):
        busy_notice = "Сейчас идёт оформление заказа. Завершите его или отмените: /cancel"
    elif is_admin_fsm_state(current):
        busy_notice = "Сначала завершите действие в админке или нажмите /cancel"
    elif is_catalog_qty_state(current):
        busy_notice = "Сначала завершите выбор товара (назад) или отмените: /cancel"

    if not busy_notice:
        return True

    if isinstance(event, CallbackQuery):
        await event.answer(busy_notice, show_alert=True)
    else:
        await event.answer(busy_notice, reply_markup=main_menu_keyboard())
    return False


async def clear_state_if_set(state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
