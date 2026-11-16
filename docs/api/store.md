# Store API Reference

Path-based persistent storage for `dag.Model` objects.

## Quick Start

```python
from lattice.store import connect
from lattice import VanillaOption

db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

# Create and store
option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.save()

# Retrieve
loaded = db["/Instruments/AAPL_C_150"]
print(loaded.Strike())  # 150.0
```

## Connection

### `connect(url)`

Connect to a store using a URL.

```python
from lattice.store import connect

# SQLite file storage
db = connect("sqlite:///trading.db")

# SQLite in-memory
db = connect("sqlite:///:memory:")

# In-memory (testing)
db = connect("memory://")
```

**Parameters:**
- `url` - Connection URL string

**Returns:** `Store` instance

**Supported Schemes:**
| Scheme | Description |
|--------|-------------|
| `memory://` | In-memory storage (for testing) |
| `sqlite:///path.db` | SQLite file storage (write-ahead logging; `path.db-wal` and `path.db-shm` sit beside the file while it is open) |
| `sqlite:///:memory:` | SQLite in-memory |

## Store Class

### Type Registration

#### `db.register_type(pattern, cls)`

Register a Model class for a path pattern.

```python
db.register_type("/Instruments/*", VanillaOption)
db.register_type("/Books/*", Book)
db.register_type("/Positions/*/*", Position)  # Nested: /Positions/{book}/{symbol}
```

**Parameters:**
- `pattern` - Glob pattern for paths (e.g., `/Instruments/*`)
- `cls` - The `dag.Model` subclass

`*` matches across `/`, so `/Instruments/*` also covers
`/Instruments/Bonds/UST`. When several patterns match a path, the most
specific one (the most literal characters) wins, whatever the order of
registration: register `/Instruments/Bonds/*` for `Bond` and it takes
precedence over `/Instruments/*` there.

### CRUD Operations

#### `db[path] = obj`

Store an object at a path.

```python
option = VanillaOption()
option.Strike.set(150.0)
db["/Instruments/AAPL_C_150"] = option
```

**Raises:** `TypeMismatchError` if object doesn't match registered pattern

#### `db[path]`

Retrieve an object by path.

```python
option = db["/Instruments/AAPL_C_150"]
```

**Raises:**
- `NotFoundError` if path doesn't exist
- `TypeNotRegisteredError` if no type registered for pattern

#### `del db[path]`

Delete an object.

```python
del db["/Instruments/AAPL_C_150"]
```

**Raises:** `NotFoundError` if path doesn't exist

#### `path in db`

Check if a path exists.

```python
if "/Instruments/AAPL_C_150" in db:
    print("Found!")
```

#### `db.get(path, default=None)`

Get object or default if not found.

```python
option = db.get("/Instruments/MAYBE", default=None)
```

### Factory Method

#### `db.new(cls, path)`

Create a new object and store it at the path.

```python
option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.save()
```

**Parameters:**
- `cls` - The Model class to instantiate
- `path` - Path to store at

**Returns:** The newly created and stored Model instance

### Saving

#### `db.save(obj)`

Save changes to a tracked object.

```python
option = db["/Instruments/TEST"]
option.Strike.set(200.0)
db.save(option)
```

**Raises:** `ValueError` if object not tracked by this store

### Queries

#### `db.query(pattern)`

Query paths matching a glob pattern.

```python
for path in db.query("/Instruments/AAPL_*"):
    print(path)
```

**Parameters:**
- `pattern` - Glob pattern (e.g., `/Instruments/AAPL_*`)

**Returns:** Iterator of matching paths

#### `db.list(prefix, recursive=False)`

List paths under a prefix.

```python
# Direct children only
for path in db.list("/Instruments/"):
    print(path)

# All descendants
for path in db.list("/", recursive=True):
    print(path)
```

### Transactions

#### `db.transaction()`

Context manager for atomic operations.

```python
with db.transaction():
    db["/Books/DESK"] = book
    db["/Positions/DESK/AAPL"] = position
    # Both committed atomically, or both rolled back
```

If the block raises, every write and delete made inside it is undone on both
the SQLite and memory backends. Objects you changed in memory keep their new
values; reload them from the store if you need the saved state.

### Lifecycle

#### `db.close()`

Close the store connection.

```python
db.close()
```

#### Context Manager

