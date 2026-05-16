from __future__ import annotations

import html
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import is_admin
from milk_bot.bot.handlers.common import block_if_busy_fsm
from milk_bot.bot.keyboards.inline import cart_keyboard
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.services import cart as cart_service
from milk_bot.bot.utils.formatters import format_money
from milk_bot.bot.utils.menu_keyboard import pin_main_menu

router = Router()


def _cart_text(lines: list) -> str:
    from milk_bot.bot.db.models import CartItem

    if not lines:
        return "Корзина пуста."
    rows: list[str] = []
    total = Decimal("0")
    inactive_note = False
    for li in lines:
        if not isinstance(li, CartItem) or not li.product:
            continue
        p = li.product
        if not p.is_active:
            inactive_note = True
            continue
        sub = (p.price * li.quantity).quantize(Decimal("0.01"))
        total += sub
        name = html.escape(p.name)
        rows.append(
            f"• {name}\n  {li.quantity} × {format_money(p.price)} = {format_money(sub)}"
        )
    if not rows:
        return (
            "В корзине нет доступных товаров.\n"
            "Недоступные позиции убраны — откройте каталог заново."
        )
    body = "\n\n".join(rows)
    text = f"{body}\n\n<b>Итого: {format_money(total)}</b>"
    if inactive_note:
        text += "\n\n<i>Некоторые товары сняты с продажи и не учитываются.</i>"
    return text


async def _show_cart(target: Message, session: AsyncSession, user_id: int, *, edit: bool) -> None:
    removed = await cart_service.remove_inactive_lines(session, user_id)
    lines = await catalog_service.cart_lines(session, user_id)
    text = _cart_text(lines)
    kb = cart_keyboard(lines) if lines else None
    if removed and "убраны" not in text:
        text = f"<i>Убрано недоступных позиций: {removed}</i>\n\n{text}"
    if edit:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🛒 Корзина")
async def open_cart(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if is_admin(message.from_user.id if message.from_user else 0):
        return
    if not await block_if_busy_fsm(message, state):
        return
    await state.clear()
    await pin_main_menu(message)
    await _show_cart(message, session, message.from_user.id, edit=False)


@router.callback_query(F.data.startswith("cr:"))
async def cart_actions(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    uid = cq.from_user.id
    parts = cq.data.split(":")
    op = parts[1]
    if op == "co":
        from milk_bot.bot.handlers.order import start_order_fsm_from_cart

        if not await block_if_busy_fsm(cq, state):
            return
        await start_order_fsm_from_cart(cq, session, state)
        return
    if not await block_if_busy_fsm(cq, state):
        return
    if op == "clear":
        await cart_service.clear_cart(session, uid)
        await cq.answer("Корзина очищена")
        await _show_cart(cq.message, session, uid, edit=True)
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
