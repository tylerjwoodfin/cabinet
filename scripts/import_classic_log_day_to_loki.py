#!/usr/bin/env python3
"""
Import one day of classic Cabinet *.log lines into Grafana Loki via the push API.

Parses the same line shape as cabinet.log.cabinet_log_query (with optional @hostname).
Each line is pushed as JSON matching Cabinet JSONL / Promtail so labels stay consistent.

Usage:
  python import_classic_log_day_to_loki.py --date 2026-05-01 \\
      --log-dir ~/.cabinet/log --loki http://127.0.0.1:3100
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone


LOG_PATTERN = re.compile(
    r"^(?P<timestamp>[^\s]+\s+[^\s]+)\s+—\s+(?P<level>\w+)"
    r"(?:\s+\[(?P<tags>[^\]]+)\])?\s+->\s+"
    r"(?P<path>[^:]+):(?P<line>\d+)(?:@(?P<hostname>\S+))?\s+->\s+"
    r"(?P<message>.+)$"
)


def _parse_local_timestamp(ts_head: str) -> datetime | None:
    ts_head = ts_head.strip().replace(",", ".", 1)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            naive = datetime.strptime(ts_head, fmt)
            local_tz = datetime.now().astimezone().tzinfo
            return naive.replace(tzinfo=local_tz).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def classic_line_to_payload(
    raw_line: str,
    *,
    job: str,
    host: str,
    filename_hint: str,
    import_batch: str,
) -> tuple[dict[str, str], str, str] | None:
    """Return (stream_labels, ts_ns, json_log_line) or None if unparsed."""
    line = raw_line.strip()
    if not line:
        return None
    m = LOG_PATTERN.match(line)
    if not m:
        utc = datetime.now(timezone.utc)
        ns = str(int(utc.timestamp() * 1_000_000_000))
        payload = {
            "timestamp": utc.isoformat().replace("+00:00", "Z"),
            "level": "info",
            "message": line,
            "tags": ["unparsed_classic"],
            "source": {"file": "unknown", "line": 0},
            "hostname": "unknown",
        }
        labels = {
            "job": job,
            "host": host,
            "level": "info",
            "hostname": "unknown",
            "filename": filename_hint,
            "cabinet_import": "classic",
            "import_batch": import_batch,
        }
        return labels, ns, json.dumps(payload, ensure_ascii=False)

    d = m.groupdict()
    utc = _parse_local_timestamp(d["timestamp"])
    if utc is None:
        return None
    ns = str(int(utc.timestamp() * 1_000_000_000))

    tags: list[str] = []
    if d.get("tags"):
        tags = [t.strip() for t in d["tags"].split(",") if t.strip()]

    lev = d["level"].lower()
    if lev == "warn":
        lev = "warning"

    hostname = (d.get("hostname") or "").strip() or "unknown"

    payload = {
        "timestamp": utc.isoformat().replace("+00:00", "Z"),
        "level": lev,
        "message": d["message"],
        "tags": tags,
        "source": {"file": d["path"], "line": int(d["line"])},
        "hostname": hostname,
    }

    labels = {
        "job": job,
        "host": host,
        "level": lev,
        "hostname": hostname,
        "filename": filename_hint,
        "cabinet_import": "classic",
        "import_batch": import_batch,
    }
    return labels, ns, json.dumps(payload, ensure_ascii=False)


def labels_key(labels: dict[str, str]) -> frozenset[tuple[str, str]]:
    return frozenset(labels.items())


def _monotonic_ns_per_stream(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Loki rejects duplicate timestamps within a stream; nudge duplicates by 1 ns."""
    out: list[tuple[str, str]] = []
    last = -1
    for ns, line in sorted(values, key=lambda x: (int(x[0]), x[1])):
        n = int(ns)
        if n <= last:
            n = last + 1
        last = n
        out.append((str(n), line))
    return out


def push_streams(
    loki_url: str,
    by_labels: dict[frozenset[tuple[str, str]], list[tuple[str, str]]],
    timeout: float,
) -> None:
    """POST one JSON body per stream. Combined /push with many streams only ingests a subset."""
    base = loki_url.rstrip("/")
    for key, vals in by_labels.items():
        labels = dict(key)
        vals_sorted = _monotonic_ns_per_stream(vals)
        body = json.dumps(
            {"streams": [{"stream": labels, "values": vals_sorted}]}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/loki/api/v1/push",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status not in (200, 204):
                    raise RuntimeError(f"Loki push HTTP {resp.status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Loki push HTTP {exc.code}: {detail}") from exc


def main() -> int:
    ap = argparse.ArgumentParser(description="Import classic Cabinet daily .log into Loki")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--log-dir", required=True, help="Cabinet path_dir_log root")
    ap.add_argument("--loki", default="http://127.0.0.1:3100", help="Loki base URL")
    ap.add_argument("--job", default="cabinet", help="Loki job label (match Promtail)")
    ap.add_argument("--host", default="cloud", help="Loki host label (match Promtail)")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument(
        "--import-batch",
        default=None,
        metavar="ID",
        help="Label import_batch (default: unix timestamp; use a new id when re-importing)",
    )
    args = ap.parse_args()

    import_batch = args.import_batch or str(int(time.time()))

    log_dir = os.path.expanduser(args.log_dir)
    day = args.date
    log_path = os.path.join(log_dir, day, f"LOG_DAILY_{day}.log")
    if not os.path.isfile(log_path):
        print(f"Not found: {log_path}", file=sys.stderr)
        return 1

    filename_hint = f"/logs/{day}/LOG_DAILY_{day}.log.import"

    by_labels: dict[frozenset[tuple[str, str]], list[tuple[str, str]]] = defaultdict(
        list
    )
    parsed = 0
    with open(log_path, encoding="utf-8") as f:
        for raw in f:
            got = classic_line_to_payload(
                raw,
                job=args.job,
                host=args.host,
                filename_hint=filename_hint,
                import_batch=import_batch,
            )
            if not got:
                continue
            labels, ns, jline = got
            by_labels[labels_key(labels)].append((ns, jline))
            parsed += 1

    if not by_labels:
        print("No lines parsed; nothing to push.", file=sys.stderr)
        return 1

    push_streams(args.loki, by_labels, args.timeout)
    print(
        f"Pushed {parsed} entries from {log_path} to {args.loki} "
        f"(import_batch={import_batch})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
