from __future__ import annotations

from collections.abc import Callable
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


def dispatch_update(
    update: Mapping[str, Any],
    *,
    summary_text_provider: Callable[[], str] | None = None,
    review_text_provider: Callable[[], str] | None = None,
    review_done_text_provider: Callable[[str | None], str] | None = None,
) -> list[BotReply]:
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

    command_name = _command_name(text)
    if command_name == "start":
        return [BotReply(chat_id=chat_id, text=START_TEXT)]
    if command_name == "summary" and summary_text_provider is not None:
        return [BotReply(chat_id=chat_id, text=summary_text_provider())]
    if command_name == "review" and review_text_provider is not None:
        return [BotReply(chat_id=chat_id, text=review_text_provider())]
    if command_name == "done" and review_done_text_provider is not None:
        return [BotReply(chat_id=chat_id, text=review_done_text_provider(_command_argument(text)))]

    return []


def _command_name(text: str) -> str | None:
    first_token = text.strip().split(maxsplit=1)[0] if text.strip() else ""
    if not first_token.startswith("/"):
        return None
    return first_token[1:].split("@", maxsplit=1)[0].lower()


def _command_argument(text: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1].strip() or None
