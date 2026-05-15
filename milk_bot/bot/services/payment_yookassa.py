"""Stub for future YooKassa integration (MVP: disabled via settings)."""


def is_online_payment_available() -> bool:
    from milk_bot.bot.config import get_settings

    return get_settings().online_payment_enabled


async def create_payment_stub(*_args, **_kwargs) -> None:  # pragma: no cover - placeholder
    raise NotImplementedError("Online payments are disabled in MVP")
