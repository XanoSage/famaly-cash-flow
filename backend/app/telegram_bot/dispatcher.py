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
    review_categories_text_provider: Callable[[str | None], str | BotReplyContent] | None = None,
    review_category_text_provider: Callable[[str | None, str | None], str] | None = None,
    text_message_provider: Callable[[str], str | None] | None = None,
) -> list[BotAction]:
    callback_replies = _dispatch_callback_query(
        update,
        review_done_text_provider=review_done_text_provider,
        review_categories_text_provider=review_categories_text_provider,
        review_category_text_provider=review_category_text_provider,
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
    if command_name is None and text_message_provider is not None:
        reply_text = text_message_provider(text)
        if reply_text:
            return [BotReply(chat_id=chat_id, text=reply_text)]

    return []


def _dispatch_callback_query(
    update: Mapping[str, Any],
    *,
    review_done_text_provider: Callable[[str | None], str] | None,
    review_categories_text_provider: Callable[[str | None], str | BotReplyContent] | None,
    review_category_text_provider: Callable[[str | None, str | None], str] | None,
) -> list[BotAction]:
    callback_query = update.get("callback_query")
    if not isinstance(callback_query, Mapping):
        return []

    callback_query_id = callback_query.get("id")
    data = callback_query.get("data")
    if not isinstance(callback_query_id, str) or not isinstance(data, str):
        return []

    chat_id = _callback_chat_id(callback_query)
    if data.startswith("review_done:") and review_done_text_provider is not None:
        text = review_done_text_provider(data.removeprefix("review_done:"))
        return _callback_actions(callback_query_id, chat_id, text)

    if data.startswith("review_categories:") and review_categories_text_provider is not None:
        content = review_categories_text_provider(data.removeprefix("review_categories:"))
        return _callback_actions(callback_query_id, chat_id, content)

    if data.startswith("review_category:") and review_category_text_provider is not None:
        transaction_id, category_id = _split_callback_payload(data.removeprefix("review_category:"))
        text = review_category_text_provider(transaction_id, category_id)
        return _callback_actions(callback_query_id, chat_id, text)

    return []


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


def _callback_actions(
    callback_query_id: str,
    chat_id: int | None,
    value: str | BotReplyContent,
) -> list[BotAction]:
    text = value.text if isinstance(value, BotReplyContent) else value
    actions: list[BotAction] = [BotCallbackAnswer(callback_query_id=callback_query_id, text=text)]
    if chat_id is not None:
        actions.append(_to_bot_reply(chat_id, value))
    return actions


def _split_callback_payload(value: str) -> tuple[str | None, str | None]:
    parts = value.split(":", maxsplit=1)
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]


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
