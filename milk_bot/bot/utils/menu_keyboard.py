"""Нижняя (reply) клавиатура."""

from __future__ import annotations

from aiogram.types import Message

from milk_bot.bot.keyboards.reply import menu_keyboard_for


async def answer_with_menu(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    """Ответ с актуальным нижним меню (без снятия клавиатуры)."""
    uid = message.from_user.id if message.from_user else 0
    await message.answer(
        text,
        reply_markup=menu_keyboard_for(uid),
        parse_mode=parse_mode,
    )


async def keep_bottom_menu(message: Message) -> None:
    """Вернуть нижнее меню, если бот прислал только inline-кнопки в чате."""
    uid = message.from_user.id if message.from_user else 0
    await message.answer("·", reply_markup=menu_keyboard_for(uid))


async def answer_with_main_menu(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    await answer_with_menu(message, text, parse_mode=parse_mode)
