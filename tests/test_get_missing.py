"""Tests for get() missing-attribute handling and dotted CLI paths."""

from __future__ import annotations

import io
from contextlib import redirect_stderr
from unittest.mock import MagicMock

from cabinet.cabinet import Cabinet, _expand_dotted_path


def test_expand_dotted_path_splits_segments():
    assert _expand_dotted_path(["taiga.api_root"]) == ["taiga", "api_root"]
    assert _expand_dotted_path(["taiga", "api_root"]) == ["taiga", "api_root"]
    assert _expand_dotted_path(["a.b", "c"]) == ["a", "b", "c"]
    assert _expand_dotted_path(["a..b."]) == ["a", "b"]


def test_get_warn_missing_prints_stderr_without_log(tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    data_file.write_text("{}", encoding="utf-8")

    cab = Cabinet()
    cab.mongodb_enabled = False
    cab.path_file_data = str(data_file)
    cab.log = MagicMock()

    err = io.StringIO()
    with redirect_stderr(err):
        result = cab.get("github", warn_missing=True)

    assert result is None
    assert "Attribute 'github' is missing" in err.getvalue()
    cab.log.assert_not_called()


def test_get_missing_silent_by_default(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text("{}", encoding="utf-8")

    cab = Cabinet()
    cab.mongodb_enabled = False
    cab.path_file_data = str(data_file)
    cab.log = MagicMock()

    err = io.StringIO()
    with redirect_stderr(err):
        result = cab.get("github")

    assert result is None
    assert err.getvalue() == ""
    cab.log.assert_not_called()
