from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import Order
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.services import notifier as notifier_service
from milk_bot.bot.states.admin import AdminContactReplyStates
from milk_bot.bot.utils.fsm import clear_state_if_set

router = Router()


async def _last_order_contact(session: AsyncSession, user_id: int) -> tuple[str | None, str | None]:
    result = await session.execute(
        select(Order.full_name, Order.phone)
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None, None
    return row[0], row[1]


async def _start_reply_to_client(
    event: Message | CallbackQuery,
    state: FSMContext,
    *,
    client_user_id: int,
    client_label: str,
) -> None:
    await clear_state_if_set(state)
    await state.set_state(AdminContactReplyStates.waiting_text)
    await state.update_data(
        client_user_id=client_user_id,
        client_label=client_label,
    )
    text = (
        f"💬 Ответ клиенту <b>{client_label}</b>\n\n"
        "Напишите текст — он придёт клиенту в этот бот.\n"
        "Отмена: /cancel"
    )
    if isinstance(event, CallbackQuery):
        assert event.message is not None
        await event.message.answer(text, parse_mode="HTML")
    else:
        await event.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("cr:"), AdminFilter())
async def contact_reply_start(cq: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await cq.answer()
    client_user_id = int(cq.data.split(":")[1])
    name, phone = await _last_order_contact(session, client_user_id)
    label = name or "клиент"
    if phone:
        label = f"{label}, {phone}"
    await _start_reply_to_client(cq, state, client_user_id=client_user_id, client_label=label)


@router.message(AdminContactReplyStates.waiting_text, AdminFilter())
async def contact_reply_send(message: Message, state: FSMContext, bot) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите текст ответа или /cancel")
        return
    data = await state.get_data()
    client_user_id = int(data["client_user_id"])
    client_label = data.get("client_label", "клиент")
    ok = await notifier_service.send_contact_reply_to_client(bot, client_user_id, text)
    await state.clear()
    if ok:
        await message.answer(f"✅ Ответ отправлен: {client_label}")
    else:
        await message.answer(
            "Не удалось доставить сообщение — возможно, клиент заблокировал бота "
            "или ещё не нажимал /start."
        )
