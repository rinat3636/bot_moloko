from aiogram import Router

from milk_bot.bot.handlers import start


def setup_routers() -> Router:
    root = Router()
    root.include_router(start.router)
    return root
