"""Нижняя (reply) клавиатура: принудительное обновление в Telegram."""

from __future__ import annotations

from aiogram.types import Message

from milk_bot.bot.keyboards.reply import main_menu_keyboard, remove_keyboard


async def pin_main_menu(message: Message) -> None:
    """Поставить актуальные кнопки внизу экрана (перед ответом с inline-кнопками)."""
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
    msg = await bot.send_message(chat_id, ".", reply_markup=main_menu_keyboard())
    try:
        await bot.delete_message(chat_id, msg.message_id)
    except Exception:  # noqa: BLE001
        pass


async def answer_with_main_menu(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    """Сбросить старую клавиатуру и отправить текст с актуальным меню внизу."""
    await pin_main_menu(message)
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode=parse_mode)
