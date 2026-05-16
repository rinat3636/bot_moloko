from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from milk_bot.bot.config import get_settings, is_admin
from milk_bot.bot.keyboards.inline import admin_main_keyboard
from milk_bot.bot.keyboards.reply import main_menu_keyboard
from milk_bot.bot.utils.formatters import format_money

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    user_is_admin = is_admin(uid)

    if user_is_admin:
        await message.answer(
            "<b>Панель администратора</b>\n\n"
            "Кнопки <b>в этом сообщении</b> (не внизу экрана):\n"
            "📦 Заказы · 💰 Цены · 📊 Статистика · 📢 Рассылка\n\n"
            "Открыть снова — отправьте /start",
            reply_markup=admin_main_keyboard(),
            parse_mode="HTML",
        )

    await message.answer(
        "Здравствуйте! Доставка молочной продукции до двери.\n"
        + (
            "Меню <b>внизу</b> — для заказов (как у покупателей)."
            if user_is_admin
            else "Выберите раздел в меню ниже."
        ),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML" if user_is_admin else None,
    )

@router.message(F.text == "ℹ️ О доставке")
async def about_delivery(message: Message, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm

    if not await block_if_busy_fsm(message, state):
        return
    settings = get_settings()
    lines = [
        "🥛 <b>О доставке</b>",
        "",
        "Привозим свежую молочную продукцию <b>до двери</b>.",
        "",
        "При оформлении заказа выберите удобные <b>дату</b> и <b>время</b> — "
        "мы привезём заказ в выбранный интервал.",
        "",
        "Оплата — <b>наличными</b> при получении.",
    ]
    if settings.min_order_amount > 0:
        lines.extend(
            [
                "",
                f"Минимальная сумма заказа — <b>{format_money(settings.min_order_amount)}</b>.",
            ]
        )
    lines.extend(["", "Вопросы по заказу — напишите нам после оформления, мы на связи."])
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📞 Контакты")
async def contacts(message: Message, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm

    if not await block_if_busy_fsm(message, state):
        return
    await message.answer(
        "📞 <b>Контакты</b>\n\n"
        "После оформления заказа все вопросы можно задать <b>в этом чате</b> — "
        "мы ответим по статусу доставки и составу заказа.\n\n"
        "Срочные вопросы — через управляющую компанию вашего дома.",
        parse_mode="HTML",
    )
