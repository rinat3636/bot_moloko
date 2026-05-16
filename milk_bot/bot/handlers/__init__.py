from aiogram import Router

from milk_bot.bot.handlers import cart, catalog, common, contact, my_orders, order, start
from milk_bot.bot.handlers.admin import router as admin_router


def setup_routers() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(admin_router)
    root.include_router(catalog.router)
    root.include_router(contact.router)
    root.include_router(cart.router)
    root.include_router(order.router)
    root.include_router(my_orders.router)
    root.include_router(start.router)
    return root
