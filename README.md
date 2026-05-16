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

## Деплой на Railway / Render / Docker

Платформа должна собирать образ из **Dockerfile** (уже в репозитории) или использовать `nixpacks.toml`.

**Тип сервиса:** Worker / Background — не Web (у бота polling, нет HTTP-порта).

**Переменные в панели хостинга (обязательно):**

| Переменная | Пример |
|------------|--------|
| `BOT_TOKEN` | от @BotFather |
| `ADMIN_IDS` | `123456789` |
| `PYTHONPATH` | `/app` (для Docker) или `.` (Nixpacks) |
| `DATABASE_URL` | `sqlite+aiosqlite:////app/data/milk_bot.db` (путь на постоянный диск/volume) |

Опционально: `ORDERS_CHAT_ID`, `MIN_ORDER_AMOUNT`, `DELIVERY_SLOTS`, `TIMEZONE`.

После депоя один раз выполните импорт каталога (Shell на сервере):

```bash
python -m scripts.import_catalog
```

**Railway:** `railway.toml` указывает `builder = "DOCKERFILE"`.  
**Render:** Blueprint `render.yaml` — тип `worker`, runtime `docker`.

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
6. `/admin`: категории (создать, переименовать, удалить без товаров), товары (создать, правка цены/названия/описания/фото, скрыть, удалить), фильтры заказов по статусу и дате доставки, смена статусов — клиент получает сообщение.
7. Рассылка: подтверждение, лимит ~25 сообщ/с, отчёт.
8. Импорт каталога идемпотентен по `source_url`. С сайта [n-i.ru](https://n-i.ru/moloko.html) подтягиваются **название, описание, URL фото** (в боте показываются как картинка). **Цен на сайте нет** — после импорта цены **0 ₽**, выставляются в `/admin` → Каталог.
