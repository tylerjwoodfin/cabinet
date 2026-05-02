"""Validation tests for cabinet.log helpers and routing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cabinet.helpers import parse_config_bool
from cabinet.log import (
    cabinet_log,
    cabinet_log_query,
    cabinet_log_query_issues,
    format_log_timestamp_local,
    normalize_level,
    validate_level,
)


def test_parse_config_bool():
    assert parse_config_bool(True) is True
    assert parse_config_bool(False) is False
    assert parse_config_bool("") is False
    assert parse_config_bool(None) is False
    assert parse_config_bool("true") is True
    assert parse_config_bool("FALSE") is False
    assert parse_config_bool("1") is True
    assert parse_config_bool(0) is False


def test_normalize_level_warn_alias():
    assert normalize_level("warn") == "warning"
    assert normalize_level(None) == "info"


def test_validate_level_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid log level"):
        validate_level("nosuch")


def test_format_log_timestamp_local():
    ts = datetime(2026, 4, 28, 12, 0, 0, 123000, tzinfo=timezone.utc)
    s = format_log_timestamp_local(ts)
    assert "2026" in s
    assert "04-28" in s
    assert ",123" in s or "123" in s


def test_cabinet_log_file_mode(tmp_path):
    cab = MagicMock()
    cab.path_dir_log = str(tmp_path)

    cabinet_log(cab, "hello file", level="info", is_quiet=True)

    day_dir = tmp_path / datetime.now().strftime("%Y-%m-%d")
    log_files = list(day_dir.glob("*.log"))
    assert len(log_files) == 1
    text = log_files[0].read_text(encoding="utf-8")
    assert "hello file" in text


def test_cabinet_log_with_mongodb_enabled_still_writes_files_only(tmp_path):
    """MongoDB may be on for Cabinet data; log() still writes only to files."""
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.path_dir_log = str(tmp_path)
    coll = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    cab.database = db

    cabinet_log(cab, "mongo msg", level="warning", is_quiet=True)

    day_dir = tmp_path / datetime.now().strftime("%Y-%m-%d")
    log_paths = list(day_dir.glob("*.log"))
    assert len(log_paths) == 1
    assert "mongo msg" in log_paths[0].read_text(encoding="utf-8")

    coll.insert_one.assert_not_called()
    db.create_collection.assert_not_called()


def test_cabinet_log_writes_jsonl_when_loki_enabled(tmp_path):
    today = datetime.now().strftime("%Y-%m-%d")
    cab = SimpleNamespace(
        path_dir_log=str(tmp_path),
        logging_loki_enabled=True,
    )
    cabinet_log(cab, "for loki", level="info", tags=["t1"], is_quiet=True)

    day_dir = tmp_path / today
    jsonl_files = list(day_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    payload = json.loads(jsonl_files[0].read_text(encoding="utf-8").strip())
    assert payload["message"] == "for loki"
    assert payload["level"] == "info"
    assert payload["tags"] == ["t1"]
    assert "timestamp" in payload
    assert "source" in payload
    assert "hostname" in payload


def test_cabinet_log_no_jsonl_when_loki_disabled(tmp_path):
    cab = SimpleNamespace(path_dir_log=str(tmp_path))
    cabinet_log(cab, "plain", level="info", is_quiet=True)

    day_dir = tmp_path / datetime.now().strftime("%Y-%m-%d")
    assert list(day_dir.glob("*.jsonl")) == []


def test_cabinet_log_forced_folder_with_mongo_enabled(tmp_path):
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.path_dir_log = str(tmp_path)

    custom = str(tmp_path / "forced")
    cabinet_log(cab, "on disk", level="info", log_folder_path=custom, is_quiet=True)

    forced_dir = tmp_path / "forced"
    log_files = list(forced_dir.glob("*.log"))
    assert len(log_files) == 1
    assert "on disk" in log_files[0].read_text(encoding="utf-8")


def test_cabinet_log_query_reads_files_even_when_mongodb_enabled(tmp_path):
    from datetime import date

    today = date.today()
    day_dir = tmp_path / str(today)
    day_dir.mkdir(parents=True)
    log_path = day_dir / f"LOG_DAILY_{today}.log"
    log_path.write_text(
        f"{today.isoformat()} 14:00:00,001 — INFO -> pkg/f.py:1@h -> line one\n",
        encoding="utf-8",
    )
    cab = SimpleNamespace(
        mongodb_enabled=True,
        path_dir_log=str(tmp_path),
        database=MagicMock(),
        _mongodb_with_timeout=MagicMock(),
    )
    lines = cabinet_log_query(
        cab,
        log_file=f"LOG_DAILY_{today}.log",
        date_filter=str(today),
        level="info",
    )
    assert len(lines) == 1
    assert "line one" in lines[0]


def test_cabinet_log_query_issues_file_scan(tmp_path):
    from datetime import date

    today = date.today()
    day_dir = tmp_path / str(today)
    day_dir.mkdir(parents=True)
    log_path = day_dir / f"LOG_DAILY_{today}.log"
    log_path.write_text(
        "2020-01-01 12:00:00 — WARNING -> a:b@c -> too old\n"
        f"{today.isoformat()} 15:00:00 — ERROR -> a:b@c -> recent err\n",
        encoding="utf-8",
    )

    def get_file_as_array(
        file_name, file_path="", strip=True, ignore_not_found=False
    ):
        from pathlib import Path

        base = Path(file_path).expanduser()
        fp = base / file_name
        if not fp.is_file():
            return None if ignore_not_found else None
        text = fp.read_text(encoding="utf-8")
        if strip:
            text = text.strip()
        return text.split("\n") if text else []

    cab = SimpleNamespace(
        path_dir_log=str(tmp_path),
        get_file_as_array=get_file_as_array,
    )
    out = cabinet_log_query_issues(cab, since=timedelta(hours=24))
    assert len(out) == 1
    assert "recent err" in out[0]
    assert "too old" not in out[0]


def test_cabinet_log_query_file_mode_since_accepts_asctime_without_fractional_seconds(
    tmp_path,
):
    from datetime import date

    today = date.today()
    day_dir = tmp_path / str(today)
    day_dir.mkdir(parents=True)
    log_path = day_dir / f"LOG_DAILY_{today}.log"
    log_path.write_text(
        f"{today.isoformat()} 12:00:00 — INFO -> pkg/f.py:9@z -> hello\n",
        encoding="utf-8",
    )
    cab = SimpleNamespace(path_dir_log=str(tmp_path))
    out = cabinet_log_query(
        cab,
        log_file=f"LOG_DAILY_{today}.log",
        date_filter=str(today),
        level="info",
        since=timedelta(days=7),
    )
    assert len(out) == 1
    assert "hello" in out[0]
