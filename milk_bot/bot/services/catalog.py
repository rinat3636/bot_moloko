from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from milk_bot.bot.db.models import CartItem, Category, Product


async def list_categories(session: AsyncSession, *, active_only: bool = False) -> list[Category]:
    if not active_only:
        res = await session.execute(
            select(Category).order_by(Category.sort_order, Category.name)
        )
        return list(res.scalars().all())
    res = await session.execute(
        select(Category)
        .where(
            select(Product.id)
            .where(Product.category_id == Category.id, Product.is_active.is_(True))
            .exists()
        )
        .order_by(Category.sort_order, Category.name)
    )
    return list(res.scalars().all())


async def count_products_in_category(session: AsyncSession, category_id: int) -> int:
    q = await session.execute(
        select(func.count())
        .select_from(Product)
        .where(
            Product.category_id == category_id,
            Product.is_active.is_(True),
        )
    )
    return int(q.scalar_one())


async def list_products_page(
    session: AsyncSession,
    category_id: int,
    offset: int,
    limit: int,
) -> list[Product]:
    res = await session.execute(
        select(Product)
        .where(
            Product.category_id == category_id,
            Product.is_active.is_(True),
        )
        .order_by(Product.id)
        .offset(offset)
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    res = await session.execute(select(Product).where(Product.id == product_id))
    return res.scalars().first()


async def get_category(session: AsyncSession, category_id: int) -> Category | None:
    res = await session.execute(select(Category).where(Category.id == category_id))
    return res.scalars().first()


async def count_category_products_total(session: AsyncSession, category_id: int) -> int:
    q = await session.execute(
        select(func.count()).select_from(Product).where(Product.category_id == category_id)
    )
    return int(q.scalar_one())


async def rename_category(session: AsyncSession, category_id: int, name: str) -> Category | None:
    cat = await get_category(session, category_id)
    if not cat:
        return None
    cat.name = name
    await session.flush()
    return cat


async def delete_category(session: AsyncSession, category_id: int) -> tuple[bool, str]:
    total = await count_category_products_total(session, category_id)
    if total > 0:
        return False, f"В категории {total} товар(ов). Сначала удалите или перенесите их."
    cat = await get_category(session, category_id)
    if not cat:
        return False, "Категория не найдена."
    await session.delete(cat)
    await session.flush()
    return True, "Категория удалена."


async def cart_lines(session: AsyncSession, user_id: int) -> list[CartItem]:
    res = await session.execute(
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.id)
    )
    return list(res.scalars().all())


async def cart_total(session: AsyncSession, user_id: int) -> Decimal:
    lines = await cart_lines(session, user_id)
    total = Decimal("0")
    for li in lines:
        total += li.product.price * li.quantity  # type: ignore[union-attr]
    return total.quantize(Decimal("0.01"))
