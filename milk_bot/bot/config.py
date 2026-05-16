from __future__ import annotations

from functools import lru_cache
from typing import List

from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")
    orders_chat_id: str | None = Field(default=None, alias="ORDERS_CHAT_ID")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./milk_bot.db",
        alias="DATABASE_URL",
    )
    online_payment_enabled: bool = Field(
        default=False,
        alias="ONLINE_PAYMENT_ENABLED",
    )
    delivery_slots: str = Field(
        default="10:00-12:00,12:00-14:00,14:00-16:00,16:00-18:00,18:00-20:00",
        alias="DELIVERY_SLOTS",
    )
    min_order_amount: float = Field(default=0, alias="MIN_ORDER_AMOUNT")
    cancel_deadline_hours: int = Field(default=3, alias="CANCEL_DEADLINE_HOURS")
    timezone: str = Field(default="Europe/Moscow", alias="TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("online_payment_enabled", mode="before")
    @classmethod
    def parse_bool(cls, v):  # noqa: ANN001
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        return str(v).lower() in {"1", "true", "yes", "on"}

    def admin_id_list(self) -> List[int]:
        raw = (self.admin_ids or "").strip()
        if not raw:
            return []
        normalized = raw.replace(";", ",").replace("\n", ",")
        out: List[int] = []
        for part in normalized.split(","):
            token = part.strip().strip('"').strip("'")
            if not token:
                continue
            try:
                out.append(int(token))
            except ValueError:
                logger.warning("ADMIN_IDS: пропущено значение {!r} (нужен числовой Telegram ID)", token)
        return out

    def delivery_slot_list(self) -> List[str]:
        return [s.strip() for s in self.delivery_slots.split(",") if s.strip()]

    def orders_chat_id_int(self) -> int | None:
        if not self.orders_chat_id or not str(self.orders_chat_id).strip():
            return None
        return int(str(self.orders_chat_id).strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
