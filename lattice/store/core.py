"""Core Store class for path-based object persistence."""

from contextlib import contextmanager
import time
import weakref
from typing import Any, Dict, Iterator, Optional, Type, Union
from urllib.parse import urlparse

import dag

from .backends.base import StorageBackend, StoredObject
from .backends.memory import MemoryBackend
from .serialization import Serializer, TypeRegistry
from .exceptions import (
    NotFoundError,
    TypeNotRegisteredError,
    TypeMismatchError,
    TransactionError,
)


class Store:
    """Path-based persistent storage for dag.Model objects.

    Provides a dict-like interface for storing and retrieving objects
    using hierarchical paths like "/Instruments/AAPL_C_150".

    Example:
        from lattice.store import Store, connect
        from lattice import VanillaOption

        # Connect to storage
        db = connect("sqlite:///trading.db")

        # Register types
        db.register_type("/Instruments/*", VanillaOption)

        # Store objects
        option = VanillaOption()
        option.Strike.set(150.0)
        db["/Instruments/AAPL_C_150"] = option

        # Retrieve objects
        loaded = db["/Instruments/AAPL_C_150"]
        print(loaded.Strike())  # 150.0

        # Query
        for path in db.query("/Instruments/*"):
            print(path)
    """

    def __init__(self, backend: StorageBackend):
        """Create a Store with the given backend.

        Use connect() for convenient URL-based connection.

        Args:
            backend: Storage backend instance
        """
        self._backend = backend
        self._type_registry = TypeRegistry()
        self._serializer = Serializer()
        self._identity_map: Dict[str, dag.Model] = {}  # path -> loaded object
        self._object_paths: Dict[int, str] = {}  # id(obj) -> path
        self._in_transaction = False
        self._tx_handle = None

    # Type registration

    def register_type(self, pattern: str, cls: Type[dag.Model]) -> None:
        """Register a path pattern for a Model type.

        Args:
            pattern: Path pattern with wildcards (e.g., "/Instruments/*")
            cls: The Model class for objects at matching paths

        Example:
            db.register_type("/Instruments/*", VanillaOption)
            db.register_type("/Books/*", Book)
            db.register_type("/Positions/*/*", Position)
        """
        self._type_registry.register(pattern, cls)

    # Dict-like interface

    def __getitem__(self, path: str) -> dag.Model:
        """Retrieve object by path.

        Args:
            path: Object path (e.g., "/Instruments/AAPL_C_150")

        Returns:
            The Model instance

        Raises:
            NotFoundError: If no object exists at path
            TypeNotRegisteredError: If no type registered for path pattern
        """
        # Check identity map first (already loaded)
        if path in self._identity_map:
            return self._identity_map[path]

        # Load from backend
        stored = self._backend.get(path)
        if stored is None:
            raise NotFoundError(path)

        # Get the type
        cls = self._type_registry.get_type(path)
        if cls is None:
            raise TypeNotRegisteredError(path)

        # Deserialize (pass schema_version for migration support)
        obj = self._serializer.deserialize(cls, stored.data, stored.schema_version)

        # Set object's store awareness
        obj._store_ref = weakref.ref(self)
        obj._store_path = path

        # Register in identity map
        self._identity_map[path] = obj
        self._object_paths[id(obj)] = path

        return obj

    def __setitem__(self, path: str, obj: dag.Model) -> None:
        """Store object at path.

        Args:
            path: Object path (e.g., "/Instruments/AAPL_C_150")
            obj: The Model instance to store

        Raises:
            TypeMismatchError: If object type doesn't match registered pattern
        """
        # Validate type
        if not self._type_registry.validate_path(path, obj):
            expected = self._type_registry.get_type(path)
            raise TypeMismatchError(path, expected, type(obj))

        # Serialize
        data = self._serializer.serialize(obj)

        # Get schema version from class
        schema_version = self._serializer.get_schema_version(type(obj))

        # Create stored object
        now = time.time()
        existing = self._backend.get(path)

        stored = StoredObject(
            path=path,
            type_name=type(obj).__name__,
            data=data,
            version=existing.version + 1 if existing else 1,
            schema_version=schema_version,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )

        # Store
        self._backend.put(stored)

        # Set object's store awareness
        obj._store_ref = weakref.ref(self)
        obj._store_path = path

        # Update identity map
        self._identity_map[path] = obj
        self._object_paths[id(obj)] = path

    def __delitem__(self, path: str) -> None:
        """Delete object at path.

        Args:
            path: Object path to delete

        Raises:
            NotFoundError: If no object exists at path
        """
        if not self._backend.delete(path):
            raise NotFoundError(path)

        # Remove from identity map and clear object's store awareness
        if path in self._identity_map:
            obj = self._identity_map.pop(path)
            self._object_paths.pop(id(obj), None)
            # Clear object's store awareness
            obj._store_ref = None
            obj._store_path = None

    def __contains__(self, path: str) -> bool:
        """Check if object exists at path.

        Args:
            path: Object path to check

        Returns:
            True if object exists
        """
        return self._backend.exists(path)

    # Explicit save

    def save(self, obj: dag.Model) -> None:
        """Explicitly save an object that was previously stored.

        The object must have been retrieved from or stored in this Store
        so we know its path.

        Args:
            obj: The Model instance to save

        Raises:
            ValueError: If object is not tracked by this store
        """
        path = self._object_paths.get(id(obj))
        if path is None:
            raise ValueError(
                "Object is not tracked by this store. "
                "Use db[path] = obj to store it first."
            )
        self[path] = obj

    def get_path(self, obj: dag.Model) -> Optional[str]:
        """Get the path for a tracked object.

        Args:
            obj: The Model instance

        Returns:
            Path if tracked, None otherwise
        """
        return self._object_paths.get(id(obj))

    def new(self, cls: Type[dag.Model], path: str) -> dag.Model:
        """Create a new object and store it at the given path.

        Convenience method that combines object creation and storage.

        Args:
            cls: The Model class to instantiate
            path: Path to store the object at

        Returns:
            The newly created and stored Model instance

        Raises:
            TypeMismatchError: If cls doesn't match the registered pattern

        Example:
            option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
            option.Strike.set(150.0)
            option.save()
        """
        obj = cls()
        self[path] = obj
        return obj

    # Query operations

    def list(self, prefix: str, recursive: bool = False) -> Iterator[str]:
        """List paths under a prefix.

        Args:
            prefix: Path prefix (e.g., "/Instruments/")
            recursive: If True, list all descendants

        Yields:
            Paths under the prefix
        """
        return self._backend.list(prefix, recursive=recursive)

    def query(self, pattern: str) -> Iterator[str]:
        """Query paths matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "/Instruments/AAPL_*")

        Yields:
            Matching paths
        """
        return self._backend.query(pattern)

    def get(self, path: str, default: Any = None) -> Optional[dag.Model]:
        """Get object at path, or default if not found.

        Args:
            path: Object path
            default: Value to return if not found

        Returns:
            Object or default
        """
        try:
            return self[path]
        except NotFoundError:
            return default

    # Transaction support

    @contextmanager
    def transaction(self):
        """Context manager for atomic transactions.

        Changes within the transaction are committed on successful exit,
        or rolled back on exception.

        Example:
            with db.transaction():
                db["/Books/NEW"] = book
                db["/Positions/NEW/AAPL"] = position
                # Both committed atomically
        """
        if self._in_transaction:
            # Nested transaction - just yield (changes go to outer tx)
            yield
            return

        if not self._backend.supports_transactions:
            # Backend doesn't support transactions, just execute
            yield
            return

        self._in_transaction = True
        self._tx_handle = self._backend.begin_transaction()
        try:
            yield
            self._backend.commit_transaction(self._tx_handle)
        except Exception:
            self._backend.rollback_transaction(self._tx_handle)
            # Clear identity map on rollback (objects may be stale)
            self._identity_map.clear()
            self._object_paths.clear()
            raise
        finally:
            self._in_transaction = False
            self._tx_handle = None

    # Lifecycle

    def close(self) -> None:
        """Close the store and release resources."""
        self._backend.close()
        self._identity_map.clear()
        self._object_paths.clear()

    def __enter__(self) -> "Store":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    # Utility

    def clear_cache(self) -> None:
        """Clear the identity map cache.

        Useful if you want to force reload from storage.
        Note: This does not clear objects' store awareness - they retain
        their path and can still call save().
        """
        self._identity_map.clear()
        self._object_paths.clear()


