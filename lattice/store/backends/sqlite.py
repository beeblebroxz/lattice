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
        # Index for prefix queries
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_objects_path ON objects(path)
            """
        )

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
