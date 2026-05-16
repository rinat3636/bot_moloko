from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import is_admin
from milk_bot.bot.handlers.common import block_if_busy_fsm
from milk_bot.bot.keyboards.reply import MAIN_MENU_TEXTS
from milk_bot.bot.keyboards.inline import (
    categories_keyboard,
    product_qty_keyboard,
    products_keyboard,
    search_results_keyboard,
)
from milk_bot.bot.services import catalog as catalog_service
from milk_bot.bot.services import cart as cart_service
from milk_bot.bot.states.catalog import ProductQtyStates, SearchStates
from milk_bot.bot.utils.catalog_labels import (
    format_category_products_message,
    format_search_results_message,
)
from milk_bot.bot.utils.catalog_ui import show_product_card
from milk_bot.bot.utils.formatters import format_money
from milk_bot.bot.utils.menu_keyboard import pin_main_menu
from milk_bot.bot.utils.product_display import format_product_card_caption

router = Router()
PAGE_SIZE = 7
SEARCH_PAGE_SIZE = 7


async def _prompt_search(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_query)
    await message.answer(
        "Введите <b>одно слово</b> или фразу — как удобно.\n"
        "Например: <b>молоко</b>, <b>кефир</b>, <b>творог 5%</b>.\n\n"
        "Нужно хотя бы <b>2 буквы</b> (не два слова). Отмена: /cancel",
        parse_mode="HTML",
    )


