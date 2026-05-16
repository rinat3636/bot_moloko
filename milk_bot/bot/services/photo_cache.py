from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import get_admin_ids, get_settings
from milk_bot.bot.db.models import Product

_CACHE_DIR = Path("data/photo_cache")
_memory: dict[str, str] = {}
_locks: dict[str, asyncio.Lock] = {}


def _cache_chat_id() -> int | None:
    settings = get_settings()
    orders = settings.orders_chat_id_int()
    if orders is not None:
        return orders
    admins = get_admin_ids()
    return admins[0] if admins else None


def _disk_path(url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return _CACHE_DIR / f"{key}.bin"


async def _download_to_disk(url: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _disk_path(url)
    if path.is_file() and path.stat().st_size > 0:
        return path
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "milk-bot/1.0"},
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        path.write_bytes(response.content)
    return path


async def resolve_product_photo(
    bot: Bot,
    session: AsyncSession,
    product: Product,
) -> str | None:
    """URL → disk cache → Telegram file_id (сохраняется в БД)."""
    raw = (product.photo_file_id or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        return raw

    cached = _memory.get(raw)
    if cached:
        return cached

    lock = _locks.setdefault(raw, asyncio.Lock())
    async with lock:
        cached = _memory.get(raw)
        if cached:
            return cached

        current = (product.photo_file_id or "").strip()
        if current and not current.startswith(("http://", "https://")):
            return current

        chat_id = _cache_chat_id()
        if chat_id is None:
            logger.warning("No PHOTO cache chat (ADMIN_IDS / ORDERS_CHAT_ID) — using URL")
            return raw

        try:
            path = await _download_to_disk(raw)
            sent = await bot.send_photo(
                chat_id,
                photo=BufferedInputFile(path.read_bytes(), filename="product.jpg"),
                disable_notification=True,
            )
            file_id = sent.photo[-1].file_id
            _memory[raw] = file_id
            product.photo_file_id = file_id
            await session.flush()
            try:
                await sent.delete()
            except Exception:  # noqa: BLE001
                pass
            return file_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("Photo cache failed for {}: {}", raw, exc)
            return raw
