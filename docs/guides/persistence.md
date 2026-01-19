# Persistence Guide

This guide covers storing and retrieving objects with `lattice.store`.

## Overview

The store module provides path-based object storage, similar to a filesystem or key-value store but for `dag.Model` objects.

```python
from lattice.store import connect
from lattice import VanillaOption

db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

# Store and retrieve like a dict
db["/Instruments/AAPL_C_150"] = option
loaded = db["/Instruments/AAPL_C_150"]
```

## Connecting

### SQLite (Recommended)

```python
# File-based (persists to disk)
db = connect("sqlite:///trading.db")

# In-memory (for testing)
db = connect("sqlite:///:memory:")
```

### Memory Backend

```python
# Pure in-memory (no persistence)
db = connect("memory://")
```

## Type Registration

Before storing objects, register which types go where:

```python
db.register_type("/Instruments/*", VanillaOption)
db.register_type("/Stocks/*", Stock)
db.register_type("/Books/*", Book)
db.register_type("/Positions/*/*", Position)  # Nested paths
```

Patterns use glob syntax:
- `*` matches any single path segment
- `**` matches multiple segments (not yet supported)

## Storing Objects

### Method 1: Assignment

```python
option = VanillaOption()
option.Strike.set(150.0)
option.Spot.set(155.0)

db["/Instruments/AAPL_C_150"] = option
```

### Method 2: Factory (Recommended)

```python
# Create and store in one step
option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.save()
```

## Retrieving Objects

```python
# Direct access
option = db["/Instruments/AAPL_C_150"]

# With default
option = db.get("/Instruments/MAYBE", default=None)

# Check existence
if "/Instruments/AAPL_C_150" in db:
    option = db["/Instruments/AAPL_C_150"]
```

## Saving Changes

Objects track their store automatically:

```python
option = db["/Instruments/AAPL_C_150"]
option.Strike.set(160.0)

# Option 1: Via object
option.save()

# Option 2: Via store
db.save(option)

# Option 3: Re-assign
db["/Instruments/AAPL_C_150"] = option
```

## Object Self-Awareness

Stored objects know their path and store:

```python
option = db["/Instruments/AAPL_C_150"]

print(option.path())  # "/Instruments/AAPL_C_150"
print(option.store)   # <Store instance>

# Access other objects via store
other = option.store["/Instruments/GOOGL_C_100"]
```

## Querying

### List by Prefix

```python
# Direct children
for path in db.list("/Instruments/"):
    print(path)

# All descendants
for path in db.list("/", recursive=True):
    print(path)
```

### Query by Pattern

```python
# All AAPL options
for path in db.query("/Instruments/AAPL_*"):
    option = db[path]
    print(f"{path}: Strike={option.Strike()}")

# All instruments
for path in db.query("/Instruments/*"):
    print(path)
```

## Deleting

```python
del db["/Instruments/AAPL_C_150"]

# Object loses its store awareness
print(option.path())  # None
```

## Transactions

Group operations atomically:

```python
with db.transaction():
    db["/Books/DESK"] = book
    db["/Positions/DESK/AAPL"] = position
    # Both committed together, or both rolled back
```

If an exception occurs, all changes are rolled back:

```python
try:
    with db.transaction():
        db["/Books/DESK"] = book
        raise ValueError("Something went wrong")
        db["/Books/OTHER"] = other  # Never reached
except ValueError:
    pass

# book was NOT saved (rolled back)
```

## What Gets Persisted

Only `dag.Input` fields are persisted. Computed values are recalculated on load.

```python
class MyModel(dag.Model):
    @dag.computed(dag.Input)  # Persisted
    def Strike(self):
        return 100.0

    @dag.computed  # NOT persisted
    def Price(self):
        return self.calculate_price()
```

## Session Patterns

### Context Manager

```python
with connect("sqlite:///trading.db") as db:
    db.register_type("/Instruments/*", VanillaOption)
    db["/Instruments/TEST"] = option
# Automatically closed
```

### Long-Running

```python
db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

# ... use db throughout application ...

db.close()  # When done
```

## Path Conventions

Recommended structure:

```
/Instruments/
    /AAPL_C_150_Jun24    # Options
    /GOOGL_P_140_Jun24
/Stocks/
    /AAPL                # Equities
    /GOOGL
/Bonds/
    /UST_10Y             # Fixed income
/Books/
    /MARKET_MAKER        # Trading books
    /CLIENT_ABC
/Positions/
    /MARKET_MAKER/       # Positions by book
        /AAPL_C_150
        /GOOGL_P_140
```

## Example: Trading Workflow

```python
from lattice.store import connect
from lattice import VanillaOption
from lattice.trading import TradingSystem

# Setup persistence
db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

# Create instruments
aapl_call = db.new(VanillaOption, "/Instruments/AAPL_C_150")
aapl_call.Strike.set(150.0)
aapl_call.Spot.set(155.0)
aapl_call.save()

googl_put = db.new(VanillaOption, "/Instruments/GOOGL_P_140")
googl_put.Strike.set(140.0)
googl_put.Spot.set(145.0)
googl_put.save()

# Later: Load and use
for path in db.query("/Instruments/*"):
    inst = db[path]
    print(f"{path}: Price=${inst.Price():.4f}")

db.close()
```

## Supported Types

The serializer handles:
- Primitives: `str`, `int`, `float`, `bool`, `None`
- Collections: `list`, `dict`
- Dates: `datetime` (as ISO 8601)

Not supported:
- Direct `dag.Model` references (store the path instead)
- Custom classes (unless they have `__dict__`)

## Errors

| Exception | When |
|-----------|------|
| `NotFoundError` | Path doesn't exist |
| `TypeNotRegisteredError` | No type for path pattern |
| `TypeMismatchError` | Object type wrong for path |
| `SerializationError` | Can't serialize value |
| `TransactionError` | Transaction failed |

## Tips

1. **Use `db.new()`** - Creates and stores in one step, object is immediately saveable

2. **Save after changes** - Changes aren't persisted until you call `save()`

3. **Use transactions** - For related changes that should succeed or fail together

4. **Check existence** - Use `in` or `get()` with default for optional objects

5. **Clear cache if needed** - Use `db.clear_cache()` to force reload from storage
