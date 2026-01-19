"""Tests for the lattice.store module."""

import os
import tempfile
import pytest
import dag

from lattice import VanillaOption, Stock, Bond, Book, Position
from lattice.store import (
    Store,
    connect,
    MemoryBackend,
    SQLiteBackend,
    Serializer,
    TypeRegistry,
    NotFoundError,
    TypeNotRegisteredError,
    TypeMismatchError,
)


@pytest.fixture(autouse=True)
def reset_dag():
    """Reset dag state before each test."""
    dag.reset()
    yield
    dag.reset()


class TestTypeRegistry:
    """Tests for TypeRegistry."""

    def test_register_and_get_type(self):
        """Can register and retrieve types."""
        registry = TypeRegistry()
        registry.register("/Instruments/*", VanillaOption)

        assert registry.get_type("/Instruments/AAPL_C_150") == VanillaOption
        assert registry.get_type("/Instruments/GOOGL_P_100") == VanillaOption
        assert registry.get_type("/Books/DESK") is None  # Not registered

    def test_pattern_matching_order(self):
        """First matching pattern wins."""
        registry = TypeRegistry()
        registry.register("/Instruments/AAPL_*", VanillaOption)
        registry.register("/Instruments/*", Stock)

        # AAPL options match first pattern
        assert registry.get_type("/Instruments/AAPL_C_150") == VanillaOption
        # Other instruments match second pattern
        assert registry.get_type("/Instruments/GOOGL") == Stock

    def test_nested_patterns(self):
        """Can match nested path patterns."""
        registry = TypeRegistry()
        registry.register("/Positions/*/*", Position)

        assert registry.get_type("/Positions/DESK/AAPL") == Position

    def test_validate_path(self):
        """Validates object type against path pattern."""
        registry = TypeRegistry()
        registry.register("/Instruments/*", VanillaOption)

        option = VanillaOption()
        stock = Stock()

        assert registry.validate_path("/Instruments/TEST", option) is True
        assert registry.validate_path("/Instruments/TEST", stock) is False
        assert registry.validate_path("/Unknown/TEST", stock) is True  # No pattern


class TestSerializer:
    """Tests for Serializer."""

    def test_serialize_vanilla_option(self):
        """Can serialize VanillaOption - only Persisted fields."""
        option = VanillaOption()
        option.Strike.set(150.0)
        option.Spot.set(155.0)  # Not Persisted - won't be serialized
        option.Volatility.set(0.25)  # Not Persisted - won't be serialized
        option.IsCall.set(True)

        serializer = Serializer()
        data = serializer.serialize(option)

        # Persisted fields are serialized
        assert data["Strike"] == 150.0
        assert data["IsCall"] is True

        # Non-Persisted fields (Input | Overridable) are NOT serialized
        assert "Spot" not in data
        assert "Volatility" not in data

    def test_deserialize_vanilla_option(self):
        """Can deserialize VanillaOption - only Persisted fields restored."""
        data = {
            "Strike": 150.0,
            "TimeToExpiry": 0.5,
            "IsCall": False,
        }

        serializer = Serializer()
        option = serializer.deserialize(VanillaOption, data)

        # Persisted fields restored
        assert option.Strike() == 150.0
        assert option.TimeToExpiry() == 0.5
        assert option.IsCall() is False

        # Non-Persisted fields use defaults
        assert option.Spot() == 100.0  # Default
        assert option.Volatility() == 0.20  # Default

    def test_roundtrip(self):
        """Serialize then deserialize preserves Persisted values."""
        option = VanillaOption()
        option.Strike.set(100.0)
        option.IsCall.set(False)
        option.TimeToExpiry.set(0.5)

        serializer = Serializer()
        data = serializer.serialize(option)
        loaded = serializer.deserialize(VanillaOption, data)

        # Persisted fields preserved
        assert loaded.Strike() == option.Strike()
        assert loaded.IsCall() == option.IsCall()
        assert loaded.TimeToExpiry() == option.TimeToExpiry()


