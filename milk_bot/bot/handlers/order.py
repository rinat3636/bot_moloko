from __future__ import annotations

import html
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Contact, Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import get_settings
from milk_bot.bot.db.models import CartItem
from milk_bot.bot.keyboards.inline import (
    confirm_order_keyboard,
    delivery_dates_keyboard,
    delivery_slots_keyboard,
    payment_keyboard,
)
from milk_bot.bot.keyboards.reply import phone_request_keyboard, remove_keyboard
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.services import order as order_service
from milk_bot.bot.services import payment_yookassa
from milk_bot.bot.states.order import OrderCheckoutStates
from milk_bot.bot.utils.formatters import format_money
from milk_bot.bot.utils.validators import normalize_phone, validate_address, validate_full_name

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
    await cq.answer()
    await state.set_state(OrderCheckoutStates.waiting_name)
    await cq.message.edit_text(
        "Оформление заказа.\nВведите <b>ФИО</b> (минимум два слова, без цифр).\n\n"
        "Отмена: /cancel",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ord:x")
async def cb_cancel_inline(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.clear()
    await cq.message.edit_text("Оформление отменено.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Оформление отменено.", reply_markup=remove_keyboard())


@router.message(OrderCheckoutStates.waiting_name, F.text)
async def step_name(message: Message, state: FSMContext) -> None:
    ok, val = validate_full_name(message.text or "")
    if not ok:
        await message.answer(val)
        return
    await state.update_data(full_name=val)
    await state.set_state(OrderCheckoutStates.waiting_phone)
    await message.answer(
        "Укажите телефон: нажмите кнопку ниже или введите вручную в формате +7…",
        reply_markup=phone_request_keyboard(),
    )


@router.message(OrderCheckoutStates.waiting_phone, F.contact)
async def step_phone_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if not contact or contact.user_id != message.from_user.id:
        await message.answer("Отправьте свой контакт через кнопку.")
        return
    raw = contact.phone_number or ""
    ok, phone = normalize_phone(raw)
    if not ok:
        await message.answer("Не удалось распознать номер. Введите вручную +7XXXXXXXXXX.")
        return
    await state.update_data(phone=phone)
    await state.set_state(OrderCheckoutStates.waiting_address)
    await message.answer("Введите адрес доставки (от 10 символов).", reply_markup=remove_keyboard())


@router.message(OrderCheckoutStates.waiting_phone, F.text)
async def step_phone_text(message: Message, state: FSMContext) -> None:
    ok, phone = normalize_phone(message.text or "")
    if not ok:
        await message.answer("Неверный формат. Нужно +7XXXXXXXXXX или 8XXXXXXXXXX.")
        return
    await state.update_data(phone=phone)
    await state.set_state(OrderCheckoutStates.waiting_address)
    await message.answer("Введите адрес доставки (от 10 символов).", reply_markup=remove_keyboard())


@router.message(OrderCheckoutStates.waiting_address, F.text)
async def step_address(message: Message, state: FSMContext) -> None:
    ok, val = validate_address(message.text or "")
    if not ok:
        await message.answer(val)
        return
    await state.update_data(address=val)
    await state.set_state(OrderCheckoutStates.waiting_date)
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    await message.answer(
        "Выберите дату доставки:",
        reply_markup=delivery_dates_keyboard(today),
    )


@router.callback_query(OrderCheckoutStates.waiting_date, F.data.startswith("dl:"))
async def step_date_cb(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    d = date.fromisoformat(cq.data.split(":", 1)[1])
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
    await cq.answer()
    slot = cq.data.split(":", 1)[1]
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
    await cq.answer()
    method = cq.data.split(":", 1)[1]
    if method == "online" and not payment_yookassa.is_online_payment_available():
        await cq.answer("Онлайн-оплата отключена", show_alert=True)
        return
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
    lines = await catalog_service.cart_lines(session, user_id)
    rows: list[str] = []
    total = Decimal("0")
    for li in lines:
        if not isinstance(li, CartItem) or not li.product:
            continue
        sub = (li.product.price * li.quantity).quantize(Decimal("0.01"))
        total += sub
        rows.append(
            f"• {html.escape(li.product.name)} × {li.quantity} = {format_money(sub)}"
        )
    body = "\n".join(rows) if rows else "(пусто)"
    d = date.fromisoformat(data["delivery_date"])
    pay = "Наличными при получении" if data.get("payment_method") == "cash" else data.get("payment_method")
    return (
        f"<b>Проверьте заказ</b>\n\n"
        f"👤 {html.escape(data['full_name'])}\n"
        f"📞 {html.escape(data['phone'])}\n"
        f"📍 {html.escape(data['address'])}\n"
        f"📅 {d:%d.%m.%Y}, {html.escape(data['delivery_slot'])}\n"
        f"💵 {html.escape(str(pay))}\n\n"
        f"Состав:\n{body}\n\n"
        f"<b>Итого: {format_money(total)}</b>"
    )


@router.callback_query(OrderCheckoutStates.waiting_confirm, F.data == "ord:ok")
async def step_confirm_ok(
    cq: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    await cq.answer()
    data = await state.get_data()
    uid = cq.from_user.id
    try:
        order = await order_service.create_order_from_cart(
            session,
            uid,
            full_name=data["full_name"],
            phone=data["phone"],
            address=data["address"],
            delivery_date=date.fromisoformat(data["delivery_date"]),
            delivery_slot=data["delivery_slot"],
            payment_method=data.get("payment_method", "cash"),
        )
    except ValueError as e:
        code = str(e)
        if code == "min_amount":
            await cq.answer(
                f"Минимальная сумма заказа {get_settings().min_order_amount} ₽",
                show_alert=True,
            )
        else:
            await cq.answer("Не удалось оформить заказ", show_alert=True)
        return
    await state.clear()
    await cq.message.edit_text(
        f"Заказ #{order.id} принят. Мы свяжемся для подтверждения.",
    )
    await notifier_service.notify_new_order(bot, order)


