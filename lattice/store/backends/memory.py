"""In-memory storage backend for testing."""

import fnmatch
from typing import Any, Dict, Iterator, Optional

from .base import StorageBackend, StoredObject


class MemoryBackend(StorageBackend):
    """In-memory storage backend.

    Useful for testing and temporary storage. Data is lost when the
    backend is closed or the process ends.

    Example:
        backend = MemoryBackend()
        backend.connect()

        backend.put(StoredObject(path="/test", type_name="Test", data={"x": 1}))
        obj = backend.get("/test")
    """

    def __init__(self):
        self._data: Dict[str, StoredObject] = {}
        self._connected = False

    def connect(self, **kwargs) -> None:
        """Initialize the in-memory store."""
        self._data = {}
        self._connected = True

    def close(self) -> None:
        """Clear the in-memory store."""
        self._data.clear()
        self._connected = False

    def get(self, path: str) -> Optional[StoredObject]:
        """Retrieve object by path."""
        return self._data.get(path)

    def put(self, obj: StoredObject) -> None:
        """Store or update object."""
        self._data[obj.path] = obj

    def delete(self, path: str) -> bool:
        """Delete object at path."""
        if path in self._data:
            del self._data[path]
            return True
        return False

    def exists(self, path: str) -> bool:
        """Check if path exists."""
        return path in self._data

    def list(self, prefix: str, recursive: bool = False) -> Iterator[str]:
        """List paths under prefix."""
        # Normalize prefix to end with /
        if not prefix.endswith("/"):
            prefix = prefix + "/"

        for path in sorted(self._data.keys()):
            if not path.startswith(prefix):
                continue

            # Get the part after the prefix
            suffix = path[len(prefix) :]

            if recursive:
                yield path
            else:
                # Only yield direct children (no more slashes in suffix)
                if "/" not in suffix:
                    yield path

    def query(self, pattern: str) -> Iterator[str]:
        """Query paths matching glob pattern."""
        for path in sorted(self._data.keys()):
            if fnmatch.fnmatch(path, pattern):
                yield path

    # Transaction support - memory backend uses simple copy-on-write

    def begin_transaction(self) -> Any:
        """Begin a transaction by snapshotting current state."""
        return dict(self._data)  # Shallow copy of the dict

    def commit_transaction(self, handle: Any) -> None:
        """Commit transaction (nothing to do - changes already in place)."""
        pass

    def rollback_transaction(self, handle: Any) -> None:
        """Rollback transaction by restoring snapshot."""
        if handle is not None:
            self._data = handle

    @property
    def supports_transactions(self) -> bool:
        """Memory backend supports basic transactions."""
        return True
