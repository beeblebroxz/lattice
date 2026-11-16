"""SQLite storage backend."""

import fnmatch
import json
import sqlite3
from typing import Any, Iterator, Optional

from .base import StorageBackend, StoredObject


class SQLiteBackend(StorageBackend):
    """SQLite storage backend.

    Stores objects in a SQLite database file. Zero configuration required.
    Good for development and single-user production scenarios.

    Example:
        backend = SQLiteBackend()
        backend.connect(path="trading.db")

        # Or in-memory
        backend.connect(path=":memory:")
    """

    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
        self._path: Optional[str] = None

    def connect(self, path: str = ":memory:", **kwargs) -> None:
        """Connect to SQLite database.

        Args:
            path: Database file path, or ":memory:" for in-memory database
        """
        self._path = path
        # isolation_level=None puts the connection in autocommit mode: each
        # statement commits on its own unless we have issued BEGIN ourselves.
        # That keeps transaction boundaries explicit (see begin_transaction),
        # so writes inside a transaction really can be rolled back.
        self._conn = sqlite3.connect(
            path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        if path != ":memory:":
            # Write-ahead logging: a commit appends to the log and syncs once,
            # instead of writing and syncing a rollback journal as well. That
            # makes each save several times cheaper with the same durability
            # (synchronous stays at its default, FULL). SQLite keeps "-wal"
            # and "-shm" files beside the database while it is open.
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the objects table if it doesn't exist."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                path TEXT PRIMARY KEY,
                type_name TEXT NOT NULL,
                data TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        # Migrate existing tables to add schema_version if needed
        self._migrate_schema()
        # Older databases carry a separate index on path. The primary key
        # already indexes it, so the extra one only doubled index writes.
        self._conn.execute("DROP INDEX IF EXISTS idx_objects_path")

    def _migrate_schema(self) -> None:
        """Add schema_version column to existing databases if missing."""
        cursor = self._conn.execute("PRAGMA table_info(objects)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "schema_version" not in columns:
            self._conn.execute(
                "ALTER TABLE objects ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1"
            )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get(self, path: str) -> Optional[StoredObject]:
        """Retrieve object by path."""
        cursor = self._conn.execute(
            "SELECT * FROM objects WHERE path = ?", (path,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        return StoredObject(
            path=row["path"],
            type_name=row["type_name"],
            data=json.loads(row["data"]),
            version=row["version"],
            schema_version=row["schema_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def put(self, obj: StoredObject) -> None:
        """Store or update object."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO objects
                (path, type_name, data, version, schema_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obj.path,
                obj.type_name,
                json.dumps(obj.data),
                obj.version,
                obj.schema_version,
                obj.created_at,
                obj.updated_at,
            ),
        )

    def upsert(
        self,
        path: str,
        type_name: str,
        data: Any,
        schema_version: int,
        now: float,
    ) -> None:
        """Create or replace the object at path in a single statement.

        The version bump happens inside SQLite, so a save does not need to
        read the existing row first.
        """
        if sqlite3.sqlite_version_info < (3, 24):
            # No ON CONFLICT ... DO UPDATE before SQLite 3.24: read then write.
            super().upsert(path, type_name, data, schema_version, now)
            return
        self._conn.execute(
            """
            INSERT INTO objects
                (path, type_name, data, version, schema_version, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                type_name = excluded.type_name,
                data = excluded.data,
                version = objects.version + 1,
                schema_version = excluded.schema_version,
                updated_at = excluded.updated_at
            """,
            (path, type_name, json.dumps(data), schema_version, now, now),
        )

    def delete(self, path: str) -> bool:
        """Delete object at path."""
        cursor = self._conn.execute(
            "DELETE FROM objects WHERE path = ?", (path,)
        )
        return cursor.rowcount > 0

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        cursor = self._conn.execute(
            "SELECT 1 FROM objects WHERE path = ?", (path,)
        )
        return cursor.fetchone() is not None

    def list(self, prefix: str, recursive: bool = False) -> Iterator[str]:
        """List paths under prefix."""
        # Normalize prefix
        if not prefix.endswith("/"):
            prefix = prefix + "/"

        # Range scan on the primary key: every path starting with "prefix/"
        # sorts between "prefix/" and "prefix0" ("0" is the character after
        # "/"). Unlike LIKE, this is exact: "_" and "%" in a path are literal
        # and the match is case-sensitive.
        upper = prefix[:-1] + chr(ord("/") + 1)
        cursor = self._conn.execute(
            "SELECT path FROM objects WHERE path >= ? AND path < ? ORDER BY path",
            (prefix, upper),
        )

        for row in cursor:
            path = row["path"]
            suffix = path[len(prefix) :]

            if recursive:
                yield path
            else:
                # Only yield direct children (no more slashes in suffix)
                if "/" not in suffix:
                    yield path

    def query(self, pattern: str) -> Iterator[str]:
        """Query paths matching glob pattern.

        Note: SQLite GLOB is case-sensitive and uses * and ? wildcards,
        matching fnmatch behavior.
        """
        # fnmatch's * and ? map directly to GLOB. Character-class negation
        # differs: fnmatch writes [!abc], GLOB writes [^abc].
        cursor = self._conn.execute(
            "SELECT path FROM objects WHERE path GLOB ? ORDER BY path",
            (pattern.replace("[!", "[^"),),
        )

        for row in cursor:
            yield row["path"]

    # Transaction support

    def begin_transaction(self) -> Any:
        """Begin a transaction."""
        self._conn.execute("BEGIN")
        return True

    def commit_transaction(self, handle: Any) -> None:
        """Commit transaction."""
        self._conn.execute("COMMIT")

    def rollback_transaction(self, handle: Any) -> None:
        """Rollback transaction."""
        self._conn.execute("ROLLBACK")

    @property
    def supports_transactions(self) -> bool:
        """SQLite supports transactions."""
        return True
