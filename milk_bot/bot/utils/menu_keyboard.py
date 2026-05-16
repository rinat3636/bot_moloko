"""Принудительное обновление нижней (reply) клавиатуры в Telegram."""

from __future__ import annotations

from aiogram.types import Message

from milk_bot.bot.keyboards.reply import main_menu_keyboard, remove_keyboard


async def answer_with_main_menu(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    """Снять старую клавиатуру и показать актуальное меню внизу экрана."""
    await message.answer("·", reply_markup=remove_keyboard())
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode=parse_mode)
