"""
Logging helpers for Cabinet: file and MongoDB backends, and log querying.
"""

from __future__ import annotations

import inspect
import logging
import os
import re
import socket
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import TYPE_CHECKING, Any

from pymongo import ASCENDING
from pymongo.errors import CollectionInvalid, OperationFailure
from prompt_toolkit import HTML, print_formatted_text

from . import helpers

if TYPE_CHECKING:
    from .cabinet import Cabinet

DEFAULT_MONGO_LOG_COLLECTION = "log"
# TTL on `timestamp`: MongoDB deletes documents this many seconds after `timestamp`.
LOG_TTL_DAYS = 90
LOG_TTL_SECONDS = int(timedelta(days=LOG_TTL_DAYS).total_seconds())
LOG_TTL_INDEX_NAME = "cabinet_log_timestamp_ttl"
_log_ttl_index_ensured: set[tuple[int, str]] = set()

VALID_LOG_LEVELS = frozenset({"debug", "info", "warning", "error", "critical"})

# Severity levels included by :func:`cabinet_log_query_issues` (warning and above).
_LOG_QUERY_ISSUE_LEVELS = ("critical", "error", "warning")


def normalize_level(level: str | None) -> str:
    if level is None:
        return "info"
    low = level.lower()
    if low == "warn":
        return "warning"
    return low


def validate_level(level: str) -> None:
    normalized = normalize_level(level)
    if normalized not in VALID_LOG_LEVELS:
        raise ValueError(
            f"Invalid log level: {level}. Must be in {', '.join(sorted(VALID_LOG_LEVELS))}."
        )


def _resolve_caller(skip_prefixes: tuple[str, ...]) -> tuple[str, int]:
    caller_file = "unknown"
    caller_line = 0
    stack = inspect.stack()
    for frame_info in stack:
        module = inspect.getmodule(frame_info.frame)
        module_name = module.__name__ if module else None
        if not module_name:
            continue
        if any(module_name.startswith(p) for p in skip_prefixes):
            continue
        if "logging" in module_name:
            continue
        caller_file = os.path.join(
            os.path.basename(os.path.dirname(frame_info.filename)),
            os.path.basename(frame_info.filename),
        )
        caller_line = frame_info.lineno
        break
    return caller_file, caller_line


def _emit_console(level: str, message: str, is_quiet: bool) -> None:
    color_map = {
        "debug": "ansiwhite",
        "info": "ansigreen",
        "warning": "ansiyellow",
        "error": "ansired",
        "critical": "ansimagenta",
    }
    color = color_map[level.lower()]
    escaped_msg = escape(message)
    if not is_quiet:
        print_formatted_text(HTML(f"<{color}>{level.upper()}: {escaped_msg}</{color}>"))


def _since_to_utc_cutoff(since: timedelta | datetime) -> datetime:
    if isinstance(since, timedelta):
        return datetime.now(timezone.utc) - since
    if since.tzinfo is None:
        return since.replace(tzinfo=timezone.utc)
    return since.astimezone(timezone.utc)


def _ensure_log_ttl_index(cabinet: Cabinet, collection_name: str) -> None:
    cache_key = (id(cabinet.database), collection_name)
    if cache_key in _log_ttl_index_ensured:
        return
    coll = cabinet.database[collection_name]
    coll.create_index(
        [("timestamp", ASCENDING)],
        expireAfterSeconds=LOG_TTL_SECONDS,
        name=LOG_TTL_INDEX_NAME,
    )
    _log_ttl_index_ensured.add(cache_key)


def _insert_log_document(
    cabinet: Cabinet, collection_name: str, log_entry: dict[str, Any]
) -> None:
    try:
        cabinet.database.create_collection(collection_name)
    except CollectionInvalid:
        # pymongo raises this when the collection already exists (vs. OperationFailure on some servers).
        pass
    except OperationFailure as exc:
        # 48 == NamespaceExists — collection already present (race or prior create).
        if getattr(exc, "code", None) != 48:
            raise

    _ensure_log_ttl_index(cabinet, collection_name)
    cabinet.database[collection_name].insert_one(log_entry)


