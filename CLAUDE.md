# Lattice - Project Context for Claude

## Overview

Lattice is a quant pricing and trading library that builds on two foundational libraries:
- **dag** - Computation graph for memoized, dependency-tracked calculations
- **livetable** - High-performance columnar tables with reactive views

The library provides:
- Financial instruments with reactive pricing (options, stocks, bonds, FX, etc.)
- Trading system with books, positions, and P&L tracking
- Risk analysis (Greeks, stress testing, VaR)
- Persistent storage with SQLite backend
- Real-time web UI for visualization

## Project Structure

```
lattice/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── docs/                         # Documentation
│   ├── index.md                  # Docs home
│   ├── api/                      # API reference
│   │   ├── instruments.md
│   │   ├── trading.md
│   │   ├── risk.md
│   │   └── store.md
│   └── guides/                   # User guides
│       ├── getting-started.md
│       └── persistence.md
├── lattice/
│   ├── __init__.py               # Public API exports
│   ├── instruments/              # Financial instruments (dag.Model)
│   │   ├── __init__.py
│   │   ├── base.py               # Instrument base class
│   │   ├── options.py            # VanillaOption
│   │   ├── equity.py             # Stock
│   │   ├── fixedincome.py        # Bond
│   │   ├── derivatives.py        # Forward, Future
│   │   └── fx.py                 # FXPair, FXForward
│   ├── models/                   # Pricing models
│   │   ├── __init__.py
│   │   └── blackscholes.py       # BS pricing + Greeks
│   ├── trading/                  # Trading system (dag.Model + livetable)
│   │   ├── __init__.py
│   │   ├── system.py             # TradingSystem orchestrator
│   │   ├── book.py               # Book (dag.Model)
│   │   ├── trade.py              # Trade (dag.Model)
│   │   ├── position.py           # Position (dag.Model)
│   │   ├── positions.py          # PositionTable (livetable)
│   │   ├── blotter.py            # TradeBlotter (livetable)
│   │   └── dashboard.py          # TradingDashboard UI
│   ├── risk/                     # Risk analysis
│   │   ├── __init__.py           # Public API: delta, gamma, stress, var
│   │   ├── sensitivities.py      # Bump-and-reval Greeks
│   │   ├── portfolio.py          # Portfolio-level risk
│   │   ├── scenarios.py          # Stress scenarios
│   │   ├── var.py                # Value at Risk
│   │   └── engine.py             # RiskEngine for batch operations
│   ├── store/                    # Persistent storage
│   │   ├── __init__.py           # Public API: connect, Store
│   │   ├── core.py               # Store class
│   │   ├── serialization.py      # Serializer, TypeRegistry
│   │   ├── exceptions.py         # StoreError hierarchy
│   │   └── backends/
│   │       ├── __init__.py
│   │       ├── base.py           # StorageBackend ABC
│   │       ├── memory.py         # In-memory backend
│   │       └── sqlite.py         # SQLite backend
│   ├── ui/                       # Web UI framework
│   │   ├── __init__.py           # Public API: DagApp, show, bind
│   │   ├── app.py                # DagApp main class
│   │   ├── bindings.py           # UI bindings to dag nodes
│   │   ├── server.py             # aiohttp web server
│   │   └── protocol.py           # WebSocket protocol
│   └── market/                   # Market data (future)
│       ├── __init__.py
│       └── quotes.py             # Quote storage
├── examples/
│   ├── option_pricer_web.py      # Interactive option pricer
│   ├── quick_start.py            # Basic demo
│   ├── greeks_deep_dive.py       # Analytic vs numerical Greeks comparison
│   ├── multi_instrument_risk.py  # Risk across asset classes (Options, Bonds, Forwards, FX)
│   ├── sensitivity_analysis.py   # Bump-and-reval methodology deep dive
│   ├── bond_risk_analysis.py     # Fixed income risk (Duration, Convexity, DV01)
│   ├── trading_demo.py           # Trading system demo
│   └── trading_dashboard.py      # Full dashboard
└── tests/
    ├── test_instruments.py
    ├── test_options.py
    ├── test_blackscholes.py
    ├── test_trading.py
    ├── test_books.py
    ├── test_risk.py
    ├── test_store.py
    └── test_ui.py
```

## Dependencies

- **dag-framework**: Provides `dag.Model`, `@dag.computed`, `dag.scenario()`, flags
- **livetable**: Provides `Table`, `Schema`, `DataType` for fast tabular data
- **numpy**: Numerical computations (Black-Scholes, etc.)
- **aiohttp**: Async web server for UI

## Coding Conventions

- Type hints throughout
- Docstrings follow Google style
- Tests use pytest
- **Computed functions use PascalCase** (inherited from dag)
  - Examples: `def Price(self)`, `def Delta(self)`, `def TotalPnL(self)`
- Regular methods use snake_case
  - Examples: `def add(...)`, `def trade(...)`, `def run_scenario(...)`

## Key Patterns

### dag.Model for Instruments

