from __future__ import annotations

import html
import re
from decimal import Decimal

from milk_bot.bot.db.models import Product
from milk_bot.bot.utils.formatters import format_money

# Лимит Telegram для текста inline-кнопки
_BTN_MAX_LEN = 64


def product_button_label(index: int, name: str, price: Decimal) -> str:
    """Короткая подпись кнопки: номер + хвост названия (вкус/фасовка) + цена."""
    price_s = format_money(price)
    prefix = f"{index}. "
    suffix = f" · {price_s}"
    room = _BTN_MAX_LEN - len(prefix) - len(suffix)
    if room < 6:
        return f"{prefix}{name[: max(1, room)]}{suffix}"[:_BTN_MAX_LEN]

    core = _compact_name(name)
    if len(core) <= room:
        return f"{prefix}{core}{suffix}"

    tail = core[-(room - 1) :].lstrip(" ,·\"'")
    return f"{prefix}…{tail}{suffix}"


def _compact_name(name: str) -> str:
    """Убирает повторяющийся префикс категории, оставляет отличительную часть."""
    t = re.sub(r"\s+", " ", (name or "").strip())
    for marker in (
        " со вкусом ",
        " со вкусом",
        " натуральный ",
        " натуральный",
        " бутылка ",
        " стакан ",
        " вес ",
        " жирность ",
    ):
        pos = t.lower().find(marker.strip())
        if pos > 8:
            return t[pos:].strip()
    return t


def format_category_products_message(
    products: list[Product],
    *,
    title: str,
    page: int,
    pages: int,
) -> str:
    lines = [
        f"<b>{html.escape(title)}</b>",
        f"Стр. {page + 1} из {pages}",
        "",
    ]
    for i, p in enumerate(products, start=1):
        lines.append(f"{i}. {html.escape(p.name)} — {format_money(p.price)}")
    lines.extend(["", "Выберите товар по номеру:"])
    return "\n".join(lines)


def format_search_results_message(
    products: list[Product],
    *,
    query: str,
    page: int,
    pages: int,
    total: int,
) -> str:
    q = html.escape(query)
    lines = [
        f"<b>🔍 Поиск:</b> {q}",
        f"Найдено: {total} · стр. {page + 1} из {pages}",
        "",
    ]
    if not products:
        lines.append("Ничего не найдено. Попробуйте другое слово (например «молоко», «кефир»).")
        return "\n".join(lines)
    for i, p in enumerate(products, start=1):
        lines.append(f"{i}. {html.escape(p.name)} — {format_money(p.price)}")
    lines.extend(["", "Выберите товар:"])
    return "\n".join(lines)