def write_log_mongo(
    cabinet: Cabinet,
    message: str,
    level: str,
    *,
    is_quiet: bool,
    tags: list[str] | None,
    collection_name: str,
) -> None:
    caller_file, caller_line = _resolve_caller(
        ("cabinet.cabinet", "cabinet.log"),
    )
    hostname = socket.gethostname()
    log_entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc),
        "level": level.upper(),
        "message": message,
        "source": {"file": caller_file, "line": caller_line},
        "hostname": hostname,
    }
    if tags:
        log_entry["tags"] = list(tags)

    cabinet._mongodb_with_timeout(  # pylint: disable=protected-access
        lambda: _insert_log_document(cabinet, collection_name, log_entry)
    )
    _emit_console(level, message, is_quiet)


def write_log_file(
    cabinet: Cabinet,
    message: str,
    level: str,
    *,
    log_name: str | None,
    log_folder_path: str | None,
    is_quiet: bool,
    tags: list[str] | None,
) -> None:
    color_map = {
        "debug": "ansiwhite",
        "info": "ansigreen",
        "warning": "ansiyellow",
        "error": "ansired",
        "critical": "ansimagenta",
    }

    class ColorConsoleHandler(logging.StreamHandler):
        def emit(self, record):
            color = color_map[record.levelname.lower()]
            msg = self.format(record)
            escaped_msg = escape(msg)
            print_formatted_text(
                HTML(f"<{color}>{record.levelname}: {escaped_msg}</{color}>")
            )

    today = str(date.today())
    resolved_folder = log_folder_path or os.path.join(cabinet.path_dir_log, today)
    resolved_folder = os.path.expanduser(resolved_folder)

    if not os.path.exists(resolved_folder):
        os.makedirs(resolved_folder)

    resolved_log_name = log_name if log_name is not None else f"LOG_DAILY_{today}"

    logger = logging.getLogger(resolved_log_name)
    logger.setLevel(getattr(logging, level.upper()))

    if logger.hasHandlers():
        logger.handlers = []

    file_handler = logging.FileHandler(
        os.path.join(resolved_folder, f"{resolved_log_name}.log"),
        mode="a",
    )

    caller_file, caller_line = _resolve_caller(
        ("cabinet.cabinet", "cabinet.log"),
    )
    hostname = socket.gethostname()

    tags_str = ""
    if tags:
        tags_str = f" [{','.join(tags)}]"

    file_handler.setFormatter(
        logging.Formatter(
            f"%(asctime)s — %(levelname)s{tags_str} -> {caller_file}:{caller_line}"
            f"@{hostname} -> %(message)s"
        )
    )
    logger.addHandler(file_handler)

    if not is_quiet:
        console_handler = ColorConsoleHandler()
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

    getattr(logger, level.lower())(message)


def cabinet_log(
    cabinet: Cabinet,
    message: str = "",
    log_name: str | None = None,
    level: str | None = None,
    log_folder_path: str | None = None,
    is_quiet: bool | None = None,
    tags: list[str] | None = None,
    collection_name: str | None = None,
) -> None:
    if not message:
        raise ValueError("Message cannot be empty")

    level = normalize_level(level)
    validate_level(level)

    if is_quiet is None:
        is_quiet = level == "debug"

    use_mongo = (
        log_folder_path is None
        and helpers.parse_config_bool(getattr(cabinet, "mongodb_enabled", False))
        and getattr(cabinet, "database", None) is not None
    )

    if use_mongo:
        coll = collection_name or DEFAULT_MONGO_LOG_COLLECTION
        write_log_file(
            cabinet,
            message,
            level,
            log_name=log_name,
            log_folder_path=None,
            is_quiet=is_quiet,
            tags=tags,
        )
        try:
            write_log_mongo(
                cabinet,
                message,
                level,
                is_quiet=True,
                tags=tags,
                collection_name=coll,
            )
        except Exception as error:
            warn_body = f"log written to file but MongoDB failed: {error}"
            write_log_file(
                cabinet,
                warn_body,
                "warning",
                log_name=log_name,
                log_folder_path=None,
                is_quiet=True,
                tags=None,
            )
            print(f"Warning: {warn_body}", file=sys.stderr)
    else:
        write_log_file(
            cabinet,
            message,
            level,
            log_name=log_name,
            log_folder_path=log_folder_path,
            is_quiet=is_quiet,
            tags=tags,
        )


