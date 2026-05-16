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
