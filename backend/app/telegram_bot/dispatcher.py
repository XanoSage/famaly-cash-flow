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
    reply_markup: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class BotReplyContent:
    text: str
    reply_markup: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class BotCallbackAnswer:
    callback_query_id: str
    text: str


BotAction = BotReply | BotCallbackAnswer


def dispatch_update(
    update: Mapping[str, Any],
    *,
    summary_text_provider: Callable[[], str] | None = None,
    review_text_provider: Callable[[], str | BotReplyContent] | None = None,
    review_done_text_provider: Callable[[str | None], str] | None = None,
) -> list[BotAction]:
    callback_replies = _dispatch_callback_query(
        update,
        review_done_text_provider=review_done_text_provider,
    )
    if callback_replies:
        return callback_replies

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
        return [_to_bot_reply(chat_id, review_text_provider())]
    if command_name == "done" and review_done_text_provider is not None:
        return [BotReply(chat_id=chat_id, text=review_done_text_provider(_command_argument(text)))]

    return []


def _dispatch_callback_query(
    update: Mapping[str, Any],
    *,
    review_done_text_provider: Callable[[str | None], str] | None,
) -> list[BotAction]:
    if review_done_text_provider is None:
        return []

    callback_query = update.get("callback_query")
    if not isinstance(callback_query, Mapping):
        return []

    callback_query_id = callback_query.get("id")
    data = callback_query.get("data")
    if not isinstance(callback_query_id, str) or not isinstance(data, str):
        return []
    if not data.startswith("review_done:"):
        return []

    text = review_done_text_provider(data.removeprefix("review_done:"))
    actions: list[BotAction] = [BotCallbackAnswer(callback_query_id=callback_query_id, text=text)]

    chat_id = _callback_chat_id(callback_query)
    if chat_id is not None:
        actions.append(BotReply(chat_id=chat_id, text=text))
    return actions


def _callback_chat_id(callback_query: Mapping[str, Any]) -> int | None:
    message = callback_query.get("message")
    if not isinstance(message, Mapping):
        return None
    chat = message.get("chat")
    if not isinstance(chat, Mapping):
        return None
    chat_id = chat.get("id")
    return chat_id if isinstance(chat_id, int) else None


def _to_bot_reply(chat_id: int, value: str | BotReplyContent) -> BotReply:
    if isinstance(value, BotReplyContent):
        return BotReply(chat_id=chat_id, text=value.text, reply_markup=value.reply_markup)
    return BotReply(chat_id=chat_id, text=value)


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
