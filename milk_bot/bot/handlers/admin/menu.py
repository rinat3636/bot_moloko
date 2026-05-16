from aiogram import F, Router
from aiogram.types import CallbackQuery

from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.keyboards.reply import admin_menu_keyboard

router = Router()


@router.callback_query(F.data == "ad:hm", AdminFilter())
async def admin_home(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.answer(
        "Управление — кнопки внизу экрана.",
        reply_markup=admin_menu_keyboard(),
    )