```python
with connect("sqlite:///trading.db") as db:
    db.register_type("/Instruments/*", VanillaOption)
    # ... use db ...
# Automatically closed
```

### Utility

#### `db.get_path(obj)`

Get the path for a tracked object.

```python
path = db.get_path(option)  # "/Instruments/AAPL_C_150"
```

#### `db.clear_cache()`

Clear the identity map cache to force reload from storage.

```python
db.clear_cache()
```

## Object Self-Awareness

Stored objects know their path and store. These methods come from the
`lattice.store.Storable` mixin, which all lattice instruments and the trading
models (`Book`, `Trade`, `Position`) include. To get them on your own model,
list the mixin before `dag.Model`:

```python
from lattice.store import Storable

class MyModel(Storable, dag.Model):
    ...
```

A plain `dag.Model` can still be stored; use `db[path] = obj` and `db.save(obj)`.

### `obj.path()`

Get the object's path in its store.

```python
option = db["/Instruments/AAPL_C_150"]
print(option.path())  # "/Instruments/AAPL_C_150"
```

### `obj.save()`

Save the object to its store.

```python
option = db["/Instruments/AAPL_C_150"]
option.Strike.set(160.0)
option.save()  # Persists the change
```

### `obj.store`

Access the store the object belongs to.

```python
option = db["/Instruments/AAPL_C_150"]
other = option.store["/Instruments/GOOGL_C_100"]
```

## Exceptions

| Exception | Description |
|-----------|-------------|
| `StoreError` | Base class for all store errors |
| `NotFoundError` | Path doesn't exist |
| `TypeNotRegisteredError` | No type registered for path pattern |
| `TypeMismatchError` | Object type doesn't match pattern |
| `SerializationError` | Failed to serialize/deserialize |
| `TransactionError` | Transaction failed |

## Path Conventions

Recommended path structure:

```
/Instruments/
  /AAPL_C_150        -> VanillaOption
  /GOOGL_P_140       -> VanillaOption
/Stocks/
  /AAPL              -> Stock
/Bonds/
  /UST_10Y           -> Bond
/Books/
  /MARKET_MAKER      -> Book
  /CLIENT_ABC        -> Book
/Positions/
  /MARKET_MAKER/
    /AAPL_C_150      -> Position
```

## Serialization

Only `dag.Persisted` fields are saved. Plain `dag.Input` fields (typically
market data) and computed values are not: inputs revert to their defaults on
load and computed values are recalculated.

```python
class MyModel(dag.Model):
    @dag.computed(dag.Persisted)  # Saved
    def Strike(self):
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)  # NOT saved - market data
    def Spot(self):
        return 100.0

    @dag.computed  # NOT saved - recalculated
    def Price(self):
        return self.calculate_price()
```

### Trading models

`Book`, `Trade` and `Position` persist their identity and economics. Market
prices and links to live objects are not saved, and are set again after load.

| Class | Persisted | Not persisted |
|-------|-----------|---------------|
| `Book` | `BookId`, `Name`, `BookType`, `ParentBookId` | its list of positions |
| `Trade` | `TradeId`, `Symbol`, `Quantity`, `Price`, `BuyerBookId`, `SellerBookId`, `Timestamp` | `MarketPrice` |
| `Position` | `Symbol`, `BookId`, `Quantity`, `AvgPrice` | `MarketPrice`, `LinkedInstrument` |

A `Book` loaded from the store is a standalone record: `Positions()` is empty
until a `TradingSystem` populates it. The store does not save or rebuild a
`TradingSystem`; store its books, trades and positions individually.

Supported types:
- Primitives: `str`, `int`, `float`, `bool`, `None`
- Collections: `list`, `dict`
- Dates: `datetime` (serialized as ISO 8601)

## Example: Full Workflow

```python
from lattice.store import connect
from lattice import VanillaOption, Book

# Connect
db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)
db.register_type("/Books/*", Book)

# Create objects
option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.Spot.set(155.0)
option.Volatility.set(0.20)
option.save()

book = db.new(Book, "/Books/DESK")
book.Name.set("Market Maker")
book.save()

# Query
print("All instruments:")
for path in db.query("/Instruments/*"):
    inst = db[path]
    print(f"  {path}: Strike={inst.Strike()}")

# Atomic updates
with db.transaction():
    option.Strike.set(160.0)
    option.save()
    book.Name.set("Updated Desk")
    book.save()

db.close()
```
