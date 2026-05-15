from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from milk_bot.bot.config import get_settings
from milk_bot.bot.db.models import CartItem, Order, OrderItem, Product
from milk_bot.bot.services import cart as cart_service


async def create_order_from_cart(
    session: AsyncSession,
    user_id: int,
    *,
    full_name: str,
    phone: str,
    address: str,
    delivery_date: date,
    delivery_slot: str,
    payment_method: str,
    comment: str | None = None,
) -> Order:
    settings = get_settings()
    lines = await session.execute(
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(CartItem.user_id == user_id)
    )
    items = list(lines.scalars().all())
    if not items:
        raise ValueError("empty_cart")
    total = Decimal("0")
    snapshots: list[tuple[Product, int]] = []
    for li in items:
        p = li.product
        if not p or not p.is_active:
            continue
        line_sum = p.price * li.quantity
        total += line_sum
        snapshots.append((p, li.quantity))
    if not snapshots:
        raise ValueError("empty_cart")
    total = total.quantize(Decimal("0.01"))
    if total < Decimal(str(settings.min_order_amount)):
        raise ValueError("min_amount")

    order = Order(
        user_id=user_id,
        full_name=full_name,
        phone=phone,
        address=address,
        delivery_date=delivery_date,
        delivery_slot=delivery_slot,
        payment_method=payment_method,
        status="new",
        total=total,
        comment=comment,
    )
    session.add(order)
    await session.flush()
    for p, qty in snapshots:
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=p.id,
                product_name=p.name,
                price=p.price,
                quantity=qty,
            )
        )
    await cart_service.clear_cart(session, user_id)
    await session.flush()
    res = await session.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return res.scalar_one()


async def list_user_orders(session: AsyncSession, user_id: int, limit: int = 10) -> list[Order]:
    res = await session.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    res = await session.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    return res.scalars().first()


async def can_customer_cancel(session: AsyncSession, order: Order) -> bool:
    if order.status != "new":
        return False
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    start = datetime.combine(order.delivery_date, datetime.min.time(), tzinfo=tz)
    deadline = start - timedelta(hours=settings.cancel_deadline_hours)
    now = datetime.now(tz)
    return now < deadline


async def cancel_order_customer(session: AsyncSession, order: Order) -> None:
    order.status = "cancelled"
    await session.flush()


async def set_order_status(session: AsyncSession, order_id: int, status: str) -> Order | None:
    order = await get_order(session, order_id)
    if not order:
        return None
    order.status = status
    await session.flush()
    return order
