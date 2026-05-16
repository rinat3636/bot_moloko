from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.config import is_admin
from milk_bot.bot.db.models import Order
from milk_bot.bot.handlers.common import block_if_busy_fsm
from milk_bot.bot.keyboards.reply import ADMIN_MENU_TEXTS, MAIN_MENU_TEXTS, menu_keyboard_for
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.states.contact import ContactStates
from milk_bot.bot.utils.menu_keyboard import answer_with_menu

router = Router()


@router.message(F.text == "📞 Контакты")
async def contacts_start(message: Message, state: FSMContext) -> None:
    if not await block_if_busy_fsm(message, state):
        return
    if is_admin(message.from_user.id if message.from_user else 0):
        return
    await state.clear()
    await state.set_state(ContactStates.waiting_message)
    uid = message.from_user.id if message.from_user else 0
    await message.answer(
        "📞 <b>Обратная связь</b>\n\n"
        "Напишите <b>одним сообщением</b> вопрос, пожелание или замечание — "
        "мы передадим администратору и ответим здесь же в чате.\n\n"
        "Отмена: /cancel",
        parse_mode="HTML",
        reply_markup=menu_keyboard_for(uid),
    )


async def _client_phone_from_orders(session: AsyncSession, user_id: int) -> str | None:
    result = await session.execute(
        select(Order.phone)
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.message(ContactStates.waiting_message, F.text)
async def contacts_message(
    message: Message, state: FSMContext, bot, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if text in MAIN_MENU_TEXTS or text in ADMIN_MENU_TEXTS:
        await state.clear()
        if text == "📞 Контакты":
            await contacts_start(message, state)
        return
    if len(text) < 3:
        await message.answer("Слишком коротко. Напишите обращение подробнее (от 3 символов).")
        return
    uid = message.from_user.id if message.from_user else 0
    phone = await _client_phone_from_orders(session, uid)
    await notifier_service.notify_admins_contact_message(
        bot,
        user_id=uid,
        full_name=message.from_user.full_name if message.from_user else None,
        phone=phone,
        username=message.from_user.username if message.from_user else None,
        text=text,
    )
    await state.clear()
    await answer_with_menu(
        message,
        "Спасибо! Ваше обращение принято — ответим в этом чате.",
    )
