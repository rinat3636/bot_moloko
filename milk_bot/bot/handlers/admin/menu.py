from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from loguru import logger

from milk_bot.bot.config import get_admin_ids
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.keyboards.inline import admin_main_keyboard

router = Router()


async def _open_admin_panel(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    admins = get_admin_ids()
    logger.info("/admin from user_id={} admins_configured={}", uid, len(admins))
    if not admins:
        await message.answer(
            "Админ-панель не настроена: на сервере пустой или неверный <b>ADMIN_IDS</b>.\n\n"
            f"Ваш Telegram ID: <code>{uid}</code>\n\n"
            "Добавьте его в Variables на Railway и сделайте Redeploy.",
            parse_mode="HTML",
        )
        return
    if uid not in admins:
        await message.answer(
            "Нет доступа к админ-панели.\n\n"
            f"Ваш Telegram ID: <code>{uid}</code>\n\n"
            "В Railway укажите <b>ADMIN_IDS</b> = этот номер (можно несколько через запятую).\n"
            "Не используйте @username — только цифры.\n"
            "После изменения — Redeploy.",
            parse_mode="HTML",
        )
        return
    await message.answer(
        "Панель администратора:",
        reply_markup=admin_main_keyboard(),
    )


@router.message(Command("admin"))
async def admin_cmd(message: Message) -> None:
    await _open_admin_panel(message)


@router.callback_query(F.data == "ad:hm", AdminFilter())
async def admin_home(cq: CallbackQuery) -> None:
    await cq.answer()
    await cq.message.edit_text("Панель администратора:", reply_markup=admin_main_keyboard())
