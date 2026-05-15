from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "ig:n")
async def cb_ignore(cq: CallbackQuery) -> None:
    await cq.answer()
