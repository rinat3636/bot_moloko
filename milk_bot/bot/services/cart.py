from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import CartItem


async def get_line(session: AsyncSession, user_id: int, product_id: int) -> CartItem | None:
    res = await session.execute(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        )
    )
    return res.scalars().first()


async def set_quantity(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: int,
) -> CartItem | None:
    if quantity <= 0:
        await remove_product(session, user_id, product_id)
        return None
    from milk_bot.bot.db.models import Product

    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        raise ValueError("inactive")
    line = await get_line(session, user_id, product_id)
    if line is None:
        line = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        session.add(line)
    else:
        line.quantity = quantity
    await session.flush()
    return line


async def add_product(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    delta: int = 1,
) -> CartItem:
    line = await get_line(session, user_id, product_id)
    if line is None:
        line = CartItem(user_id=user_id, product_id=product_id, quantity=max(1, delta))
        session.add(line)
    else:
        line.quantity = max(1, line.quantity + delta)
    await session.flush()
    return line


async def remove_product(session: AsyncSession, user_id: int, product_id: int) -> None:
    line = await get_line(session, user_id, product_id)
    if line:
        await session.delete(line)


async def remove_line_by_id(session: AsyncSession, line_id: int, user_id: int) -> bool:
    res = await session.execute(
        select(CartItem).where(CartItem.id == line_id, CartItem.user_id == user_id)
    )
    line = res.scalars().first()
    if not line:
        return False
    await session.delete(line)
    return True


async def remove_inactive_lines(session: AsyncSession, user_id: int) -> int:
    from milk_bot.bot.services.catalog import cart_lines

    removed = 0
    for li in await cart_lines(session, user_id):
        if li.product is not None and not li.product.is_active:
            await session.delete(li)
            removed += 1
    if removed:
        await session.flush()
    return removed


async def clear_cart(session: AsyncSession, user_id: int) -> None:
    res = await session.execute(select(CartItem).where(CartItem.user_id == user_id))
    for row in res.scalars().all():
        await session.delete(row)


async def adjust_line_quantity(
    session: AsyncSession,
    line_id: int,
    user_id: int,
    delta: int,
) -> CartItem | None:
    res = await session.execute(
        select(CartItem).where(CartItem.id == line_id, CartItem.user_id == user_id)
    )
    line = res.scalars().first()
    if not line:
        return None
    line.quantity += delta
    if line.quantity <= 0:
        await session.delete(line)
        return None
    await session.flush()
    return line
