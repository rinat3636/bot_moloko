from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from milk_bot.bot.config import get_settings


def delivery_date_bounds() -> tuple[date, date]:
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    return today + timedelta(days=1), today + timedelta(days=8)


def is_allowed_delivery_date(d: date) -> bool:
    start, end = delivery_date_bounds()
    return start <= d <= end


def is_allowed_delivery_slot(slot: str) -> bool:
    return slot in get_settings().delivery_slot_list()
