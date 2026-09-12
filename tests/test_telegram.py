"""Tests for Cabinet Telegram helpers."""

from __future__ import annotations

import io
import json
import subprocess
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from cabinet.telegram import DEFAULT_TIMEOUT, Telegram, telegram, _default_openclaw_bin


def _make_telegram(
    bot_token: str | None = None,
    target: str | None = "999",
    channel: str = "telegram",
    openclaw_bin: str = "openclaw",
) -> Telegram:
    client = Telegram.__new__(Telegram)
    client.bot_token = bot_token
    client.target = target
    client.channel = channel
    client.openclaw_bin = openclaw_bin
    client.cab = MagicMock()
    return client


def _ok_response(payload: dict | None = None) -> MagicMock:
    body = json.dumps(payload or {"ok": True, "result": {"message_id": 1}})
    response = MagicMock()
    response.read.return_value = body.encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _ok_proc() -> MagicMock:
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = "ok"
    proc.stderr = ""
    return proc


def test_send_uses_openclaw_when_no_bot_token():
    client = _make_telegram()

    with (
        patch("cabinet.telegram.shutil.which", return_value="/bin/openclaw"),
        patch("cabinet.telegram.subprocess.run", return_value=_ok_proc()) as run,
        patch("cabinet.telegram.print_formatted_text"),
    ):
        result = client.send("hello world")

    assert result is True
    run.assert_called_once_with(
        [
            "/bin/openclaw",
            "message",
            "send",
            "--channel",
            "telegram",
            "--target",
            "999",
            "--message",
            "hello world",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=DEFAULT_TIMEOUT,
    )


def test_send_posts_to_bot_api_when_token_set():
    client = _make_telegram(bot_token="123:abc")

    with (
        patch("cabinet.telegram.urllib.request.urlopen", return_value=_ok_response()) as urlopen,
        patch("cabinet.telegram.subprocess.run") as run,
        patch("cabinet.telegram.print_formatted_text"),
    ):
        result = client.send("hello world")

    assert result is True
    run.assert_not_called()
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.telegram.org/bot123:abc/sendMessage"
    assert json.loads(request.data.decode("utf-8")) == {
        "chat_id": "999",
        "text": "hello world",
    }


def test_send_uses_explicit_target_override():
    client = _make_telegram()

    with (
        patch("cabinet.telegram.shutil.which", return_value="openclaw"),
        patch("cabinet.telegram.subprocess.run", return_value=_ok_proc()) as run,
        patch("cabinet.telegram.print_formatted_text"),
    ):
        assert client.send("hi", target=12345) is True

    assert run.call_args.args[0][6] == "12345"


def test_send_rejects_empty_message():
    client = _make_telegram()
    with patch("cabinet.telegram.subprocess.run") as run:
        assert client.send("   ") is False
    run.assert_not_called()
    client.cab.log.assert_called_with("Telegram message is empty", level="error")


def test_send_requires_target():
    client = _make_telegram(target=None)
    with patch("cabinet.telegram.subprocess.run") as run:
        assert client.send("hi") is False
    run.assert_not_called()
    client.cab.log.assert_called_with(
        "cabinet -> telegram -> target is unset",
        level="error",
    )


def test_send_openclaw_missing_binary():
    client = _make_telegram()
    with (
        patch("cabinet.telegram.shutil.which", return_value=None),
        patch("cabinet.telegram.subprocess.run", side_effect=FileNotFoundError()),
    ):
        assert client.send("hi") is False
    error_logs = [
        call.args[0]
        for call in client.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("not found" in msg for msg in error_logs)


def test_send_openclaw_nonzero_exit():
    client = _make_telegram()
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = ""
    proc.stderr = "gateway down"
    with (
        patch("cabinet.telegram.shutil.which", return_value="openclaw"),
        patch("cabinet.telegram.subprocess.run", return_value=proc),
    ):
        assert client.send("hi") is False
    error_logs = [
        call.args[0]
        for call in client.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("gateway down" in msg for msg in error_logs)


def test_send_handles_http_error():
    client = _make_telegram(bot_token="123:abc")
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
    client = _make_telegram(bot_token="123:abc")
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
    client = _make_telegram(bot_token="123:abc")
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
        timeout=DEFAULT_TIMEOUT,
    )


def test_init_reads_config_aliases():
    cab = MagicMock()
    cab.get.side_effect = lambda *keys: {
        ("telegram", "bot_token"): None,
        ("telegram", "token"): None,
        ("telegram", "target"): None,
        ("telegram", "chat_id"): 4242,
        ("telegram", "channel"): None,
        ("telegram", "openclaw_bin"): "/usr/local/bin/openclaw",
    }.get(keys)

    client = Telegram(cab=cab)
    assert client.bot_token is None
    assert client.target == "4242"
    assert client.channel == "telegram"
    assert client.openclaw_bin == "/usr/local/bin/openclaw"


def test_default_openclaw_bin_prefers_diary_llm_wrapper():
    wrapper = MagicMock()
    wrapper.is_file.return_value = True
    with (
        patch("cabinet.telegram.DIARY_LLM_OPENCLAW", wrapper),
        patch("cabinet.telegram.os.access", return_value=True),
    ):
        assert _default_openclaw_bin() == str(wrapper)


def test_default_openclaw_bin_falls_back_to_path():
    wrapper = MagicMock()
    wrapper.is_file.return_value = False
    with patch("cabinet.telegram.DIARY_LLM_OPENCLAW", wrapper):
        assert _default_openclaw_bin() == "openclaw"


def test_send_openclaw_timeout():
    client = _make_telegram()
    with (
        patch("cabinet.telegram.shutil.which", return_value="openclaw"),
        patch(
            "cabinet.telegram.subprocess.run",
            side_effect=subprocess.TimeoutExpired("openclaw", 60),
        ),
    ):
        assert client.send("hi") is False
    error_logs = [
        call.args[0]
        for call in client.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("timed out" in msg for msg in error_logs)
