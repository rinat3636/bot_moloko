from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from milk_bot.bot.config import is_admin
from milk_bot.bot.keyboards.reply import menu_keyboard_for
from milk_bot.bot.utils.menu_keyboard import answer_with_menu
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


def is_contact_state(state_str: str | None) -> bool:
    if not state_str:
        return False
    return state_str.startswith("ContactStates:")


@router.callback_query(F.data == "ig:n")
async def cb_ignore(cq: CallbackQuery) -> None:
    await cq.answer()


@router.message(Command("cancel"))
async def cmd_cancel_global(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if not current:
        await answer_with_menu(message, "Нечего отменять.")
        return
    if is_checkout_state(current):
        notice = "Оформление заказа отменено."
    elif is_admin_fsm_state(current):
        notice = "Действие в админ-панели отменено."
    elif is_search_state(current):
        notice = "Поиск отменён."
    elif is_contact_state(current):
        notice = "Обращение не отправлено."
    else:
        notice = "Действие отменено."
    await clear_fsm_with_menu(message, state, notice=notice)


async def _reply_busy(event: Message | CallbackQuery, text: str) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
    else:
        uid = event.from_user.id if event.from_user else 0
        await event.answer(text, reply_markup=menu_keyboard_for(uid))


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
    if is_contact_state(current):
        await _reply_busy(
            event,
            "Сначала отправьте обращение или отмените: /cancel",
        )
        return False
    return True
