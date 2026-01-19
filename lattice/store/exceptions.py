"""Exceptions for the lattice.store module."""


class StoreError(Exception):
    """Base exception for all store errors."""

    pass


class ConnectionError(StoreError):
    """Failed to connect to storage backend."""

    pass


class NotFoundError(StoreError, KeyError):
    """Object not found at the specified path."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"No object at path: {path}")


class TypeNotRegisteredError(StoreError, TypeError):
    """No type registered for the given path pattern."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"No type registered for path: {path}")


class TypeMismatchError(StoreError, TypeError):
    """Object type doesn't match the registered type for the path."""

    def __init__(self, path: str, expected: type, actual: type):
        self.path = path
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Path {path} expects {expected.__name__}, got {actual.__name__}"
        )


class SerializationError(StoreError):
    """Failed to serialize or deserialize an object."""

    pass


class TransactionError(StoreError):
    """Transaction-related error."""

    pass
