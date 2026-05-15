from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from milk_bot.bot.keyboards.reply import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Доставка молочной продукции до двери.\n"
        "Выберите раздел в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )
