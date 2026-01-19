# Lattice

A quant pricing and trading library built on [dag](https://github.com/beeblebroxz/dag) and [livetable](https://github.com/beeblebroxz/livetable).

## Features

- **Option Pricing**: Black-Scholes pricing with Greeks (Delta, Gamma, Vega, Theta, Rho)
- **Reactive Computation**: Built on dag for automatic dependency tracking and memoization
- **Fast Tables**: Position and trade management using livetable's high-performance tables
- **Scenario Analysis**: What-if calculations using dag's scenario system

## Installation

```bash
pip install lattice
```

Or install from source:

```bash
git clone https://github.com/beeblebroxz/lattice.git
cd lattice
pip install -e .
```

## Quick Start

### Option Pricing

```python
from lattice.instruments import VanillaOption

# Create an option
option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(105.0)
option.Volatility.set(0.20)
option.Rate.set(0.05)
option.TimeToExpiry.set(0.5)
option.IsCall.set(True)

# Price and Greeks are computed automatically
print(f"Price: {option.Price():.4f}")
print(f"Delta: {option.Delta():.4f}")
print(f"Gamma: {option.Gamma():.4f}")
print(f"Vega:  {option.Vega():.4f}")

# Changes automatically invalidate dependent calculations
option.Spot.set(110.0)
print(f"New Price: {option.Price():.4f}")  # Recomputed
```

### Scenario Analysis

```python
import lattice

option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(100.0)
option.Volatility.set(0.20)
option.Rate.set(0.05)
option.TimeToExpiry.set(0.25)
option.IsCall.set(True)

base_price = option.Price()

# Temporary override for scenario analysis
with lattice.scenario():
    option.Spot.override(105.0)  # +5% spot bump
    bumped_price = option.Price()
    print(f"Price impact: {bumped_price - base_price:.4f}")

# Original value restored
print(f"Base price: {option.Price():.4f}")
```

### Position Tracking

```python
from lattice.trading import PositionTable

# Create a position table
positions = PositionTable()

# Add positions
positions.add("AAPL_C_150_Jun24", quantity=10, avg_price=5.50)
positions.add("AAPL_P_145_Jun24", quantity=-5, avg_price=3.20)
positions.add("GOOGL_C_140_Jun24", quantity=20, avg_price=8.00)

# Iterate (25x faster than pandas)
for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} @ ${pos['avg_price']:.2f}")

# Filter views (zero-copy)
long_positions = positions.filter(lambda r: r["quantity"] > 0)
print(f"Long positions: {len(long_positions)}")
```

### Trade Blotter

```python
from lattice.trading import TradeBlotter

blotter = TradeBlotter()

# Record trades
blotter.record("AAPL_C_150_Jun24", "BUY", 5, 5.25)
blotter.record("AAPL_C_150_Jun24", "BUY", 5, 5.75)
blotter.record("AAPL_P_145_Jun24", "SELL", 5, 3.20)

# View trades
for trade in blotter:
    print(f"{trade['side']} {trade['quantity']} {trade['symbol']} @ {trade['price']}")
```

## Architecture

Lattice combines two foundational libraries:

- **dag**: Provides the computation graph for pricing models. Computed functions are memoized and automatically invalidate when dependencies change.

- **livetable**: Provides high-performance columnar tables for positions, trades, and market data. 25x faster iteration than pandas with zero-copy views.

## API Reference

### Instruments

- `VanillaOption` - European vanilla option with Black-Scholes pricing

### Trading

- `PositionTable` - Position tracking with livetable
- `TradeBlotter` - Trade recording with livetable

### Models

- `blackscholes` - Black-Scholes pricing formulas and Greeks

## License

MIT License - see [LICENSE](LICENSE) for details.
