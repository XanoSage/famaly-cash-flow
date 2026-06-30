from app.telegram_bot.dispatcher import START_TEXT, BotCallbackAnswer, BotReply, BotReplyContent, dispatch_update


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


def test_dispatch_update_returns_review_reply_with_markup() -> None:
    reply_markup = {"inline_keyboard": [[{"text": "Done", "callback_data": "review_done:1"}]]}

    replies = dispatch_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "text": "/review",
            },
        },
        review_text_provider=lambda: BotReplyContent(text="Review text", reply_markup=reply_markup),
    )

    assert replies == [BotReply(chat_id=42, text="Review text", reply_markup=reply_markup)]


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


def test_dispatch_update_handles_review_done_callback() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "callback_query": {
                "id": "callback-1",
                "data": "review_done:transaction-123",
                "message": {"chat": {"id": 42, "type": "private"}},
            },
        },
        review_done_text_provider=lambda transaction_id: f"Done {transaction_id}",
    )

    assert replies == [
        BotCallbackAnswer(callback_query_id="callback-1", text="Done transaction-123"),
        BotReply(chat_id=42, text="Done transaction-123"),
    ]


def test_dispatch_update_handles_review_categories_callback() -> None:
    reply_markup = {"inline_keyboard": [[{"text": "Food", "callback_data": "review_category:t:c"}]]}

    replies = dispatch_update(
        {
            "update_id": 1,
            "callback_query": {
                "id": "callback-1",
                "data": "review_categories:transaction-token",
                "message": {"chat": {"id": 42, "type": "private"}},
            },
        },
        review_categories_text_provider=lambda transaction_id: BotReplyContent(
            text=f"Categories {transaction_id}",
            reply_markup=reply_markup,
        ),
    )

    assert replies == [
        BotCallbackAnswer(callback_query_id="callback-1", text="Categories transaction-token"),
        BotReply(chat_id=42, text="Categories transaction-token", reply_markup=reply_markup),
    ]


def test_dispatch_update_handles_review_category_callback() -> None:
    replies = dispatch_update(
        {
            "update_id": 1,
            "callback_query": {
                "id": "callback-1",
                "data": "review_category:transaction-token:category-token",
                "message": {"chat": {"id": 42, "type": "private"}},
            },
        },
        review_category_text_provider=lambda transaction_id, category_id: (
            f"Category {transaction_id} {category_id}"
        ),
    )

    assert replies == [
        BotCallbackAnswer(
            callback_query_id="callback-1",
            text="Category transaction-token category-token",
        ),
        BotReply(chat_id=42, text="Category transaction-token category-token"),
    ]


def test_dispatch_update_ignores_unknown_or_incomplete_updates() -> None:
    assert dispatch_update({"update_id": 1}) == []
    assert dispatch_update({"message": {"chat": {"id": 42}, "text": "/unknown"}}) == []
    assert dispatch_update({"message": {"chat": {"id": "42"}, "text": "/start"}}) == []
