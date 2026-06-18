from app.telegram_bot.dispatcher import START_TEXT, dispatch_update


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


def test_dispatch_update_ignores_unknown_or_incomplete_updates() -> None:
    assert dispatch_update({"update_id": 1}) == []
    assert dispatch_update({"message": {"chat": {"id": 42}, "text": "/unknown"}}) == []
    assert dispatch_update({"message": {"chat": {"id": "42"}, "text": "/start"}}) == []
