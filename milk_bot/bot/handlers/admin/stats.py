from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import get_settings
from milk_bot.bot.db.models import Order, OrderItem
from milk_bot.bot.filters.admin import AdminFilter

router = Router()


def _revenue(rows: list[Order]) -> Decimal:
    t = Decimal("0")
    for r in rows:
        t += r.total
    return t.quantize(Decimal("0.01"))


async def build_stats_text(session: AsyncSession) -> str:
    res = await session.execute(select(Order))
    all_o = list(res.scalars().all())
    tz = ZoneInfo(get_settings().timezone)
    now = datetime.now(tz)

    def in_days(n: int) -> list[Order]:
        start = now - timedelta(days=n)
        out: list[Order] = []
        for o in all_o:
            ts = o.created_at
            if ts is None:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=tz)
            else:
                ts = ts.astimezone(tz)
            if ts >= start:
                out.append(o)
        return out

    d1 = in_days(1)
    d7 = in_days(7)
    d30 = in_days(30)

    top = await session.execute(
        select(OrderItem.product_name, func.sum(OrderItem.quantity).label("q"))
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    )
    top_lines = "\n".join(f"{n}: {int(q)}" for n, q in top.all()) or "—"

    return (
        f"📊 <b>Статистика</b>\n\n"
        f"За 24ч: заказов {len(d1)}, сумма {_revenue(d1)} ₽\n"
        f"За 7 дней: {len(d7)}, сумма {_revenue(d7)} ₽\n"
        f"За 30 дней: {len(d30)}, сумма {_revenue(d30)} ₽\n\n"
        f"Топ товаров:\n{top_lines}"
    )


async def send_stats_report(message: Message, session: AsyncSession) -> None:
    await message.answer(await build_stats_text(session), parse_mode="HTML")


@router.callback_query(F.data == "ad:st", AdminFilter())
async def admin_stats(cq: CallbackQuery, session: AsyncSession) -> None:
    await cq.answer()
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    await cq.message.edit_text(
        await build_stats_text(session),
        reply_markup=b.as_markup(),
        parse_mode="HTML",
    )
