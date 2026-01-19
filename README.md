# Lattice

**A reactive quant pricing and trading library for Python.**

Built on [dag](https://github.com/beeblebroxz/dag) (computation graphs) and [livetable](https://github.com/beeblebroxz/livetable) (fast tables).

> **Try it:** `python examples/option_pricer_web.py` then open http://localhost:8080

## Highlights

- **Reactive Pricing** - Change an input, all dependent values update automatically
- **Multi-Asset Support** - Options, stocks, bonds, forwards, futures, FX
- **Trading Books** - Full position management with P&L tracking
- **Risk Analysis** - Bump-and-reval Greeks, stress testing, VaR calculations
- **Persistent Storage** - Path-based object database with SQLite backend
- **Real-time Web UI** - Visualize and interact with models in your browser

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

## Quick Start

```python
from lattice import VanillaOption
from lattice.ui import show

option = VanillaOption()
option.Spot.set(105.0)
option.Strike.set(100.0)
option.Volatility.set(0.20)

# Price and Greeks computed automatically
print(f"Price: ${option.Price():.4f}")
print(f"Delta: {option.Delta():.4f}")

# Changes automatically propagate
option.Spot.set(110.0)
print(f"New Price: ${option.Price():.4f}")

# Interactive UI
show(option)  # Opens browser
```

## Key Features

### Instruments

```python
from lattice import VanillaOption, Stock, Bond, Forward, FXPair

option = VanillaOption()
stock = Stock()
bond = Bond()
forward = Forward()
fx = FXPair()
```

### Trading System

```python
from lattice.trading import TradingSystem

system = TradingSystem()
desk = system.book("MARKET_MAKER")
client = system.book("CLIENT")

system.trade(desk, client, "AAPL_C_150", 100, 5.25)
system.set_market_price("AAPL_C_150", 5.50)

print(f"P&L: ${desk.TotalPnL():.2f}")
```

### Risk Analysis

```python
from lattice import VanillaOption, risk

option = VanillaOption()
option.Spot.set(100.0)

# Numerical Greeks
print(f"Delta: {risk.delta(option):.4f}")
print(f"Gamma: {risk.gamma(option):.6f}")

# Stress testing
result = risk.run_scenario(desk, "market_crash")
print(f"P&L Impact: ${result['pnl_impact']:,.2f}")

# VaR
var = risk.parametric_var(desk, confidence=0.95, holding_period=1)
print(f"VaR: ${var['var']:,.2f}")
```

### Persistent Storage

```python
from lattice.store import connect

db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.save()

# Later...
loaded = db["/Instruments/AAPL_C_150"]
```

### Scenario Analysis

```python
import lattice

option = VanillaOption()
option.Spot.set(100.0)

with lattice.scenario():
    option.Spot.override(105.0)
    print(f"Bumped: ${option.Price():.4f}")

# Automatically restored
print(f"Base: ${option.Price():.4f}")
```

## Documentation

- **[Getting Started](docs/guides/getting-started.md)** - Installation and first steps
- **[Persistence Guide](docs/guides/persistence.md)** - Storing and loading objects

### API Reference

- [Instruments](docs/api/instruments.md) - VanillaOption, Stock, Bond, FX, etc.
- [Trading](docs/api/trading.md) - TradingSystem, Book, Trade, Position
- [Risk](docs/api/risk.md) - Greeks, stress testing, VaR
- [Store](docs/api/store.md) - Persistent storage API

## Examples

```bash
# Interactive option pricer
python examples/option_pricer_web.py

# Quick demo
python examples/quick_start.py
```

## Architecture

```
                     Your Code
option.Spot.set(105) --> option.Price() --> Delta, Gamma...
system.trade(...)    --> book.TotalPnL() --> Positions, P&L...
risk.delta(option)   --> risk.stress(...)  --> VaR, Scenarios...
db["/path"] = obj    --> db.query("/...")  --> Persistence
                          |
                          v
+-----------------------------------------------------------+
|                       Lattice                             |
|  Instruments | Trading | Risk | Store | Tables | UI       |
+-----------------------------------------------------------+
          |                          |
          v                          v
     +----------+              +------------+
     |   dag    |              |  livetable |
     +----------+              +------------+
```

## License

MIT License - see [LICENSE](LICENSE) for details.
