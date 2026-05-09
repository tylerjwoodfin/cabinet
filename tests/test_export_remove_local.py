"""Local-storage behavior for export and remove."""

from __future__ import annotations

from cabinet.cabinet import Cabinet


def test_remove_local_mode_prints_and_returns(capsys):
    cab = Cabinet.__new__(Cabinet)
    cab.mongodb_enabled = False
    cab.remove("a", "b", is_print=False)
    out = capsys.readouterr().out
    assert "MongoDB" in out
    assert "remove is only supported" in out


def test_export_local_writes_data_json(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cab_dir = tmp_path / ".cabinet"
    cab_dir.mkdir()
    log_dir = tmp_path / ".local" / "share" / "cabinet" / "log"
    log_dir.mkdir(parents=True)
    (cab_dir / "data.json").write_text('{"k": "v", "n": 1}', encoding="utf-8")

    cab = Cabinet.__new__(Cabinet)
    cab.mongodb_enabled = False
    cab.path_file_data = str(cab_dir / "data.json")
    cab.path_dir_log = str(log_dir)
    cab.log = lambda *args, **kwargs: None  # noqa: ARG005

    cab.export()

    export_dir = cab_dir / "export"
    files = sorted(export_dir.glob("*"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert '"k"' in text
    assert '"v"' in text
    assert '"n"' in text
