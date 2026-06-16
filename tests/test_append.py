"""Tests for append (local JSON storage)."""

from __future__ import annotations

import json

from cabinet.cabinet import Cabinet


def _local_cab(tmp_path, data: dict) -> Cabinet:
    cab_dir = tmp_path / ".cabinet"
    cab_dir.mkdir()
    log_dir = tmp_path / ".local" / "share" / "cabinet" / "log"
    log_dir.mkdir(parents=True)
    data_file = cab_dir / "data.json"
    data_file.write_text(json.dumps(data), encoding="utf-8")

    cab = Cabinet.__new__(Cabinet)
    cab.mongodb_enabled = False
    cab.path_file_data = str(data_file)
    cab.path_dir_log = str(log_dir)
    cab.log = lambda *args, **kwargs: None  # noqa: ARG005
    cab.cached_data = []
    cab.update_cache = lambda: None  # noqa: ARG005
    return cab


def test_append_to_list_persists(tmp_path):
    cab = _local_cab(tmp_path, {"holidays": []})

    result = cab.append("holidays", "2026-06-19", is_print=False)

    assert result == ["2026-06-19"]
    assert cab.get("holidays") == ["2026-06-19"]

    cab.append("holidays", "2026-07-03", is_print=False)
    assert cab.get("holidays") == ["2026-06-19", "2026-07-03"]


def test_append_to_string_persists(tmp_path):
    cab = _local_cab(tmp_path, {"greeting": "hello"})

    cab.append("greeting", " world", is_print=False)

    assert cab.get("greeting") == "hello world"
