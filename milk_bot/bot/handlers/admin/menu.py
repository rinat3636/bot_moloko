from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.keyboards.inline import admin_main_keyboard

router = Router()


@router.message(Command("admin"), AdminFilter())
async def admin_open(message: Message) -> None:
    await message.answer("Панель администратора:", reply_markup=admin_main_keyboard())


@router.callback_query(F.data == "ad:hm", AdminFilter())
async def admin_home(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.edit_text("Панель администратора:", reply_markup=admin_main_keyboard())
