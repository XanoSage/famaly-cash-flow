from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.telegram_bot.context import (
    LINK_FAILURE_TEXT,
    PRIVATE_CHAT_ONLY_TEXT,
    START_TEXT,
    UNLINKED_TELEGRAM_TEXT,
    TelegramRequestContext,
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
ContextResolver = Callable[[int, int, dict[str, object]], TelegramRequestContext | None]


def dispatch_update(
    update: Mapping[str, Any],
    *,
    context_resolver: ContextResolver,
    link_text_provider: Callable[[str, int, int, dict[str, object]], str] | None = None,
    summary_text_provider: Callable[[TelegramRequestContext], str] | None = None,
    review_text_provider: Callable[[TelegramRequestContext], str | BotReplyContent] | None = None,
    review_done_text_provider: Callable[[TelegramRequestContext, str | None], str] | None = None,
    review_categories_text_provider: Callable[
        [TelegramRequestContext, str | None], str | BotReplyContent
    ]
    | None = None,
    review_category_text_provider: Callable[[TelegramRequestContext, str | None, str | None], str]
    | None = None,
    account_text_provider: Callable[[TelegramRequestContext], str | BotReplyContent] | None = None,
    account_select_text_provider: Callable[[TelegramRequestContext, str | None], str] | None = None,
    text_message_provider: Callable[[TelegramRequestContext, str], str | None] | None = None,
) -> list[BotAction]:
    callback_query = update.get("callback_query")
    if isinstance(callback_query, Mapping):
        return _dispatch_callback_query(
            callback_query,
            context_resolver=context_resolver,
            review_done_text_provider=review_done_text_provider,
            review_categories_text_provider=review_categories_text_provider,
            review_category_text_provider=review_category_text_provider,
            account_select_text_provider=account_select_text_provider,
        )

    message = update.get("message")
    if not isinstance(message, Mapping):
        return []
    chat = message.get("chat")
    sender = message.get("from")
    text = message.get("text")
    if (
        not isinstance(chat, Mapping)
        or not isinstance(sender, Mapping)
        or not isinstance(text, str)
    ):
        return []

    chat_id = _chat_id(chat.get("id"))
    telegram_user_id = _positive_int(sender.get("id"))
    if chat_id is None:
        return []
    private_chat = chat.get("type") == "private"
    profile = _profile(sender)
    command_name = _command_name(text)

    if command_name == "start":
        link_token = _command_argument(text)
        if link_token is None:
            return [BotReply(chat_id=chat_id, text=START_TEXT)]
        if not private_chat or telegram_user_id is None:
            return [BotReply(chat_id=chat_id, text=PRIVATE_CHAT_ONLY_TEXT)]
        if link_text_provider is None:
            return [BotReply(chat_id=chat_id, text=LINK_FAILURE_TEXT)]
        return [
            BotReply(
                chat_id=chat_id,
                text=link_text_provider(link_token, telegram_user_id, chat_id, profile),
            )
        ]

    if not private_chat:
        if command_name in {"summary", "review", "done", "account"} or command_name is None:
            return [BotReply(chat_id=chat_id, text=PRIVATE_CHAT_ONLY_TEXT)]
        return []
    if telegram_user_id is None:
        return [BotReply(chat_id=chat_id, text=UNLINKED_TELEGRAM_TEXT)]

    context = context_resolver(telegram_user_id, chat_id, profile)
    if context is None:
        return [BotReply(chat_id=chat_id, text=UNLINKED_TELEGRAM_TEXT)]

    if command_name == "summary" and summary_text_provider is not None:
        return [BotReply(chat_id=chat_id, text=summary_text_provider(context))]
    if command_name == "review" and review_text_provider is not None:
        return [_to_bot_reply(chat_id, review_text_provider(context))]
    if command_name == "done" and review_done_text_provider is not None:
        return [
            BotReply(
                chat_id=chat_id,
                text=review_done_text_provider(context, _command_argument(text)),
            )
        ]
    if command_name == "account" and account_text_provider is not None:
        return [_to_bot_reply(chat_id, account_text_provider(context))]
    if command_name in {None, "income"} and text_message_provider is not None:
        reply_text = text_message_provider(context, text)
        if reply_text:
            return [BotReply(chat_id=chat_id, text=reply_text)]
    return []


def _dispatch_callback_query(
    callback_query: Mapping[str, Any],
    *,
    context_resolver: ContextResolver,
    review_done_text_provider: Callable[[TelegramRequestContext, str | None], str] | None,
    review_categories_text_provider: Callable[
        [TelegramRequestContext, str | None], str | BotReplyContent
    ]
    | None,
    review_category_text_provider: Callable[[TelegramRequestContext, str | None, str | None], str]
    | None,
    account_select_text_provider: Callable[[TelegramRequestContext, str | None], str] | None,
) -> list[BotAction]:
    callback_query_id = callback_query.get("id")
    data = callback_query.get("data")
    if not isinstance(callback_query_id, str) or not isinstance(data, str):
        return []

    message = callback_query.get("message")
    if not isinstance(message, Mapping):
        return [BotCallbackAnswer(callback_query_id, PRIVATE_CHAT_ONLY_TEXT)]
    chat = message.get("chat")
    sender = callback_query.get("from")
    if not isinstance(chat, Mapping) or not isinstance(sender, Mapping):
        return [BotCallbackAnswer(callback_query_id, PRIVATE_CHAT_ONLY_TEXT)]
    chat_id = _chat_id(chat.get("id"))
    telegram_user_id = _positive_int(sender.get("id"))
    if chat.get("type") != "private" or chat_id is None:
        return [BotCallbackAnswer(callback_query_id, PRIVATE_CHAT_ONLY_TEXT)]
    if telegram_user_id is None:
        return _callback_actions(callback_query_id, chat_id, UNLINKED_TELEGRAM_TEXT)

    context = context_resolver(telegram_user_id, chat_id, _profile(sender))
    if context is None:
        return _callback_actions(callback_query_id, chat_id, UNLINKED_TELEGRAM_TEXT)

    if data.startswith("review_done:") and review_done_text_provider is not None:
        text = review_done_text_provider(context, data.removeprefix("review_done:"))
        return _callback_actions(callback_query_id, chat_id, text)
    if data.startswith("review_categories:") and review_categories_text_provider is not None:
        content = review_categories_text_provider(context, data.removeprefix("review_categories:"))
        return _callback_actions(callback_query_id, chat_id, content)
    if data.startswith("review_category:") and review_category_text_provider is not None:
        transaction_id, category_id = _split_callback_payload(data.removeprefix("review_category:"))
        text = review_category_text_provider(context, transaction_id, category_id)
        return _callback_actions(callback_query_id, chat_id, text)
    if data.startswith("account_set:") and account_select_text_provider is not None:
        text = account_select_text_provider(context, data.removeprefix("account_set:"))
        return _callback_actions(callback_query_id, chat_id, text)

    return [BotCallbackAnswer(callback_query_id, "Действие недоступно.")]


def _callback_actions(
    callback_query_id: str,
    chat_id: int,
    value: str | BotReplyContent,
) -> list[BotAction]:
    text = value.text if isinstance(value, BotReplyContent) else value
    return [
        BotCallbackAnswer(callback_query_id=callback_query_id, text=text),
        _to_bot_reply(chat_id, value),
    ]


def _to_bot_reply(chat_id: int, value: str | BotReplyContent) -> BotReply:
    if isinstance(value, BotReplyContent):
        return BotReply(chat_id=chat_id, text=value.text, reply_markup=value.reply_markup)
    return BotReply(chat_id=chat_id, text=value)


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


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _chat_id(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value == 0:
        return None
    return value


def _profile(sender: Mapping[str, Any]) -> dict[str, object]:
    return {
        "username": sender.get("username"),
        "first_name": sender.get("first_name"),
        "last_name": sender.get("last_name"),
    }
