from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


START_TEXT = (
    "Привет! Я бот Family Cash Flow.\n\n"
    "Пока умею принимать команды и скоро помогу быстро проверять операции.\n"
    "Следующие команды в плане: /summary и /review."
)


@dataclass(frozen=True)
class BotReply:
    chat_id: int
    text: str


def dispatch_update(update: Mapping[str, Any]) -> list[BotReply]:
    message = update.get("message")
    if not isinstance(message, Mapping):
        return []

    chat = message.get("chat")
    if not isinstance(chat, Mapping):
        return []

    chat_id = chat.get("id")
    text = message.get("text")
    if not isinstance(chat_id, int) or not isinstance(text, str):
        return []

    if _command_name(text) == "start":
        return [BotReply(chat_id=chat_id, text=START_TEXT)]

    return []


def _command_name(text: str) -> str | None:
    first_token = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    if not first_token.startswith("/"):
        return None
    return first_token[1:].split("@", maxsplit=1)[0].lower()