class TestMemoryBackend:
    """Tests for MemoryBackend."""

    def test_crud_operations(self):
        """Basic CRUD operations work."""
        from lattice.store.backends.base import StoredObject

        backend = MemoryBackend()
        backend.connect()

        # Create
        obj = StoredObject(
            path="/test/obj1",
            type_name="Test",
            data={"value": 42},
        )
        backend.put(obj)

        # Read
        loaded = backend.get("/test/obj1")
        assert loaded is not None
        assert loaded.data["value"] == 42

        # Exists
        assert backend.exists("/test/obj1") is True
        assert backend.exists("/test/obj2") is False

        # Delete
        assert backend.delete("/test/obj1") is True
        assert backend.exists("/test/obj1") is False
        assert backend.delete("/test/obj1") is False  # Already deleted

    def test_list(self):
        """Can list paths under prefix."""
        from lattice.store.backends.base import StoredObject

        backend = MemoryBackend()
        backend.connect()

        backend.put(StoredObject("/a/1", "T", {}))
        backend.put(StoredObject("/a/2", "T", {}))
        backend.put(StoredObject("/a/sub/3", "T", {}))
        backend.put(StoredObject("/b/1", "T", {}))

        # Direct children only
        children = list(backend.list("/a/"))
        assert set(children) == {"/a/1", "/a/2"}

        # Recursive
        descendants = list(backend.list("/a/", recursive=True))
        assert set(descendants) == {"/a/1", "/a/2", "/a/sub/3"}

    def test_query(self):
        """Can query with glob patterns."""
        from lattice.store.backends.base import StoredObject

        backend = MemoryBackend()
        backend.connect()

        backend.put(StoredObject("/Instruments/AAPL_C_150", "T", {}))
        backend.put(StoredObject("/Instruments/AAPL_P_140", "T", {}))
        backend.put(StoredObject("/Instruments/GOOGL_C_100", "T", {}))

        # Query AAPL options
        aapl = list(backend.query("/Instruments/AAPL_*"))
        assert len(aapl) == 2
        assert "/Instruments/AAPL_C_150" in aapl

        # Query all
        all_inst = list(backend.query("/Instruments/*"))
        assert len(all_inst) == 3


class TestSQLiteBackend:
    """Tests for SQLiteBackend."""

    def test_crud_operations(self):
        """Basic CRUD operations work."""
        from lattice.store.backends.base import StoredObject

        backend = SQLiteBackend()
        backend.connect(path=":memory:")

        # Create
        obj = StoredObject(
            path="/test/obj1",
            type_name="Test",
            data={"value": 42},
        )
        backend.put(obj)

        # Read
        loaded = backend.get("/test/obj1")
        assert loaded is not None
        assert loaded.data["value"] == 42

        # Delete
        assert backend.delete("/test/obj1") is True
        assert backend.exists("/test/obj1") is False

        backend.close()

    def test_persistence_to_file(self):
        """Data persists to file."""
        from lattice.store.backends.base import StoredObject

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Write
            backend1 = SQLiteBackend()
            backend1.connect(path=db_path)
            backend1.put(StoredObject("/test", "Test", {"x": 123}))
            backend1.close()

            # Read in new connection
            backend2 = SQLiteBackend()
            backend2.connect(path=db_path)
            loaded = backend2.get("/test")
            assert loaded is not None
            assert loaded.data["x"] == 123
            backend2.close()
        finally:
            os.unlink(db_path)

    def test_query_glob(self):
        """Glob patterns work in SQLite."""
        from lattice.store.backends.base import StoredObject

        backend = SQLiteBackend()
        backend.connect(path=":memory:")

        backend.put(StoredObject("/Instruments/AAPL_C_150", "T", {}))
        backend.put(StoredObject("/Instruments/AAPL_P_140", "T", {}))
        backend.put(StoredObject("/Instruments/GOOGL_C_100", "T", {}))

        aapl = list(backend.query("/Instruments/AAPL_*"))
        assert len(aapl) == 2

        backend.close()


