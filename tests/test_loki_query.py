"""Tests for Loki query helpers (HTTP mocked)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cabinet.log import (
    cabinet_log_query_documents_loki,
    cabinet_log_query_issues_loki,
    cabinet_log_query_loki,
    format_json_log_record_as_cabinet_line,
    loki_query_range,
)


def _cab(url: str = "http://127.0.0.1:3100"):
    return SimpleNamespace(
        logging_loki_url=url,
        logging_loki_job="cabinet",
        logging_loki_query_timeout=5,
    )


def test_require_loki_url_raises():
    cab = SimpleNamespace()
    with pytest.raises(ValueError, match="loki_url"):
        loki_query_range(cab, '{job="cabinet"}', limit=10)


def _patch_urlopen_body(payload: dict):
    body = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body
    cm.__exit__.return_value = None
    return patch("cabinet.log.urllib.request.urlopen", return_value=cm)


def test_loki_query_range_parses_streams():
    payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "stream": {"job": "cabinet", "level": "info"},
                    "values": [
                        [
                            "1704110400000000000",
                            '{"timestamp":"2024-01-01T12:00:00Z","level":"info","message":"hello","tags":["t"],"source":{"file":"x.py","line":2},"hostname":"h"}',
                        ]
                    ],
                }
            ]
        },
    }

    with _patch_urlopen_body(payload) as m_url:
        cab = _cab()
        out = loki_query_range(
            cab,
            '{job="cabinet"}',
            limit=100,
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

    m_url.assert_called_once()
    assert len(out) == 1
    labels, ts_ns, line = out[0]
    assert labels.get("job") == "cabinet"
    assert "hello" in line
    assert ts_ns == "1704110400000000000"


def test_cabinet_log_query_documents_loki_filters():
    payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "stream": {"job": "cabinet", "filename": "/logs/2024-01-01/a.jsonl"},
                    "values": [
                        [
                            "1704110400000000000",
                            '{"timestamp":"2024-01-01T12:00:00Z","level":"warning","message":"warn msg","tags":["backup"],"source":{"file":"tools/b.py","line":1},"hostname":"cloud"}',
                        ],
                        [
                            "1704110500000000000",
                            '{"timestamp":"2024-01-01T15:00:00Z","level":"info","message":"skip","tags":[],"source":{"file":"c.py","line":1},"hostname":"cloud"}',
                        ],
                    ],
                }
            ]
        },
    }
    with _patch_urlopen_body(payload):
        cab = _cab()
        docs = cabinet_log_query_documents_loki(
            cab,
            level="warning",
            hostname="cloud",
            tags=["backup"],
            path="tools",
            message="warn",
            limit=10,
            since=timedelta(days=7),
        )
    assert len(docs) == 1
    assert docs[0]["message"] == "warn msg"
    assert docs[0]["level"] == "warning"


def test_format_json_log_record_as_cabinet_line():
    rec = {
        "timestamp": datetime(2024, 1, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
        "level": "info",
        "message": "m",
        "tags": ["a"],
        "source": {"file": "f.py", "line": 3},
        "hostname": "host",
    }
    line = format_json_log_record_as_cabinet_line(rec)
    assert "INFO" in line
    assert "m" in line
    assert "[a]" in line
    assert "f.py" in line
    assert "host" in line


def test_cabinet_log_query_issues_loki_filters_levels():
    payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "stream": {"job": "cabinet"},
                    "values": [
                        [
                            "1704110400000000000",
                            '{"timestamp":"2024-01-01T12:00:00Z","level":"info","message":"i","tags":[],"source":{"file":"a","line":1},"hostname":"h"}',
                        ],
                        [
                            "1704110500000000000",
                            '{"timestamp":"2024-01-01T13:00:00Z","level":"error","message":"e","tags":[],"source":{"file":"a","line":2},"hostname":"h"}',
                        ],
                    ],
                }
            ]
        },
    }
    with _patch_urlopen_body(payload):
        cab = _cab()
        lines = cabinet_log_query_issues_loki(cab, since=timedelta(days=1), limit=50)

    assert len(lines) == 1
    assert "ERROR" in lines[0]
    assert "e" in lines[0]


def test_cabinet_log_query_loki_returns_formatted_lines():
    payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "stream": {"job": "cabinet"},
                    "values": [
                        [
                            "1704110400000000000",
                            '{"timestamp":"2024-01-01T12:00:00Z","level":"info","message":"x","tags":[],"source":{"file":"a","line":1},"hostname":"h"}',
                        ],
                    ],
                }
            ]
        },
    }
    with _patch_urlopen_body(payload):
        cab = _cab()
        lines = cabinet_log_query_loki(cab, since=timedelta(days=1))

    assert len(lines) == 1
    assert "INFO" in lines[0]
    assert "x" in lines[0]
