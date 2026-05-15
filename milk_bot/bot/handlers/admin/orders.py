from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from milk_bot.bot.db.models import Order
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.keyboards.inline import admin_main_keyboard, admin_order_status_keyboard
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.services import order as order_service

router = Router()


@router.callback_query(F.data == "ad:or", AdminFilter())
async def admin_orders_home(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    result = await session.execute(
        select(Order).options(selectinload(Order.items)).order_by(Order.id.desc()).limit(20)
    )
    orders = list(result.scalars().unique().all())
    if not orders:
        await cq.message.edit_text("Заказов пока нет.", reply_markup=admin_main_keyboard())
        return
    lines = [f"#{o.id} {o.status} {o.delivery_date} {float(o.total):.0f}₽" for o in orders]
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    b = InlineKeyboardBuilder()
    for o in orders[:10]:
        b.add(InlineKeyboardButton(text=f"#{o.id}", callback_data=f"ao:v:{o.id}"))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    await cq.message.edit_text("Последние заказы:\n" + "\n".join(lines), reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ao:v:"), AdminFilter())
async def admin_order_view(cq: CallbackQuery, session: AsyncSession) -> None:
    oid = int(cq.data.split(":")[2])
    o = await order_service.get_order(session, oid)
    if not o:
        await cq.answer("Нет", show_alert=True)
        return
    await cq.answer()
    parts = [
        f"<b>Заказ #{o.id}</b> {o.status}",
        f"{o.full_name} {o.phone}",
        f"{o.address}",
        f"{o.delivery_date} {o.delivery_slot}",
    ]
    for it in o.items:
        parts.append(f"• {it.product_name} ×{it.quantity}")
    parts.append(f"Итого {float(o.total):.2f} ₽")
    await cq.message.edit_text(
        "\n".join(parts),
        reply_markup=admin_order_status_keyboard(o.id, o.status),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("os:"), AdminFilter())
async def admin_set_status(
    cq: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    _, oid_s, status = cq.data.split(":", 2)
    oid = int(oid_s)
    order = await order_service.set_order_status(session, oid, status)
    await cq.answer("Статус обновлён")
    if order:
        await notifier_service.notify_order_status(bot, order.user_id, order)
    o = await order_service.get_order(session, oid)
    if o:
        await cq.message.edit_reply_markup(
            reply_markup=admin_order_status_keyboard(o.id, o.status)
        )


@router.callback_query(F.data.startswith("ao:a:"), AdminFilter())
async def admin_accept(cq: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    oid = int(cq.data.split(":")[2])
    order = await order_service.set_order_status(session, oid, "confirmed")
    await cq.answer("Принят")
    if order:
        await notifier_service.notify_order_status(bot, order.user_id, order)


@router.callback_query(F.data.startswith("ao:r:"), AdminFilter())
async def admin_reject(cq: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    oid = int(cq.data.split(":")[2])
    order = await order_service.set_order_status(session, oid, "cancelled")
    await cq.answer("Отклонён")
    if order:
        await notifier_service.notify_order_status(bot, order.user_id, order)


@router.callback_query(F.data.startswith("ao:c:"), AdminFilter())
async def admin_contact(cq: CallbackQuery) -> None:
    await cq.answer("Свяжитесь с клиентом вручную в Telegram по номеру из заказа.", show_alert=True)