def _utc_datetime_for_display(ts: Any) -> datetime:
    """Normalize to an aware UTC instant for conversion to local display time."""
    if not isinstance(ts, datetime):
        raise TypeError("expected datetime")
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def format_log_timestamp_local(ts: Any) -> str:
    """
    Format a log ``timestamp`` (typically UTC in MongoDB) using the **system local**
    timezone for display. Naive datetimes are treated as UTC. Non-datetimes fall back to
    ``str(ts)``.
    """
    if not isinstance(ts, datetime):
        return str(ts)
    try:
        local = _utc_datetime_for_display(ts).astimezone()
    except (TypeError, ValueError, OSError):
        return str(ts)
    return local.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def format_mongo_log_line(doc: dict[str, Any]) -> str:
    ts = doc.get("timestamp")
    if isinstance(ts, datetime):
        ts_str = format_log_timestamp_local(ts)
    else:
        ts_str = str(ts)
    lev = doc.get("level", "INFO")
    tags = doc.get("tags") or []
    if isinstance(tags, str):
        tags_part = f" [{tags}]" if tags else ""
    else:
        tags_part = (
            f" [{','.join(str(t) for t in tags)}]" if tags else ""
        )
    src = doc.get("source") or {}
    path = src.get("file", "unknown")
    line = src.get("line", 0)
    host = doc.get("hostname", "")
    msg = doc.get("message", "")
    return f"{ts_str} — {lev}{tags_part} -> {path}:{line}@{host} -> {msg}"