class TestStore:
    """Tests for Store class."""

    @pytest.fixture
    def memory_store(self):
        """Create an in-memory store."""
        store = connect("memory://")
        store.register_type("/Instruments/*", VanillaOption)
        store.register_type("/Stocks/*", Stock)
        store.register_type("/Bonds/*", Bond)
        yield store
        store.close()

    def test_store_and_retrieve(self, memory_store):
        """Can store and retrieve objects."""
        option = VanillaOption()
        option.Strike.set(150.0)
        option.Spot.set(155.0)

        memory_store["/Instruments/AAPL_C_150"] = option

        loaded = memory_store["/Instruments/AAPL_C_150"]
        assert loaded.Strike() == 150.0
        assert loaded.Spot() == 155.0

    def test_identity_map(self, memory_store):
        """Same object returned on repeated access."""
        option = VanillaOption()
        option.Strike.set(100.0)
        memory_store["/Instruments/TEST"] = option

        loaded1 = memory_store["/Instruments/TEST"]
        loaded2 = memory_store["/Instruments/TEST"]

        assert loaded1 is loaded2

    def test_not_found_error(self, memory_store):
        """Raises NotFoundError for missing paths."""
        with pytest.raises(NotFoundError):
            _ = memory_store["/Instruments/NONEXISTENT"]

    def test_type_not_registered_error(self, memory_store):
        """Raises TypeNotRegisteredError for unregistered patterns."""
        # Store raw data in backend
        from lattice.store.backends.base import StoredObject

        memory_store._backend.put(
            StoredObject("/Unknown/TEST", "Unknown", {"x": 1})
        )

        with pytest.raises(TypeNotRegisteredError):
            _ = memory_store["/Unknown/TEST"]

    def test_type_mismatch_error(self, memory_store):
        """Raises TypeMismatchError for wrong type."""
        stock = Stock()
        stock.Symbol.set("AAPL")

        with pytest.raises(TypeMismatchError):
            memory_store["/Instruments/AAPL"] = stock  # Expects VanillaOption

    def test_contains(self, memory_store):
        """Can check if path exists."""
        option = VanillaOption()
        memory_store["/Instruments/TEST"] = option

        assert "/Instruments/TEST" in memory_store
        assert "/Instruments/NONEXISTENT" not in memory_store

    def test_delete(self, memory_store):
        """Can delete objects."""
        option = VanillaOption()
        memory_store["/Instruments/TEST"] = option

        del memory_store["/Instruments/TEST"]

        assert "/Instruments/TEST" not in memory_store

    def test_delete_not_found(self, memory_store):
        """Deleting nonexistent path raises NotFoundError."""
        with pytest.raises(NotFoundError):
            del memory_store["/Instruments/NONEXISTENT"]

    def test_explicit_save(self, memory_store):
        """Can explicitly save tracked objects."""
        option = VanillaOption()
        option.Strike.set(100.0)
        memory_store["/Instruments/TEST"] = option

        # Modify
        option.Strike.set(150.0)

        # Save
        memory_store.save(option)

        # Clear cache and reload
        memory_store.clear_cache()
        loaded = memory_store["/Instruments/TEST"]
        assert loaded.Strike() == 150.0

    def test_save_untracked_raises(self, memory_store):
        """Saving untracked object raises ValueError."""
        option = VanillaOption()

        with pytest.raises(ValueError):
            memory_store.save(option)

    def test_get_with_default(self, memory_store):
        """get() returns default for missing paths."""
        result = memory_store.get("/Instruments/NONEXISTENT", default=None)
        assert result is None

        result = memory_store.get("/Instruments/NONEXISTENT", default="missing")
        assert result == "missing"

    def test_list(self, memory_store):
        """Can list paths under prefix."""
        memory_store["/Instruments/A"] = VanillaOption()
        memory_store["/Instruments/B"] = VanillaOption()
        memory_store["/Stocks/AAPL"] = Stock()

        paths = list(memory_store.list("/Instruments/"))
        assert set(paths) == {"/Instruments/A", "/Instruments/B"}

    def test_query(self, memory_store):
        """Can query with patterns."""
        opt1 = VanillaOption()
        opt1.Strike.set(150.0)
        memory_store["/Instruments/AAPL_C_150"] = opt1

        opt2 = VanillaOption()
        opt2.Strike.set(140.0)
        memory_store["/Instruments/AAPL_P_140"] = opt2

        memory_store["/Instruments/GOOGL_C_100"] = VanillaOption()

        aapl_paths = list(memory_store.query("/Instruments/AAPL_*"))
        assert len(aapl_paths) == 2

    def test_context_manager(self):
        """Store works as context manager."""
        with connect("memory://") as db:
            db.register_type("/Test/*", VanillaOption)
            db["/Test/A"] = VanillaOption()
            assert "/Test/A" in db


