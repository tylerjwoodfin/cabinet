"""
Logging helpers for Cabinet: file logging (source of truth), optional JSON lines for
Promtail/Loki.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import TYPE_CHECKING, Any

from prompt_toolkit import HTML, print_formatted_text

if TYPE_CHECKING:
    from .cabinet import Cabinet

VALID_LOG_LEVELS = frozenset({"debug", "info", "warning", "error", "critical"})

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


def _loki_jsonl_enabled(cabinet: Cabinet) -> bool:
    """True when ``logging_loki_enabled`` is explicitly set True on the instance."""
    try:
        val = object.__getattribute__(cabinet, "logging_loki_enabled")
    except AttributeError:
        return False
    return val is True


def _append_jsonl_line(
    jsonl_path: str,
    record: dict[str, Any],
) -> None:
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(jsonl_path, "a", encoding="utf-8") as jf:
        jf.write(line)


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
    """
    Append one line to the classic Cabinet log file. Never raises.

    When ``cabinet.logging_loki_enabled`` is True, also appends a JSON line to a sibling
    ``.jsonl`` file for Promtail → Loki (filesystem only; no HTTP).
    """
    try:
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
        resolved_folder = os.path.expandvars(os.path.expanduser(resolved_folder))

        if not os.path.exists(resolved_folder):
            os.makedirs(resolved_folder)

        resolved_log_name = log_name if log_name is not None else f"LOG_DAILY_{today}"

        logger = logging.getLogger(resolved_log_name)
        logger.setLevel(getattr(logging, level.upper()))

        if logger.hasHandlers():
            logger.handlers = []

        log_file_path = os.path.join(resolved_folder, f"{resolved_log_name}.log")
        file_handler = logging.FileHandler(log_file_path, mode="a")

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

        if _loki_jsonl_enabled(cabinet):
            try:
                ts_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                tag_list = list(tags) if tags else []
                payload: dict[str, Any] = {
                    "timestamp": ts_iso,
                    "level": normalize_level(level),
                    "message": message,
                    "tags": tag_list,
                    "source": {"file": caller_file, "line": caller_line},
                    "hostname": hostname,
                }
                jsonl_path = os.path.join(resolved_folder, f"{resolved_log_name}.jsonl")
                _append_jsonl_line(jsonl_path, payload)
            except Exception:
                pass
    except Exception as exc:
        print(f"Cabinet logging failed (ignored): {exc}", file=sys.stderr)


def cabinet_log(
    cabinet: Cabinet,
    message: str = "",
    log_name: str | None = None,
    level: str | None = None,
    log_folder_path: str | None = None,
    is_quiet: bool | None = None,
    tags: list[str] | None = None,
) -> None:
    if not message:
        raise ValueError("Message cannot be empty")

    level = normalize_level(level)
    validate_level(level)

    if is_quiet is None:
        is_quiet = level == "debug"

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
    Format a timezone-aware or UTC ``datetime`` using the **system local** timezone for
    display. Naive datetimes are treated as UTC. Non-datetimes fall back to ``str(ts)``.
    """
    if not isinstance(ts, datetime):
        return str(ts)
    try:
        local = _utc_datetime_for_display(ts).astimezone()
    except (TypeError, ValueError, OSError):
        return str(ts)
    return local.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def cabinet_log_query(
    cabinet: Cabinet,
    log_file: str | None = None,
    tags: list[str] | None = None,
    path: str | None = None,
    hostname: str | None = None,
    level: str | None = None,
    date_filter: str | None = None,
    message: str | None = None,
    since: timedelta | datetime | None = None,
) -> list[str]:
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

    File lines use ``logging``'s default ``asctime`` (often without fractional seconds).
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


def cabinet_log_query_issues(
    cabinet: Cabinet,
    *,
    since: timedelta | datetime | None = None,
) -> list[str]:
    """
    Return formatted log lines at **WARNING**, **ERROR**, or **CRITICAL** within ``since``.

    Default ``since`` is the last 24 hours. Reads today’s and yesterday’s daily **files**
    under ``path_dir_log``.

    Lines are deduplicated, sorted chronologically (by parsed local timestamp), and in the
    same textual format as :func:`cabinet_log_query`.
    """
    if since is None:
        since = timedelta(hours=24)

    merged = _collect_log_issue_lines_from_files(cabinet, since)
    merged = list(dict.fromkeys(merged))
    merged.sort(key=_log_issue_line_sort_key)
    return merged


# --- Loki query (HTTP read path; optional ``logging.loki_url`` in config) -----------


def _require_loki_url(cabinet: Cabinet) -> str:
    try:
        url = object.__getattribute__(cabinet, "logging_loki_url")
    except AttributeError as exc:
        raise ValueError(
            "Loki URL not configured. Set logging.loki_url in config.json "
            "(e.g. http://127.0.0.1:3100)."
        ) from exc
    if not isinstance(url, str) or not url.strip():
        raise ValueError(
            "Loki URL not configured. Set logging.loki_url in config.json "
            "(e.g. http://127.0.0.1:3100)."
        )
    return url.strip().rstrip("/")


