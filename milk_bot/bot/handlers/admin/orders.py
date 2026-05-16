from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import get_settings
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.keyboards.inline import admin_order_status_keyboard
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.services import order as order_service

router = Router()

STATUS_LABELS = {
    "new": "🆕 Новые",
    "confirmed": "✅ Подтверждённые",
    "in_delivery": "🚚 В доставке",
    "delivered": "📬 Доставлены",
    "cancelled": "❌ Отменённые",
}


def _orders_filter_keyboard() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Все заказы", callback_data="of:all"))
    for code, label in STATUS_LABELS.items():
        b.row(InlineKeyboardButton(text=label, callback_data=f"of:st:{code}"))
    b.row(InlineKeyboardButton(text="📅 Доставка сегодня", callback_data="of:dt:today"))
    b.row(InlineKeyboardButton(text="📅 Доставка завтра", callback_data="of:dt:tomorrow"))
    b.row(InlineKeyboardButton(text="📅 Доставка 7 дней", callback_data="of:dt:week"))
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    return b


async def _render_orders_list(
    message,
    session: AsyncSession,
    *,
    title: str,
    status: str | None = None,
    delivery_date: date | None = None,
    delivery_from: date | None = None,
    delivery_to: date | None = None,
) -> None:
    orders = await order_service.list_orders_admin(
        session,
        status=status,
        delivery_date=delivery_date,
        delivery_from=delivery_from,
        delivery_to=delivery_to,
        limit=30,
    )
    if not orders:
        await message.edit_text(
            f"{title}\n\nЗаказов не найдено.",
            reply_markup=_orders_filter_keyboard().as_markup(),
        )
        return
    lines = [
        f"#{o.id} | {o.status} | {o.delivery_date:%d.%m} | {float(o.total):.0f} ₽"
        for o in orders
    ]
    b = InlineKeyboardBuilder()
    for o in orders[:12]:
        b.add(InlineKeyboardButton(text=f"#{o.id}", callback_data=f"ao:v:{o.id}"))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="🔍 Фильтры", callback_data="ad:or"))
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    await message.edit_text(
        f"{title}\n\n" + "\n".join(lines),
        reply_markup=b.as_markup(),
    )


async def open_orders_menu(message: Message, session: AsyncSession) -> None:
    await message.answer(
        "Заказы — выберите фильтр:",
        reply_markup=_orders_filter_keyboard().as_markup(),
    )


@router.callback_query(F.data == "ad:or", AdminFilter())
async def admin_orders_home(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    await cq.message.edit_text(
        "Заказы — выберите фильтр:",
        reply_markup=_orders_filter_keyboard().as_markup(),
    )


@router.callback_query(F.data == "of:all", AdminFilter())
async def orders_filter_all(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    await _render_orders_list(cq.message, session, title="Все заказы (последние 30)")


@router.callback_query(F.data.startswith("of:st:"), AdminFilter())
async def orders_filter_status(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    status = cq.data.split(":")[2]
    label = STATUS_LABELS.get(status, status)
    await _render_orders_list(
        cq.message, session, title=f"Заказы: {label}", status=status
    )


@router.callback_query(F.data.startswith("of:dt:"), AdminFilter())
async def orders_filter_date(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    kind = cq.data.split(":")[2]
    if kind == "today":
        await _render_orders_list(
            cq.message,
            session,
            title=f"Доставка {today:%d.%m.%Y}",
            delivery_date=today,
        )
    elif kind == "tomorrow":
        d = today + timedelta(days=1)
        await _render_orders_list(
            cq.message,
            session,
            title=f"Доставка {d:%d.%m.%Y}",
            delivery_date=d,
        )
    elif kind == "week":
        end = today + timedelta(days=7)
        await _render_orders_list(
            cq.message,
            session,
            title=f"Доставка {today:%d.%m} — {end:%d.%m}",
            delivery_from=today,
            delivery_to=end,
        )


@router.callback_query(F.data.startswith("ao:v:"), AdminFilter())
async def admin_order_view(cq: CallbackQuery, session: AsyncSession) -> None:
    oid = int(cq.data.split(":")[2])
    o = await order_service.get_order(session, oid)
    if not o:
        await cq.answer("Нет", show_alert=True)
        return
    await cq.answer()
    parts = [
        f"<b>Заказ #{o.id}</b> — {o.status}",
        f"👤 {o.full_name}, {o.phone}",
        f"📍 {o.address}",
        f"📅 {o.delivery_date:%d.%m.%Y}, {o.delivery_slot}",
        f"💵 {o.payment_method}",
        "",
        "Состав:",
    ]
    for it in o.items:
        parts.append(
            f"• {it.product_name} × {it.quantity} = {float(it.price * it.quantity):.2f} ₽"
        )
    parts.append(f"\n<b>Итого: {float(o.total):.2f} ₽</b>")
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
    try:
        order = await order_service.set_order_status(session, oid, status)
    except ValueError:
        await cq.answer("Недопустимый статус", show_alert=True)
        return
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
    try:
        order = await order_service.set_order_status(session, oid, "confirmed")
    except ValueError:
        await cq.answer("Ошибка статуса", show_alert=True)
        return
    await cq.answer("Принят")
    if order:
        await notifier_service.notify_order_status(bot, order.user_id, order)


@router.callback_query(F.data.startswith("ao:r:"), AdminFilter())
async def admin_reject(cq: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    oid = int(cq.data.split(":")[2])
    try:
        order = await order_service.set_order_status(session, oid, "cancelled")
    except ValueError:
        await cq.answer("Ошибка статуса", show_alert=True)
        return
    await cq.answer("Отклонён")
    if order:
        await notifier_service.notify_order_status(bot, order.user_id, order)


@router.callback_query(F.data.startswith("ao:c:"), AdminFilter())
async def admin_contact(cq: CallbackQuery, session: AsyncSession) -> None:
    oid = int(cq.data.split(":")[2])
    o = await order_service.get_order(session, oid)
    if not o:
        await cq.answer("Заказ не найден", show_alert=True)
        return
    await cq.answer(
        f"Клиент: {o.full_name}\nТелефон: {o.phone}\nUser ID: {o.user_id}",
        show_alert=True,
    )
