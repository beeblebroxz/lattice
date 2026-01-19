"""Path-based persistent storage for dag.Model objects.

This module provides a dict-like interface for storing and retrieving
dag.Model objects using hierarchical paths like "/Instruments/AAPL_C_150".

Quick Start:
    from lattice.store import connect
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

Supported backends:
    - memory://           In-memory storage (testing)
    - sqlite:///path.db   SQLite file storage
    - sqlite:///:memory:  SQLite in-memory

Key Classes:
    - Store: Main storage interface with dict-like access
    - connect(): Create a Store from a URL

Backend Classes:
    - MemoryBackend: In-memory storage for testing
    - SQLiteBackend: SQLite file storage

Serialization:
    - Only dag.Persisted fields are automatically serialized
    - Objects must be explicitly saved with db[path] = obj or db.save(obj)
"""

from .core import Store, connect
from .backends import StorageBackend, StoredObject, MemoryBackend, SQLiteBackend
from .serialization import Serializer, TypeRegistry
from .exceptions import (
    StoreError,
    NotFoundError,
    TypeNotRegisteredError,
    TypeMismatchError,
    SerializationError,
    TransactionError,
)

__all__ = [
    # Main API
    "Store",
    "connect",
    # Backends
    "StorageBackend",
    "StoredObject",
    "MemoryBackend",
    "SQLiteBackend",
    # Serialization
    "Serializer",
    "TypeRegistry",
    # Exceptions
    "StoreError",
    "NotFoundError",
    "TypeNotRegisteredError",
    "TypeMismatchError",
    "SerializationError",
    "TransactionError",
]
