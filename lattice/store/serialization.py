"""Serialization and type registry for lattice.store."""

import fnmatch
import json
import warnings
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

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

    Only fields marked with dag.Serialized flag are persisted.
    Use dag.Persisted (= Input | Serialized) for fields that should be
    both settable and persisted.

    Supports schema evolution:
    - Extra fields in data (removed from class): Warned and ignored
    - Missing fields in data (added to class): Use default values
    - Field migrations: Register migrators for version upgrades

    Example:
        serializer = Serializer()

        # Serialize
        data = serializer.serialize(option)
        # {'Strike': 150.0, 'Expiry': '2024-12-20', ...}

        # Deserialize
        option2 = serializer.deserialize(VanillaOption, data)

        # Register migration
        serializer.register_migration(VanillaOption, 1, 2, migrate_v1_to_v2)
    """

    def __init__(self, strict: bool = False, warn_extra_fields: bool = True):
        """Initialize the serializer.

        Args:
            strict: If True, raise on unknown fields; if False, warn and skip
            warn_extra_fields: If True, emit warnings for unknown fields
        """
        self.strict = strict
        self.warn_extra_fields = warn_extra_fields
        # Migrations: {cls: {(from_version, to_version): migrator_func}}
        self._migrations: Dict[Type, Dict[Tuple[int, int], Callable]] = {}

    def register_migration(
        self,
        cls: Type[dag.Model],
        from_version: int,
        to_version: int,
        migrator: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        """Register a migration function for schema changes.

        The migrator function receives the data dict and should return
        a modified data dict compatible with the target version.

        Args:
            cls: The Model class
            from_version: Source schema version
            to_version: Target schema version
            migrator: Function that transforms data from old to new schema

        Example:
            def migrate_v1_to_v2(data):
                if 'OldField' in data:
                    data['NewField'] = data.pop('OldField')
                return data

            serializer.register_migration(MyModel, 1, 2, migrate_v1_to_v2)
        """
        if cls not in self._migrations:
            self._migrations[cls] = {}
        self._migrations[cls][(from_version, to_version)] = migrator

    def _apply_migrations(
        self,
        cls: Type[dag.Model],
        data: Dict[str, Any],
        from_version: int,
        to_version: int,
    ) -> Dict[str, Any]:
        """Apply migrations to upgrade data from one schema version to another.

        Args:
            cls: The Model class
            data: The data dict to migrate
            from_version: Current schema version of the data
            to_version: Target schema version

        Returns:
            Migrated data dict
        """
        if from_version >= to_version:
            return data

        migrations = self._migrations.get(cls, {})
        current = from_version
        result = data.copy()

        while current < to_version:
            # Look for a direct migration or step-by-step
            migrator = migrations.get((current, to_version))
            if migrator:
                result = migrator(result)
                current = to_version
            else:
                # Try stepping through versions one at a time
                next_version = current + 1
                migrator = migrations.get((current, next_version))
                if migrator:
                    result = migrator(result)
                    current = next_version
                else:
                    # No migration path found, warn and continue
                    warnings.warn(
                        f"No migration path from schema v{current} to v{to_version} "
                        f"for {cls.__name__}. Some data may be lost or incorrect.",
                        UserWarning,
                    )
                    break

        return result

    def get_schema_version(self, cls: Type[dag.Model]) -> int:
        """Get the schema version for a Model class.

        Classes can define _schema_version_ attribute to track their schema.
        Defaults to 1 if not defined.

        Args:
            cls: The Model class

        Returns:
            Schema version integer
        """
        return getattr(cls, "_schema_version_", 1)

    def serialize(self, obj: dag.Model) -> Dict[str, Any]:
        """Serialize a Model to a dictionary.

        Extracts values from computed functions marked with the Serialized flag.
        Only fields with dag.Serialized (or dag.Persisted which includes it)
        are persisted.

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
                # Only persist fields with Serialized flag
                if descriptor.flags & Flags.Serialized:
                    accessor = getattr(obj, name)
                    value = accessor()
                    # Convert to JSON-compatible format
                    data[name] = self._to_json_compatible(value)
            return data
        except Exception as e:
            raise SerializationError(f"Failed to serialize {type(obj).__name__}: {e}")

    def deserialize(
        self,
        cls: Type[dag.Model],
        data: Dict[str, Any],
        schema_version: Optional[int] = None,
    ) -> dag.Model:
        """Deserialize a dictionary to a Model instance.

        Creates a new instance and sets all Serialized fields from the data.
        Handles schema evolution:
        - Applies migrations if schema_version < current class version
        - Warns about unknown fields (removed from class)
        - Uses default values for missing fields (added to class)

        Args:
            cls: The Model class to instantiate
            data: Dictionary of field names to values
            schema_version: Schema version of the stored data (for migrations)

        Returns:
            New Model instance with values restored

        Raises:
            SerializationError: If deserialization fails (in strict mode)
        """
        try:
            # Apply migrations if needed
            current_version = self.get_schema_version(cls)
            if schema_version is not None and schema_version < current_version:
                data = self._apply_migrations(cls, data, schema_version, current_version)

            obj = cls()

            # Track which fields in data we actually use
            used_fields = set()

            for name, value in data.items():
                descriptor = obj._computed_functions_.get(name)

                if descriptor is None:
                    # Field exists in data but not in class (removed field)
                    if self.strict:
                        raise SerializationError(
                            f"Unknown field '{name}' in {cls.__name__}. "
                            f"Field may have been removed from the class."
                        )
                    elif self.warn_extra_fields:
                        warnings.warn(
                            f"Ignoring unknown field '{name}' when loading {cls.__name__}. "
                            f"This field may have been removed from the class definition.",
                            UserWarning,
                        )
                    continue

                # Only restore fields that have Serialized flag AND can be set (Input flag)
                if descriptor.flags & Flags.Serialized:
                    if descriptor.flags & Flags.Input:
                        # Convert from JSON format and set
                        converted = self._from_json_compatible(value)
                        getattr(obj, name).set(converted)
                        used_fields.add(name)
                    else:
                        # Serialized but not Input - read-only persisted field
                        # We can't set it, so just skip (it will use its computed value)
                        warnings.warn(
                            f"Field '{name}' in {cls.__name__} is Serialized but not Input. "
                            f"Cannot restore value; using computed default.",
                            UserWarning,
                        )

            return obj
        except SerializationError:
            raise
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
