from __future__ import annotations

from aiogram.types import CallbackQuery, Message, URLInputFile
from aiogram.types import InputMediaPhoto

from milk_bot.bot.db.models import Product


def product_photo(p: Product) -> str | URLInputFile:
    fid = p.photo_file_id
    if not fid:
        raise ValueError("no_photo")
    if fid.startswith("http://") or fid.startswith("https://"):
        return URLInputFile(fid)
    return fid


async def show_product_card(
    target: Message | CallbackQuery,
    *,
    text: str,
    reply_markup,
    product: Product,
    parse_mode: str = "HTML",
) -> None:
    message = target if isinstance(target, Message) else target.message
    assert message is not None
    bot = message.bot
    chat_id = message.chat.id

    try:
        photo = product_photo(product)
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