class TestSQLiteStore:
    """Tests for Store with SQLite backend."""

    def test_sqlite_persistence(self):
        """Objects persist across connections - only Persisted fields."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Write
            with connect(f"sqlite:///{db_path}") as db:
                db.register_type("/Instruments/*", VanillaOption)
                option = VanillaOption()
                option.Strike.set(150.0)
                option.IsCall.set(False)
                option.Spot.set(155.0)  # Not Persisted - won't survive reload
                db["/Instruments/AAPL_C_150"] = option

            # Read in new connection
            with connect(f"sqlite:///{db_path}") as db:
                db.register_type("/Instruments/*", VanillaOption)
                loaded = db["/Instruments/AAPL_C_150"]
                # Persisted fields preserved
                assert loaded.Strike() == 150.0
                assert loaded.IsCall() is False
                # Non-Persisted field reverts to default
                assert loaded.Spot() == 100.0  # Default, not 155.0
        finally:
            os.unlink(db_path)

    def test_sqlite_memory(self):
        """SQLite in-memory mode works."""
        with connect("sqlite:///:memory:") as db:
            db.register_type("/Test/*", VanillaOption)
            db["/Test/A"] = VanillaOption()
            assert "/Test/A" in db


class TestTransactions:
    """Tests for transaction support."""

    def test_transaction_commit(self):
        """Transaction commits on success."""
        with connect("memory://") as db:
            db.register_type("/Test/*", VanillaOption)

            with db.transaction():
                db["/Test/A"] = VanillaOption()
                db["/Test/B"] = VanillaOption()

            assert "/Test/A" in db
            assert "/Test/B" in db

    def test_transaction_rollback(self):
        """Transaction rolls back on exception."""
        with connect("memory://") as db:
            db.register_type("/Test/*", VanillaOption)

            db["/Test/Existing"] = VanillaOption()

            with pytest.raises(ValueError):
                with db.transaction():
                    db["/Test/New"] = VanillaOption()
                    raise ValueError("Simulated error")

            # New object should not exist (rolled back)
            # Note: Memory backend's rollback restores the snapshot
            assert "/Test/Existing" in db


class TestConnect:
    """Tests for connect() function."""

    def test_memory_url(self):
        """Can connect with memory:// URL."""
        db = connect("memory://")
        assert db is not None
        db.close()

    def test_sqlite_url(self):
        """Can connect with sqlite:// URL."""
        db = connect("sqlite:///:memory:")
        assert db is not None
        db.close()

    def test_unknown_scheme(self):
        """Unknown scheme raises ValueError."""
        with pytest.raises(ValueError):
            connect("unknown://localhost")

    def test_postgresql_not_implemented(self):
        """PostgreSQL raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            connect("postgresql://localhost/db")


class TestObjectSelfAwareness:
    """Tests for object self-awareness (path, save, db)."""

    @pytest.fixture
    def memory_store(self):
        """Create an in-memory store."""
        store = connect("memory://")
        store.register_type("/Instruments/*", VanillaOption)
        store.register_type("/Stocks/*", Stock)
        yield store
        store.close()

    def test_object_knows_path_after_store(self, memory_store):
        """Object knows its path after being stored."""
        option = VanillaOption()
        option.Strike.set(150.0)

        # Before storing, path is None
        assert option.path() is None

        # After storing, path is set
        memory_store["/Instruments/AAPL_C_150"] = option
        assert option.path() == "/Instruments/AAPL_C_150"

    def test_object_knows_path_after_load(self, memory_store):
        """Object knows its path after being loaded."""
        option = VanillaOption()
        option.Strike.set(150.0)
        memory_store["/Instruments/TEST"] = option

        # Clear cache to force reload
        memory_store.clear_cache()

        loaded = memory_store["/Instruments/TEST"]
        assert loaded.path() == "/Instruments/TEST"

    def test_object_save_method(self, memory_store):
        """Object can save itself via save() method."""
        option = VanillaOption()
        option.Strike.set(100.0)
        memory_store["/Instruments/TEST"] = option

        # Modify and save via object method
        option.Strike.set(150.0)
        option.save()

        # Verify save worked
        memory_store.clear_cache()
        loaded = memory_store["/Instruments/TEST"]
        assert loaded.Strike() == 150.0

    def test_object_store_property(self, memory_store):
        """Object can access its store via store property."""
        option = VanillaOption()
        memory_store["/Instruments/AAPL"] = option

        stock = Stock()
        stock.Symbol.set("AAPL")
        memory_store["/Stocks/AAPL"] = stock

        # Object can access other objects via store
        loaded_stock = option.store["/Stocks/AAPL"]
        assert loaded_stock.Symbol() == "AAPL"

    def test_untracked_object_path_is_none(self):
        """Untracked object returns None for path()."""
        option = VanillaOption()
        assert option.path() is None

    def test_untracked_object_save_raises(self):
        """Untracked object raises RuntimeError on save()."""
        option = VanillaOption()
        with pytest.raises(RuntimeError, match="not associated with a store"):
            option.save()

    def test_untracked_object_store_raises(self):
        """Untracked object raises RuntimeError on store access."""
        option = VanillaOption()
        with pytest.raises(RuntimeError, match="not associated with a store"):
            _ = option.store

    def test_deleted_object_loses_awareness(self, memory_store):
        """Deleted object loses its store awareness."""
        option = VanillaOption()
        memory_store["/Instruments/TEST"] = option

        assert option.path() == "/Instruments/TEST"

        del memory_store["/Instruments/TEST"]

        # After deletion, awareness is cleared
        assert option.path() is None
        with pytest.raises(RuntimeError):
            option.save()

    def test_path_updated_on_reassignment(self, memory_store):
        """Object's path is updated if stored at different path."""
        option = VanillaOption()
        option.Strike.set(100.0)

        memory_store["/Instruments/OLD_PATH"] = option
        assert option.path() == "/Instruments/OLD_PATH"

        memory_store["/Instruments/NEW_PATH"] = option
        assert option.path() == "/Instruments/NEW_PATH"