async def _render_search_results(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    query: str,
    page: int,
    *,
    edit: bool,
) -> None:
    total = await catalog_service.count_search_products(session, query)
    pages = max(1, (total + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE) if total else 1
    page = max(0, min(page, pages - 1))
    products = await catalog_service.search_products_page(
        session, query, page * SEARCH_PAGE_SIZE, SEARCH_PAGE_SIZE
    )
    text = format_search_results_message(
        products, query=query, page=page, pages=pages, total=total
    )
    kb = search_results_keyboard(page, total, SEARCH_PAGE_SIZE, products)
    await state.set_state(SearchStates.browsing)
    await state.update_data(search_q=query, search_page=page)
    if edit and message.text is not None:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def _render_categories(message: Message, session: AsyncSession, *, edit: bool = False) -> None:
    cats = await catalog_service.list_categories(session, active_only=True)
    if not cats:
        text = "Каталог пока пуст. Администратор скоро добавит товары."
        if edit and message.text is not None:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return
    text = "Выберите категорию:"
    kb = categories_keyboard(cats)
    if edit and message.text is not None:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def _render_products_list(
    message: Message,
    session: AsyncSession,
    category_id: int,
    page: int,
) -> None:
    total = await catalog_service.count_products_in_category(session, category_id)
    if total == 0:
        await message.edit_text("В этой категории пока нет активных товаров.")
        return
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    offset = page * PAGE_SIZE
    products = await catalog_service.list_products_page(
        session, category_id, offset, PAGE_SIZE
    )
    cat = await catalog_service.get_category(session, category_id)
    title = cat.name if cat else "Категория"
    text = format_category_products_message(
        products, title=title, page=page, pages=pages
    )
    kb = products_keyboard(category_id, page, total, PAGE_SIZE, products)
    await message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🥛 Каталог")
async def open_catalog(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if is_admin(message.from_user.id if message.from_user else 0):
        return
    if not await block_if_busy_fsm(message, state):
        return
    await state.clear()
    await pin_main_menu(message)
    await _render_categories(message, session, edit=False)


@router.message(F.text == "🔍 Поиск")
async def open_search(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if is_admin(message.from_user.id if message.from_user else 0):
        return
    if not await block_if_busy_fsm(message, state):
        return
    await state.clear()
    await pin_main_menu(message)
    await _prompt_search(message, state)


@router.callback_query(F.data == "sr:ask")
async def cb_search_ask(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await block_if_busy_fsm(cq, state):
        return
    await cq.answer()
    await state.clear()
    await pin_main_menu(cq.message)
    await _prompt_search(cq.message, state)


@router.message(SearchStates.waiting_query, F.text)
async def search_query_entered(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    text = (message.text or "").strip()
    if text in MAIN_MENU_TEXTS:
        await state.clear()
        if text == "🥛 Каталог":
            await _render_categories(message, session, edit=False)
        elif text == "🔍 Поиск":
            await _prompt_search(message, state)
        elif text == "🛒 Корзина":
            from milk_bot.bot.handlers.cart import _show_cart

            await _show_cart(message, session, message.from_user.id, edit=False)
        return
    query = text
    if len(query) < 2:
        await message.answer(
            "Слишком коротко. Введите хотя бы 2 буквы — например «молоко»."
        )
        return
    await _render_search_results(message, session, state, query, 0, edit=False)


@router.callback_query(SearchStates.browsing, F.data.startswith("sp:"))
async def cb_search_page(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await block_if_busy_fsm(cq, state):
        return
    await cq.answer()
    page = int(cq.data.split(":")[1])
    data = await state.get_data()
    query = str(data.get("search_q", "")).strip()
    if not query:
        await state.clear()
        await _render_categories(cq.message, session, edit=True)
        return
    await _render_search_results(cq.message, session, state, query, page, edit=True)


@router.callback_query(F.data == "ct:l")
async def cb_cat_list(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await block_if_busy_fsm(cq, state):
        return
    await state.clear()
    await cq.answer()
    await _render_categories(cq.message, session, edit=True)


@router.callback_query(F.data.startswith("ct:"))
async def cb_cat_open(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if cq.data == "ct:l":
        return
    if not await block_if_busy_fsm(cq, state):
        return
    await state.clear()
    await cq.answer()
    cid = int(cq.data.split(":")[1])
    await _render_products_list(cq.message, session, cid, 0)


@router.callback_query(F.data.startswith("pg:"))
async def cb_page(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await block_if_busy_fsm(cq, state):
        return
    await cq.answer()
    _, cid_s, page_s = cq.data.split(":")
    await _render_products_list(cq.message, session, int(cid_s), int(page_s))


@router.callback_query(F.data.startswith("vw:"))
async def cb_view_product(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await block_if_busy_fsm(cq, state):
        return
    parts = cq.data.split(":")
    pid = int(parts[1])
    ctx = parts[2] if len(parts) > 2 else "0"
    page = int(parts[3]) if len(parts) > 3 else 0
    from_search = ctx == "s"
    cid = 0 if from_search else int(ctx)
    p = await catalog_service.get_product(session, pid)
    if not p or not p.is_active:
        await cq.answer("Товар недоступен", show_alert=True)
        return
    await cq.answer()
    prev = await state.get_data()
    await state.set_state(ProductQtyStates.picking)
    await state.update_data(
        pid=pid,
        qty=1,
        cid=cid,
        page=page,
        from_search=from_search,
        search_q=prev.get("search_q", "") if from_search else prev.get("search_q"),
    )
    text = format_product_card_caption(p, 1)
    kb = product_qty_keyboard(pid, 1)
    await show_product_card(cq, text=text, reply_markup=kb, product=p, session=session)


@router.callback_query(ProductQtyStates.picking, F.data == "pq:m")
async def cb_qty_minus(cq: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    qty = max(1, int(data.get("qty", 1)) - 1)
    await state.update_data(qty=qty)
    await _refresh_product_card(cq, session, state, qty)
    await cq.answer()


@router.callback_query(ProductQtyStates.picking, F.data == "pq:p")
async def cb_qty_plus(cq: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    qty = min(99, int(data.get("qty", 1)) + 1)
    await state.update_data(qty=qty)
    await _refresh_product_card(cq, session, state, qty)
    await cq.answer()


async def _refresh_product_card(
    cq: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    qty: int,
) -> None:
    data = await state.get_data()
    pid = int(data["pid"])
    p = await catalog_service.get_product(session, pid)
    if not p:
        return
    text = format_product_card_caption(p, qty)
    kb = product_qty_keyboard(pid, qty)
    await show_product_card(cq, text=text, reply_markup=kb, product=p, session=session)


@router.callback_query(ProductQtyStates.picking, F.data == "pq:a")
async def cb_add_cart(cq: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    uid = cq.from_user.id
    pid = int(data["pid"])
    qty = int(data.get("qty", 1))
    p = await catalog_service.get_product(session, pid)
    if not p or not p.is_active:
        await cq.answer("Товар недоступен", show_alert=True)
        return
    try:
        await cart_service.set_quantity(session, uid, pid, qty)
    except ValueError:
        await cq.answer("Товар недоступен", show_alert=True)
        return
    await state.clear()
    await cq.answer("Добавлено в корзину", show_alert=True)
    chat_id = cq.message.chat.id
    if cq.message.photo:
        await cq.message.delete()
        await cq.bot.send_message(chat_id, "Товар добавлен в корзину.")
    else:
        await cq.message.edit_text("Товар добавлен в корзину.")


@router.callback_query(ProductQtyStates.picking, F.data == "pq:b")
async def cb_product_back(cq: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await cq.answer()
    data = await state.get_data()
    from_search = bool(data.get("from_search"))
    cid = int(data.get("cid", 0))
    page = int(data.get("page", 0))
    search_q = str(data.get("search_q", "")).strip()
    chat_id = cq.message.chat.id
    if from_search and search_q:
        if cq.message.photo:
            await cq.message.delete()
            msg = await cq.bot.send_message(chat_id, "🔍")
            await _render_search_results(msg, session, state, search_q, page, edit=False)
        else:
            await _render_search_results(cq.message, session, state, search_q, page, edit=True)
        return
    await state.clear()
    if cq.message.photo:
        await cq.message.delete()
        msg = await cq.bot.send_message(chat_id, "Каталог")
        await _render_products_list(msg, session, cid, page)
    else:
        await _render_products_list(cq.message, session, cid, page)
