from types import SimpleNamespace

from app.telegram_bot.context import (
    PRIVATE_CHAT_ONLY_TEXT,
    START_TEXT,
    UNLINKED_TELEGRAM_TEXT,
    TelegramRequestContext,
)
from app.telegram_bot.dispatcher import (
    BotCallbackAnswer,
    BotReply,
    BotReplyContent,
    dispatch_update,
)


def _context(telegram_user_id: int = 77) -> TelegramRequestContext:
    return TelegramRequestContext(
        identity=SimpleNamespace(telegram_user_id=telegram_user_id),
        user=SimpleNamespace(id="application-user"),
        family=SimpleNamespace(id="family-a"),
        private_chat_id=42,
        default_account=None,
    )


def _update(text: str, *, chat_type: str = "private", sender_id: int = 77) -> dict:
    return {
        "message": {
            "chat": {"id": 42 if chat_type == "private" else -42, "type": chat_type},
            "from": {"id": sender_id, "username": "display-only"},
            "text": text,
        }
    }


def test_start_without_token_explains_web_linking() -> None:
    replies = dispatch_update(_update("/start"), context_resolver=lambda *_: None)

    assert replies == [BotReply(chat_id=42, text=START_TEXT)]


def test_start_token_is_only_consumed_in_private_chat() -> None:
    consumed: list[tuple[str, int, int]] = []
    replies = dispatch_update(
        _update("/start valid-token", chat_type="group"),
        context_resolver=lambda *_: None,
        link_text_provider=lambda token, user_id, chat_id, _: (
            consumed.append((token, user_id, chat_id)) or "linked"
        ),
    )

    assert replies == [BotReply(chat_id=-42, text=PRIVATE_CHAT_ONLY_TEXT)]
    assert consumed == []


def test_summary_requires_linked_sender_and_uses_context_family() -> None:
    resolved: list[tuple[int, int, dict[str, object]]] = []
    context = _context()
    replies = dispatch_update(
        _update("/summary"),
        context_resolver=lambda uid, cid, profile: resolved.append((uid, cid, profile)) or context,
        summary_text_provider=lambda actual: f"Summary for {actual.family.id}",
    )

    assert replies == [BotReply(chat_id=42, text="Summary for family-a")]
    assert resolved[0][0:2] == (77, 42)
    assert resolved[0][2]["username"] == "display-only"


def test_unlinked_sender_cannot_read_summary() -> None:
    replies = dispatch_update(
        _update("/summary"),
        context_resolver=lambda *_: None,
        summary_text_provider=lambda _: "private financial data",
    )

    assert replies == [BotReply(chat_id=42, text=UNLINKED_TELEGRAM_TEXT)]


def test_income_command_is_dispatched_to_the_linked_private_chat_text_handler() -> None:
    context = _context()
    received: list[tuple[TelegramRequestContext, str]] = []
    replies = dispatch_update(
        _update("/income 25000 Зарплата"),
        context_resolver=lambda *_: context,
        text_message_provider=lambda actual, text: (
            received.append((actual, text)) or "Income saved"
        ),
    )

    assert received == [(context, "/income 25000 Зарплата")]
    assert replies == [BotReply(chat_id=42, text="Income saved")]


def test_cash_command_is_dispatched_to_the_linked_private_chat_text_handler() -> None:
    context = _context()
    received: list[tuple[TelegramRequestContext, str]] = []
    replies = dispatch_update(
        _update("/cash 450 Рынок"),
        context_resolver=lambda *_: context,
        text_message_provider=lambda actual, text: (
            received.append((actual, text)) or "Cash expense saved"
        ),
    )

    assert received == [(context, "/cash 450 Рынок")]
    assert replies == [BotReply(chat_id=42, text="Cash expense saved")]


def test_sensitive_group_command_returns_only_private_chat_instruction() -> None:
    called = False

    def resolve(*_):
        nonlocal called
        called = True
        return _context()

    replies = dispatch_update(
        _update("/summary", chat_type="supergroup"),
        context_resolver=resolve,
        summary_text_provider=lambda _: "private financial data",
    )

    assert replies == [BotReply(chat_id=-42, text=PRIVATE_CHAT_ONLY_TEXT)]
    assert called is False


def test_review_markup_is_returned_only_after_sender_resolution() -> None:
    markup = {"inline_keyboard": [[{"text": "Done", "callback_data": "review_done:abc"}]]}
    replies = dispatch_update(
        _update("/review"),
        context_resolver=lambda *_: _context(),
        review_text_provider=lambda _: BotReplyContent(text="Review", reply_markup=markup),
    )

    assert replies == [BotReply(chat_id=42, text="Review", reply_markup=markup)]


def test_callback_authorization_uses_callback_sender_id() -> None:
    resolved_ids: list[int] = []
    replies = dispatch_update(
        {
            "callback_query": {
                "id": "callback-1",
                "from": {"id": 912, "username": "same_display_name"},
                "data": "review_done:transaction-id",
                "message": {"chat": {"id": 42, "type": "private"}},
            }
        },
        context_resolver=lambda telegram_id, *_: resolved_ids.append(telegram_id) or _context(),
        review_done_text_provider=lambda context, tx_id: f"{context.user.id}:{tx_id}",
    )

    assert resolved_ids == [912]
    assert replies == [
        BotCallbackAnswer(callback_query_id="callback-1", text="application-user:transaction-id"),
        BotReply(chat_id=42, text="application-user:transaction-id"),
    ]


def test_unlinked_callback_cannot_run_mutation() -> None:
    called = False

    def mark_done(*_):
        nonlocal called
        called = True
        return "changed"

    replies = dispatch_update(
        {
            "callback_query": {
                "id": "callback-2",
                "from": {"id": 912},
                "data": "review_done:transaction-id",
                "message": {"chat": {"id": 42, "type": "private"}},
            }
        },
        context_resolver=lambda *_: None,
        review_done_text_provider=mark_done,
    )

    assert called is False
    assert replies[0].text == UNLINKED_TELEGRAM_TEXT
