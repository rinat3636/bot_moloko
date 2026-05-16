from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from milk_bot.bot.config import get_settings, is_admin
from milk_bot.bot.utils.formatters import format_money
from milk_bot.bot.utils.menu_keyboard import answer_with_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0

    if is_admin(uid):
        await answer_with_menu(
            message,
            "Режим <b>администратора</b>.\n\n"
            "Внизу: заказы, цены, статистика, рассылка.\n"
            "Покупательское меню (каталог, корзина) вам не показывается.",
            parse_mode="HTML",
        )
        return

    await answer_with_menu(
        message,
        "Здравствуйте! Доставка молочной продукции до двери.\n"
        "Выберите раздел в меню ниже.",
    )


@router.message(F.text == "ℹ️ О доставке")
async def about_delivery(message: Message, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm
    from milk_bot.bot.keyboards.reply import menu_keyboard_for

    if not await block_if_busy_fsm(message, state):
        return
    if is_admin(message.from_user.id if message.from_user else 0):
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
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=menu_keyboard_for(message.from_user.id if message.from_user else 0),
    )


@router.message(F.text == "📞 Контакты")
async def contacts(message: Message, state: FSMContext) -> None:
    from milk_bot.bot.handlers.common import block_if_busy_fsm
    from milk_bot.bot.keyboards.reply import menu_keyboard_for

    if not await block_if_busy_fsm(message, state):
        return
    if is_admin(message.from_user.id if message.from_user else 0):
        return
    await message.answer(
        "📞 <b>Контакты</b>\n\n"
        "После оформления заказа все вопросы можно задать <b>в этом чате</b> — "
        "мы ответим по статусу доставки и составу заказа.\n\n"
        "Срочные вопросы — через управляющую компанию вашего дома.",
        parse_mode="HTML",
        reply_markup=menu_keyboard_for(message.from_user.id if message.from_user else 0),
    )
