from __future__ import annotations

from decimal import Decimal

from milk_bot.bot.db.models import Order


def format_money(value: Decimal | float | int) -> str:
    if isinstance(value, Decimal):
        v = value
    else:
        v = Decimal(str(value))
    return f"{v.quantize(Decimal('0.01'))} ₽"


def order_lines_preview(order: Order) -> str:
    lines: list[str] = []
    for it in order.items:
        sub = (it.price * it.quantity).quantize(Decimal("0.01"))
        lines.append(f"• {it.product_name} × {it.quantity} = {format_money(sub)}")
    return "\n".join(lines) if lines else "(пусто)"
