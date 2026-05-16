"""Сгенерировать PDF-инструкцию по боту (запуск: python docs/generate_instruction_pdf.py)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("Установите: pip install fpdf2")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "Инструкция_бот_молоко.pdf"

# Шрифт с кириллицей (Windows)
FONT_REGULAR = [
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
FONT_BOLD = [
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
    Path(r"C:\Windows\Fonts\segoeuib.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def find_fonts() -> tuple[Path, Path]:
    regular = next((p for p in FONT_REGULAR if p.is_file()), None)
    bold = next((p for p in FONT_BOLD if p.is_file()), None)
    if not regular:
        raise FileNotFoundError("Не найден шрифт с кириллицей (Arial / DejaVu)")
    return regular, bold or regular


class ManualPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Manual", size=9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Стр. {self.page_no()}", align="C")


def section(pdf: ManualPDF, title: str) -> None:
    pdf.ln(4)
    pdf.set_font("Manual", "B", 14)
    pdf.set_text_color(30, 80, 140)
    pdf.multi_cell(pdf.epw, 8, title)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def bullet(pdf: ManualPDF, text: str) -> None:
    pdf.set_font("Manual", size=11)
    pdf.multi_cell(pdf.epw, 6, f"  -  {text}")


def paragraph(pdf: ManualPDF, text: str) -> None:
    pdf.set_font("Manual", size=11)
    pdf.multi_cell(pdf.epw, 6, text)
    pdf.ln(1)


def _load_site_categories() -> list[str]:
    try:
        sys.path.insert(0, str(ROOT))
        from milk_bot.bot.services.n_i_catalog import fetch_site_category_names

        return asyncio.run(fetch_site_category_names())
    except Exception:
        return [
            "Айран",
            "Кефир",
            "Кисели",
            "Масло сливочное",
            "Масло топлёное",
            "Молоко",
            "Продукты для бизнеса",
            "Простокваша",
            "Ряженка",
            "Сливки",
            "Сметана",
            "Сметанно-творожные",
            "Сырки",
            "Тан",
            "Творог",
            "Творожки",
            "Йогурт",
            "Доп. ассортимент",
        ]


def build() -> None:
    regular, bold = find_fonts()
    pdf = ManualPDF()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("Manual", "", str(regular))
    pdf.add_font("Manual", "B", str(bold))
    pdf.add_page()

    pdf.set_font("Manual", "B", 18)
    pdf.multi_cell(pdf.epw, 10, "Инструкция: бот доставки молока")
    pdf.set_font("Manual", size=11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(pdf.epw, 6, "Краткое описание функций для жильцов и администратора")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    section(pdf, "1. Для жильца (покупателя)")
    paragraph(
        pdf,
        "Найдите бота в Telegram и нажмите «Запустить» (/start). "
        "Внизу экрана — кнопки меню.",
    )
    bullet(pdf, "Каталог — выбор категории и товара, просмотр фото и описания, добавление в корзину.")
    bullet(pdf, "Корзина — список выбранного, изменение количества, оформление заказа.")
    bullet(
        pdf,
        "Оформление заказа — одним сообщением три строки: имя, телефон, адрес доставки; "
        "затем дата и время доставки; подтверждение.",
    )
    bullet(pdf, "Мои заказы — история заказов и отмена (если заказ ещё новый и до доставки есть время).")
    bullet(pdf, "О доставке — условия, оплата наличными при получении.")
    bullet(pdf, "Контакты — как связаться по вопросам заказа.")
    bullet(pdf, "Отмена действия — команда /cancel, если бот просит ввести данные.")

    section(pdf, "2. Для администратора")
    paragraph(
        pdf,
        "После /start администратору показывается панель с кнопками. "
        "Доступ только у указанных в настройках Telegram-ID.",
    )
    bullet(pdf, "Заказы — список, фильтры, смена статуса (новый, принят, в доставке, доставлен, отменён).")
    bullet(
        pdf,
        "Цены — только в боте. С сайта n-i.ru подтягиваются название, фото и описание; "
        "цен на сайте нет, их выставляет администратор в разделе «Цены».",
    )
    bullet(pdf, "Статистика — сводка по заказам за период.")
    bullet(pdf, "Рассылка — сообщение всем пользователям бота (текст или фото с подписью).")

    section(pdf, "3. Каталог с сайта")
    paragraph(
        pdf,
        "Ассортимент большой: разделы и товары подтягиваются с n-i.ru. "
        "В боте покупатель сначала выбирает категорию, затем товар.",
    )
    categories = _load_site_categories()
    if categories:
        pdf.set_font("Manual", "B", 11)
        pdf.multi_cell(pdf.epw, 6, "Разделы каталога (с сайта):")
        pdf.set_font("Manual", size=10)
        cols = 2
        col_w = pdf.epw / cols
        y_start = pdf.get_y()
        x_left = pdf.l_margin
        half = (len(categories) + 1) // 2
        for i, name in enumerate(categories):
            col = 0 if i < half else 1
            row = i if col == 0 else i - half
            pdf.set_xy(x_left + col * col_w, y_start + row * 5.5)
            pdf.cell(col_w, 5.5, f"  -  {name}")
        pdf.set_y(y_start + max(half, len(categories) - half) * 5.5 + 4)
    bullet(pdf, "При первом запуске и раз в сутки каталог обновляется (названия, описания, фото).")
    bullet(
        pdf,
        "На сайте цен нет — у новых позиций в боте 0 ₽, пока администратор не задаст цену в «Цены».",
    )
    bullet(pdf, "Товары, снятые с сайта, скрываются из каталога для покупателей.")
    bullet(
        pdf,
        "Появились новые разделы на сайте — они подтянутся при следующем обновлении каталога.",
    )

    section(pdf, "4. Оплата и доставка")
    bullet(pdf, "Оплата — наличными курьеру при получении.")
    bullet(pdf, "Дату и интервал доставки клиент выбирает при оформлении.")
    bullet(pdf, "О новом заказе администратор получает уведомление в Telegram.")

    section(pdf, "5. Полезные команды")
    bullet(pdf, "/start — главное меню и (для админа) панель управления.")
    bullet(pdf, "/cancel — отменить текущее действие (оформление заказа, ввод цены и т.д.).")

    pdf.ln(6)
    pdf.set_font("Manual", size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        pdf.epw,
        5,
        "Документ описывает функции бота. Технические настройки сервера "
        "выполняет разработчик или ответственный за эксплуатацию.",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"Создан файл: {OUT}")


if __name__ == "__main__":
    build()
