from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.telegram_bot.dispatcher import BotAction, BotCallbackAnswer, BotReply


TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramApiError(RuntimeError):
    pass


def send_bot_replies(bot_token: str | None, replies: Iterable[BotAction]) -> int:
    if not bot_token:
        return 0

    sent_count = 0
    for reply in replies:
        if isinstance(reply, BotReply):
            send_message(
                bot_token,
                chat_id=reply.chat_id,
                text=reply.text,
                reply_markup=reply.reply_markup,
            )
        elif isinstance(reply, BotCallbackAnswer):
            answer_callback_query(
                bot_token,
                callback_query_id=reply.callback_query_id,
                text=reply.text,
            )
        sent_count += 1
    return sent_count


def send_message(
    bot_token: str,
    *,
    chat_id: int,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return _post_json(
        url=f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def answer_callback_query(
    bot_token: str,
    *,
    callback_query_id: str,
    text: str,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    return _post_json(
        url=f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/answerCallbackQuery",
        payload={"callback_query_id": callback_query_id, "text": text},
        timeout_seconds=timeout_seconds,
    )


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read()
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise TelegramApiError(f"Telegram API returned HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise TelegramApiError(f"Telegram API request failed: {exc.reason}") from exc

    try:
        decoded_body = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TelegramApiError("Telegram API returned invalid JSON") from exc

    if not isinstance(decoded_body, dict) or decoded_body.get("ok") is not True:
        raise TelegramApiError(f"Telegram API returned unsuccessful response: {decoded_body}")

    return decoded_body
