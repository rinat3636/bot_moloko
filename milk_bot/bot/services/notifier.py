from __future__ import annotations

from aiogram import Bot
from loguru import logger

from milk_bot.bot.config import get_settings
from milk_bot.bot.db.models import Order
from milk_bot.bot.keyboards.inline import admin_order_keyboard
from milk_bot.bot.utils.formatters import format_money, order_lines_preview


def _payment_label(method: str) -> str:
    if method == "cash":
        return "Наличными при получении"
    if method == "online":
        return "Онлайн (YooKassa, не активно)"
    return method


async def notify_new_order(bot: Bot, order: Order) -> None:
    settings = get_settings()
    lines = order_lines_preview(order)
    text = (
        f"🆕 Заказ #{order.id}\n"
        f"👤 {order.full_name}, {order.phone}\n"
        f"📍 {order.address}\n"
        f"📅 {order.delivery_date:%d.%m.%Y}, {order.delivery_slot}\n"
        f"💵 {_payment_label(order.payment_method)}\n\n"
        f"Состав:\n{lines}\n\n"
        f"Итого: {format_money(order.total)}"
    )
    kb = admin_order_keyboard(order.id)
    for aid in settings.admin_id_list():
        try:
            await bot.send_message(aid, text, reply_markup=kb)
        except Exception as exc:  # noqa: BLE001
            logger.warning("notify admin {} failed: {}", aid, exc)
    chat = settings.orders_chat_id_int()
    if chat is not None:
        try:
            await bot.send_message(chat, text, reply_markup=kb)
        except Exception as exc:  # noqa: BLE001
            logger.warning("notify orders chat failed: {}", exc)


async def notify_admins_order_cancelled(bot: Bot, order: Order) -> None:
    settings = get_settings()
    text = (
        f"❌ Клиент отменил заказ #{order.id}\n"
        f"👤 {order.full_name}, {order.phone}\n"
        f"📅 {order.delivery_date:%d.%m.%Y}, {order.delivery_slot}"
    )
    for aid in settings.admin_id_list():
        try:
            await bot.send_message(aid, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("notify admin cancel {} failed: {}", aid, exc)
    chat = settings.orders_chat_id_int()
    if chat is not None:
        try:
            await bot.send_message(chat, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("notify orders chat cancel failed: {}", exc)


async def notify_order_status(bot: Bot, user_id: int, order: Order) -> None:
    labels = {
        "new": "новый",
        "confirmed": "подтверждён",
        "in_delivery": "в доставке",
        "delivered": "доставлен",
        "cancelled": "отменён",
    }
    ru = labels.get(order.status, order.status)
    try:
        await bot.send_message(
            user_id,
            f"Заказ #{order.id}: статус обновлён — <b>{ru}</b>.",
            parse_mode="HTML",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("notify user {} status: {}", user_id, exc)
