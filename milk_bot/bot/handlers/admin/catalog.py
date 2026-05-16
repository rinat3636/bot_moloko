from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import Category, Product
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.states.admin import AdminCategoryStates, AdminProductStates
from milk_bot.bot.utils.formatters import format_money

router = Router()


async def _catalog_home(message: Message, session: AsyncSession) -> None:
    cats = await catalog_service.list_categories(session)
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(InlineKeyboardButton(text=c.name, callback_data=f"ac:cg:{c.id}"))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="➕ Категория", callback_data="ac:cn"))
    b.row(InlineKeyboardButton(text="➕ Товар", callback_data="ac:pn"))
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    await message.edit_text("Каталог (категории):", reply_markup=b.as_markup())


@router.callback_query(F.data == "ad:ct", AdminFilter())
async def admin_catalog_home(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    await _catalog_home(cq.message, session)


@router.callback_query(F.data.startswith("ac:cg:"), AdminFilter())
async def admin_category_menu(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    cat = await catalog_service.get_category(session, cid)
    if not cat:
        await cq.answer("Категория не найдена", show_alert=True)
        return
    total = await catalog_service.count_category_products_total(session, cid)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📦 Товары", callback_data=f"ac:pc:{cid}"))
    b.row(InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"ac:crn:{cid}"))
    b.row(InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"ac:cdel:{cid}"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:ct"))
    await cq.message.edit_text(
        f"Категория: <b>{cat.name}</b>\nТоваров: {total}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ac:cn", AdminFilter())
async def admin_cat_new(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.set_state(AdminCategoryStates.waiting_name)
    await state.update_data(cat_action="create")
    await cq.message.edit_text("Введите название новой категории:\n\nОтмена: /cancel")


@router.callback_query(F.data.startswith("ac:crn:"), AdminFilter())
async def admin_cat_rename_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    await state.set_state(AdminCategoryStates.waiting_name)
    await state.update_data(cat_action="rename", category_id=cid)
    await cq.message.edit_text(
        "Введите новое название категории:\n\nОтмена: /cancel",
    )


@router.message(AdminCategoryStates.waiting_name, F.text, AdminFilter())
async def admin_cat_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Слишком короткое название (минимум 2 символа).")
        return
    data = await state.get_data()
    action = data.get("cat_action", "create")
    if action == "rename":
        cid = int(data["category_id"])
        dup = await session.scalar(
            select(Category).where(Category.name == name, Category.id != cid)
        )
        if dup:
            await message.answer("Категория с таким названием уже есть.")
            return
        cat = await catalog_service.rename_category(session, cid, name)
        if not cat:
            await message.answer("Категория не найдена.")
        else:
            await message.answer(f"Категория переименована в «{name}».")
    else:
        dup = await session.scalar(select(Category).where(Category.name == name))
        if dup:
            await message.answer("Категория с таким названием уже есть.")
            return
        try:
            session.add(Category(name=name))
            await session.flush()
            await message.answer(f"Категория «{name}» создана.")
        except IntegrityError:
            await message.answer("Категория с таким названием уже есть.")
            return
    await state.clear()


@router.callback_query(F.data.startswith("ac:cdel:"), AdminFilter())
async def admin_cat_delete(cq: CallbackQuery, session: AsyncSession) -> None:
    cid = int(cq.data.split(":")[2])
    ok, msg = await catalog_service.delete_category(session, cid)
    await cq.answer(msg, show_alert=not ok)
    if ok:
        await _catalog_home(cq.message, session)


@router.callback_query(F.data == "ac:pn", AdminFilter())
async def admin_prod_pick_cat(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    cats = await catalog_service.list_categories(session)
    if not cats:
        await cq.message.edit_text("Сначала создайте категорию.")
        return
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(InlineKeyboardButton(text=c.name, callback_data=f"ac:pnc:{c.id}"))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:ct"))
    await cq.message.edit_text("Выберите категорию для товара:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ac:pnc:"), AdminFilter())
async def admin_prod_name_prompt(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_name)
    await state.update_data(category_id=cid)
    await cq.message.edit_text("Введите название товара:\n\nОтмена: /cancel")


@router.message(AdminProductStates.waiting_name, F.text, AdminFilter())
async def admin_prod_price_prompt(message: Message, state: FSMContext) -> None:
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(AdminProductStates.waiting_price)
    await message.answer("Введите цену в рублях (например 99.50):")


@router.message(AdminProductStates.waiting_price, F.text, AdminFilter())
async def admin_prod_desc_prompt(message: Message, state: FSMContext) -> None:
    try:
        price = Decimal((message.text or "").replace(",", ".").replace(" ", ""))
        if price < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("Неверная цена. Пример: 99.50")
        return
    await state.update_data(price=str(price.quantize(Decimal("0.01"))))
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
    await message.answer(f"Товар «{p.name}» создан. Цена: {format_money(p.price)}")


@router.callback_query(F.data.startswith("ac:pc:"), AdminFilter())
async def admin_prod_list_cat(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    cid = int(cq.data.split(":")[2])
    await _render_category_products(cq.message, session, cid)


async def _render_category_products(message: Message, session: AsyncSession, cid: int) -> None:
    cat = await catalog_service.get_category(session, cid)
    res = await session.execute(
        select(Product).where(Product.category_id == cid).order_by(Product.id)
    )
    products = list(res.scalars().all())
    title = cat.name if cat else "Категория"
    if not products:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ac:cg:{cid}"))
        await message.edit_text(f"«{title}»: товаров нет.", reply_markup=b.as_markup())
        return
    b = InlineKeyboardBuilder()
    for p in products:
        label = ("✅ " if p.is_active else "🚫 ") + p.name[:28]
        b.add(InlineKeyboardButton(text=label, callback_data=f"ac:pe:{p.id}"))
    b.adjust(1)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"ac:cg:{cid}"))
    await message.edit_text(f"Товары — {title}:", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("ac:pe:"), AdminFilter())
async def admin_prod_edit(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await _render_product_editor(cq.message, session, pid)


async def _render_product_editor(message: Message, session: AsyncSession, pid: int) -> None:
    p = await session.get(Product, pid)
    if not p:
        return
    desc = (p.description or "—")[:200]
    photo = "есть" if p.photo_file_id else "нет"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💰 Цена", callback_data=f"ac:pp:{pid}"))
    b.row(InlineKeyboardButton(text="✏️ Название", callback_data=f"ac:pnm:{pid}"))
    b.row(InlineKeyboardButton(text="📝 Описание", callback_data=f"ac:pds:{pid}"))
    b.row(InlineKeyboardButton(text="🖼 Фото", callback_data=f"ac:pf:{pid}"))
    b.row(InlineKeyboardButton(text="Скрыть/показать", callback_data=f"ac:ph:{pid}"))
    b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"ac:pd:{pid}"))
    b.row(InlineKeyboardButton(text="⬅️", callback_data=f"ac:pc:{p.category_id}"))
    await message.edit_text(
        f"<b>{p.name}</b>\n"
        f"Цена: {format_money(p.price)}\n"
        f"Активен: {'да' if p.is_active else 'нет'}\n"
        f"Фото: {photo}\n"
        f"Описание: {desc}",
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("ac:pp:"), AdminFilter())
async def admin_prod_edit_price_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_edit_price)
    await state.update_data(edit_product_id=pid)
    await cq.message.edit_text("Введите новую цену в рублях:\n\nОтмена: /cancel")


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
        await message.answer("Неверная цена.")
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
    panel = await message.answer(f"Цена обновлена: {format_money(price)}")
    await _render_product_editor(panel, session, pid)


