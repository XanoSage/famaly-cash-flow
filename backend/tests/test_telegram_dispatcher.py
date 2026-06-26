from app.telegram_bot.dispatcher import START_TEXT, BotReply, dispatch_update


def test_dispatch_update_returns_start_reply() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/start",
            },
        }
    )

    assert len(replies) == 1
    assert replies[0].chat_id == 42
    assert replies[0].text == START_TEXT


def test_dispatch_update_supports_bot_mention_command() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/start@FamilyCashFlowBot",
            },
        }
    )

    assert len(replies) == 1


def test_dispatch_update_returns_summary_reply() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/summary",
            },
        },
        summary_text_provider=lambda: "Summary text",
    )

    assert replies == [BotReply(chat_id=42, text="Summary text")]
    assert replies[0].chat_id == 42
    assert replies[0].text == "Summary text"


def test_dispatch_update_returns_review_reply() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/review",
            },
        },
        review_text_provider=lambda: "Review text",
    )

    assert replies == [BotReply(chat_id=42, text="Review text")]


def test_dispatch_update_returns_review_done_reply() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/done transaction-123",
            },
        },
        review_done_text_provider=lambda transaction_id: f"Done {transaction_id}",
    )

    assert replies == [BotReply(chat_id=42, text="Done transaction-123")]


def test_dispatch_update_returns_review_done_usage_without_argument() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/done",
            },
        },
        review_done_text_provider=lambda transaction_id: f"Done {transaction_id}",
    )

    assert replies == [BotReply(chat_id=42, text="Done None")]


def test_dispatch_update_ignores_unknown_or_incomplete_updates() -> None:
    assert dispatch_update({"update_id": 1}) == []
    assert dispatch_update({"message": {"chat": {"id": 42}, "text": "/unknown"}}) == []
    assert dispatch_update({"message": {"chat": {"id": "42"}, "text": "/start"}}) == []
