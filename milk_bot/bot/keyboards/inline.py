from __future__ import annotations

from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from milk_bot.bot.config import get_settings
from milk_bot.bot.db.models import Category, Product
from milk_bot.bot.utils.catalog_labels import product_button_label
from milk_bot.bot.utils.formatters import format_money


def categories_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.add(InlineKeyboardButton(text=c.name, callback_data=f"ct:{c.id}"))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="🔍 Поиск по каталогу", callback_data="sr:ask"))
    return b.as_markup()


def search_results_keyboard(
    page: int,
    total: int,
    page_size: int,
    products: list[Product],
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, p in enumerate(products, start=1):
        label = product_button_label(i, p.name, p.price)
        b.add(InlineKeyboardButton(text=label, callback_data=f"vw:{p.id}:s:{page}"))
    b.adjust(1)
    pages = max(1, (total + page_size - 1) // page_size)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"sp:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="ig:n"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"sp:{page+1}"))
    if nav and total > 0:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="⬅️ К категориям", callback_data="ct:l"))
    return b.as_markup()


def products_keyboard(
    category_id: int,
    page: int,
    total: int,
    page_size: int,
    products: list[Product],
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, p in enumerate(products, start=1):
        label = product_button_label(i, p.name, p.price)
        b.add(InlineKeyboardButton(text=label, callback_data=f"vw:{p.id}:{category_id}:{page}"))
    b.adjust(1)
    pages = max(1, (total + page_size - 1) // page_size)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pg:{category_id}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{pages}", callback_data="ig:n"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pg:{category_id}:{page+1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="⬅️ К категориям", callback_data="ct:l"))
    return b.as_markup()


def product_qty_keyboard(product_id: int, qty: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="−", callback_data="pq:m"),
        InlineKeyboardButton(text=str(qty), callback_data="ig:n"),
        InlineKeyboardButton(text="+", callback_data="pq:p"),
    )
    b.row(InlineKeyboardButton(text="В корзину", callback_data="pq:a"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="pq:b"))
    return b.as_markup()


def cart_keyboard(lines: list) -> InlineKeyboardMarkup:
    from milk_bot.bot.db.models import CartItem

    b = InlineKeyboardBuilder()
    for li in lines:
        if not isinstance(li, CartItem) or not li.product:
            continue
        b.row(
            InlineKeyboardButton(text="−", callback_data=f"cr:m:{li.id}"),
            InlineKeyboardButton(
                text=f"{li.product.name[:25]} ×{li.quantity}",
                callback_data=f"ig:n",
            ),
            InlineKeyboardButton(text="+", callback_data=f"cr:p:{li.id}"),
        )
        b.row(InlineKeyboardButton(text="🗑 удалить", callback_data=f"cr:d:{li.id}"))
    b.row(InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="cr:clear"))
    b.row(InlineKeyboardButton(text="✅ Оформить заказ", callback_data="cr:co"))
    return b.as_markup()


def delivery_dates_keyboard(today: date) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 9):
        d = today + timedelta(days=i)
        b.add(
            InlineKeyboardButton(
                text=d.strftime("%d.%m"),
                callback_data=f"dl:{d.isoformat()}",
            )
        )
    b.adjust(4)
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ord:x"))
    return b.as_markup()


def delivery_slots_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for slot in get_settings().delivery_slot_list():
        b.add(InlineKeyboardButton(text=slot.replace("-", "–"), callback_data=f"sl:{slot}"))
    b.adjust(1)
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ord:x"))
    return b.as_markup()


def payment_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Наличными при получении", callback_data="pay:cash"))
    if get_settings().online_payment_enabled:
        b.row(InlineKeyboardButton(text="Онлайн (YooKassa)", callback_data="pay:online"))
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="ord:x"))
    return b.as_markup()


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="ord:ok"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="ord:x"),
    )
    return b.as_markup()


def admin_main_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(InlineKeyboardButton(text="📦 Заказы", callback_data="ad:or"))
    b.add(InlineKeyboardButton(text="💰 Цены", callback_data="ad:ct"))
    b.add(InlineKeyboardButton(text="📊 Статистика", callback_data="ad:st"))
    b.add(InlineKeyboardButton(text="📢 Рассылка", callback_data="ad:bc"))
    b.adjust(2)
    return b.as_markup()


def admin_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"ao:a:{order_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ao:r:{order_id}"),
    )
    b.row(InlineKeyboardButton(text="📞 Связаться", callback_data=f"ao:c:{order_id}"))
    return b.as_markup()


def admin_order_status_keyboard(order_id: int, current: str) -> InlineKeyboardMarkup:
    opts = [
        ("new", "🆕 new"),
        ("confirmed", "✅ confirmed"),
        ("in_delivery", "🚚 in_delivery"),
        ("delivered", "📬 delivered"),
        ("cancelled", "❌ cancelled"),
    ]
    b = InlineKeyboardBuilder()
    for code, label in opts:
        mark = "• " if code == current else ""
        b.add(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"os:{order_id}:{code}"))
    b.adjust(1)
    return b.as_markup()
