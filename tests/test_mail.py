"""Tests for Cabinet mail helpers (port coercion, recipients)."""

from __future__ import annotations

import pytest

from cabinet.mail import _coerce_smtp_port, _normalize_recipients


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
