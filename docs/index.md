# Lattice Documentation

**A reactive quant pricing and trading library for Python.**

Built on [dag](https://github.com/beeblebroxz/dag) (computation graphs) and [livetable](https://github.com/beeblebroxz/livetable) (fast tables).

## Overview

Lattice provides:

- **Reactive Instruments** - Options, stocks, bonds, forwards, futures, FX with automatic dependency tracking
- **Trading System** - Books, trades, positions with real-time P&L
- **Risk Analysis** - Greeks, stress testing, VaR calculations
- **Persistent Storage** - Path-based object database with SQLite backend
- **Web UI** - Real-time visualization of models in your browser

## Quick Links

### Guides
- [Getting Started](guides/getting-started.md) - Installation and first steps
- [Persistence Guide](guides/persistence.md) - Storing and loading objects

### API Reference
- [Instruments](api/instruments.md) - VanillaOption, Stock, Bond, FX, etc.
- [Trading](api/trading.md) - TradingSystem, Book, Trade, Position
- [Risk](api/risk.md) - Greeks, stress testing, VaR
- [Store](api/store.md) - Persistent storage API

## Architecture

```
                     Your Code
option.Spot.set(105) --> option.Price() --> Delta, Gamma...
system.trade(...)    --> book.TotalPnL() --> Positions, P&L...
risk.delta(option)   --> risk.stress(book) --> VaR, Scenarios...
db["/path"] = obj    --> db.query("/...")  --> Persistence
                          |
                          v
+-----------------------------------------------------------+
|                       Lattice                             |
|  Instruments: VanillaOption | Stock | Bond | FX | Forward |
|  Trading:     Book | Trade | Position | TradingSystem     |
|  Risk:        sensitivity | Greeks | stress | VaR         |
|  Store:       connect | Store | SQLite | Memory           |
|  Tables:      PositionTable | TradeBlotter                |
|  UI:          DagApp | show() | Dashboards                |
+-----------------------------------------------------------+
          |                          |
          v                          v
     +----------+              +------------+
     |   dag    |              |  livetable |
     |  graphs  |              |   tables   |
     +----------+              +------------+
```

## Installation

```bash
pip install lattice
```

Or from source:

```bash
git clone https://github.com/beeblebroxz/lattice.git
cd lattice
pip install -e .
```

## Minimal Example

```python
from lattice import VanillaOption
from lattice.ui import show

option = VanillaOption()
option.Spot.set(105.0)
option.Strike.set(100.0)

print(f"Price: ${option.Price():.4f}")
print(f"Delta: {option.Delta():.4f}")

show(option)  # Opens browser with interactive UI
```
