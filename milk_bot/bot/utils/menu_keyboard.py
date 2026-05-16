"""Нижняя (reply) клавиатура: принудительное обновление в Telegram."""

from __future__ import annotations

from aiogram.types import Message

from milk_bot.bot.keyboards.reply import menu_keyboard_for, remove_keyboard


async def pin_menu(message: Message) -> None:
    """Поставить актуальные кнопки внизу (клиент или админ)."""
    uid = message.from_user.id if message.from_user else 0
    kb = menu_keyboard_for(uid)
    bot = message.bot
    chat_id = message.chat.id
    try:
        tmp = await bot.send_message(chat_id, ".", reply_markup=remove_keyboard())
        try:
            await bot.delete_message(chat_id, tmp.message_id)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    msg = await bot.send_message(chat_id, ".", reply_markup=kb)
    try:
        await bot.delete_message(chat_id, msg.message_id)
    except Exception:  # noqa: BLE001
        pass


async def pin_main_menu(message: Message) -> None:
    """Совместимость: обновить нижнее меню с учётом роли пользователя."""
    await pin_menu(message)


async def answer_with_menu(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    uid = message.from_user.id if message.from_user else 0
    await pin_menu(message)
    await message.answer(
        text,
        reply_markup=menu_keyboard_for(uid),
        parse_mode=parse_mode,
    )


async def answer_with_main_menu(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    await answer_with_menu(message, text, parse_mode=parse_mode)
