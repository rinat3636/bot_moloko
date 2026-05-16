from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from milk_bot.bot.keyboards.reply import main_menu_keyboard
from milk_bot.bot.utils.fsm import (
    clear_fsm_with_menu,
    is_admin_fsm_state,
    is_checkout_state,
)

router = Router()


def is_search_state(state_str: str | None) -> bool:
    if not state_str:
        return False
    return state_str.startswith("SearchStates:")


@router.callback_query(F.data == "ig:n")
async def cb_ignore(cq: CallbackQuery) -> None:
    await cq.answer()


@router.message(Command("cancel"))
async def cmd_cancel_global(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if not current:
        await message.answer("Нечего отменять.", reply_markup=main_menu_keyboard())
        return
    if is_checkout_state(current):
        notice = "Оформление заказа отменено."
    elif is_admin_fsm_state(current):
        notice = "Действие в админ-панели отменено."
    elif is_search_state(current):
        notice = "Поиск отменён."
    else:
        notice = "Действие отменено."
    await clear_fsm_with_menu(message, state, notice=notice)


async def _reply_busy(event: Message | CallbackQuery, text: str) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
    else:
        await event.answer(text, reply_markup=main_menu_keyboard())


async def block_if_busy_fsm(event: Message | CallbackQuery, state: FSMContext) -> bool:
    """True — можно обрабатывать действие."""
    current = await state.get_state()
    if is_checkout_state(current):
        await _reply_busy(
            event,
            "Сейчас идёт оформление заказа. Завершите его или отмените: /cancel",
        )
        return False
    if is_admin_fsm_state(current):
        await _reply_busy(
            event,
            "Сначала завершите действие в админке или нажмите /cancel",
        )
        return False
    if current and current.startswith("ProductQtyStates:"):
        await _reply_busy(
            event,
            "Сначала завершите выбор товара (назад) или отмените: /cancel",
        )
        return False
    return True
