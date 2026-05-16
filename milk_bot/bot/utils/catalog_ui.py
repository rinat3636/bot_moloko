from __future__ import annotations

from aiogram import Bot
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import Product
from milk_bot.bot.services.photo_cache import resolve_product_photo


async def product_photo_media(
    bot: Bot,
    session: AsyncSession,
    product: Product,
) -> str:
    fid = await resolve_product_photo(bot, session, product)
    if not fid:
        raise ValueError("no_photo")
    return fid


async def show_product_card(
    target: Message | CallbackQuery,
    *,
    text: str,
    reply_markup,
    product: Product,
    session: AsyncSession,
    parse_mode: str = "HTML",
) -> None:
    message = target if isinstance(target, Message) else target.message
    assert message is not None
    bot = message.bot
    chat_id = message.chat.id

    try:
        photo = await product_photo_media(bot, session, product)
    except ValueError:
        if isinstance(target, CallbackQuery):
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return

    if isinstance(target, CallbackQuery) and message.photo:
        media = InputMediaPhoto(media=photo, caption=text[:1024], parse_mode=parse_mode)
        await message.edit_media(media=media, reply_markup=reply_markup)
        return

    if isinstance(target, CallbackQuery):
        await message.delete()
        await bot.send_photo(
            chat_id,
            photo,
            caption=text[:1024],
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    else:
        await bot.send_photo(
            chat_id,
            photo,
            caption=text[:1024],
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
