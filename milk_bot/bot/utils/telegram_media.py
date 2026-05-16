from __future__ import annotations

from aiogram.types import Message


def photo_file_id_from_message(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    doc = message.document
    if doc and doc.mime_type and doc.mime_type.startswith("image/"):
        return doc.file_id
    return None
