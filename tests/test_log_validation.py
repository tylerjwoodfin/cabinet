"""Validation tests for cabinet.log helpers and routing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import CollectionInvalid, OperationFailure

from cabinet.helpers import parse_config_bool
from cabinet.log import (
    DEFAULT_MONGO_LOG_COLLECTION,
    LOG_TTL_INDEX_NAME,
    LOG_TTL_SECONDS,
    _insert_log_document,
    cabinet_log,
    cabinet_log_query,
    cabinet_log_query_issues,
    format_mongo_log_line,
    log_query_documents,
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


def test_format_mongo_log_line():
    ts = datetime(2026, 4, 28, 12, 0, 0, 123000, tzinfo=timezone.utc)
    local = ts.astimezone()
    line = format_mongo_log_line(
        {
            "timestamp": ts,
            "level": "ERROR",
            "message": "oops",
            "source": {"file": "pkg/mod.py", "line": 42},
            "hostname": "host1",
            "tags": ["x", "y"],
        }
    )
    assert "ERROR" in line
    assert "[x,y]" in line
    assert "pkg/mod.py" in line
    assert "host1" in line
    assert "oops" in line
    assert local.strftime("%Y-%m-%d %H:%M:%S") in line


def test_log_query_documents_requires_mongodb():
    cab = MagicMock()
    cab.mongodb_enabled = False
    with pytest.raises(ValueError, match="MongoDB must be enabled"):
        log_query_documents(cab, since=timedelta(hours=1))


def test_log_query_documents_builds_query_and_calls_timeout(tmp_path):
    cab = MagicMock()
    cab.mongodb_enabled = True
    inserted = []

    def fake_timeout(fn):
        inserted.append(fn())
        return inserted[-1]

    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.__iter__ = lambda self: iter([{"_id": 1, "message": "m"}])

    cab.database = {DEFAULT_MONGO_LOG_COLLECTION: MagicMock()}
    cab.database[DEFAULT_MONGO_LOG_COLLECTION].find.return_value = cursor
    cab._mongodb_with_timeout = fake_timeout

    out = log_query_documents(cab, level="error", since=timedelta(days=1), limit=10)
    cab.database[DEFAULT_MONGO_LOG_COLLECTION].find.assert_called_once()
    call_kw = cab.database[DEFAULT_MONGO_LOG_COLLECTION].find.call_args[0][0]
    assert call_kw["level"] == "ERROR"
    assert "$gte" in call_kw["timestamp"]
    assert out == [{"_id": 1, "message": "m"}]


def test_cabinet_log_file_mode(tmp_path):
    cab = MagicMock()
    cab.mongodb_enabled = False
    cab.path_dir_log = str(tmp_path)

    cabinet_log(cab, "hello file", level="info", is_quiet=True)

    day_dir = tmp_path / datetime.now().strftime("%Y-%m-%d")
    log_files = list(day_dir.glob("*.log"))
    assert len(log_files) == 1
    text = log_files[0].read_text(encoding="utf-8")
    assert "hello file" in text


def test_cabinet_log_mongo_mode_inserts(tmp_path):
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.path_dir_log = str(tmp_path)
    coll = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    cab.database = db

    def fake_timeout(op):
        return op()

    cab._mongodb_with_timeout = fake_timeout

    cabinet_log(cab, "mongo msg", level="warning", is_quiet=True)

    day_dir = tmp_path / datetime.now().strftime("%Y-%m-%d")
    log_paths = list(day_dir.glob("*.log"))
    assert len(log_paths) == 1
    assert "mongo msg" in log_paths[0].read_text(encoding="utf-8")

    db.create_collection.assert_called_once_with(DEFAULT_MONGO_LOG_COLLECTION)
    coll.create_index.assert_called_once_with(
        [("timestamp", 1)],
        expireAfterSeconds=LOG_TTL_SECONDS,
        name=LOG_TTL_INDEX_NAME,
    )
    coll.insert_one.assert_called_once()
    doc = coll.insert_one.call_args[0][0]
    assert doc["message"] == "mongo msg"
    assert doc["level"] == "WARNING"
    assert doc["hostname"]
    assert "timestamp" in doc


def test_cabinet_log_mongo_failure_still_writes_file(tmp_path, capsys):
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.path_dir_log = str(tmp_path)
    coll = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    cab.database = db
    coll.insert_one.side_effect = RuntimeError("mongo down")

    cab._mongodb_with_timeout = lambda op: op()

    cabinet_log(cab, "survives", level="info", is_quiet=True)

    day_dir = tmp_path / datetime.now().strftime("%Y-%m-%d")
    paths = list(day_dir.glob("*.log"))
    assert len(paths) == 1
    text = paths[0].read_text(encoding="utf-8")
    assert "survives" in text
    assert "MongoDB failed" in text
    assert "MongoDB failed" in capsys.readouterr().err


def test_insert_log_document_ignores_namespace_exists():
    cab = MagicMock()
    coll = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    calls = []

    def create_side_effect(name):
        calls.append("create")
        raise OperationFailure("exists", code=48)

    db.create_collection.side_effect = create_side_effect
    cab.database = db

    _insert_log_document(cab, "log", {"message": "x"})

    assert calls == ["create"]
    coll.create_index.assert_called_once_with(
        [("timestamp", 1)],
        expireAfterSeconds=LOG_TTL_SECONDS,
        name=LOG_TTL_INDEX_NAME,
    )
    coll.insert_one.assert_called_once_with({"message": "x"})


def test_insert_log_document_ignores_collection_invalid():
    cab = MagicMock()
    coll = MagicMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    db.create_collection.side_effect = CollectionInvalid("collection log already exists")
    cab.database = db

    _insert_log_document(cab, "log", {"message": "y"})

    coll.create_index.assert_called_once_with(
        [("timestamp", 1)],
        expireAfterSeconds=LOG_TTL_SECONDS,
        name=LOG_TTL_INDEX_NAME,
    )
    coll.insert_one.assert_called_once_with({"message": "y"})


def test_cabinet_log_file_when_mongo_if_folder_forced(tmp_path):
    """log_folder_path forces file logging even when MongoDB is enabled."""
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.path_dir_log = str(tmp_path)

    custom = str(tmp_path / "forced")
    cabinet_log(cab, "on disk", level="info", log_folder_path=custom, is_quiet=True)

    forced_dir = tmp_path / "forced"
    log_files = list(forced_dir.glob("*.log"))
    assert len(log_files) == 1
    assert "on disk" in log_files[0].read_text(encoding="utf-8")


def test_cabinet_log_query_mongo_branch():
    cab = MagicMock()
    cab.mongodb_enabled = True
    coll = MagicMock()
    cab.database = {"log": coll}
    cur = MagicMock()
    coll.find.return_value = cur
    cur.sort.return_value = cur
    cur.limit.return_value = cur
    cur.__iter__ = lambda self: iter(
        [
            {
                "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "level": "INFO",
                "message": "x",
                "source": {"file": "f.py", "line": 1},
                "hostname": "h",
            }
        ]
    )

    def fake_timeout(fn):
        return fn()

    cab._mongodb_with_timeout = fake_timeout

    lines = cabinet_log_query(cab, level="info")
    assert len(lines) == 1
    assert "INFO" in lines[0]
    assert "x" in lines[0]


def test_cabinet_log_query_mongo_since_in_find_filter():
    cab = MagicMock()
    cab.mongodb_enabled = True
    coll = MagicMock()
    cab.database = {"log": coll}
    cur = MagicMock()
    coll.find.return_value = cur
    cur.sort.return_value = cur
    cur.limit.return_value = cur
    cur.__iter__ = lambda self: iter([])

    cab._mongodb_with_timeout = lambda fn: fn()

    cabinet_log_query(cab, since=timedelta(hours=3), level="WARN")

    q = coll.find.call_args[0][0]
    assert q["level"] == "WARNING"
    assert "$gte" in q["timestamp"]


@patch("cabinet.log.cabinet_log_query")
def test_cabinet_log_query_issues_mongo_merges_levels(mock_cq):
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.database = {"log": MagicMock()}
    mock_cq.side_effect = lambda cabinet, **kw: [f"{kw['level']}-line"]

    out = cabinet_log_query_issues(cab)
    assert set(out) == {"critical-line", "error-line", "warning-line"}
    assert mock_cq.call_count == 3


@patch("cabinet.log.cabinet_log_query", side_effect=RuntimeError("mongo down"))
@patch(
    "cabinet.log._collect_log_issue_lines_from_files",
    return_value=["2026-04-28 12:00:00 — ERROR -> x:y@z -> from file"],
)
def test_cabinet_log_query_issues_mongo_failure_falls_back(mock_files, mock_cq):
    cab = MagicMock()
    cab.mongodb_enabled = True
    cab.database = {"log": MagicMock()}
    assert cabinet_log_query_issues(cab) == [
        "2026-04-28 12:00:00 — ERROR -> x:y@z -> from file"
    ]
    mock_files.assert_called_once()


def test_cabinet_log_query_issues_file_fallback(tmp_path):
    from datetime import date
    from types import SimpleNamespace

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
        mongodb_enabled=False,
        database=None,
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
    from types import SimpleNamespace

    today = date.today()
    day_dir = tmp_path / str(today)
    day_dir.mkdir(parents=True)
    log_path = day_dir / f"LOG_DAILY_{today}.log"
    log_path.write_text(
        f"{today.isoformat()} 12:00:00 — INFO -> pkg/f.py:9@z -> hello\n",
        encoding="utf-8",
    )
    cab = SimpleNamespace(mongodb_enabled=False, path_dir_log=str(tmp_path))
    out = cabinet_log_query(
        cab,
        log_file=f"LOG_DAILY_{today}.log",
        date_filter=str(today),
        level="info",
        since=timedelta(days=7),
    )
    assert len(out) == 1
    assert "hello" in out[0]
