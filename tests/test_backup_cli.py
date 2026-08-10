"""Tests for the CLI backup/validate-backup/restore commands."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from immich_dog_tagger.cli import main


@pytest.fixture
def db_state_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    monkeypatch.setenv("STATE_DIR", str(d))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("YOLO_MODEL", str(tmp_path / "yolo11n.pt"))

    db = d / "state.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'authoritative')")
    conn.commit()
    conn.close()
    return d


def test_cli_backup_creates_backup_file(db_state_dir, capsys):
    main(["backup"])
    out = capsys.readouterr().out
    assert "Backup created:" in out
    assert (db_state_dir / "backups").exists()
    backups = list((db_state_dir / "backups").glob("state-*.db"))
    assert len(backups) == 1


def test_cli_validate_backup_passes_for_valid_backup(db_state_dir, capsys):
    main(["backup"])
    backup_path = next((db_state_dir / "backups").glob("state-*.db"))
    main(["validate-backup", str(backup_path)])
    out = capsys.readouterr().out
    assert "valid" in out.lower()


def test_cli_validate_backup_fails_for_invalid_file(db_state_dir, tmp_path, capsys):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not sqlite")
    with pytest.raises(SystemExit):
        main(["validate-backup", str(bad)])
    out = capsys.readouterr().out
    assert "invalid" in out.lower()


def test_cli_restore_replaces_database_and_preserves_rollback(db_state_dir, capsys):
    main(["backup"])
    backup_path = next((db_state_dir / "backups").glob("state-*.db"))

    # Corrupt live db
    (db_state_dir / "state.db").write_bytes(b"corrupted")

    main(["restore", str(backup_path)])
    out = capsys.readouterr().out
    assert "Restored from:" in out
    assert "Rollback copy:" in out

    conn = sqlite3.connect(str(db_state_dir / "state.db"))
    row = conn.execute("SELECT val FROM test WHERE id=1").fetchone()
    conn.close()
    assert row[0] == "authoritative"


def test_cli_restore_rejects_invalid_backup(db_state_dir, tmp_path, capsys):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not sqlite")
    with pytest.raises(SystemExit):
        main(["restore", str(bad)])
    # Live db unchanged
    conn = sqlite3.connect(str(db_state_dir / "state.db"))
    row = conn.execute("SELECT val FROM test WHERE id=1").fetchone()
    conn.close()
    assert row[0] == "authoritative"