def _mongo_timestamp_bounds(
    date_filter: str | None,
    since: timedelta | datetime | None,
) -> dict[str, Any] | None:
    """Build MongoDB ``timestamp`` range: optional calendar day + optional ``since`` cutoff."""
    if date_filter is None and since is None:
        return None
    bounds: dict[str, Any] = {}
    if date_filter:
        day_start = datetime.strptime(date_filter, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        bounds["$gte"] = day_start
        bounds["$lt"] = day_end
    if since is not None:
        cutoff = _since_to_utc_cutoff(since)
        if "$gte" in bounds:
            bounds["$gte"] = max(bounds["$gte"], cutoff)
        else:
            bounds["$gte"] = cutoff
    return bounds


def log_query_documents(
    cabinet: Cabinet,
    *,
    level: str | None = None,
    since: timedelta | datetime | None = None,
    collection_name: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return recent log documents from MongoDB, optionally filtered by level and time.

    Args:
        cabinet: Configured Cabinet instance.
        level: Log level (e.g. error, INFO); matching is case-insensitive.
        since: Only entries at or after this UTC time, or within this timedelta of now.
        collection_name: MongoDB collection (defaults to the ``log`` collection).
        limit: Maximum documents to return, newest first.

    Raises:
        ValueError: If MongoDB is not enabled.
    """
    if not helpers.parse_config_bool(getattr(cabinet, "mongodb_enabled", False)):
        raise ValueError("MongoDB must be enabled to query logs from the database")

    coll = collection_name or DEFAULT_MONGO_LOG_COLLECTION
    query: dict[str, Any] = {}
    if level is not None:
        query["level"] = normalize_level(level).upper()
    ts_bounds = _mongo_timestamp_bounds(None, since)
    if ts_bounds:
        query["timestamp"] = ts_bounds

    def _find():
        cur = (
            cabinet.database[coll]
            .find(query)
            .sort("timestamp", -1)
            .limit(limit)
        )
        return list(cur)

    return cabinet._mongodb_with_timeout(_find)  # pylint: disable=protected-access


def _build_mongo_log_query_filter(
    *,
    tags: list[str] | None,
    path: str | None,
    hostname: str | None,
    level: str | None,
    date_filter: str | None,
    message: str | None,
    since: timedelta | datetime | None = None,
) -> dict[str, Any]:
    q: dict[str, Any] = {}
    if level:
        q["level"] = normalize_level(level).upper()
    if hostname:
        q["hostname"] = hostname
    if tags:
        q["tags"] = {"$in": list(tags)}
    if path:
        q["source.file"] = {"$regex": re.escape(path), "$options": "i"}
    if message:
        q["message"] = {"$regex": re.escape(message), "$options": "i"}
    ts_bounds = _mongo_timestamp_bounds(date_filter, since)
    if ts_bounds:
        q["timestamp"] = ts_bounds
    return q


def cabinet_log_query(
    cabinet: Cabinet,
    log_file: str | None = None,
    tags: list[str] | None = None,
    path: str | None = None,
    hostname: str | None = None,
    level: str | None = None,
    date_filter: str | None = None,
    message: str | None = None,
    collection_name: str | None = None,
    since: timedelta | datetime | None = None,
) -> list[str]:
    if helpers.parse_config_bool(getattr(cabinet, "mongodb_enabled", False)):
        coll = collection_name or DEFAULT_MONGO_LOG_COLLECTION
        mongo_filter = _build_mongo_log_query_filter(
            tags=tags,
            path=path,
            hostname=hostname,
            level=level,
            date_filter=date_filter,
            message=message,
            since=since,
        )

        def _run():
            cur = cabinet.database[coll].find(mongo_filter).sort("timestamp", -1).limit(
                5000
            )
            return [format_mongo_log_line(d) for d in cur]

        return cabinet._mongodb_with_timeout(_run)  # pylint: disable=protected-access

    # ——— file-based query (original behavior) ———
    if log_file is None:
        today = str(date.today())
        log_file = f"LOG_DAILY_{today}.log"

    if not os.path.isabs(log_file):
        if date_filter:
            log_file_path = os.path.join(cabinet.path_dir_log, date_filter, log_file)
        else:
            today = str(date.today())
            log_file_path = os.path.join(cabinet.path_dir_log, today, log_file)

            if not os.path.exists(log_file_path):
                for date_dir in os.listdir(cabinet.path_dir_log):
                    potential_path = os.path.join(
                        cabinet.path_dir_log, date_dir, log_file
                    )
                    if os.path.exists(potential_path):
                        log_file_path = potential_path
                        break
    else:
        log_file_path = log_file

    if not os.path.exists(log_file_path):
        raise FileNotFoundError(f"Log file not found: {log_file_path}")

    log_pattern = re.compile(
        r"^(?P<timestamp>[^\s]+\s+[^\s]+)\s+—\s+(?P<level>\w+)"
        r"(?:\s+\[(?P<tags>[^\]]+)\])?\s+->\s+"
        r"(?P<path>[^:]+):(?P<line>\d+)@(?P<hostname>\S+)\s+->\s+"
        r"(?P<message>.+)$"
    )

    matching_lines: list[str] = []

    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                match = log_pattern.match(line)
                if not match:
                    continue

                log_data = match.groupdict()

                if level and log_data["level"].upper() != normalize_level(level).upper():
                    continue

                if hostname and log_data["hostname"] != hostname:
                    continue

                if date_filter and not log_data["timestamp"].startswith(date_filter):
                    continue

                if since is not None:
                    # File ``asctime`` is local wall time; match :func:`_collect_log_issue_lines_from_files`.
                    cutoff_naive = _file_issue_cutoff_naive(since)
                    parsed_ts = _parse_local_display_log_ts(log_data["timestamp"])
                    if parsed_ts is None or parsed_ts < cutoff_naive:
                        continue

                if message and message.lower() not in log_data["message"].lower():
                    continue

                if path and path.lower() not in log_data["path"].lower():
                    continue

                if tags:
                    log_tags_str = log_data.get("tags", "")
                    if log_tags_str:
                        log_tags = [t.strip() for t in log_tags_str.split(",")]
                        if not any(tag in log_tags for tag in tags):
                            continue
                    else:
                        continue

                matching_lines.append(line)

    except Exception as e:
        raise RuntimeError(f"Error reading log file {log_file_path}: {str(e)}") from e

    return matching_lines


def _parse_local_display_log_ts(ts_str: str) -> datetime | None:
    """
    Parse the leading timestamp from a cabinet log line as **naive local** time.

    File logs use ``logging``'s default ``asctime`` (often without milliseconds); Mongo-backed
    lines from :func:`format_mongo_log_line` use fractional seconds in local time.
    """
    ts_str = ts_str.strip()
    try:
        normalized = ts_str.replace(",", ".", 1)
        return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(ts_str[:10], "%Y-%m-%d")
            except ValueError:
                return None


def _log_issue_line_sort_key(line: str) -> tuple[datetime, str]:
    parts = line.split(" — ", 1)
    parsed = _parse_local_display_log_ts(parts[0]) if parts else None
    if parsed is None:
        return (datetime.min, line)
    return (parsed, line)


def _file_issue_cutoff_naive(since: timedelta | datetime) -> datetime:
    cutoff_utc = _since_to_utc_cutoff(since)
    return cutoff_utc.astimezone().replace(tzinfo=None)


def _collect_log_issue_lines_from_files(
    cabinet: Cabinet, since: timedelta | datetime
) -> list[str]:
    """Scan today and yesterday daily log files; keep WARNING+ lines on or after ``since``."""
    cutoff_naive = _file_issue_cutoff_naive(since)
    out: list[str] = []
    today = date.today()
    for day_offset in (0, 1):
        day = today - timedelta(days=day_offset)
        log_path = os.path.join(cabinet.path_dir_log, str(day))
        log_name = f"LOG_DAILY_{day}.log"
        lines = (
            cabinet.get_file_as_array(
                log_name, file_path=log_path, ignore_not_found=True
            )
            or []
        )
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            upper = line.upper()
            if not any(k in upper for k in ("ERROR", "WARN", "CRITICAL")):
                continue
            head = line.split(" — ", 1)[0]
            parsed = _parse_local_display_log_ts(head)
            if parsed is None or parsed < cutoff_naive:
                continue
            out.append(line)
    out.sort(key=_log_issue_line_sort_key)
    return out


def _mongodb_log_query_usable(cabinet: Cabinet) -> bool:
    return helpers.parse_config_bool(
        getattr(cabinet, "mongodb_enabled", False)
    ) and getattr(cabinet, "database", None) is not None


def cabinet_log_query_issues(
    cabinet: Cabinet,
    *,
    since: timedelta | datetime | None = None,
    collection_name: str | None = None,
) -> list[str]:
    """
    Return formatted log lines at **WARNING**, **ERROR**, or **CRITICAL** within ``since``.

    Default ``since`` is the last 24 hours. When MongoDB is enabled, queries the log collection
    (see :func:`cabinet_log_query`). If the query raises or MongoDB is not configured, falls back
    to scanning today's and yesterday's daily files under ``path_dir_log``.

    Lines are deduplicated, sorted chronologically (by parsed local timestamp), and ready for
    display (same format as :func:`cabinet_log_query`).
    """
    if since is None:
        since = timedelta(hours=24)

    if _mongodb_log_query_usable(cabinet):
        try:
            merged: list[str] = []
            for lev in _LOG_QUERY_ISSUE_LEVELS:
                merged.extend(
                    cabinet_log_query(
                        cabinet,
                        level=lev,
                        since=since,
                        collection_name=collection_name,
                    )
                )
        except Exception:
            pass
        else:
            merged = list(dict.fromkeys(merged))
            merged.sort(key=_log_issue_line_sort_key)
            return merged

    merged = _collect_log_issue_lines_from_files(cabinet, since)
    merged = list(dict.fromkeys(merged))
    merged.sort(key=_log_issue_line_sort_key)
    return merged
