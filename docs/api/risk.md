# Risk API Reference

Risk analysis including Greeks, stress testing, and VaR calculations.

## Numerical Greeks

General-purpose bump-and-reval functions that work for any instrument.

```python
from lattice import VanillaOption, risk

option = VanillaOption()
option.Spot.set(100.0)
option.Strike.set(100.0)
option.Volatility.set(0.20)

# Numerical Greeks
print(f"Delta: {risk.delta(option):.4f}")
print(f"Gamma: {risk.gamma(option):.6f}")
print(f"Vega:  {risk.vega(option):.4f}")
print(f"Theta: {risk.theta(option):.4f}")
print(f"Rho:   {risk.rho(option):.4f}")
```

### Functions

| Function | Description |
|----------|-------------|
| `risk.delta(inst, bump=0.01)` | dPrice/dSpot via central difference |
| `risk.gamma(inst, bump=0.01)` | d²Price/dSpot² |
| `risk.vega(inst, bump=0.01)` | Price change per 1% vol move |
| `risk.theta(inst, days=1)` | Price change per day |
| `risk.rho(inst, bump=0.0001)` | Price change per 1bp rate move |
| `risk.dv01(bond, bump=0.0001)` | Dollar value of 1bp yield change |

### General Sensitivity

```python
# Sensitivity of any output to any input
sens = risk.sensitivity(option, "Spot", "Price", bump=0.01)

# Custom outputs
delta_sens = risk.sensitivity(option, "Spot", "Delta", bump=0.01)
```

**Parameters:**
- `inst` - The instrument
- `input_name` - Name of input field to bump
- `output_name` - Name of output field to measure
- `bump` - Bump size (relative for prices, absolute for rates)

## Portfolio Risk

Aggregate risk metrics for trading books.

```python
from lattice.trading import TradingSystem
from lattice import risk

system = TradingSystem()
desk = system.book("OPTIONS_DESK")
client = system.book("CLIENT")

system.trade(desk, client, "AAPL_C_150", 100, 5.25)
system.set_market_price("AAPL_C_150", 5.50)

# Portfolio delta
print(f"Portfolio Delta: {risk.portfolio_delta(desk):.2f}")

# Full exposure breakdown
exposure = risk.portfolio_exposure(desk)
print(f"Gross Exposure: ${exposure['gross_exposure']:,.2f}")
print(f"Net Exposure: ${exposure['net_exposure']:,.2f}")
print(f"Long Exposure: ${exposure['long_exposure']:,.2f}")
print(f"Short Exposure: ${exposure['short_exposure']:,.2f}")
```

### Functions

| Function | Description |
|----------|-------------|
| `risk.portfolio_delta(book)` | Aggregate delta exposure |
| `risk.portfolio_exposure(book)` | Exposure breakdown dict |

## Stress Testing

Apply market shocks and measure P&L impact.

```python
# Basic stress test
result = risk.stress(desk, spot_shock=-0.10, vol_shock=0.20)
print(f"Base P&L: ${result['base_pnl']:,.2f}")
print(f"Stressed P&L: ${result['stressed_pnl']:,.2f}")
print(f"P&L Impact: ${result['pnl_impact']:,.2f}")
```

### `risk.stress(book, **shocks)`

Apply custom shocks to a portfolio.

**Shock Parameters:**
| Parameter | Description |
|-----------|-------------|
| `spot_shock` | Relative spot change (-0.10 = -10%) |
| `vol_shock` | Absolute vol change (0.05 = +5 vol points) |
| `rate_shock` | Absolute rate change (0.01 = +1%) |

**Returns:** Dict with `base_pnl`, `stressed_pnl`, `pnl_impact`

## Predefined Scenarios

```python
# Run a predefined scenario
crash_result = risk.run_scenario(desk, "market_crash")
print(f"Market Crash Impact: ${crash_result['pnl_impact']:,.2f}")

# Run all scenarios
all_results = risk.run_all_scenarios(desk)
for scenario, result in all_results.items():
    print(f"{scenario}: ${result['pnl_impact']:+,.2f}")

# List available scenarios
for name, params in risk.list_scenarios().items():
    print(f"{name}: {params}")
```

### Available Scenarios

| Scenario | Description |
|----------|-------------|
| `market_crash` | -20% spot, +50% vol |
| `rate_hike` | +1% rates |
| `rate_cut` | -1% rates |
| `vol_spike` | +10% vol |
| `vol_crush` | -10% vol |
| `flight_to_quality` | -10% spot, -0.5% rates |
| `risk_on` | +5% spot, -5% vol |
| `stagflation` | -5% spot, +2% rates |

### Custom Scenarios

```python
# Add custom scenario
risk.add_scenario("my_stress", spot_shock=-0.15, vol_shock=0.30)

# Run it
result = risk.run_scenario(desk, "my_stress")

# Remove it
risk.remove_scenario("my_stress")
```

## Value at Risk (VaR)

