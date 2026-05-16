from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.handlers.common import block_if_busy_fsm
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.services import order as order_service

router = Router()


@router.message(F.text == "📦 Мои заказы")
async def my_orders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await block_if_busy_fsm(message, state):
        return
    uid = message.from_user.id
    orders = await order_service.list_user_orders(session, uid, limit=10)
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return
    lines = [
        f"#{o.id} | {o.created_at:%d.%m.%Y} | {o.status} | {float(o.total):.2f} ₽"
        for o in orders
    ]
    await message.answer("Ваши заказы:\n" + "\n".join(lines))
    b = InlineKeyboardBuilder()
    for o in orders:
        b.button(text=f"#{o.id}", callback_data=f"mo:{o.id}")
    b.adjust(4)
    await message.answer("Подробности:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("mo:"))
async def order_detail(cq: CallbackQuery, session: AsyncSession) -> None:
    oid = int(cq.data.split(":")[1])
    o = await order_service.get_order(session, oid)
    if not o or o.user_id != cq.from_user.id:
        await cq.answer("Заказ не найден", show_alert=True)
        return
    parts = [
        f"<b>Заказ #{o.id}</b>",
        f"Статус: {o.status}",
        f"Сумма: {float(o.total):.2f} ₽",
        f"Адрес: {o.address}",
        f"Дата: {o.delivery_date:%d.%m.%Y} {o.delivery_slot}",
        "Состав:",
    ]
    for it in o.items:
        parts.append(f"• {it.product_name} × {it.quantity} = {float(it.price * it.quantity):.2f} ₽")
    text = "\n".join(parts)
    kb = None
    if o.status == "new" and await order_service.can_customer_cancel(session, o):
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"mc:{o.id}")]
            ]
        )
    await cq.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("mc:"))
async def cancel_my(cq: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    oid = int(cq.data.split(":")[1])
    o = await order_service.get_order(session, oid)
    if not o or o.user_id != cq.from_user.id:
        await cq.answer("Нельзя", show_alert=True)
        return
    if not await order_service.can_customer_cancel(session, o):
        await cq.answer("Отмена недоступна", show_alert=True)
        return
    await order_service.cancel_order_customer(session, o)
    await notifier_service.notify_admins_order_cancelled(bot, o)
    await cq.answer("Заказ отменён")
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