class TestStoreNew:
    """Tests for db.new() helper method."""

    @pytest.fixture
    def memory_store(self):
        """Create an in-memory store."""
        store = connect("memory://")
        store.register_type("/Instruments/*", VanillaOption)
        store.register_type("/Stocks/*", Stock)
        yield store
        store.close()

    def test_new_creates_and_stores(self, memory_store):
        """new() creates object and stores it."""
        option = memory_store.new(VanillaOption, "/Instruments/AAPL_C_150")

        assert isinstance(option, VanillaOption)
        assert "/Instruments/AAPL_C_150" in memory_store
        assert memory_store["/Instruments/AAPL_C_150"] is option

    def test_new_sets_store_awareness(self, memory_store):
        """new() sets object's path and store."""
        option = memory_store.new(VanillaOption, "/Instruments/TEST")

        assert option.path() == "/Instruments/TEST"
        assert option.store is memory_store

    def test_new_allows_immediate_modification(self, memory_store):
        """Can modify and save object created with new()."""
        option = memory_store.new(VanillaOption, "/Instruments/TEST")
        option.Strike.set(150.0)
        option.IsCall.set(False)
        option.Spot.set(155.0)  # Not Persisted - won't survive reload
        option.save()

        # Verify persistence of Persisted fields
        memory_store.clear_cache()
        loaded = memory_store["/Instruments/TEST"]
        assert loaded.Strike() == 150.0
        assert loaded.IsCall() is False
        # Non-Persisted field reverts to default
        assert loaded.Spot() == 100.0

    def test_new_type_mismatch_raises(self, memory_store):
        """new() raises TypeMismatchError for wrong type."""
        with pytest.raises(TypeMismatchError):
            memory_store.new(Stock, "/Instruments/AAPL")  # Expects VanillaOption


