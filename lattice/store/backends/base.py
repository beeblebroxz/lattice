"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
import time


@dataclass
class StoredObject:
    """Serialized object representation stored in the backend."""

    path: str
    type_name: str
    data: dict  # Serialized field values (JSON-compatible)
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class StorageBackend(ABC):
    """Abstract base class for storage backends.

    Backends implement the actual storage mechanism (memory, SQLite, PostgreSQL, etc.)
    while the Store class handles serialization, type registration, and the public API.
    """

    @abstractmethod
    def connect(self, **kwargs) -> None:
        """Establish connection to storage.

        Args:
            **kwargs: Backend-specific connection parameters
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection and release resources."""
        pass

    @abstractmethod
    def get(self, path: str) -> Optional[StoredObject]:
        """Retrieve object by path.

        Args:
            path: The object path (e.g., "/Instruments/AAPL_C_150")

        Returns:
            StoredObject if found, None otherwise
        """
        pass

    @abstractmethod
    def put(self, obj: StoredObject) -> None:
        """Store or update object.

        Args:
            obj: The StoredObject to persist
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete object at path.

        Args:
            path: The object path to delete

        Returns:
            True if object existed and was deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists.

        Args:
            path: The object path to check

        Returns:
            True if object exists at path
        """
        pass

    @abstractmethod
    def list(self, prefix: str, recursive: bool = False) -> Iterator[str]:
        """List paths under prefix.

        Args:
            prefix: Path prefix to list under (e.g., "/Instruments/")
            recursive: If True, list all descendants; if False, only direct children

        Yields:
            Paths matching the prefix
        """
        pass

    @abstractmethod
    def query(self, pattern: str) -> Iterator[str]:
        """Query paths matching glob pattern.

        Args:
            pattern: Glob pattern (e.g., "/Instruments/AAPL_*")

        Yields:
            Paths matching the pattern
        """
        pass

    # Transaction support (optional - default implementations do nothing)

    def begin_transaction(self) -> Any:
        """Begin a transaction.

        Returns:
            Transaction handle (backend-specific), or None if not supported
        """
        return None

    def commit_transaction(self, handle: Any) -> None:
        """Commit transaction.

        Args:
            handle: Transaction handle from begin_transaction()
        """
        pass

    def rollback_transaction(self, handle: Any) -> None:
        """Rollback transaction.

        Args:
            handle: Transaction handle from begin_transaction()
        """
        pass

    @property
    def supports_transactions(self) -> bool:
        """Whether this backend supports transactions."""
        return False
