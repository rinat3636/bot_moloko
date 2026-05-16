from __future__ import annotations

from aiogram.types import Update


def chat_id_from_update(update: Update | None) -> int | None:
    if update is None:
        return None
    if update.message:
        return update.message.chat.id
    if update.edited_message:
        return update.edited_message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.channel_post:
        return update.channel_post.chat.id
    return None


def user_id_from_update(update: Update | None) -> int | None:
    if update is None:
        return None
    if update.message and update.message.from_user:
        return update.message.from_user.id
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    return None
