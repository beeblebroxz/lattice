# Lattice - Project Context for Claude

## Overview

Lattice is a quant pricing and trading library that builds on two foundational libraries:
- **dag** - Computation graph for memoized, dependency-tracked calculations
- **livetable** - High-performance columnar tables with reactive views

## Project Structure

```
lattice/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── lattice/
│   ├── __init__.py           # Public API exports
│   ├── instruments/          # Financial instruments (dag.Model)
│   │   ├── __init__.py
│   │   ├── base.py           # Instrument base class
│   │   └── options.py        # VanillaOption
│   ├── models/               # Pricing models
│   │   ├── __init__.py
│   │   └── blackscholes.py   # BS pricing + Greeks
│   ├── market/               # Market data
│   │   ├── __init__.py
│   │   └── quotes.py         # Quote storage
│   └── trading/              # Trading/positions
│       ├── __init__.py
│       ├── positions.py      # PositionTable
│       ├── blotter.py        # TradeBlotter
│       └── pnl.py            # P&L calculations
├── examples/
└── tests/
```

## Dependencies

- **dag-framework**: Provides `dag.Model`, `@dag.computed`, `dag.scenario()`, etc.
- **livetable**: Provides `Table`, `Schema`, `DataType` for fast tabular data
- **numpy**: Numerical computations

## Coding Conventions

- Type hints are used throughout
- Docstrings follow Google style
- Tests use pytest
- **Computed functions use PascalCase** (inherited from dag convention)
  - Examples: `def Price(self)`, `def Delta(self)`, `def Spot(self)`
- Regular methods use snake_case
  - Examples: `def add(self, ...)`, `def record(self, ...)`

## Key Integration Patterns

### dag.Model for Instruments

```python
import dag

class VanillaOption(dag.Model):
    @dag.computed(dag.Input)
    def Strike(self):
        return 100.0

    @dag.computed
    def Price(self):
        # Dependencies on Spot, Strike, etc. are tracked automatically
        return black_scholes_price(...)
```

### livetable for Tables

```python
from livetable import Table, Schema, DataType

schema = Schema([
    ("symbol", DataType.STRING),
    ("quantity", DataType.INT64),
    ("avg_price", DataType.FLOAT64),
])
table = Table(schema)
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_options.py
```

## Development Setup

```bash
# Install dependencies in editable mode
pip install -e /path/to/dag
pip install /path/to/livetable/impl/target/wheels/livetable-*.whl

# Install lattice
pip install -e .
```
