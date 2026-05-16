from __future__ import annotations

import html
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import get_settings
from milk_bot.bot.keyboards.inline import (
    confirm_order_keyboard,
    delivery_dates_keyboard,
    delivery_slots_keyboard,
    payment_keyboard,
)
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.services import order as order_service
from milk_bot.bot.services import payment_yookassa
from milk_bot.bot.states.order import OrderCheckoutStates
from milk_bot.bot.utils.formatters import format_money
from milk_bot.bot.utils.order_checkout import is_allowed_delivery_date, is_allowed_delivery_slot
from milk_bot.bot.utils.validators import parse_checkout_contacts

router = Router()


async def start_order_fsm_from_cart(
    cq: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    uid = cq.from_user.id
    lines = await catalog_service.cart_lines(session, uid)
    if not lines:
        await cq.answer("Корзина пуста", show_alert=True)
        return
    try:
        await order_service.get_cart_checkout_summary(session, uid)
    except ValueError as e:
        code = str(e)
        if code == "inactive_only":
            await cq.answer(
                "В корзине только недоступные товары. Обновите корзину.",
                show_alert=True,
            )
        elif code == "zero_total":
            await cq.answer(
                "У товаров в корзине цена 0 ₽. Администратор выставит цены в разделе «Цены».",
                show_alert=True,
            )
        else:
            await cq.answer("Корзина пуста", show_alert=True)
        return
    await state.clear()
    await cq.answer()
    await state.set_state(OrderCheckoutStates.waiting_contacts)
    await cq.message.edit_text(
        "<b>Оформление заказа</b>\n\n"
        "Отправьте <b>одним сообщением</b> три строки:\n"
        "1) имя\n"
        "2) телефон\n"
        "3) адрес доставки\n\n"
        "Пример:\n"
        "<code>Ринат\n"
        "89001234567\n"
        "ул. Пример, д. 1, кв. 15</code>\n\n"
        "Отмена: /cancel",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ord:x")
async def cb_cancel_inline(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.clear()
    await cq.message.edit_text("Оформление отменено.")


@router.message(OrderCheckoutStates.waiting_contacts, F.text)
async def step_contacts(message: Message, state: FSMContext) -> None:
    ok, err, data = parse_checkout_contacts(message.text or "")
    if not ok or data is None:
        await message.answer(err)
        return
    await state.update_data(**data)
    await state.set_state(OrderCheckoutStates.waiting_date)
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    await message.answer(
        "Выберите дату доставки:\n\nОтмена: /cancel",
        reply_markup=delivery_dates_keyboard(today),
    )


@router.callback_query(OrderCheckoutStates.waiting_date, F.data.startswith("dl:"))
async def step_date_cb(cq: CallbackQuery, state: FSMContext) -> None:
    try:
        d = date.fromisoformat(cq.data.split(":", 1)[1])
    except ValueError:
        await cq.answer("Некорректная дата", show_alert=True)
        return
    if not is_allowed_delivery_date(d):
        await cq.answer("Эта дата недоступна для доставки", show_alert=True)
        return
    await cq.answer()
    await state.update_data(delivery_date=d.isoformat())
    await state.set_state(OrderCheckoutStates.waiting_time)
    await cq.message.edit_text(
        "Выберите интервал доставки:",
        reply_markup=delivery_slots_keyboard(),
    )


@router.callback_query(OrderCheckoutStates.waiting_time, F.data.startswith("sl:"))
async def step_slot_cb(
    cq: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    slot = cq.data.split(":", 1)[1]
    if not is_allowed_delivery_slot(slot):
        await cq.answer("Недоступный интервал", show_alert=True)
        return
    await cq.answer()
    await state.update_data(delivery_slot=slot)
    await state.set_state(OrderCheckoutStates.waiting_payment)
    if not payment_yookassa.is_online_payment_available():
        await state.update_data(payment_method="cash")
        await state.set_state(OrderCheckoutStates.waiting_confirm)
        await cq.message.edit_text(
            await _build_preview_text(session, cq.from_user.id, state),
            reply_markup=confirm_order_keyboard(),
            parse_mode="HTML",
        )
        return
    await cq.message.edit_text("Выберите способ оплаты:", reply_markup=payment_keyboard())


@router.callback_query(OrderCheckoutStates.waiting_payment, F.data.startswith("pay:"))
async def step_payment_cb(
    cq: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    method = cq.data.split(":", 1)[1]
    if method == "online" and not payment_yookassa.is_online_payment_available():
        await cq.answer("Онлайн-оплата отключена", show_alert=True)
        return
    await cq.answer()
    await state.update_data(payment_method=method)
    await state.set_state(OrderCheckoutStates.waiting_confirm)
    await cq.message.edit_text(
        await _build_preview_text(session, cq.from_user.id, state),
        reply_markup=confirm_order_keyboard(),
        parse_mode="HTML",
    )


async def _build_preview_text(
    session: AsyncSession, user_id: int, state: FSMContext
) -> str:
    data = await state.get_data()
    snapshots, skipped = await order_service.get_cart_checkout_summary(session, user_id)
    rows: list[str] = []
    total = Decimal("0")
    for p, qty in snapshots:
        sub = (p.price * qty).quantize(Decimal("0.01"))
        total += sub
        rows.append(f"• {html.escape(p.name)} × {qty} = {format_money(sub)}")
    body = "\n".join(rows) if rows else "(пусто)"
    d = date.fromisoformat(data["delivery_date"])
    pay = (
        "Наличными при получении"
        if data.get("payment_method") == "cash"
        else data.get("payment_method", "cash")
    )
    extra = ""
    if skipped:
        extra += (
            "\n\n⚠️ Не попадут в заказ (сняты с продажи):\n"
            + html.escape(", ".join(skipped))
        )
    if total == 0:
        extra += "\n\n⚠️ Сумма 0 ₽ — уточним стоимость при подтверждении."
    return (
        f"<b>Проверьте заказ</b>\n\n"
        f"👤 {html.escape(data['full_name'])}\n"
        f"📞 {html.escape(data['phone'])}\n"
        f"📍 {html.escape(data['address'])}\n"
        f"📅 {d:%d.%m.%Y}, {html.escape(data['delivery_slot'])}\n"
        f"💵 {html.escape(str(pay))}\n\n"
        f"Состав:\n{body}\n\n"
        f"<b>Итого: {format_money(total)}</b>{extra}"
    )


@router.callback_query(OrderCheckoutStates.waiting_confirm, F.data == "ord:ok")
async def step_confirm_ok(
    cq: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    data = await state.get_data()
    d = date.fromisoformat(data["delivery_date"])
    slot = data["delivery_slot"]
    if not is_allowed_delivery_date(d) or not is_allowed_delivery_slot(slot):
        await cq.answer("Дата или интервал больше недоступны", show_alert=True)
        return
    await cq.answer()
    uid = cq.from_user.id
    try:
        order, skipped = await order_service.create_order_from_cart(
            session,
            uid,
            full_name=data["full_name"],
            phone=data["phone"],
            address=data["address"],
            delivery_date=d,
            delivery_slot=slot,
            payment_method=data.get("payment_method", "cash"),
        )
    except ValueError as e:
        code = str(e)
        if code == "min_amount":
            await cq.answer(
                f"Минимальная сумма заказа {get_settings().min_order_amount} ₽",
                show_alert=True,
            )
        elif code == "inactive_only":
            await cq.answer("В корзине нет доступных товаров", show_alert=True)
        elif code == "zero_total":
            await cq.answer(
                "Сумма заказа 0 ₽. Выставьте цены в админке (💰 Цены).",
                show_alert=True,
            )
        else:
            await cq.answer("Не удалось оформить заказ", show_alert=True)
        return
    await state.clear()
    text = f"Заказ #{order.id} принят. Мы свяжемся для подтверждения."
    if skipped:
        text += f"\n\nНе вошли в заказ (недоступны): {', '.join(skipped)}."
    if order.total == 0:
        text += "\n\nСумма уточняется — цены в каталоге обновляются."
    await cq.message.edit_text(text)
    await notifier_service.notify_new_order(bot, order)
