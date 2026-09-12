"""Tests for Cabinet Telegram helpers."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from cabinet.telegram import Telegram, telegram


def _make_telegram(
    bot_token: str | None = "123:abc",
    target: str | None = "999",
) -> Telegram:
    client = Telegram.__new__(Telegram)
    client.bot_token = bot_token
    client.target = target
    client.cab = MagicMock()
    return client


def _ok_response(payload: dict | None = None) -> MagicMock:
    body = json.dumps(payload or {"ok": True, "result": {"message_id": 1}})
    response = MagicMock()
    response.read.return_value = body.encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def test_send_posts_to_bot_api():
    client = _make_telegram()

    with (
        patch("cabinet.telegram.urllib.request.urlopen", return_value=_ok_response()) as urlopen,
        patch("cabinet.telegram.print_formatted_text"),
    ):
        result = client.send("hello world")

    assert result is True
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.telegram.org/bot123:abc/sendMessage"
    assert json.loads(request.data.decode("utf-8")) == {
        "chat_id": "999",
        "text": "hello world",
    }
    urlopen.assert_called_once()
    assert urlopen.call_args.kwargs["timeout"] == 10


def test_send_uses_explicit_target_override():
    client = _make_telegram()

    with (
        patch("cabinet.telegram.urllib.request.urlopen", return_value=_ok_response()) as urlopen,
        patch("cabinet.telegram.print_formatted_text"),
    ):
        assert client.send("hi", target=12345) is True

    request = urlopen.call_args.args[0]
    assert json.loads(request.data.decode("utf-8"))["chat_id"] == "12345"


def test_send_rejects_empty_message():
    client = _make_telegram()
    with patch("cabinet.telegram.urllib.request.urlopen") as urlopen:
        assert client.send("   ") is False
    urlopen.assert_not_called()
    client.cab.log.assert_called_with("Telegram message is empty", level="error")


def test_send_requires_target():
    client = _make_telegram(target=None)
    with patch("cabinet.telegram.urllib.request.urlopen") as urlopen:
        assert client.send("hi") is False
    urlopen.assert_not_called()
    client.cab.log.assert_called_with(
        "cabinet -> telegram -> target is unset",
        level="error",
    )


def test_send_requires_bot_token():
    client = _make_telegram(bot_token=None)
    with patch("cabinet.telegram.urllib.request.urlopen") as urlopen:
        assert client.send("hi") is False
    urlopen.assert_not_called()
    client.cab.log.assert_called_with(
        "cabinet -> telegram -> bot_token is unset",
        level="error",
    )


def test_send_handles_http_error():
    client = _make_telegram()
    error = HTTPError(
        "https://api.telegram.org/bot123:abc/sendMessage",
        401,
        "Unauthorized",
        hdrs=None,
        fp=io.BytesIO(b'{"ok":false,"description":"Unauthorized"}'),
    )

    with patch("cabinet.telegram.urllib.request.urlopen", side_effect=error):
        assert client.send("hi") is False

    error_logs = [
        call.args[0]
        for call in client.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("Telegram HTTP 401" in msg for msg in error_logs)


def test_send_handles_network_error():
    client = _make_telegram()
    with patch(
        "cabinet.telegram.urllib.request.urlopen",
        side_effect=URLError("timed out"),
    ):
        assert client.send("hi") is False
    error_logs = [
        call.args[0]
        for call in client.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("Telegram send failed" in msg for msg in error_logs)


def test_send_handles_api_rejection():
    client = _make_telegram()
    payload = {"ok": False, "description": "Bad Request: chat not found"}
    with patch("cabinet.telegram.urllib.request.urlopen", return_value=_ok_response(payload)):
        assert client.send("hi") is False
    error_logs = [
        call.args[0]
        for call in client.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("chat not found" in msg for msg in error_logs)


def test_module_telegram_helper_delegates_to_class():
    with patch("cabinet.telegram.Telegram") as cls:
        cls.return_value.send.return_value = True
        result = telegram("hi", target="1", is_quiet=True)

    assert result is True
    cls.assert_called_once_with()
    cls.return_value.send.assert_called_once_with(
        "hi",
        target="1",
        logging_enabled=True,
        is_quiet=True,
        timeout=10,
    )


def test_init_reads_config_aliases():
    cab = MagicMock()
    cab.get.side_effect = lambda *keys: {
        ("telegram", "bot_token"): None,
        ("telegram", "token"): "from-token",
        ("telegram", "target"): None,
        ("telegram", "chat_id"): 4242,
    }.get(keys)

    client = Telegram(cab=cab)
    assert client.bot_token == "from-token"
    assert client.target == "4242"
