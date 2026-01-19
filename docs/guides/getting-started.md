# Getting Started

This guide walks you through installing Lattice and building your first pricing model.

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

## Your First Option

```python
from lattice import VanillaOption

# Create an option
option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(105.0)
option.Volatility.set(0.20)
option.Rate.set(0.05)
option.TimeToExpiry.set(1.0)
option.IsCall.set(True)

# Price and Greeks are computed automatically
print(f"Price: ${option.Price():.4f}")
print(f"Delta: {option.Delta():.4f}")
print(f"Gamma: {option.Gamma():.6f}")
```

## Reactivity

When you change an input, dependent values automatically update:

```python
option.Spot.set(100.0)
price_at_100 = option.Price()

option.Spot.set(110.0)  # Change spot
price_at_110 = option.Price()  # Automatically recomputed

print(f"Price moved from ${price_at_100:.2f} to ${price_at_110:.2f}")
```

## Scenario Analysis

Use `lattice.scenario()` to temporarily override values:

```python
import lattice

option = VanillaOption()
option.Spot.set(100.0)

base_price = option.Price()

# Temporary override
with lattice.scenario():
    option.Spot.override(105.0)
    bumped_price = option.Price()
    print(f"Price if spot +5%: ${bumped_price:.4f}")

# Original value automatically restored
print(f"Original price: ${option.Price():.4f}")
```

## Interactive UI

Display any model in your browser:

```python
from lattice.ui import show

option = VanillaOption()
option.Spot.set(100.0)
option.Strike.set(100.0)

show(option)  # Opens browser with interactive UI
```

Or build a custom app:

```python
from lattice.ui import DagApp, bind

option = VanillaOption()
option.Strike.set(100.0)

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

app.run(port=8080)
```

## Other Instruments

Lattice supports multiple instrument types:

```python
from lattice import Stock, Bond, Forward, FXPair

# Stock
stock = Stock()
stock.Symbol.set("AAPL")
stock.Price.set(150.0)
stock.Dividend.set(0.96)
print(f"Dividend Yield: {stock.DividendYield():.2%}")

# Bond
bond = Bond()
bond.FaceValue.set(1000.0)
bond.CouponRate.set(0.05)
bond.YieldToMaturity.set(0.04)
bond.MaturityYears.set(10)
print(f"Bond Price: ${bond.Price():.2f}")
print(f"Duration: {bond.Duration():.2f} years")

# Forward
forward = Forward()
forward.Spot.set(100.0)
forward.Rate.set(0.05)
forward.TimeToExpiry.set(1.0)
print(f"Forward Price: ${forward.ForwardPrice():.2f}")

# FX Pair
eurusd = FXPair()
eurusd.Spot.set(1.0850)
eurusd.BaseRate.set(0.04)
eurusd.QuoteRate.set(0.05)
print(f"1Y Forward: {eurusd.Forward(1.0):.4f}")
```

## Position Tracking

Track positions with fast livetable-based tables:

```python
from lattice import PositionTable

positions = PositionTable()

positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
positions.add("GOOGL_C_140", quantity=20, avg_price=8.00)

for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} @ ${pos['avg_price']:.2f}")

# Filter to long positions
long_only = positions.filter(lambda r: r["quantity"] > 0)
```

## Trading System

For full book/position/P&L management:

```python
from lattice.trading import TradingSystem

system = TradingSystem()

# Create books
desk = system.book("MARKET_MAKER")
client = system.book("CLIENT")

# Execute trades
system.trade(desk, client, "AAPL_C_150", 100, 5.25)

# Set market prices
system.set_market_price("AAPL_C_150", 5.50)

# P&L updates automatically
print(f"Desk P&L: ${desk.TotalPnL():.2f}")

# Interactive dashboard
system.show()
```

## Risk Analysis

Compute Greeks numerically for any instrument:

```python
from lattice import VanillaOption, risk

option = VanillaOption()
option.Spot.set(100.0)

print(f"Delta: {risk.delta(option):.4f}")
print(f"Gamma: {risk.gamma(option):.6f}")
print(f"Vega:  {risk.vega(option):.4f}")
```

Stress test portfolios:

```python
result = risk.run_scenario(desk, "market_crash")
print(f"P&L Impact: ${result['pnl_impact']:,.2f}")
```

## Persistence

Store and retrieve objects:

```python
from lattice.store import connect

db = connect("sqlite:///trading.db")
db.register_type("/Instruments/*", VanillaOption)

# Store
option = db.new(VanillaOption, "/Instruments/AAPL_C_150")
option.Strike.set(150.0)
option.save()

# Retrieve later
loaded = db["/Instruments/AAPL_C_150"]
print(loaded.Strike())  # 150.0
```

## Next Steps

- [Instruments API](../api/instruments.md) - Full instrument reference
- [Trading API](../api/trading.md) - Books, trades, positions
- [Risk API](../api/risk.md) - Greeks, stress testing, VaR
- [Store API](../api/store.md) - Persistence
