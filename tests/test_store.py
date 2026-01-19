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
        """Can serialize VanillaOption."""
        option = VanillaOption()
        option.Strike.set(150.0)
        option.Spot.set(155.0)
        option.Volatility.set(0.25)
        option.IsCall.set(True)

        serializer = Serializer()
        data = serializer.serialize(option)

        assert data["Strike"] == 150.0
        assert data["Spot"] == 155.0
        assert data["Volatility"] == 0.25
        assert data["IsCall"] is True

    def test_deserialize_vanilla_option(self):
        """Can deserialize VanillaOption."""
        data = {
            "Strike": 150.0,
            "Spot": 155.0,
            "Volatility": 0.25,
            "Rate": 0.05,
            "TimeToExpiry": 1.0,
            "IsCall": True,
        }

        serializer = Serializer()
        option = serializer.deserialize(VanillaOption, data)

        assert option.Strike() == 150.0
        assert option.Spot() == 155.0
        assert option.Volatility() == 0.25
        assert option.IsCall() is True

    def test_roundtrip(self):
        """Serialize then deserialize preserves values."""
        option = VanillaOption()
        option.Strike.set(100.0)
        option.Spot.set(105.0)
        option.Volatility.set(0.20)

        serializer = Serializer()
        data = serializer.serialize(option)
        loaded = serializer.deserialize(VanillaOption, data)

        assert loaded.Strike() == option.Strike()
        assert loaded.Spot() == option.Spot()
        assert loaded.Volatility() == option.Volatility()


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
        """Objects persist across connections."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Write
            with connect(f"sqlite:///{db_path}") as db:
                db.register_type("/Instruments/*", VanillaOption)
                option = VanillaOption()
                option.Strike.set(150.0)
                option.Spot.set(155.0)
                db["/Instruments/AAPL_C_150"] = option

            # Read in new connection
            with connect(f"sqlite:///{db_path}") as db:
                db.register_type("/Instruments/*", VanillaOption)
                loaded = db["/Instruments/AAPL_C_150"]
                assert loaded.Strike() == 150.0
                assert loaded.Spot() == 155.0
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
        option.Spot.set(155.0)
        option.save()

        # Verify persistence
        memory_store.clear_cache()
        loaded = memory_store["/Instruments/TEST"]
        assert loaded.Strike() == 150.0
        assert loaded.Spot() == 155.0

    def test_new_type_mismatch_raises(self, memory_store):
        """new() raises TypeMismatchError for wrong type."""
        with pytest.raises(TypeMismatchError):
            memory_store.new(Stock, "/Instruments/AAPL")  # Expects VanillaOption
