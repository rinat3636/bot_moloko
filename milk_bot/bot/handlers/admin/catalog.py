from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import Category, Product
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.keyboards.inline import admin_main_keyboard
from milk_bot.bot.states.admin import AdminCategoryStates, AdminProductStates

router = Router()


@router.callback_query(F.data == "ad:ct", AdminFilter())
async def admin_catalog_home(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    res = await session.execute(select(Category).order_by(Category.sort_order, Category.name))
    cats = list(res.scalars().all())
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(InlineKeyboardButton(text=c.name, callback_data=f"ac:pc:{c.id}"))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="➕ Категория", callback_data="ac:cn"))
    b.row(InlineKeyboardButton(text="➕ Товар", callback_data="ac:pn"))
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    await cq.message.edit_text("Каталог (категории):", reply_markup=b.as_markup())


@router.callback_query(F.data == "ac:cn", AdminFilter())
async def admin_cat_new(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.set_state(AdminCategoryStates.waiting_name)
    await cq.message.edit_text("Введите название новой категории:")


@router.message(AdminCategoryStates.waiting_name, F.text, AdminFilter())
async def admin_cat_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Слишком короткое название.")
        return
    session.add(Category(name=name))
    await state.clear()
    await message.answer(f"Категория «{name}» создана.")


@router.callback_query(F.data == "ac:pn", AdminFilter())
async def admin_prod_pick_cat(cq: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await cq.answer()
    res = await session.execute(select(Category).order_by(Category.name))
    cats = list(res.scalars().all())
    if not cats:
        await cq.message.edit_text("Сначала создайте категорию.")
        return
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(InlineKeyboardButton(text=c.name, callback_data=f"ac:pnc:{c.id}"))
    b.adjust(2)
    await cq.message.edit_text("Выберите категорию для товара:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ac:pnc:"), AdminFilter())
async def admin_prod_name_prompt(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_name)
    await state.update_data(category_id=cid)
    await cq.message.edit_text("Введите название товара:")


@router.message(AdminProductStates.waiting_name, F.text, AdminFilter())
async def admin_prod_price_prompt(message: Message, state: FSMContext) -> None:
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(AdminProductStates.waiting_price)
    await message.answer("Введите цену в рублях (например 99.50):")


@router.message(AdminProductStates.waiting_price, F.text, AdminFilter())
async def admin_prod_desc_prompt(message: Message, state: FSMContext) -> None:
    try:
        price = Decimal((message.text or "").replace(",", "."))
    except Exception:
        await message.answer("Неверная цена.")
        return
    await state.update_data(price=str(price))
    await state.set_state(AdminProductStates.waiting_description)
    await message.answer("Введите описание (или «-» без описания):")


@router.message(AdminProductStates.waiting_description, F.text, AdminFilter())
async def admin_prod_photo_prompt(message: Message, state: FSMContext) -> None:
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    await state.update_data(description=desc)
    await state.set_state(AdminProductStates.waiting_photo)
    await message.answer("Пришлите фото товара (или «-» чтобы пропустить):")


@router.message(AdminProductStates.waiting_photo, AdminFilter())
async def admin_prod_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    photo_id = None
    if message.text and message.text.strip() == "-":
        photo_id = None
    elif message.photo:
        photo_id = message.photo[-1].file_id
    else:
        await message.answer("Нужно фото или «-».")
        return
    p = Product(
        category_id=int(data["category_id"]),
        name=data["name"],
        description=data.get("description") or None,
        price=Decimal(data["price"]),
        photo_file_id=photo_id,
        is_active=True,
    )
    session.add(p)
    await state.clear()
    await message.answer(f"Товар «{p.name}» создан.")


@router.callback_query(F.data.startswith("ac:pc:"), AdminFilter())
async def admin_prod_list_cat(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    await _render_category_products(cq.message, session, cid)


async def _render_category_products(message: Message, session: AsyncSession, cid: int) -> None:
    res = await session.execute(select(Product).where(Product.category_id == cid).order_by(Product.id))
    products = list(res.scalars().all())
    if not products:
        await message.edit_text("В категории нет товаров.")
        return
    b = InlineKeyboardBuilder()
    for p in products:
        label = ("✅ " if p.is_active else "🚫 ") + p.name[:28]
        b.add(InlineKeyboardButton(text=label, callback_data=f"ac:pe:{p.id}"))
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:ct"))
    await message.edit_text("Товары:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ac:pe:"), AdminFilter())
async def admin_prod_edit(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await _render_product_editor(cq.message, session, pid)


async def _render_product_editor(message: Message, session: AsyncSession, pid: int) -> None:
    p = await session.get(Product, pid)
    if not p:
        return
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Скрыть/показать", callback_data=f"ac:ph:{pid}"))
    b.row(InlineKeyboardButton(text="Удалить", callback_data=f"ac:pd:{pid}"))
    b.row(InlineKeyboardButton(text="⬅️", callback_data=f"ac:pc:{p.category_id}"))
    await message.edit_text(
        f"{p.name}\nЦена: {p.price} ₽\nАктивен: {p.is_active}",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data.startswith("ac:ph:"), AdminFilter())
async def admin_prod_hide(cq: CallbackQuery, session: AsyncSession) -> None:
    pid = int(cq.data.split(":")[2])
    p = await session.get(Product, pid)
    if p:
        p.is_active = not p.is_active
    await cq.answer("Ок")
    await _render_product_editor(cq.message, session, pid)


@router.callback_query(F.data.startswith("ac:pd:"), AdminFilter())
async def admin_prod_delete(cq: CallbackQuery, session: AsyncSession) -> None:
    pid = int(cq.data.split(":")[2])
    p = await session.get(Product, pid)
    cid = p.category_id if p else None
    if p:
        await session.delete(p)
    await cq.answer("Удалено")
    if cid:
        await _render_category_products(cq.message, session, cid)
    else:
        await cq.message.edit_text("Товар удалён.")
