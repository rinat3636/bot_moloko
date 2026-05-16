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


async def get_cart_checkout_summary(
    session: AsyncSession,
    user_id: int,
) -> tuple[list[tuple[Product, int]], list[str]]:
    lines = await session.execute(
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(CartItem.user_id == user_id)
    )
    items = list(lines.scalars().all())
    if not items:
        raise ValueError("empty_cart")
    snapshots: list[tuple[Product, int]] = []
    skipped: list[str] = []
    for li in items:
        p = li.product
        if not p:
            continue
        if not p.is_active:
            skipped.append(p.name)
            continue
        snapshots.append((p, li.quantity))
    if not snapshots:
        raise ValueError("inactive_only")
    return snapshots, skipped


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
) -> tuple[Order, list[str]]:
    settings = get_settings()
    snapshots, skipped = await get_cart_checkout_summary(session, user_id)
    total = Decimal("0")
    for p, qty in snapshots:
        total += p.price * qty
    total = total.quantize(Decimal("0.01"))
    if total <= 0:
        raise ValueError("zero_total")
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
    return res.scalar_one(), skipped


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


ORDER_STATUSES = ("new", "confirmed", "in_delivery", "delivered", "cancelled")


async def list_orders_admin(
    session: AsyncSession,
    *,
    status: str | None = None,
    delivery_date: date | None = None,
    delivery_from: date | None = None,
    delivery_to: date | None = None,
    limit: int = 30,
) -> list[Order]:
    q = (
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.id.desc())
        .limit(limit)
    )
    if status:
        q = q.where(Order.status == status)
    if delivery_date is not None:
        q = q.where(Order.delivery_date == delivery_date)
    if delivery_from is not None:
        q = q.where(Order.delivery_date >= delivery_from)
    if delivery_to is not None:
        q = q.where(Order.delivery_date <= delivery_to)
    res = await session.execute(q)
    return list(res.scalars().unique().all())


def is_valid_order_status(status: str) -> bool:
    return status in ORDER_STATUSES


async def set_order_status(session: AsyncSession, order_id: int, status: str) -> Order | None:
    if not is_valid_order_status(status):
        raise ValueError("invalid_status")
    order = await get_order(session, order_id)
    if not order:
        return None
    order.status = status
    await session.flush()
    return order
