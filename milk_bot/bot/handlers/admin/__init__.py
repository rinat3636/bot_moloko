from aiogram import Router

from milk_bot.bot.handlers.admin import broadcast, catalog, menu, orders, reply_menu, stats

router = Router()
router.include_router(reply_menu.router)
router.include_router(menu.router)
router.include_router(orders.router)
router.include_router(catalog.router)
router.include_router(broadcast.router)
router.include_router(stats.router)
