"""Безопасное обновление сообщения (текст или фото)."""

from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def edit_or_answer(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
) -> None:
    if message.photo:
        kwargs: dict = {"reply_markup": reply_markup}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        await message.answer(text, **kwargs)
        return
    kwargs: dict = {"reply_markup": reply_markup}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest:
        await message.answer(text, **kwargs)
