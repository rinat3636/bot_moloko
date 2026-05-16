"""Нижнее меню администратора (reply-кнопки)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.handlers.admin.catalog import open_prices_menu
from milk_bot.bot.handlers.admin.orders import open_orders_menu
from milk_bot.bot.handlers.admin.stats import send_stats_report
from milk_bot.bot.keyboards.reply import (
    ADMIN_BROADCAST,
    ADMIN_ORDERS,
    ADMIN_PRICES,
    ADMIN_STATS,
)
from milk_bot.bot.states.admin import AdminBroadcastStates
from milk_bot.bot.utils.fsm import clear_state_if_set

router = Router()


@router.message(F.text == ADMIN_ORDERS, AdminFilter())
async def reply_admin_orders(message: Message, session: AsyncSession) -> None:
    await open_orders_menu(message, session)


@router.message(F.text == ADMIN_PRICES, AdminFilter())
async def reply_admin_prices(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await clear_state_if_set(state)
    await open_prices_menu(message, session)


@router.message(F.text == ADMIN_STATS, AdminFilter())
async def reply_admin_stats(message: Message, session: AsyncSession) -> None:
    await send_stats_report(message, session)


@router.message(F.text == ADMIN_BROADCAST, AdminFilter())
async def reply_admin_broadcast(message: Message, state: FSMContext) -> None:
    await clear_state_if_set(state)
    await state.set_state(AdminBroadcastStates.waiting_body)
    await message.answer(
        "Пришлите текст рассылки. Можно фото с подписью.\nОтмена: /cancel",
    )
