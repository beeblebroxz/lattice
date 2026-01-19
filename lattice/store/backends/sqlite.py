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
        self._conn = sqlite3.connect(path, check_same_thread=False)
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
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        # Index for prefix queries
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_objects_path ON objects(path)
            """
        )
        self._conn.commit()

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
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def put(self, obj: StoredObject) -> None:
        """Store or update object."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO objects
                (path, type_name, data, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                obj.path,
                obj.type_name,
                json.dumps(obj.data),
                obj.version,
                obj.created_at,
                obj.updated_at,
            ),
        )
        self._conn.commit()

    def delete(self, path: str) -> bool:
        """Delete object at path."""
        cursor = self._conn.execute(
            "DELETE FROM objects WHERE path = ?", (path,)
        )
        self._conn.commit()
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

        # Use LIKE for prefix matching
        cursor = self._conn.execute(
            "SELECT path FROM objects WHERE path LIKE ? ORDER BY path",
            (prefix + "%",),
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
        # Convert fnmatch pattern to SQL GLOB pattern
        # fnmatch uses * and ? which map directly to GLOB
        cursor = self._conn.execute(
            "SELECT path FROM objects WHERE path GLOB ? ORDER BY path",
            (pattern,),
        )

        for row in cursor:
            yield row["path"]

    # Transaction support

    def begin_transaction(self) -> Any:
        """Begin a transaction."""
        self._conn.execute("BEGIN TRANSACTION")
        return True

    def commit_transaction(self, handle: Any) -> None:
        """Commit transaction."""
        self._conn.commit()

    def rollback_transaction(self, handle: Any) -> None:
        """Rollback transaction."""
        self._conn.rollback()

    @property
    def supports_transactions(self) -> bool:
        """SQLite supports transactions."""
        return True
