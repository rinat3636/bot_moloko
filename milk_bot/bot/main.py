from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from milk_bot.bot.config import get_settings
from milk_bot.bot.handlers import setup_routers
from milk_bot.bot.middlewares.db import DbSessionMiddleware
from milk_bot.bot.middlewares.user import UserMiddleware
from milk_bot.bot.utils.telegram import chat_id_from_update, user_id_from_update


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    logger.add(
        log_dir / "milk_bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="14 days",
        level=settings.log_level,
        encoding="utf-8",
    )


async def main() -> None:
    settings = get_settings()
    configure_logging()
    from milk_bot.bot.config import get_admin_ids

    admin_count = len(get_admin_ids())
    if admin_count:
        logger.info("ADMIN_IDS loaded: {} admin(s)", admin_count)
    else:
        logger.warning("ADMIN_IDS is empty or invalid — admin panel on /start disabled")
    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserMiddleware())

    dp.include_router(setup_routers())

    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    if settings.catalog_import_enabled:

        async def daily_catalog_import() -> None:
            from milk_bot.bot.services.catalog_import import run_catalog_import

            try:
                result = await run_catalog_import(if_empty=False)
                if result:
                    logger.info(
                        "Daily catalog sync: +{} new, {} updated, {} hidden",
                        result.inserted,
                        result.updated,
                        result.deactivated,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Daily catalog import failed: {}", exc)

        scheduler.add_job(
            daily_catalog_import,
            trigger="cron",
            hour=settings.catalog_import_hour,
            minute=0,
            id="catalog_import_daily",
            replace_existing=True,
        )
        logger.info(
            "Catalog auto-sync from n-i.ru scheduled daily at {:02d}:00 ({})",
            settings.catalog_import_hour,
            settings.timezone,
        )

    scheduler.start()

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception("Unhandled error: {}", event.exception)
        update = event.update
        chat_id = chat_id_from_update(update)
        user_id = user_id_from_update(update)
        if chat_id:
            try:
                await bot.send_message(
                    chat_id,
                    "Произошла ошибка. Попробуйте ещё раз или нажмите /start.",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to notify user chat {}: {}", chat_id, exc)
        from milk_bot.bot.config import get_admin_ids

        admins = get_admin_ids()
        detail = (
            f"⚠️ Ошибка бота\n"
            f"chat_id={chat_id} user_id={user_id}\n"
            f"<code>{event.exception}</code>"
        )
        for aid in admins:
            try:
                await bot.send_message(aid, detail)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to alert admin {}: {}", aid, exc)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
