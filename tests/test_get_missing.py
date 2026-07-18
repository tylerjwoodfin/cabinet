"""Tests for get() missing-attribute handling and dotted CLI paths."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr
from unittest.mock import MagicMock

from cabinet.cabinet import Cabinet, _expand_dotted_path


def _local_cab(tmp_path, data: dict) -> Cabinet:
    """Build a Cabinet without reading ~/.config (CI has no interactive config)."""
    cab_dir = tmp_path / ".cabinet"
    cab_dir.mkdir()
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    data_file = cab_dir / "data.json"
    data_file.write_text(json.dumps(data), encoding="utf-8")

    cab = Cabinet.__new__(Cabinet)
    cab.mongodb_enabled = False
    cab.path_file_data = str(data_file)
    cab.path_dir_log = str(log_dir)
    cab.cached_data = []
    cab.update_cache = lambda: None  # noqa: ARG005
    return cab


def test_expand_dotted_path_splits_segments():
    assert _expand_dotted_path(["taiga.api_root"]) == ["taiga", "api_root"]
    assert _expand_dotted_path(["taiga", "api_root"]) == ["taiga", "api_root"]
    assert _expand_dotted_path(["a.b", "c"]) == ["a", "b", "c"]
    assert _expand_dotted_path(["a..b."]) == ["a", "b"]


def test_get_warn_missing_prints_stderr_without_log(tmp_path):
    cab = _local_cab(tmp_path, {})
    cab.log = MagicMock()

    err = io.StringIO()
    with redirect_stderr(err):
        result = cab.get("github", warn_missing=True)

    assert result is None
    assert "Attribute 'github' is missing" in err.getvalue()
    cab.log.assert_not_called()


def test_get_missing_silent_by_default(tmp_path):
    cab = _local_cab(tmp_path, {})
    cab.log = MagicMock()

    err = io.StringIO()
    with redirect_stderr(err):
        result = cab.get("github")

    assert result is None
    assert err.getvalue() == ""
    cab.log.assert_not_called()
