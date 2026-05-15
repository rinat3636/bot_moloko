from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from milk_bot.bot.db.models import User
from milk_bot.bot.filters.admin import AdminFilter
from milk_bot.bot.states.admin import AdminBroadcastStates

router = Router()


@router.callback_query(F.data == "ad:bc", AdminFilter())
async def broadcast_start(cq: CallbackQuery, state: FSMContext) -> None:
    await cq.answer()
    await state.set_state(AdminBroadcastStates.waiting_body)
    await cq.message.edit_text(
        "Пришлите текст рассылки. Можно одним сообщением фото с подписью.\nОтмена: /cancel",
    )


@router.message(AdminBroadcastStates.waiting_body, F.photo, AdminFilter())
async def broadcast_photo_caption(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = message.caption or ""
    if not text.strip():
        data = await state.get_data()
        if not data.get("text"):
            await message.answer("Добавьте подпись к фото или сначала отправьте текст.")
            return
        text = data["text"]
    await state.update_data(text=text, photo=message.photo[-1].file_id)
    await _ask_confirm(message, state, session)


@router.message(AdminBroadcastStates.waiting_body, F.text, AdminFilter())
async def broadcast_text(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.update_data(text=message.text or "", photo=None)
    await _ask_confirm(message, state, session)


async def _ask_confirm(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(AdminBroadcastStates.waiting_confirm)
    cnt = await session.scalar(
        select(func.count()).select_from(User).where(User.is_blocked.is_(False))
    )
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=f"Отправить ({cnt})", callback_data="bc:go"),
        InlineKeyboardButton(text="Отмена", callback_data="bc:no"),
    )
    await message.answer(f"Получателей: {cnt}. Подтвердите отправку.", reply_markup=b.as_markup())


@router.callback_query(AdminBroadcastStates.waiting_confirm, F.data == "bc:no", AdminFilter())
async def broadcast_cancel_cb(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.answer()
    await cq.message.edit_text("Рассылка отменена.")


@router.callback_query(AdminBroadcastStates.waiting_confirm, F.data == "bc:go", AdminFilter())
async def broadcast_go(
    cq: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    await cq.answer()
    data = await state.get_data()
    text = data.get("text") or ""
    photo = data.get("photo")
    res = await session.execute(select(User.id).where(User.is_blocked.is_(False)))
    ids = [row[0] for row in res.all()]
    ok = err = 0
    delay = 1 / 25
    for uid in ids:
        try:
            if photo:
                await bot.send_photo(uid, photo, caption=text[:1024])
            else:
                await bot.send_message(uid, text[:4096])
            ok += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                if photo:
                    await bot.send_photo(uid, photo, caption=text[:1024])
                else:
                    await bot.send_message(uid, text[:4096])
                ok += 1
            except Exception:
                err += 1
        except Exception:
            err += 1
        await asyncio.sleep(delay)
    await state.clear()
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="ad:hm"))
    await cq.message.edit_text(f"Готово. Отправлено: {ok}, ошибок: {err}.", reply_markup=b.as_markup())
