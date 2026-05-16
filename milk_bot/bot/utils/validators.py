from __future__ import annotations

import re


def validate_name(text: str) -> tuple[bool, str]:
    t = (text or "").strip()
    if len(t) < 2:
        return False, "Введите имя (минимум 2 символа)."
    if re.search(r"\d", t):
        return False, "В имени не должно быть цифр."
    if not re.match(r"^[A-Za-zА-Яа-яЁё\-'\s]+$", t):
        return False, "Допустимы только буквы, пробелы, дефис и апостроф."
    return True, t


def normalize_phone(raw: str) -> tuple[bool, str]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits[0] == "8":
        return True, "+7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return True, "+" + digits
    if len(digits) == 10 and digits[0] in "987":
        return True, "+7" + digits
    return False, ""


def parse_checkout_contacts(text: str) -> tuple[bool, str, dict[str, str] | None]:
    """Имя, телефон и адрес — три строки в одном сообщении (адрес может быть многострочным)."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 3:
        return (
            False,
            "Отправьте одним сообщением три строки:\n"
            "1) имя\n2) телефон\n3) адрес\n\n"
            "Пример:\nРинат\n89001234567\nул. Пример, д. 1, кв. 15",
            None,
        )
    ok, name = validate_name(lines[0])
    if not ok:
        return False, name, None
    ok, phone = normalize_phone(lines[1])
    if not ok:
        return (
            False,
            "Неверный телефон во 2-й строке. Укажите 10 цифр (9XXXXXXXXX) "
            "или 11 с 8/7 в начале.",
            None,
        )
    address_text = "\n".join(lines[2:])
    ok, address = validate_address(address_text)
    if not ok:
        return False, address, None
    return True, "", {"full_name": name, "phone": phone, "address": address}


def validate_address(text: str) -> tuple[bool, str]:
    t = (text or "").strip()
    if len(t) < 10:
        return False, "Адрес слишком короткий (минимум 10 символов)."
    return True, t
