# Lattice

**A reactive quant pricing and trading library for Python.**

Built on [dag](https://github.com/beeblebroxz/dag) (computation graphs) and [livetable](https://github.com/beeblebroxz/livetable) (fast tables).

<!-- Screenshot placeholder - replace with actual screenshot -->
<!-- ![Lattice Option Pricer](docs/images/option-pricer-screenshot.png) -->

```
┌─────────────────────────────────────────────────────────────┐
│                 Black-Scholes Option Pricer                  │
├─────────────────────────────────────────────────────────────┤
│  Market Data                                                 │
│    Spot Price:     $105.00  [────────●────]                 │
│    Strike Price:   $100.00  [────────●────]                 │
│                                                              │
│  Model Parameters                                            │
│    Volatility:     25.00%   [────●────────]                 │
│    Risk-Free Rate: 5.00%    [──●──────────]                 │
│    Time to Expiry: 1.00 yr  [────────●────]                 │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  Option Price      $12.3456                                  │
│  Delta             0.6368      Gamma    0.0181              │
│  Vega              37.5241     Theta   -6.4140              │
└─────────────────────────────────────────────────────────────┘
```

## Highlights

- **Reactive Pricing** - Change an input, all dependent values update automatically
- **Real-time Web UI** - Visualize and interact with models in your browser
- **Black-Scholes Greeks** - Delta, Gamma, Vega, Theta, Rho computed efficiently
- **25x Faster Tables** - Position and trade management using livetable
- **Scenario Analysis** - What-if calculations without mutating state
- **Jupyter Ready** - Works in notebooks with IFrame display

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

### One-Line UI

```python
from lattice import VanillaOption
from lattice.ui import show

option = VanillaOption()
option.Spot.set(105.0)
option.Strike.set(100.0)

show(option)  # Opens browser with interactive UI
```

### Option Pricing

```python
from lattice import VanillaOption

# Create an option
option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(105.0)
option.Volatility.set(0.20)
option.Rate.set(0.05)
option.TimeToExpiry.set(0.5)
option.IsCall.set(True)

# Price and Greeks are computed automatically
print(f"Price: ${option.Price():.4f}")
print(f"Delta: {option.Delta():.4f}")
print(f"Gamma: {option.Gamma():.6f}")
print(f"Vega:  {option.Vega():.4f}")
print(f"Theta: {option.Theta():.4f}")

# Changes automatically invalidate dependent calculations
option.Spot.set(110.0)
print(f"New Price: ${option.Price():.4f}")  # Recomputed automatically
```

### Interactive Web UI

```python
from lattice import VanillaOption
from lattice.ui import DagApp, bind

option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(100.0)

app = DagApp("Option Pricer")
app.register(option, name="option")

app.add_section("Inputs", inputs=[
    bind(option.Spot, label="Spot Price", format="$,.2f"),
    bind(option.Strike, label="Strike", format="$,.2f"),
    bind(option.Volatility, label="Volatility", format="%"),
])

app.add_section("Results", outputs=[
    bind(option.Price, label="Price", format="$,.4f"),
    bind(option.Delta, label="Delta", format=".4f"),
])

app.run(port=8080)  # Opens http://localhost:8080
```

### Scenario Analysis

```python
import lattice
from lattice import VanillaOption

option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(100.0)

base_price = option.Price()

# Temporary override for scenario analysis
with lattice.scenario():
    option.Spot.override(105.0)  # +5% spot bump
    bumped_price = option.Price()
    print(f"Price impact: ${bumped_price - base_price:.4f}")

# Original value automatically restored
print(f"Base price: ${option.Price():.4f}")
```

### Position Tracking

```python
from lattice import PositionTable

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
from lattice import TradeBlotter

blotter = TradeBlotter()

# Record trades
blotter.record("AAPL_C_150_Jun24", "BUY", 5, 5.25)
blotter.record("AAPL_C_150_Jun24", "BUY", 5, 5.75)
blotter.record("AAPL_P_145_Jun24", "SELL", 5, 3.20)

print(f"Total notional: ${blotter.total_notional():,.2f}")
print(f"Buy trades: {len(blotter.buys())}")
```

## Examples

Run the interactive option pricer:

```bash
python examples/option_pricer_web.py
```

Or the quick start demo:

```bash
python examples/quick_start.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Your Code                             │
│   option.Spot.set(105) → option.Price() → Delta, Gamma...   │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                         Lattice                              │
│  VanillaOption │ PositionTable │ TradeBlotter │ Web UI      │
└────────┬────────────────┬───────────────────────────────────┘
         │                │
    ┌────▼────┐      ┌────▼────┐
    │   dag   │      │livetable│
    │  graphs │      │  tables │
    └─────────┘      └─────────┘
```

**dag** - Computation graphs with automatic dependency tracking, memoization, and scenarios. When you change `Spot`, only the dependent values (`Price`, `Delta`, etc.) are recomputed.

**livetable** - High-performance columnar tables. 25x faster iteration than pandas with zero-copy filtered views.

## API Reference

### Instruments

| Class | Description |
|-------|-------------|
| `VanillaOption` | European vanilla option with Black-Scholes pricing |

### Trading

| Class | Description |
|-------|-------------|
| `PositionTable` | Position tracking with filtering |
| `TradeBlotter` | Trade recording and analysis |

### UI

| Function/Class | Description |
|----------------|-------------|
| `show(model)` | Quick display of any dag model |
| `DagApp` | Full-featured app with custom layouts |
| `bind(node, ...)` | Connect dag nodes to UI elements |

### Greeks

All Greeks are computed using Black-Scholes closed-form solutions:

| Greek | Method | Description |
|-------|--------|-------------|
| Delta | `option.Delta()` | Rate of change of price w.r.t. spot |
| Gamma | `option.Gamma()` | Rate of change of delta w.r.t. spot |
| Vega | `option.Vega()` | Sensitivity to volatility |
| Theta | `option.Theta()` | Time decay (per year) |
| Rho | `option.Rho()` | Sensitivity to interest rate |

## License

MIT License - see [LICENSE](LICENSE) for details.
