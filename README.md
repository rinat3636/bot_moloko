# Milk delivery Telegram bot (MVP)

Python 3.11+, **aiogram 3**, **SQLAlchemy 2 async** (SQLite), **httpx** + **selectolax** for one-off catalog import, **APScheduler**, **pydantic-settings**, **loguru**.

## Важно про FSM

Используется `MemoryStorage`: после перезапуска процесса незавершённые сценарии сбрасываются. Для продакшена рассмотрите Redis или дисковое хранилище.

## Локальный запуск

```powershell
cd bot_moloko
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # заполните BOT_TOKEN и ADMIN_IDS
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.import_catalog
.\.venv\Scripts\python.exe -m milk_bot.bot.main
```

## VPS (Ubuntu 22.04+, systemd)

1. `sudo apt update && sudo apt install -y python3.11 python3.11-venv git`
2. Клонировать репозиторий, создать venv, `pip install -r requirements.txt`
3. Скопировать `.env` из `.env.example`, задать `BOT_TOKEN`, `ADMIN_IDS`, при необходимости `ORDERS_CHAT_ID`
4. `alembic upgrade head`
5. `python -m scripts.import_catalog`
6. Скопировать `deploy/milk_bot.service` в `/etc/systemd/system/milk_bot.service`, поправить `User`, `WorkingDirectory`, `EnvironmentFile`
7. `sudo systemctl daemon-reload && sudo systemctl enable --now milk_bot`
8. Логи: `journalctl -u milk_bot -f` и файлы в каталоге `logs/`

## Приёмка (краткий E2E)

1. Пользователь `/start` — появляется меню, запись в таблице `users`.
2. Каталог: категории → товары с пагинацией → карточка → «В корзину».
3. Корзина: +/- , очистка, оформление.
4. FSM: ФИО → телефон (контакт или текст) → адрес → дата → слот → оплата → подтверждение.
5. После подтверждения: заказ в БД, уведомление клиенту, всем админам и в `ORDERS_CHAT_ID` при наличии.
6. `/admin`: CRUD каталога (базовый сценарий), смена статусов заказа — клиент получает сообщение.
7. Рассылка: подтверждение, лимит ~25 сообщ/с, отчёт.
8. Импорт каталога идемпотентен по `source_url`.