def connect(url: str) -> Store:
    """Connect to a store using a URL.

    Supported URL schemes:
        - memory://          In-memory storage (testing)
        - sqlite:///path.db  SQLite file storage
        - sqlite:///:memory: SQLite in-memory
        - postgresql://...   PostgreSQL (future)
        - etcd://...         etcd (future)

    Args:
        url: Connection URL

    Returns:
        Connected Store instance

    Example:
        db = connect("sqlite:///trading.db")
        db = connect("memory://")
    """
    parsed = urlparse(url)
    scheme = parsed.scheme

    if scheme == "memory":
        backend = MemoryBackend()
        backend.connect()
        return Store(backend)

    elif scheme == "sqlite":
        from .backends.sqlite import SQLiteBackend

        # Handle sqlite:///path and sqlite:///:memory:
        path = parsed.path
        if path.startswith("/"):
            path = path[1:]  # Remove leading slash from file path

        backend = SQLiteBackend()
        backend.connect(path=path if path else ":memory:")
        return Store(backend)

    elif scheme == "postgresql" or scheme == "postgres":
        raise NotImplementedError("PostgreSQL backend not yet implemented")

    elif scheme == "etcd":
        raise NotImplementedError("etcd backend not yet implemented")

    else:
        raise ValueError(f"Unknown storage scheme: {scheme}")
