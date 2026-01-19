"""Serialization and type registry for lattice.store."""

import fnmatch
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type

import dag
from dag.flags import Flags

from .exceptions import SerializationError, TypeNotRegisteredError


class TypeRegistry:
    """Maps path patterns to Model types.

    Allows the store to know which class to instantiate when loading
    objects from a given path.

    Example:
        registry = TypeRegistry()
        registry.register("/Instruments/*", VanillaOption)
        registry.register("/Books/*", Book)

        cls = registry.get_type("/Instruments/AAPL_C_150")  # VanillaOption
    """

    def __init__(self):
        self._patterns: List[Tuple[str, Type[dag.Model]]] = []
        self._type_to_pattern: Dict[Type[dag.Model], str] = {}

    def register(self, pattern: str, cls: Type[dag.Model]) -> None:
        """Register a path pattern for a Model type.

        Args:
            pattern: Path pattern with wildcards (e.g., "/Instruments/*")
            cls: The Model class to instantiate for matching paths

        Patterns are matched in registration order (first match wins).
        """
        self._patterns.append((pattern, cls))
        self._type_to_pattern[cls] = pattern

    def get_type(self, path: str) -> Optional[Type[dag.Model]]:
        """Get the Model type for a path.

        Args:
            path: Object path (e.g., "/Instruments/AAPL_C_150")

        Returns:
            The registered Model class, or None if no pattern matches
        """
        for pattern, cls in self._patterns:
            if fnmatch.fnmatch(path, pattern):
                return cls
        return None

    def get_pattern(self, cls: Type[dag.Model]) -> Optional[str]:
        """Get the registered pattern for a Model type.

        Args:
            cls: The Model class

        Returns:
            The pattern string, or None if not registered
        """
        return self._type_to_pattern.get(cls)

    def validate_path(self, path: str, obj: dag.Model) -> bool:
        """Validate that an object matches its path pattern.

        Args:
            path: Object path
            obj: The Model instance

        Returns:
            True if no pattern registered or object matches expected type
        """
        expected_type = self.get_type(path)
        return expected_type is None or isinstance(obj, expected_type)

    def clear(self) -> None:
        """Remove all registered patterns."""
        self._patterns.clear()
        self._type_to_pattern.clear()


class Serializer:
    """Serialize and deserialize dag.Model instances.

    Only fields marked with dag.Persisted (or dag.Serialized) are persisted.
    Computed values are recalculated on load.

    Example:
        serializer = Serializer()

        # Serialize
        data = serializer.serialize(option)
        # {'Strike': 150.0, 'Spot': 105.0, 'Volatility': 0.2, ...}

        # Deserialize
        option2 = serializer.deserialize(VanillaOption, data)
    """

    def serialize(self, obj: dag.Model) -> Dict[str, Any]:
        """Serialize a Model to a dictionary.

        Extracts values from computed functions marked with the Input flag
        (which includes Persisted = Input | Serialized). All Input fields
        represent settable state that should be persisted.

        Args:
            obj: The Model instance to serialize

        Returns:
            Dictionary of field names to values

        Raises:
            SerializationError: If serialization fails
        """
        try:
            data = {}
            for name, descriptor in obj._computed_functions_.items():
                # Persist all Input fields (they represent settable state)
                if descriptor.flags & Flags.Input:
                    accessor = getattr(obj, name)
                    value = accessor()
                    # Convert to JSON-compatible format
                    data[name] = self._to_json_compatible(value)
            return data
        except Exception as e:
            raise SerializationError(f"Failed to serialize {type(obj).__name__}: {e}")

    def deserialize(self, cls: Type[dag.Model], data: Dict[str, Any]) -> dag.Model:
        """Deserialize a dictionary to a Model instance.

        Creates a new instance and sets all Input fields from the data.

        Args:
            cls: The Model class to instantiate
            data: Dictionary of field names to values

        Returns:
            New Model instance with values restored

        Raises:
            SerializationError: If deserialization fails
        """
        try:
            obj = cls()
            for name, value in data.items():
                descriptor = obj._computed_functions_.get(name)
                if descriptor and descriptor.flags & Flags.Input:
                    # Convert from JSON format
                    converted = self._from_json_compatible(value)
                    getattr(obj, name).set(converted)
            return obj
        except Exception as e:
            raise SerializationError(f"Failed to deserialize {cls.__name__}: {e}")

    def _to_json_compatible(self, value: Any) -> Any:
        """Convert a value to JSON-compatible format."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return {"__datetime__": value.isoformat()}
        if isinstance(value, (list, tuple)):
            return [self._to_json_compatible(v) for v in value]
        if isinstance(value, dict):
            return {k: self._to_json_compatible(v) for k, v in value.items()}
        # For dag.Model references, we'd need to store as path
        # For now, raise an error for unsupported types
        if isinstance(value, dag.Model):
            raise SerializationError(
                f"Cannot serialize Model reference directly. "
                f"Store the path/ID instead."
            )
        # Try to convert to dict if it has __dict__
        if hasattr(value, "__dict__"):
            return {
                "__type__": type(value).__name__,
                "__data__": self._to_json_compatible(vars(value)),
            }
        raise SerializationError(f"Cannot serialize type: {type(value)}")

    def _from_json_compatible(self, value: Any) -> Any:
        """Convert a value from JSON-compatible format."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._from_json_compatible(v) for v in value]
        if isinstance(value, dict):
            # Check for special markers
            if "__datetime__" in value:
                return datetime.fromisoformat(value["__datetime__"])
            if "__type__" in value and "__data__" in value:
                # Custom object - for now just return the data dict
                return self._from_json_compatible(value["__data__"])
            return {k: self._from_json_compatible(v) for k, v in value.items()}
        return value

    def to_json(self, obj: dag.Model) -> str:
        """Serialize a Model to a JSON string.

        Args:
            obj: The Model instance to serialize

        Returns:
            JSON string
        """
        data = self.serialize(obj)
        return json.dumps(data, indent=2)

    def from_json(self, cls: Type[dag.Model], json_str: str) -> dag.Model:
        """Deserialize a JSON string to a Model instance.

        Args:
            cls: The Model class to instantiate
            json_str: JSON string

        Returns:
            New Model instance
        """
        data = json.loads(json_str)
        return self.deserialize(cls, data)
