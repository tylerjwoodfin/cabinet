"""Tests for Cabinet mail helpers (port coercion, recipients, SMTP retry)."""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch

import pytest
import smtplib
import socket

from cabinet.mail import (
    DEFAULT_SMTP_MAX_RETRIES,
    DEFAULT_SMTP_RETRY_BASE_DELAY,
    Mail,
    _coerce_positive_int,
    _coerce_smtp_port,
    _is_transient_smtp_error,
    _normalize_recipients,
    _smtp_retry_delay_seconds,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        (587, 587),
        (465, 465),
        ("587", 587),
        (" 465 ", 465),
        (587.0, 587),
        ("", None),
        (" ", None),
        (True, None),
        (False, None),
        ("abc", None),
        (587.7, None),
        (0, None),
        (70000, None),
        ([], None),
    ],
)
def test_coerce_smtp_port(raw, expected):
    assert _coerce_smtp_port(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("a@b.com", ["a@b.com"]),
        ("a@b.com, c@d.com", ["a@b.com", "c@d.com"]),
        (["a@b.com", "c@d.com"], ["a@b.com", "c@d.com"]),
        (("a@b.com",), ["a@b.com"]),
        ([""], None),
        ([None, "  ", "e@f.com"], ["e@f.com"]),
        (["x@y.com, z@w.com"], ["x@y.com", "z@w.com"]),
    ],
)
def test_normalize_recipients(raw, expected):
    assert _normalize_recipients(raw) == expected


@pytest.mark.parametrize(
    "retry_number, base_delay, expected",
    [
        (1, 120, 120),
        (2, 120, 240),
        (3, 120, 480),
        (1, 60, 60),
    ],
)
def test_smtp_retry_delay_seconds(retry_number, base_delay, expected):
    assert _smtp_retry_delay_seconds(retry_number, base_delay) == expected


@pytest.mark.parametrize(
    "err, expected",
    [
        (socket.timeout(), True),
        (smtplib.SMTPServerDisconnected("closed"), True),
        (smtplib.SMTPConnectError(421, "busy"), True),
        (ConnectionError("refused"), True),
        (smtplib.SMTPAuthenticationError(535, "bad"), False),
        (ValueError("nope"), False),
    ],
)
def test_is_transient_smtp_error(err, expected):
    assert _is_transient_smtp_error(err) is expected


@pytest.mark.parametrize(
    "raw, default, expected",
    [
        (None, 3, 3),
        (5, 3, 5),
        ("120", 60, 120),
        ("bad", 60, 60),
        (True, 3, 3),
    ],
)
def test_coerce_positive_int(raw, default, expected):
    assert _coerce_positive_int(raw, default) == expected


def _make_mail() -> Mail:
    mail = Mail.__new__(Mail)
    mail.smtp_server = "smtp.example.com"
    mail.port = 587
    mail.username = "user@example.com"
    mail.password = "secret"
    mail.cab = MagicMock()
    return mail


def test_send_retries_transient_failure_then_succeeds():
    mail = _make_mail()
    message = MIMEMultipart()
    message["To"] = "dest@example.com"
    message["From"] = "user@example.com"
    message["Subject"] = "Test"

    server = MagicMock()
    server.login.side_effect = [
        smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
        None,
    ]

    with (
        patch.object(mail, "_connect_smtp", return_value=server),
        patch("cabinet.mail.time.sleep") as sleep,
        patch("cabinet.mail.print_formatted_text"),
    ):
        result = mail.send(
            "Test",
            "Body",
            to_addr="dest@example.com",
            max_retries=1,
            retry_base_delay=120,
        )

    assert result is True
    sleep.assert_called_once_with(120)
    assert server.send_message.call_count == 1
    warning_logs = [
        call.args[0]
        for call in mail.cab.log.call_args_list
        if call.kwargs.get("level") == "warning"
    ]
    assert any("Retrying in 120 seconds" in msg for msg in warning_logs)


def test_send_exhausts_retries_on_persistent_failure():
    mail = _make_mail()
    server = MagicMock()
    server.login.side_effect = smtplib.SMTPServerDisconnected("timed out")

    with (
        patch.object(mail, "_connect_smtp", return_value=server),
        patch("cabinet.mail.time.sleep") as sleep,
        patch("cabinet.mail.print_formatted_text"),
    ):
        result = mail.send(
            "Test",
            "Body",
            to_addr="dest@example.com",
            max_retries=2,
            retry_base_delay=60,
        )

    assert result is False
    assert sleep.call_args_list == [((60,),), ((120,),)]
    error_logs = [
        call.args[0]
        for call in mail.cab.log.call_args_list
        if call.kwargs.get("level") == "error"
    ]
    assert any("failed after 3 attempts" in msg for msg in error_logs)


def test_send_does_not_retry_authentication_errors():
    mail = _make_mail()
    server = MagicMock()
    server.login.side_effect = smtplib.SMTPAuthenticationError(535, "bad creds")

    with (
        patch.object(mail, "_connect_smtp", return_value=server) as connect,
        patch("cabinet.mail.time.sleep") as sleep,
        patch("cabinet.mail.print_formatted_text"),
    ):
        result = mail.send(
            "Test",
            "Body",
            to_addr="dest@example.com",
            max_retries=DEFAULT_SMTP_MAX_RETRIES,
            retry_base_delay=DEFAULT_SMTP_RETRY_BASE_DELAY,
        )

    assert result is False
    sleep.assert_not_called()
    assert connect.call_count == 1
