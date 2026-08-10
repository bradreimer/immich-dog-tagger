"""SQLite-aware backup service for state.db."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class BackupResult:
    path: Path
    created_at: datetime
    size_bytes: int


class BackupError(Exception):
    pass


class BackupService:
    def __init__(self, state_dir: Path) -> None:
        self.db_path = state_dir / "state.db"
        self.backup_dir = state_dir / "backups"

    def create_backup(self) -> BackupResult:
        if not self.db_path.exists():
            raise BackupError(f"Source database not found: {self.db_path}")

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = self.backup_dir / f"state-{ts}.db"

        if dest.exists():
            raise BackupError(f"Backup already exists: {dest}")

        try:
            src = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            dst = sqlite3.connect(str(dest))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        except sqlite3.Error as exc:
            dest.unlink(missing_ok=True)
            raise BackupError(f"Backup failed: {exc}") from exc

        created_at = datetime.now(UTC)
        return BackupResult(
            path=dest, created_at=created_at, size_bytes=dest.stat().st_size
        )

    def validate_backup(self, path: Path) -> None:
        """Raise BackupError if the file is not a valid, readable SQLite database."""
        if not path.exists():
            raise BackupError(f"Backup file not found: {path}")
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result[0] != "ok":
                    raise BackupError(f"Integrity check failed: {result[0]}")
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise BackupError(f"Cannot open backup as SQLite: {exc}") from exc

    def list_backups(self) -> list[BackupResult]:
        if not self.backup_dir.exists():
            return []
        results = []
        for p in sorted(self.backup_dir.glob("state-*.db")):
            stat = p.stat()
            results.append(
                BackupResult(
                    path=p,
                    created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    size_bytes=stat.st_size,
                )
            )
        return results

    def restore_backup(
        self, backup_path: Path, *, allow_overwrite: bool = False
    ) -> Path:
        """Replace state.db with backup_path. Returns the rollback copy path."""
        self.validate_backup(backup_path)

        rollback: Path | None = None
        if self.db_path.exists():
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            rollback = self.backup_dir / f"rollback-{ts}.db"
            if rollback.exists() and not allow_overwrite:
                raise BackupError(f"Rollback path already exists: {rollback}")
            self.db_path.rename(rollback)

        try:
            src = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
            dst = sqlite3.connect(str(self.db_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        except sqlite3.Error as exc:
            # Roll forward: put the original back
            if rollback and rollback.exists():
                rollback.rename(self.db_path)
            raise BackupError(f"Restore failed: {exc}") from exc

        return rollback or self.db_path
