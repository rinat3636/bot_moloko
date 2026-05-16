from __future__ import annotations

import html

from milk_bot.bot.db.models import Product
from milk_bot.bot.utils.formatters import format_money


def format_product_card_caption(product: Product, qty: int) -> str:
    """Единый вид карточки товара в каталоге (импорт и ручное добавление)."""
    name = html.escape(product.name)
    desc = (product.description or "").strip()
    if desc:
        body = html.escape(desc)
    else:
        body = "<i>Описание уточняется</i>"
    return (
        f"<b>{name}</b>\n"
        f"{body}\n\n"
        f"Цена: {format_money(product.price)}\n"
        f"Количество: <b>{qty}</b>"
    )


def validate_product_for_storefront(
    *,
    name: str,
    description: str | None,
    photo_file_id: str | None,
    price: object | None = None,
) -> tuple[bool, str]:
    n = (name or "").strip()
    if len(n) < 2:
        return False, "Название слишком короткое (минимум 2 символа)."
    d = (description or "").strip()
    if len(d) < 5:
        return False, "Добавьте описание (как у товаров из каталога, минимум 5 символов)."
    if not (photo_file_id or "").strip():
        return False, "Нужно фото товара — без него карточка в каталоге выглядит иначе."
    if price is not None:
        try:
            from decimal import Decimal

            p = Decimal(str(price))
            if p < 0:
                return False, "Цена не может быть отрицательной."
        except Exception:  # noqa: BLE001
            return False, "Неверная цена."
    return True, ""
