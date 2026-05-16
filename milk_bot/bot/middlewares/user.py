from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import User


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]
        from_user = getattr(event, "from_user", None)
        if from_user is None and hasattr(event, "message") and event.message:
            from_user = event.message.from_user
        if from_user is None and hasattr(event, "callback_query") and event.callback_query:
            from_user = event.callback_query.from_user
        if from_user is None and hasattr(event, "edited_message") and event.edited_message:
            from_user = event.edited_message.from_user
        if from_user is None:
            return await handler(event, data)

        user = await session.scalar(select(User).where(User.id == from_user.id))
        if user is None:
            user = User(
                id=from_user.id,
                username=from_user.username,
                full_name=from_user.full_name,
            )
            session.add(user)
            await session.flush()
        else:
            user.username = from_user.username
            user.full_name = from_user.full_name

        if user.is_blocked:
            if isinstance(event, Message):
                await event.answer("Доступ к боту ограничён. Обратитесь к администратору.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ ограничён", show_alert=True)
            return None

        data["db_user"] = user
        return await handler(event, data)