@router.callback_query(F.data.startswith("ac:pnm:"), AdminFilter())
async def admin_prod_edit_name_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_edit_name)
    await state.update_data(edit_product_id=pid)
    await cq.message.edit_text("Введите новое название:\n\nОтмена: /cancel")


@router.message(AdminProductStates.waiting_edit_name, F.text, AdminFilter())
async def admin_prod_edit_name_save(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Слишком короткое название.")
        return
    data = await state.get_data()
    pid = int(data["edit_product_id"])
    p = await session.get(Product, pid)
    if not p:
        await state.clear()
        await message.answer("Товар не найден.")
        return
    p.name = name
    await state.clear()
    panel = await message.answer(f"Название обновлено: {name}")
    await _render_product_editor(panel, session, pid)


@router.callback_query(F.data.startswith("ac:pds:"), AdminFilter())
async def admin_prod_edit_desc_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_edit_description)
    await state.update_data(edit_product_id=pid)
    await cq.message.edit_text(
        "Введите новое описание (или «-» чтобы очистить):\n\nОтмена: /cancel",
    )


@router.message(AdminProductStates.waiting_edit_description, F.text, AdminFilter())
async def admin_prod_edit_desc_save(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    data = await state.get_data()
    pid = int(data["edit_product_id"])
    p = await session.get(Product, pid)
    if not p:
        await state.clear()
        await message.answer("Товар не найден.")
        return
    p.description = desc or None
    await state.clear()
    panel = await message.answer("Описание обновлено.")
    await _render_product_editor(panel, session, pid)


@router.callback_query(F.data.startswith("ac:pf:"), AdminFilter())
async def admin_prod_edit_photo_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    pid = int(cq.data.split(":")[2])
    await state.set_state(AdminProductStates.waiting_edit_photo)
    await state.update_data(edit_product_id=pid)
    await cq.message.edit_text(
        "Пришлите новое фото или «-» чтобы убрать фото:\n\nОтмена: /cancel",
    )


@router.message(AdminProductStates.waiting_edit_photo, AdminFilter())
async def admin_prod_edit_photo_save(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    pid = int(data["edit_product_id"])
    p = await session.get(Product, pid)
    if not p:
        await state.clear()
        await message.answer("Товар не найден.")
        return
    if message.text and message.text.strip() == "-":
        p.photo_file_id = None
    elif message.photo:
        p.photo_file_id = message.photo[-1].file_id
    else:
        await message.answer("Нужно фото или «-».")
        return
    await state.clear()
    panel = await message.answer("Фото обновлено.")
    await _render_product_editor(panel, session, pid)


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
