from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from milk_bot.bot.keyboards.reply import main_menu_keyboard
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Здравствуйте! Доставка молочной продукции до двери.\n"
        "Выберите раздел в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "ℹ️ О доставке")
async def about_delivery(message: Message, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm

    if not await block_if_busy_fsm(message, state):
        return
    await message.answer(
        "Доставка молочной продукции по Москве (MVP — одно ТСЖ).\n"
        "Интервалы и дата выбираются при оформлении заказа.\n"
        "Оплата на MVP — наличными при получении.\n"
        "Минимальная сумма заказа задаётся администратором в настройках.",
    )


@router.message(F.text == "📞 Контакты")
async def contacts(message: Message, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm

    if not await block_if_busy_fsm(message, state):
        return
    await message.answer(
        "Связь с администратором — через этого бота после оформления заказа.\n"
        "Телефон для связи уточняйте у управляющей компании вашего ТСЖ.",
    )