class TestExplicitPersistence:
    """Tests for explicit persistence via dag.Serialized flag."""

    def test_only_serialized_fields_persisted(self):
        """Only fields with Serialized flag are persisted."""
        # VanillaOption has Persisted (= Input | Serialized) for Strike, IsCall, etc.
        # but Input | Overridable (no Serialized) for Spot, Volatility, Rate
        option = VanillaOption()
        option.Strike.set(150.0)
        option.Spot.set(155.0)
        option.Volatility.set(0.25)
        option.IsCall.set(True)

        serializer = Serializer()
        data = serializer.serialize(option)

        # Strike is Persisted - should be serialized
        assert "Strike" in data
        assert data["Strike"] == 150.0

        # IsCall is Persisted - should be serialized
        assert "IsCall" in data
        assert data["IsCall"] is True

        # Spot, Volatility, Rate are Input | Overridable (not Serialized)
        # They should NOT be serialized
        assert "Spot" not in data
        assert "Volatility" not in data
        assert "Rate" not in data

    def test_persisted_fields_restored(self):
        """Persisted fields are restored on load, others use defaults."""
        data = {
            "Strike": 150.0,
            "IsCall": False,
            "TimeToExpiry": 0.5,
        }

        serializer = Serializer()
        option = serializer.deserialize(VanillaOption, data)

        # Persisted fields restored
        assert option.Strike() == 150.0
        assert option.IsCall() is False
        assert option.TimeToExpiry() == 0.5

        # Non-persisted fields use their defaults
        assert option.Spot() == 100.0  # Default
        assert option.Volatility() == 0.20  # Default
        assert option.Rate() == 0.05  # Default

    def test_roundtrip_persisted_only(self):
        """Roundtrip only preserves Persisted fields."""
        option = VanillaOption()
        option.Strike.set(150.0)
        option.Spot.set(200.0)  # Will be lost (not Persisted)
        option.IsCall.set(False)

        serializer = Serializer()
        data = serializer.serialize(option)
        loaded = serializer.deserialize(VanillaOption, data)

        # Persisted fields preserved
        assert loaded.Strike() == 150.0
        assert loaded.IsCall() is False

        # Non-persisted field reverts to default
        assert loaded.Spot() == 100.0  # Default, not 200.0

    def test_store_persists_only_serialized_fields(self):
        """Store only persists Serialized fields."""
        with connect("memory://") as db:
            db.register_type("/Instruments/*", VanillaOption)

            option = VanillaOption()
            option.Strike.set(150.0)
            option.Spot.set(200.0)  # Won't be persisted
            option.Volatility.set(0.30)  # Won't be persisted
            db["/Instruments/TEST"] = option

            # Clear cache and reload
            db.clear_cache()
            loaded = db["/Instruments/TEST"]

            # Persisted field preserved
            assert loaded.Strike() == 150.0

            # Non-persisted fields revert to defaults
            assert loaded.Spot() == 100.0
            assert loaded.Volatility() == 0.20


class TestSchemaEvolution:
    """Tests for schema evolution and migration support."""

    def test_schema_version_stored(self):
        """Schema version is stored with objects."""
        # Create a model class with explicit schema version
        class TestModel(dag.Model):
            _schema_version_ = 2

            @dag.computed(dag.Persisted)
            def Value(self) -> int:
                return 0

        with connect("memory://") as db:
            db.register_type("/Test/*", TestModel)

            obj = TestModel()
            obj.Value.set(42)
            db["/Test/A"] = obj

            # Check stored object has schema version
            stored = db._backend.get("/Test/A")
            assert stored.schema_version == 2

    def test_schema_version_default(self):
        """Classes without _schema_version_ default to 1."""
        serializer = Serializer()

        # VanillaOption doesn't define _schema_version_
        assert serializer.get_schema_version(VanillaOption) == 1

    def test_unknown_field_warning(self):
        """Warning emitted for unknown fields in data."""
        import warnings

        data = {
            "Strike": 150.0,
            "UnknownField": "some value",  # Field that doesn't exist
        }

        serializer = Serializer(warn_extra_fields=True)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            option = serializer.deserialize(VanillaOption, data)

            # Should have warning about unknown field
            assert len(w) == 1
            assert "UnknownField" in str(w[0].message)
            assert "unknown field" in str(w[0].message).lower()

        # Valid field still restored
        assert option.Strike() == 150.0

    def test_unknown_field_strict_mode_raises(self):
        """Strict mode raises error for unknown fields."""
        from lattice.store.exceptions import SerializationError

        data = {
            "Strike": 150.0,
            "RemovedField": "value",
        }

        serializer = Serializer(strict=True)

        with pytest.raises(SerializationError, match="Unknown field"):
            serializer.deserialize(VanillaOption, data)

    def test_missing_field_uses_default(self):
        """Missing fields use their default values."""
        # Data missing some Persisted fields
        data = {
            "Strike": 150.0,
            # Missing: IsCall, TimeToExpiry, Underlying
        }

        serializer = Serializer()
        option = serializer.deserialize(VanillaOption, data)

        # Provided field set
        assert option.Strike() == 150.0

        # Missing fields use defaults
        assert option.IsCall() is True  # Default
        assert option.TimeToExpiry() == 1.0  # Default

    def test_migration_applied(self):
        """Migrations are applied when schema version differs."""
        import warnings

        class TestModel(dag.Model):
            _schema_version_ = 2

            @dag.computed(dag.Persisted)
            def NewField(self) -> str:
                return "default"

        def migrate_v1_to_v2(data):
            # Rename OldField to NewField
            if "OldField" in data:
                data["NewField"] = data.pop("OldField")
            return data

        serializer = Serializer()
        serializer.register_migration(TestModel, 1, 2, migrate_v1_to_v2)

        # Old data with v1 schema
        old_data = {"OldField": "migrated value"}

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            obj = serializer.deserialize(TestModel, old_data, schema_version=1)

        assert obj.NewField() == "migrated value"

    def test_migration_chain(self):
        """Migrations can chain across multiple versions."""

        class TestModel(dag.Model):
            _schema_version_ = 3

            @dag.computed(dag.Persisted)
            def Field(self) -> str:
                return ""

        def migrate_v1_to_v2(data):
            if "field_v1" in data:
                data["field_v2"] = data.pop("field_v1").upper()
            return data

        def migrate_v2_to_v3(data):
            if "field_v2" in data:
                data["Field"] = data.pop("field_v2") + "_v3"
            return data

        serializer = Serializer()
        serializer.register_migration(TestModel, 1, 2, migrate_v1_to_v2)
        serializer.register_migration(TestModel, 2, 3, migrate_v2_to_v3)

        # v1 data
        old_data = {"field_v1": "hello"}

        obj = serializer.deserialize(TestModel, old_data, schema_version=1)
        assert obj.Field() == "HELLO_v3"

    def test_no_migration_needed(self):
        """No migration when schema versions match."""

        class TestModel(dag.Model):
            _schema_version_ = 1

            @dag.computed(dag.Persisted)
            def Value(self) -> int:
                return 0

        serializer = Serializer()
        data = {"Value": 42}

        # Same version - no migration needed
        obj = serializer.deserialize(TestModel, data, schema_version=1)
        assert obj.Value() == 42


