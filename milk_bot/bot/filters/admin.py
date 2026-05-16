from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery

from milk_bot.bot.config import get_settings


class AdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if user is None:
            return False
        return user.id in get_settings().admin_id_list()