All instruments inherit from `Instrument` (which inherits from `dag.Model`) with reactive computed functions:

```python
import dag
from lattice.instruments.base import Instrument

class VanillaOption(Instrument):
    @dag.computed(dag.Input)
    def Strike(self):
        return 100.0

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self):
        return 100.0

    @dag.computed
    def Price(self):
        # Dependencies tracked automatically
        return black_scholes_price(self.Spot(), self.Strike(), ...)

    # Polymorphic interface (override base class)
    @dag.computed
    def Summary(self):
        return f"K={self.Strike():.0f} S={self.Spot():.0f}"

    @dag.computed
    def MarketValue(self):
        return self.Price()
```

### Instrument Interface

All instruments implement a common polymorphic interface:

| Method | Description | Example Output |
|--------|-------------|----------------|
| `Summary()` | Human-readable description | `"K=100 S=105 C"`, `"5% 10Y"` |
| `MarketValue()` | Current market value | Option price, bond price, forward value |

This allows generic portfolio code without type-checking:

```python
for name, inst in portfolio.items():
    print(f"{name}: {inst.Summary()} = ${inst.MarketValue():,.2f}")
```

### dag Flags

- `dag.Input` - Field can be set permanently via `.set()`
- `dag.Overridable` - Field can be temporarily overridden in scenarios
- `dag.Input | dag.Overridable` - Both settable and overridable
- `dag.Optional` - Return None instead of raising on dependency errors

### Scenario Analysis

Use `lattice.scenario()` (re-exported from dag) for temporary overrides:

```python
import lattice

with lattice.scenario():
    option.Spot.override(spot + 1)  # Temporary
    bumped_price = option.Price()
# Spot automatically restored
```

### livetable for Fast Tables

PositionTable and TradeBlotter use livetable for 25x faster iteration:

```python
from livetable import Table, Schema, DataType

schema = Schema([
    ("symbol", DataType.STRING),
    ("quantity", DataType.INT64),
])
table = Table(schema)
```

### TradingSystem Architecture

Hybrid approach combining dag.Model and livetable:

```python
system = TradingSystem()
desk = system.book("MARKET_MAKER")        # dag.Model for reactivity
client = system.book("CLIENT")
system.trade(desk, client, "AAPL", 100, 5.25)  # Creates Trade + Position
system.set_market_price("AAPL", 5.50)
print(desk.TotalPnL())  # Reactive P&L
```

### Store Persistence

Path-based object storage with SQLite backend:

```python
from lattice.store import connect

db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.save()

# Objects know their path and store
print(option.path())   # "/Instruments/AAPL_C_150"
option.save()          # Persist changes
```

### Risk Module

Numerical Greeks via bump-and-reval:

```python
from lattice import risk

delta = risk.delta(option)           # dPrice/dSpot
gamma = risk.gamma(option)           # d²Price/dSpot²
result = risk.stress(book, spot_shock=-0.10)  # Stress test
var = risk.parametric_var(book, confidence=0.95)  # VaR
```

### UI Framework

Web UI with automatic reactivity:

```python
from lattice.ui import DagApp, bind, show

# Quick display
show(option)

# Custom app
app = DagApp("Option Pricer")
app.register(option, name="option")
app.add_section("Inputs", inputs=[
    bind(option.Spot, label="Spot", format="$,.2f"),
])
app.run(port=8080)
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific module tests
pytest tests/test_store.py
pytest tests/test_risk.py

# Skip UI tests (require display)
pytest --ignore=tests/test_ui.py
```

## Common Tasks

### Adding a New Instrument

1. Create class in `lattice/instruments/` inheriting from `Instrument` (or `dag.Model`)
2. Define `@dag.computed(dag.Input)` for inputs
3. Define `@dag.computed` for derived values
4. Export in `lattice/instruments/__init__.py`
5. Export in `lattice/__init__.py`
6. Add tests in `tests/`

### Adding Risk Functions

1. Add function in `lattice/risk/sensitivities.py` or appropriate module
2. Use `lattice.scenario()` for bump-and-reval
3. Export in `lattice/risk/__init__.py`
4. Add tests in `tests/test_risk.py`

### Adding Storage Backend

1. Create `lattice/store/backends/newbackend.py`
2. Inherit from `StorageBackend` ABC
3. Implement required methods: `get`, `put`, `delete`, `exists`, `list`, `query`
4. Add scheme handling in `lattice/store/core.py:connect()`
5. Export in `lattice/store/backends/__init__.py`

## Serialization Notes

- Only `dag.Input` fields are persisted (settable state)
- Computed values are recalculated on load
- Supported types: primitives, list, dict, datetime
- Model references: store the path, not the object

## Architecture Principles

1. **Reactivity** - Use dag.Model for anything that needs automatic updates
2. **Performance** - Use livetable for bulk data (trades, positions)
3. **Separation** - Instruments don't know about trading; trading doesn't know about risk
4. **Explicit Save** - Persistence is explicit, not automatic
5. **Path-based** - Objects are addressed by hierarchical paths
