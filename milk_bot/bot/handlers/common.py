from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from milk_bot.bot.config import get_admin_ids, get_settings
from milk_bot.bot.keyboards.reply import main_menu_keyboard
from milk_bot.bot.utils.fsm import (
    clear_fsm_with_menu,
    is_admin_fsm_state,
    is_checkout_state,
)

router = Router()


@router.callback_query(F.data == "ig:n")
async def cb_ignore(cq: CallbackQuery) -> None:
    await cq.answer()


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    admins = get_admin_ids()
    access = "есть" if uid in admins else "нет"
    await message.answer(
        f"Ваш Telegram ID: <code>{uid}</code>\n"
        f"Доступ /admin: <b>{access}</b>\n\n"
        "Для админки добавьте этот ID в <b>ADMIN_IDS</b> на сервере.",
        parse_mode="HTML",
    )


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
    else:
        notice = "Действие отменено."
    await clear_fsm_with_menu(message, state, notice=notice)


async def block_if_busy_fsm(message: Message, state: FSMContext) -> bool:
    """True — можно обрабатывать пункт меню."""
    current = await state.get_state()
    if is_checkout_state(current):
        await message.answer(
            "Сейчас идёт оформление заказа. Завершите его или отмените: /cancel",
            reply_markup=main_menu_keyboard(),
        )
        return False
    if is_admin_fsm_state(current):
        await message.answer(
            "Сначала завершите действие в админке или нажмите /cancel",
            reply_markup=main_menu_keyboard(),
        )
        return False
    return True
