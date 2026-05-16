from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from milk_bot.bot.config import is_admin

MAIN_MENU_TEXTS = frozenset(
    {
        "🥛 Каталог",
        "🔍 Поиск",
        "🛒 Корзина",
        "📦 Мои заказы",
        "ℹ️ О доставке",
        "📞 Контакты",
    }
)

ADMIN_MENU_TEXTS = frozenset(
    {
        "📦 Заказы",
        "💰 Цены",
        "📊 Статистика",
        "📢 Рассылка",
    }
)

ADMIN_ORDERS = "📦 Заказы"
ADMIN_PRICES = "💰 Цены"
ADMIN_STATS = "📊 Статистика"
ADMIN_BROADCAST = "📢 Рассылка"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🥛 Каталог"),
                KeyboardButton(text="🔍 Поиск"),
            ],
            [KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="ℹ️ О доставке")],
            [KeyboardButton(text="📞 Контакты")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Каталог · поиск · корзина",
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_ORDERS), KeyboardButton(text=ADMIN_PRICES)],
            [KeyboardButton(text=ADMIN_STATS), KeyboardButton(text=ADMIN_BROADCAST)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Управление ботом",
    )


def menu_keyboard_for(user_id: int) -> ReplyKeyboardMarkup:
    if is_admin(user_id):
        return admin_menu_keyboard()
    return main_menu_keyboard()


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
