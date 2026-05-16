from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

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
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