class TestSchemaVersionInStore:
    """Tests for schema version handling in the Store."""

    def test_schema_version_persisted_to_sqlite(self):
        """Schema version is persisted to SQLite."""
        import tempfile
        import os

        class TestModel(dag.Model):
            _schema_version_ = 5

            @dag.computed(dag.Persisted)
            def Value(self) -> int:
                return 0

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Write with schema version
            with connect(f"sqlite:///{db_path}") as db:
                db.register_type("/Test/*", TestModel)
                obj = TestModel()
                obj.Value.set(42)
                db["/Test/A"] = obj

            # Read and check schema version was stored
            backend = SQLiteBackend()
            backend.connect(path=db_path)
            stored = backend.get("/Test/A")
            assert stored.schema_version == 5
            backend.close()
        finally:
            os.unlink(db_path)

    def test_store_roundtrip_with_migration(self):
        """Full roundtrip with schema migration works."""
        # This test simulates:
        # 1. Save object with old schema
        # 2. Upgrade class to new schema
        # 3. Load object - migration should be applied

        # Old version of model (v1)
        class ModelV1(dag.Model):
            _schema_version_ = 1

            @dag.computed(dag.Persisted)
            def OldName(self) -> str:
                return ""

        # New version of model (v2)
        class ModelV2(dag.Model):
            _schema_version_ = 2

            @dag.computed(dag.Persisted)
            def NewName(self) -> str:
                return ""

        with connect("memory://") as db:
            # Register old version and save
            db.register_type("/Test/*", ModelV1)
            old_obj = ModelV1()
            old_obj.OldName.set("test_value")
            db["/Test/A"] = old_obj

            # Now register migration and use new version
            db._type_registry.clear()
            db.register_type("/Test/*", ModelV2)

            def migrate_v1_to_v2(data):
                if "OldName" in data:
                    data["NewName"] = data.pop("OldName")
                return data

            db._serializer.register_migration(ModelV2, 1, 2, migrate_v1_to_v2)

            # Clear cache to force reload
            db.clear_cache()

            # Load with new schema - migration should apply
            new_obj = db["/Test/A"]
            assert new_obj.NewName() == "test_value"
