# Lattice

**A reactive quant pricing and trading library for Python.**

Built on [dag](https://github.com/beeblebroxz/dag) (computation graphs) and [livetable](https://github.com/beeblebroxz/livetable) (fast tables).

<!-- Screenshot placeholder - replace with actual screenshot -->
<!-- ![Lattice Option Pricer](docs/images/option-pricer-screenshot.png) -->

> **Try it:** `python examples/option_pricer_web.py` then open http://localhost:8080

```
+-------------------------------------------------------------+
|              Black-Scholes Option Pricer                    |
+-------------------------------------------------------------+
|  INPUTS                                                     |
|    Spot Price:     $105.00                                  |
|    Strike Price:   $100.00                                  |
|    Volatility:     25.00%                                   |
|    Risk-Free Rate: 5.00%                                    |
|    Time to Expiry: 1.00 yr                                  |
+-------------------------------------------------------------+
|  RESULTS                                                    |
|    Price   $12.3456    Delta   0.6368    Gamma   0.0181    |
|    Vega    37.5241     Theta  -6.4140    Rho    45.1893    |
+-------------------------------------------------------------+
```

## Highlights

- **Reactive Pricing** - Change an input, all dependent values update automatically
- **Multi-Asset Support** - Options, stocks, bonds, forwards, futures, FX
- **Trading Books** - Full position management with P&L tracking
- **Risk Analysis** - Bump-and-reval Greeks, stress testing, VaR calculations
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

### Other Instruments

```python
from lattice import Stock, Bond, Forward, Future, FXPair

# Stocks
stock = Stock()
stock.Symbol.set("AAPL")
stock.Price.set(150.0)
stock.Dividend.set(0.96)
print(f"Dividend Yield: {stock.DividendYield():.2%}")

# Bonds
bond = Bond()
bond.FaceValue.set(1000.0)
bond.CouponRate.set(0.05)
bond.YieldToMaturity.set(0.04)
bond.MaturityYears.set(10)
print(f"Bond Price: ${bond.Price():.2f}")
print(f"Duration: {bond.Duration():.2f} years")

# Forwards
forward = Forward()
forward.Spot.set(100.0)
forward.Rate.set(0.05)
forward.TimeToExpiry.set(1.0)
print(f"Forward Price: ${forward.ForwardPrice():.2f}")

# FX Pairs
eurusd = FXPair()
eurusd.BaseCurrency.set("EUR")
eurusd.QuoteCurrency.set("USD")
eurusd.Spot.set(1.0850)
eurusd.BaseRate.set(0.04)
eurusd.QuoteRate.set(0.05)
print(f"EUR/USD: {eurusd.Spot():.4f}")
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

# Show interactive dashboard
blotter.show()  # Opens browser with real-time updates
```

### Trading System with Books

```python
from lattice.trading import TradingSystem

# Create a trading system
system = TradingSystem()

# Create books (trading desks, customer accounts, etc.)
desk = system.book("MARKET_MAKER", book_type="trading")
client = system.book("CLIENT_ABC", book_type="customer")

# Execute trades between books
system.trade(buyer=desk, seller=client, symbol="AAPL_C_150", quantity=10, price=5.25)
system.trade(buyer=desk, seller=client, symbol="GOOGL_C_140", quantity=20, price=8.00)
system.trade(buyer=client, seller=desk, symbol="AAPL_C_150", quantity=5, price=5.50)

# Access reactive P&L (automatically updates when market prices change)
print(f"Market Maker P&L: ${desk.TotalPnL():.2f}")
print(f"Client P&L: ${client.TotalPnL():.2f}")

# Update market prices - P&L recomputes automatically
system.set_market_price("AAPL_C_150", 6.00)
print(f"MM P&L after market move: ${desk.TotalPnL():.2f}")

# View positions per book
for pos in desk.Positions():
    print(f"{pos.Symbol()}: {pos.Quantity()} @ ${pos.AvgPrice():.2f}")

# Show interactive dashboard
system.show()  # Opens browser with all books and positions
```

### Risk Analysis

The `risk` module provides numerical sensitivity calculations using bump-and-reval that work for any instrument, complementing the closed-form Greeks.

```python
from lattice import VanillaOption, Bond, risk

# Create an option
option = VanillaOption()
option.Spot.set(100.0)
option.Strike.set(100.0)
option.Volatility.set(0.20)
option.Rate.set(0.05)
option.TimeToExpiry.set(1.0)

# Numerical Greeks (work for ANY instrument)
print(f"Delta: {risk.delta(option):.4f}")      # ≈ option.Delta()
print(f"Gamma: {risk.gamma(option):.6f}")      # ≈ option.Gamma()
print(f"Vega:  {risk.vega(option):.4f}")       # ≈ option.Vega()
print(f"Theta: {risk.theta(option):.4f}")      # ≈ option.Theta()
print(f"Rho:   {risk.rho(option):.4f}")        # ≈ option.Rho()

# Bond risk metrics
bond = Bond()
bond.FaceValue.set(1000.0)
bond.CouponRate.set(0.05)
bond.YieldToMaturity.set(0.04)
bond.Maturity.set(10.0)

print(f"DV01: ${risk.dv01(bond):.2f}")         # Dollar value of 1bp yield change

# General sensitivity to any input
sens = risk.sensitivity(option, "Spot", "Price", bump=0.01)
```

#### Portfolio Risk

```python
from lattice.trading import TradingSystem
from lattice import risk

system = TradingSystem()
desk = system.book("OPTIONS_DESK")
client = system.book("CLIENT")

system.trade(desk, client, "AAPL_C_150", 100, 5.25)
system.trade(desk, client, "GOOGL_C_140", 50, 8.00)
system.set_market_price("AAPL_C_150", 5.50)
system.set_market_price("GOOGL_C_140", 7.50)

# Portfolio-level risk
print(f"Portfolio Delta: {risk.portfolio_delta(desk):.2f}")

# Portfolio exposure breakdown
exposure = risk.portfolio_exposure(desk)
print(f"Gross Exposure: ${exposure['gross_exposure']:,.2f}")
print(f"Long positions: {exposure['num_long']}")
```

#### Stress Testing

```python
# Apply stress scenarios to a portfolio
result = risk.stress(desk, spot_shock=-0.10, vol_shock=0.20)
print(f"Base P&L:     ${result['base_pnl']:,.2f}")
print(f"Stressed P&L: ${result['stressed_pnl']:,.2f}")
print(f"P&L Impact:   ${result['pnl_impact']:,.2f}")

# Run predefined scenarios
crash_result = risk.run_scenario(desk, "market_crash")  # -20% spot, +50% vol
hike_result = risk.run_scenario(desk, "rate_hike")      # +1% rates

# Run all predefined scenarios at once
all_results = risk.run_all_scenarios(desk)
for scenario, result in all_results.items():
    print(f"{scenario}: ${result['pnl_impact']:+,.2f}")

# Add custom scenarios
risk.add_scenario("my_stress", spot_shock=-0.15, vol_shock=0.30)
```

#### Value at Risk (VaR)

```python
# Parametric VaR using variance-covariance method
var_result = risk.parametric_var(desk, confidence=0.95, holding_period=1)
print(f"1-day 95% VaR: ${var_result['var']:,.2f}")
print(f"Expected Shortfall: ${var_result['expected_shortfall']:,.2f}")

# 10-day VaR for regulatory purposes
var_10d = risk.parametric_var(desk, confidence=0.99, holding_period=10)
print(f"10-day 99% VaR: ${var_10d['var']:,.2f}")

# VaR contribution by position
contributions = risk.var_contribution(desk)
for symbol, contrib in contributions.items():
    print(f"{symbol}: ${contrib:,.2f}")

# Full VaR report with matrix of confidence/holding period combinations
report = risk.var_report(desk)
```

#### RiskEngine for Batch Operations

```python
from lattice.risk import RiskEngine

engine = RiskEngine()

# Register multiple instruments
engine.add(option, "AAPL_C_150")
engine.add(bond, "UST_10Y")

# Compute all applicable Greeks at once
greeks = engine.compute_greeks()
# {'AAPL_C_150': {'delta': 0.53, 'gamma': 0.02, 'vega': 0.38, ...},
#  'UST_10Y': {'dv01': 85.23}}

# Stress test all instruments
results = engine.stress_test(Spot=-0.10)  # -10% spot shock
for name, impact in results.items():
    print(f"{name}: ${impact['price_impact']:,.2f}")
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
                         Your Code
    option.Spot.set(105) --> option.Price() --> Delta, Gamma...
    system.trade(...)    --> book.TotalPnL() --> Positions, P&L...
    risk.delta(option)   --> risk.stress(book) --> VaR, Scenarios...
                              |
                              v
    +-----------------------------------------------------------+
    |                       Lattice                             |
    |  Instruments: VanillaOption | Stock | Bond | FX | Forward |
    |  Trading:     Book | Trade | Position | TradingSystem     |
    |  Risk:        sensitivity | Greeks | stress | VaR         |
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

**dag** - Computation graphs with automatic dependency tracking, memoization, and scenarios. When you change `Spot`, only the dependent values (`Price`, `Delta`, etc.) are recomputed.

**livetable** - High-performance columnar tables. 25x faster iteration than pandas with zero-copy filtered views.

## API Reference

### Instruments

| Class | Description |
|-------|-------------|
| `VanillaOption` | European vanilla option with Black-Scholes pricing |
| `Stock` | Equity with price, dividend, and market cap |
| `Bond` | Fixed income with coupon, yield, duration, convexity |
| `Forward` | Forward contract with cost-of-carry pricing |
| `Future` | Exchange-traded futures contract |
| `FXPair` | Currency pair with spot and forward rates |
| `FXForward` | FX forward contract with interest rate parity |

### Trading (dag.Model-based)

| Class | Description |
|-------|-------------|
| `TradingSystem` | Orchestrator for books, trades, and positions |
| `Book` | Trading book with reactive P&L aggregation |
| `Trade` | Transaction between two books |
| `Position` | Position in a single instrument with P&L |

### Trading (livetable-based)

| Class | Description |
|-------|-------------|
| `PositionTable` | Fast position tracking with filtering |
| `TradeBlotter` | Trade recording and analysis |

### UI

| Function/Class | Description |
|----------------|-------------|
| `show(model)` | Quick display of any dag model |
| `DagApp` | Full-featured app with custom layouts |
| `bind(node, ...)` | Connect dag nodes to UI elements |
| `blotter.show()` | Interactive trade blotter dashboard |
| `positions.show()` | Interactive position table dashboard |
| `system.show()` | Trading system dashboard with all books |

### Greeks (Closed-Form)

Black-Scholes closed-form solutions on `VanillaOption`:

| Greek | Method | Description |
|-------|--------|-------------|
| Delta | `option.Delta()` | Rate of change of price w.r.t. spot |
| Gamma | `option.Gamma()` | Rate of change of delta w.r.t. spot |
| Vega | `option.Vega()` | Sensitivity to volatility (per 1% move) |
| Theta | `option.Theta()` | Time decay (per day) |
| Rho | `option.Rho()` | Sensitivity to interest rate (per 1% move) |

### Risk (Numerical Sensitivities)

General-purpose bump-and-reval functions that work for any instrument:

| Function | Description |
|----------|-------------|
| `risk.sensitivity(inst, input, output, bump)` | General sensitivity of any output to any input |
| `risk.delta(inst)` | dPrice/dSpot via bump-and-reval |
| `risk.gamma(inst)` | d²Price/dSpot² via central difference |
| `risk.vega(inst)` | Price change per 1% volatility move |
| `risk.theta(inst)` | Price change per day (time decay) |
| `risk.rho(inst)` | Price change per 1% rate move |
| `risk.dv01(bond)` | Dollar value of 1 basis point yield change |

### Risk (Portfolio)

Portfolio-level risk functions:

| Function | Description |
|----------|-------------|
| `risk.portfolio_delta(book)` | Aggregate delta exposure for a book |
| `risk.portfolio_exposure(book)` | Exposure breakdown (gross, long, short) |
| `risk.stress(book, spot_shock, vol_shock, rate_shock)` | Apply stress scenario, return P&L impact |

### Risk (Scenarios)

Predefined and custom stress scenarios:

| Function | Description |
|----------|-------------|
| `risk.run_scenario(book, name)` | Run a predefined scenario (e.g., "market_crash") |
| `risk.run_all_scenarios(book)` | Run all predefined scenarios |
| `risk.list_scenarios()` | List available scenarios with parameters |
| `risk.add_scenario(name, **shocks)` | Add a custom scenario |
| `risk.remove_scenario(name)` | Remove a custom scenario |

**Predefined Scenarios:**
- `market_crash` - 20% spot drop, 50% vol spike
- `rate_hike` - 1% rate increase
- `rate_cut` - 1% rate decrease
- `vol_spike` - 10% volatility increase
- `vol_crush` - 10% volatility decrease
- `flight_to_quality` - 10% spot drop, 0.5% rate decrease
- `risk_on` - 5% spot rally, 5% vol decrease
- `stagflation` - 5% spot drop, 2% rate increase

### Risk (VaR)

Value at Risk calculations using variance-covariance method:

| Function | Description |
|----------|-------------|
| `risk.parametric_var(book, confidence, holding_period)` | Compute VaR and Expected Shortfall |
| `risk.var_contribution(book)` | VaR contribution by position |
| `risk.var_report(book)` | Full VaR report with multiple confidence/period combinations |

### Risk (RiskEngine)

Batch operations across multiple instruments:

| Method | Description |
|--------|-------------|
| `engine.add(inst, name)` | Register an instrument |
| `engine.remove(name)` | Remove an instrument |
| `engine.clear()` | Remove all instruments |
| `engine.compute_greeks()` | Compute all applicable Greeks for registered instruments |
| `engine.stress_test(**shocks)` | Apply stress scenario to all instruments |

## License

MIT License - see [LICENSE](LICENSE) for details.
