from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import Product
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.states.admin import AdminProductStates
from milk_bot.bot.utils.formatters import format_money
from milk_bot.bot.utils.fsm import clear_state_if_set

router = Router()


def _prices_text() -> str:
    return (
        "💰 <b>Цены</b>\n\n"
        "Названия, фото и описания подтягиваются с сайта n-i.ru "
        "(обновление раз в сутки). На сайте <b>цен нет</b>.\n"
        "Здесь вы задаёте <b>цены</b> для бота."
    )


async def _prices_keyboard(session: AsyncSession) -> InlineKeyboardBuilder:
    cats = await catalog_service.list_categories(session)
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(InlineKeyboardButton(text=c.name, callback_data=f"ac:cg:{c.id}"))
    b.adjust(2)
    return b


async def open_prices_menu(message: Message, session: AsyncSession) -> None:
    b = await _prices_keyboard(session)
    await message.answer(
        _prices_text(),
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


async def _catalog_home(message: Message, session: AsyncSession) -> None:
    b = await _prices_keyboard(session)
    await message.edit_text(
        _prices_text(),
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ad:ct", AdminFilter())
async def admin_catalog_home(
    cq: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await clear_state_if_set(state)
    await cq.answer()
    await _catalog_home(cq.message, session)


@router.callback_query(F.data.startswith("ac:cg:"), AdminFilter())
async def admin_category_products(
    cq: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await clear_state_if_set(state)
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    await _render_category_products(cq.message, session, cid)


async def _render_category_products(message: Message, session: AsyncSession, cid: int) -> None:
    cat = await catalog_service.get_category(session, cid)
    res = await session.execute(
        select(Product).where(Product.category_id == cid).order_by(Product.name)
    )
    products = list(res.scalars().all())
    title = cat.name if cat else "Категория"
    if not products:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:ct"))
        await message.edit_text(f"«{title}»: товаров нет.", reply_markup=b.as_markup())
        return
    b = InlineKeyboardBuilder()
    for p in products:
        mark = "✅ " if p.is_active else "🚫 "
        short = p.name[:24] + "…" if len(p.name) > 24 else p.name
        label = f"{mark}{format_money(p.price)} · {short}"
        b.add(InlineKeyboardButton(text=label, callback_data=f"ac:pe:{p.id}"))
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:ct"))
    await message.edit_text(
        f"<b>{title}</b>\nВыберите товар, чтобы изменить цену:",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("ac:pe:"), AdminFilter())
async def admin_prod_edit(
    cq: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await clear_state_if_set(state)
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await _render_product_editor(cq.message, session, pid)


async def _render_product_editor(message: Message, session: AsyncSession, pid: int) -> None:
    p = await session.get(Product, pid)
    if not p:
        await message.edit_text("Товар не найден.")
        return
    desc = (p.description or "—")[:180]
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"ac:pp:{pid}"))
    b.row(InlineKeyboardButton(text="⬅️ К списку", callback_data=f"ac:cg:{p.category_id}"))
    await message.edit_text(
        f"<b>{p.name}</b>\n\n"
        f"Цена: <b>{format_money(p.price)}</b>\n"
        f"В каталоге: {'да' if p.is_active else 'нет (снят с сайта)'}\n\n"
        f"{desc}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("ac:pp:"), AdminFilter())
async def admin_prod_edit_price_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_edit_price)
    await state.update_data(edit_product_id=pid)
    await cq.message.edit_text(
        "Введите новую цену в рублях (например 89.90):\n\nОтмена: /cancel",
    )


@router.message(AdminProductStates.waiting_edit_price, F.text, AdminFilter())
async def admin_prod_edit_price_save(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        price = Decimal((message.text or "").replace(",", ".").replace(" ", ""))
        if price < 0:
            raise InvalidOperation
        price = price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        await message.answer("Неверная цена. Пример: 89.90")
        return
    data = await state.get_data()
    pid = int(data["edit_product_id"])
    p = await session.get(Product, pid)
    if not p:
        await state.clear()
        await message.answer("Товар не найден.")
        return
    p.price = price
    await state.clear()
    panel = await message.answer(f"✅ Цена обновлена: {format_money(price)}")
    await _render_product_editor(panel, session, pid)
