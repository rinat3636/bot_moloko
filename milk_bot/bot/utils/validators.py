from __future__ import annotations

import re


def validate_full_name(text: str) -> tuple[bool, str]:
    t = (text or "").strip()
    if len(t) < 3:
        return False, "Введите ФИО полностью."
    if re.search(r"\d", t):
        return False, "В ФИО не должно быть цифр."
    words = [w for w in re.split(r"\s+", t) if w]
    if len(words) < 2:
        return False, "Нужно минимум два слова (фамилия и имя)."
    word_re = re.compile(r"^[A-Za-zА-Яа-яЁё\-']+$")
    for w in words:
        if not word_re.match(w):
            return False, "Допустимы только буквы кириллицы/латиницы, дефис и апостроф."
    return True, t


def normalize_phone(raw: str) -> tuple[bool, str]:
    s = (raw or "").strip().replace(" ", "").replace("-", "")
    if s.startswith("8") and len(s) == 11 and s[1:].isdigit():
        return True, "+7" + s[1:]
    if s.startswith("+7") and len(s) == 12 and s[2:].isdigit():
        return True, s
    if s.startswith("7") and len(s) == 11 and s[1:].isdigit():
        return True, "+" + s[1:]
    return False, ""


def validate_address(text: str) -> tuple[bool, str]:
    t = (text or "").strip()
    if len(t) < 10:
        return False, "Адрес слишком короткий (минимум 10 символов)."
    return True, t