Parametric VaR using variance-covariance method.

```python
# Basic VaR
var_result = risk.parametric_var(desk, confidence=0.95, holding_period=1)
print(f"1-day 95% VaR: ${var_result['var']:,.2f}")
print(f"Expected Shortfall: ${var_result['expected_shortfall']:,.2f}")

# Regulatory VaR (10-day 99%)
var_10d = risk.parametric_var(desk, confidence=0.99, holding_period=10)
print(f"10-day 99% VaR: ${var_10d['var']:,.2f}")
```

### Functions

| Function | Description |
|----------|-------------|
| `risk.parametric_var(book, confidence, holding_period)` | Compute VaR |
| `risk.var_contribution(book)` | VaR contribution by position |
| `risk.var_report(book)` | Full report with multiple scenarios |

### VaR Result Fields

| Field | Description |
|-------|-------------|
| `var` | Value at Risk |
| `expected_shortfall` | Expected loss beyond VaR |
| `confidence` | Confidence level used |
| `holding_period` | Holding period in days |
| `portfolio_value` | Total portfolio value |

### VaR Contributions

```python
contributions = risk.var_contribution(desk)
for symbol, contrib in contributions.items():
    print(f"{symbol}: ${contrib:,.2f}")
```

### Full VaR Report

```python
report = risk.var_report(desk)
# Returns matrix of confidence levels × holding periods
```

## RiskEngine

Batch operations across multiple instruments.

```python
from lattice.risk import RiskEngine
from lattice import VanillaOption, Bond

engine = RiskEngine()

# Register instruments
option = VanillaOption()
option.Spot.set(100.0)
engine.add(option, "AAPL_C_150")

bond = Bond()
bond.YieldToMaturity.set(0.04)
engine.add(bond, "UST_10Y")

# Compute all Greeks
greeks = engine.compute_greeks()
# {'AAPL_C_150': {'delta': 0.53, 'gamma': 0.02, 'vega': 0.38, ...},
#  'UST_10Y': {'dv01': 85.23}}

# Stress test all
results = engine.stress_test(Spot=-0.10)
for name, impact in results.items():
    print(f"{name}: ${impact['price_impact']:,.2f}")
```

### Methods

| Method | Description |
|--------|-------------|
| `add(inst, name)` | Register an instrument |
| `remove(name)` | Remove an instrument |
| `clear()` | Remove all instruments |
| `compute_greeks()` | Compute all applicable Greeks |
| `stress_test(**shocks)` | Apply stress to all instruments |

## Example: Full Risk Workflow

```python
from lattice import VanillaOption, risk
from lattice.trading import TradingSystem
from lattice.risk import RiskEngine

# Setup portfolio
system = TradingSystem()
desk = system.book("OPTIONS_DESK")
client = system.book("CLIENT")

# Build positions
system.trade(desk, client, "AAPL_C_150", 100, 5.25)
system.trade(desk, client, "AAPL_P_145", -50, 3.00)
system.trade(desk, client, "GOOGL_C_140", 75, 8.00)

# Set market prices
system.set_market_price("AAPL_C_150", 5.50)
system.set_market_price("AAPL_P_145", 2.80)
system.set_market_price("GOOGL_C_140", 7.50)

# Portfolio metrics
print("=== Portfolio Risk ===")
print(f"Delta: {risk.portfolio_delta(desk):.2f}")

exposure = risk.portfolio_exposure(desk)
print(f"Gross Exposure: ${exposure['gross_exposure']:,.2f}")

# Stress tests
print("\n=== Stress Tests ===")
for scenario in ["market_crash", "vol_spike", "rate_hike"]:
    result = risk.run_scenario(desk, scenario)
    print(f"{scenario}: ${result['pnl_impact']:+,.2f}")

# VaR
print("\n=== Value at Risk ===")
var_result = risk.parametric_var(desk, confidence=0.95, holding_period=1)
print(f"1-day 95% VaR: ${var_result['var']:,.2f}")
print(f"Expected Shortfall: ${var_result['expected_shortfall']:,.2f}")

# Position-level VaR contribution
print("\n=== VaR Contributions ===")
for symbol, contrib in risk.var_contribution(desk).items():
    print(f"  {symbol}: ${contrib:,.2f}")
```

## Example Scripts

See the `examples/` directory for comprehensive risk demonstrations:

| Script | Description |
|--------|-------------|
| `greeks_deep_dive.py` | Compare analytic vs numerical Greeks, bump size sensitivity |
| `multi_instrument_risk.py` | Risk across Options, Bonds, Forwards, FX with RiskEngine |
| `sensitivity_analysis.py` | Manual bump-and-reval, forward vs central difference, sensitivity ladders |
| `bond_risk_analysis.py` | Duration, convexity, DV01 analysis with hedging examples |

```bash
python examples/greeks_deep_dive.py
python examples/multi_instrument_risk.py
python examples/sensitivity_analysis.py
python examples/bond_risk_analysis.py
```
