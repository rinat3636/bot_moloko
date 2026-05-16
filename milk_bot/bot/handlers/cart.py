from __future__ import annotations

import html
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.keyboards.inline import cart_keyboard
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.services import cart as cart_service
from milk_bot.bot.utils.formatters import format_money

router = Router()


def _cart_text(lines: list) -> str:
    from milk_bot.bot.db.models import CartItem

    if not lines:
        return "Корзина пуста."
    rows: list[str] = []
    total = Decimal("0")
    for li in lines:
        if not isinstance(li, CartItem) or not li.product:
            continue
        sub = (li.product.price * li.quantity).quantize(Decimal("0.01"))
        total += sub
        name = html.escape(li.product.name)
        rows.append(
            f"• {name}\n  {li.quantity} × {format_money(li.product.price)} = {format_money(sub)}"
        )
    body = "\n\n".join(rows)
    return f"{body}\n\n<b>Итого: {format_money(total)}</b>"


async def _show_cart(target: Message, session: AsyncSession, user_id: int, *, edit: bool) -> None:
    lines = await catalog_service.cart_lines(session, user_id)
    text = _cart_text(lines)
    kb = cart_keyboard(lines) if lines else None
    if edit:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🛒 Корзина")
async def open_cart(message: Message, session: AsyncSession, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm

    if not await block_if_busy_fsm(message, state):
        return
    await _show_cart(message, session, message.from_user.id, edit=False)


@router.callback_query(F.data.startswith("cr:"))
async def cart_actions(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    uid = cq.from_user.id
    parts = cq.data.split(":")
    op = parts[1]
    if op == "clear":
        await cart_service.clear_cart(session, uid)
        await cq.answer("Корзина очищена")
        await _show_cart(cq.message, session, uid, edit=True)
        return
    if op == "co":
        from milk_bot.bot.handlers.order import start_order_fsm_from_cart

        await start_order_fsm_from_cart(cq, session, state)
        return
    line_id = int(parts[2])
    if op == "m":
        await cart_service.adjust_line_quantity(session, line_id, uid, -1)
    elif op == "p":
        await cart_service.adjust_line_quantity(session, line_id, uid, 1)
    elif op == "d":
        await cart_service.remove_line_by_id(session, line_id, uid)
    await cq.answer()
    await _show_cart(cq.message, session, uid, edit=True)