def _loki_job_name(cabinet: Cabinet) -> str:
    try:
        job = object.__getattribute__(cabinet, "logging_loki_job")
    except AttributeError:
        return "cabinet"
    if isinstance(job, str) and job.strip():
        return job.strip()
    return "cabinet"


def _loki_query_timeout_s(cabinet: Cabinet) -> float:
    try:
        t = object.__getattribute__(cabinet, "logging_loki_query_timeout")
    except AttributeError:
        return 30.0
    if isinstance(t, (int, float)) and t > 0:
        return float(t)
    return 30.0


def _parse_iso_to_utc(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except ValueError:
        return None


def loki_query_range(
    cabinet: Cabinet,
    logql: str,
    *,
    limit: int = 500,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[tuple[dict[str, str], str, str]]:
    """
    Run ``query_range`` against Loki. Returns ``(stream labels, ts_ns, log line)`` tuples
    newest-first within each stream (caller should merge/sort if needed).

    Raises:
        ValueError: If ``logging.loki_url`` is not set.
        urllib.error.URLError: On network/HTTP failures.
        RuntimeError: If Loki returns a non-success status.
    """
    base = _require_loki_url(cabinet)
    if end is None:
        end = datetime.now(timezone.utc)
    if start is None:
        start = end - timedelta(hours=24)
    ns_start = str(int(start.timestamp() * 1_000_000_000))
    ns_end = str(int(end.timestamp() * 1_000_000_000))
    params = urllib.parse.urlencode(
        {"query": logql, "limit": str(max(1, limit)), "start": ns_start, "end": ns_end}
    )
    url = f"{base}/loki/api/v1/query_range?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    timeout = _loki_query_timeout_s(cabinet)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Loki HTTP {exc.code}: {detail}") from exc

    if body.get("status") != "success":
        raise RuntimeError(body.get("error") or body.get("message") or str(body))

    out: list[tuple[dict[str, str], str, str]] = []
    for stream in body.get("data", {}).get("result", []) or []:
        stream_labels = stream.get("stream") or {}
        for ts_ns, line in stream.get("values") or []:
            out.append((stream_labels, ts_ns, line))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def _record_from_loki_json_line(
    labels: dict[str, str],
    ts_ns: str,
    line: str,
) -> dict[str, Any]:
    try:
        rec: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError:
        rec = {
            "message": line,
            "level": labels.get("level", "info"),
            "tags": [],
            "source": {},
            "hostname": labels.get("hostname", ""),
            "timestamp": labels.get("timestamp", ""),
        }
    ts_raw = rec.get("timestamp")
    dt = None
    if isinstance(ts_raw, str):
        dt = _parse_iso_to_utc(ts_raw)
    elif isinstance(ts_raw, datetime):
        dt = ts_raw.astimezone(timezone.utc)
    if dt is not None:
        rec["timestamp"] = dt
    elif ts_ns.isdigit():
        sec = int(ts_ns) / 1_000_000_000
        rec["timestamp"] = datetime.fromtimestamp(sec, tz=timezone.utc)
    rec["_loki"] = {"labels": dict(labels), "ts_ns": ts_ns}
    return rec


def format_json_log_record_as_cabinet_line(rec: dict[str, Any]) -> str:
    """Format a Cabinet JSONL record like the classic human-readable ``.log`` line."""
    ts_val = rec.get("timestamp")
    if isinstance(ts_val, datetime):
        ts_str = format_log_timestamp_local(ts_val)
    elif isinstance(ts_val, str):
        dt = _parse_iso_to_utc(ts_val)
        ts_str = format_log_timestamp_local(dt) if dt else ts_val
    else:
        ts_str = str(ts_val)
    lev = str(rec.get("level", "info")).upper()
    if lev == "WARN":
        lev = "WARNING"
    tags = rec.get("tags") or []
    if isinstance(tags, str):
        tags_part = f" [{tags}]" if tags else ""
    else:
        tag_list = [str(t) for t in tags]
        tags_part = f" [{','.join(tag_list)}]" if tag_list else ""
    src = rec.get("source") or {}
    path = src.get("file", "unknown")
    line_no = src.get("line", 0)
    host = rec.get("hostname", "")
    msg = rec.get("message", "")
    return f"{ts_str} — {lev}{tags_part} -> {path}:{line_no}@{host} -> {msg}"


def _build_loki_selector(cabinet: Cabinet, hostname: str | None, level: str | None) -> str:
    job = _loki_job_name(cabinet)
    parts = [f'job="{job}"']
    if hostname:
        parts.append(f'hostname="{hostname}"')
    if level:
        parts.append(f'level="{normalize_level(level)}"')
    return "{" + ",".join(parts) + "}"


def _loki_record_matches(
    rec: dict[str, Any],
    labels: dict[str, str],
    *,
    tags: list[str] | None,
    path: str | None,
    message: str | None,
    date_filter: str | None,
    log_file: str | None,
    since: timedelta | datetime | None,
) -> bool:
    ts_dt = rec.get("timestamp")
    if not isinstance(ts_dt, datetime):
        return False
    ts_utc = ts_dt.astimezone(timezone.utc)

    if since is not None:
        cutoff = _since_to_utc_cutoff(since)
        if ts_utc < cutoff:
            return False

    if date_filter:
        local_head = format_log_timestamp_local(ts_dt)[:10]
        if local_head != date_filter:
            return False

    if message and message.lower() not in str(rec.get("message", "")).lower():
        return False

    if path:
        src = rec.get("source") or {}
        fpath = str(src.get("file", "")).lower()
        if path.lower() not in fpath:
            return False

    if tags:
        raw_tags = rec.get("tags")
        if isinstance(raw_tags, str):
            have = {raw_tags.strip().lower()} if raw_tags.strip() else set()
        elif isinstance(raw_tags, list):
            have = {str(t).strip().lower() for t in raw_tags}
        else:
            have = set()
        for tag in tags:
            if tag.strip().lower() not in have:
                return False

    if log_file:
        fn = labels.get("filename", "")
        if log_file not in fn and log_file not in json.dumps(rec):
            return False

    return True


def cabinet_log_query_documents_loki(
    cabinet: Cabinet,
    *,
    level: str | None = None,
    since: timedelta | datetime | None = None,
    end: datetime | None = None,
    tags: list[str] | None = None,
    path: str | None = None,
    hostname: str | None = None,
    message: str | None = None,
    date_filter: str | None = None,
    log_file: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return log entries from **Loki** (Cabinet **JSONL** streams) as dicts, newest first.

    Requires ``config.json`` → ``logging.loki_url`` (e.g. ``http://127.0.0.1:3100``).
    Each dict matches the JSONL shape (``timestamp`` as timezone-aware ``datetime``) plus
    ``_loki`` metadata. Uses HTTP; does not write logs.
    """
    if limit < 1:
        limit = 1
    window_end = end if end is not None else datetime.now(timezone.utc)
    window_start: datetime | None = None
    if since is not None and isinstance(since, datetime):
        window_start = since.astimezone(timezone.utc)
    elif since is not None:
        window_start = window_end - since
    else:
        window_start = window_end - timedelta(hours=24)

    logql = _build_loki_selector(cabinet, hostname, level)
    fetch_limit = min(5000, max(limit * 20, limit))
    triples = loki_query_range(
        cabinet,
        logql,
        limit=fetch_limit,
        start=window_start,
        end=window_end,
    )

    out: list[dict[str, Any]] = []
    for labels, ts_ns, line in triples:
        rec = _record_from_loki_json_line(labels, ts_ns, line)
        if _loki_record_matches(
            rec,
            labels,
            tags=tags,
            path=path,
            message=message,
            date_filter=date_filter,
            log_file=log_file,
            since=None,
        ):
            out.append(rec)
        if len(out) >= limit:
            break
    return out


def cabinet_log_query_loki(
    cabinet: Cabinet,
    log_file: str | None = None,
    tags: list[str] | None = None,
    path: str | None = None,
    hostname: str | None = None,
    level: str | None = None,
    date_filter: str | None = None,
    message: str | None = None,
    since: timedelta | datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[str]:
    """
    Same filter semantics as :func:`cabinet_log_query`, but data is read from **Loki**
    (Cabinet JSONL). Returns human-readable lines matching the classic ``.log`` format.
    """
    docs = cabinet_log_query_documents_loki(
        cabinet,
        level=level,
        since=since,
        end=end,
        tags=tags,
        path=path,
        hostname=hostname,
        message=message,
        date_filter=date_filter,
        log_file=log_file,
        limit=limit,
    )
    return [format_json_log_record_as_cabinet_line(d) for d in docs]


def cabinet_log_query_issues_loki(
    cabinet: Cabinet,
    *,
    since: timedelta | datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[str]:
    """
    Return **WARNING**, **ERROR**, and **CRITICAL** lines from **Loki**, same time window
    semantics as :func:`cabinet_log_query_issues` (default: last 24 hours).
    """
    if since is None:
        since = timedelta(hours=24)

    job = _loki_job_name(cabinet)
    logql = f'{{job="{job}"}}'
    window_end = end if end is not None else datetime.now(timezone.utc)
    if isinstance(since, datetime):
        window_start = since.astimezone(timezone.utc)
    else:
        window_start = window_end - since

    triples = loki_query_range(
        cabinet,
        logql,
        limit=min(5000, max(limit * 10, limit)),
        start=window_start,
        end=window_end,
    )
    lines: list[str] = []
    for labels, ts_ns, line in triples:
        rec = _record_from_loki_json_line(labels, ts_ns, line)
        lev = normalize_level(str(rec.get("level", labels.get("level", "info"))))
        if lev not in ("warning", "error", "critical"):
            continue
        lines.append(format_json_log_record_as_cabinet_line(rec))
    lines = list(dict.fromkeys(lines))
    lines.sort(key=_log_issue_line_sort_key)
    return lines[:limit]
