from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from milk_bot.bot.utils.menu_keyboard import answer_with_menu


async def clear_fsm_with_menu(message: Message, state: FSMContext, *, notice: str | None = None) -> None:
    await state.clear()
    text = notice or "Действие отменено."
    await answer_with_menu(message, text)


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
        from milk_bot.bot.keyboards.reply import menu_keyboard_for

        uid = event.from_user.id if event.from_user else 0
        await event.answer(busy_notice, reply_markup=menu_keyboard_for(uid))
    return False


async def clear_state_if_set(state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
