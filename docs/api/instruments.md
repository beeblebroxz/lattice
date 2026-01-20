# Instruments API Reference

Financial instruments with reactive pricing and Greeks.

## VanillaOption

European vanilla option with Black-Scholes pricing.

```python
from lattice import VanillaOption

option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(105.0)
option.Volatility.set(0.20)
option.Rate.set(0.05)
option.TimeToExpiry.set(1.0)
option.IsCall.set(True)

print(f"Price: ${option.Price():.4f}")
print(f"Delta: {option.Delta():.4f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `Strike` | float | 100.0 | Strike price |
| `Spot` | float | 100.0 | Underlying spot price |
| `Volatility` | float | 0.20 | Annualized volatility (0.20 = 20%) |
| `Rate` | float | 0.05 | Risk-free interest rate |
| `TimeToExpiry` | float | 1.0 | Time to expiry in years |
| `IsCall` | bool | True | True for call, False for put |

### Outputs

| Field | Description |
|-------|-------------|
| `Price()` | Black-Scholes option price |
| `Delta()` | dPrice/dSpot |
| `Gamma()` | d²Price/dSpot² |
| `Vega()` | Price change per 1% vol move |
| `Theta()` | Price change per day |
| `Rho()` | Price change per 1% rate move |
| `D1()` | Black-Scholes d1 parameter |
| `D2()` | Black-Scholes d2 parameter |
| `IntrinsicValue()` | max(0, Spot - Strike) for calls |

## Stock

Equity with price, dividend, and market metrics.

```python
from lattice import Stock

stock = Stock()
stock.Symbol.set("AAPL")
stock.Price.set(150.0)
stock.Dividend.set(0.96)
stock.SharesOutstanding.set(15_000_000_000)

print(f"Yield: {stock.DividendYield():.2%}")
print(f"Market Cap: ${stock.MarketCap():,.0f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `Symbol` | str | "" | Ticker symbol |
| `Price` | float | 0.0 | Current price |
| `Dividend` | float | 0.0 | Annual dividend |
| `SharesOutstanding` | float | 0.0 | Shares outstanding |

### Outputs

| Field | Description |
|-------|-------------|
| `DividendYield()` | Dividend / Price |
| `MarketCap()` | Price * SharesOutstanding |

## Bond

Fixed income with coupon, yield, duration, and convexity.

```python
from lattice import Bond

bond = Bond()
bond.FaceValue.set(1000.0)
bond.CouponRate.set(0.05)
bond.YieldToMaturity.set(0.04)
bond.MaturityYears.set(10)
bond.Frequency.set(2)  # Semi-annual

print(f"Price: ${bond.Price():.2f}")
print(f"Duration: {bond.Duration():.2f} years")
print(f"Convexity: {bond.Convexity():.2f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `FaceValue` | float | 1000.0 | Par value |
| `CouponRate` | float | 0.05 | Annual coupon rate |
| `YieldToMaturity` | float | 0.05 | YTM |
| `MaturityYears` | float | 10.0 | Years to maturity |
| `Frequency` | int | 2 | Payments per year |

### Outputs

| Field | Description |
|-------|-------------|
| `Price()` | Present value of cash flows |
| `CouponPayment()` | Per-period coupon amount |
| `Duration()` | Macaulay duration |
| `ModifiedDuration()` | Duration / (1 + yield/freq) |
| `Convexity()` | Second derivative of price |

## Forward

Forward contract with cost-of-carry pricing.

```python
from lattice import Forward

forward = Forward()
forward.Spot.set(100.0)
forward.Rate.set(0.05)
forward.TimeToExpiry.set(1.0)
forward.DividendYield.set(0.02)

print(f"Forward Price: ${forward.ForwardPrice():.2f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `Spot` | float | 100.0 | Spot price |
| `Rate` | float | 0.05 | Risk-free rate |
| `TimeToExpiry` | float | 1.0 | Time to expiry |
| `DividendYield` | float | 0.0 | Continuous dividend yield |
| `ContractPrice` | float | 0.0 | Agreed forward price |

### Outputs

| Field | Description |
|-------|-------------|
| `ForwardPrice()` | Fair forward price |
| `Value()` | Current contract value |

## Future

Exchange-traded futures contract.

```python
from lattice import Future

future = Future()
future.Spot.set(100.0)
future.Rate.set(0.05)
future.TimeToExpiry.set(0.25)
future.ContractSize.set(100)

print(f"Futures Price: ${future.FuturesPrice():.2f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `Spot` | float | 100.0 | Spot price |
| `Rate` | float | 0.05 | Risk-free rate |
| `TimeToExpiry` | float | 1.0 | Time to expiry |
| `DividendYield` | float | 0.0 | Dividend yield |
| `StorageCost` | float | 0.0 | Storage cost rate |
| `ContractSize` | float | 1.0 | Contract multiplier |
| `ContractPrice` | float | 0.0 | Entry price |

### Outputs

| Field | Description |
|-------|-------------|
| `FuturesPrice()` | Fair futures price |
| `Value()` | Contract value |
| `NotionalValue()` | Full notional exposure |

## FXPair

Currency pair with spot and forward rates.

```python
from lattice import FXPair

eurusd = FXPair()
eurusd.BaseCurrency.set("EUR")
eurusd.QuoteCurrency.set("USD")
eurusd.Spot.set(1.0850)
eurusd.BaseRate.set(0.04)
eurusd.QuoteRate.set(0.05)

print(f"EUR/USD: {eurusd.Spot():.4f}")
print(f"1Y Forward: {eurusd.Forward(1.0):.4f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `BaseCurrency` | str | "EUR" | Base currency |
| `QuoteCurrency` | str | "USD" | Quote currency |
| `Spot` | float | 1.0 | Spot rate |
| `BaseRate` | float | 0.0 | Base currency interest rate |
| `QuoteRate` | float | 0.0 | Quote currency interest rate |

### Outputs

| Field | Description |
|-------|-------------|
| `Forward(T)` | Forward rate for tenor T |
| `ForwardPoints(T)` | Forward points for tenor T |

## FXForward

FX forward contract with interest rate parity pricing.

```python
from lattice import FXForward

fwd = FXForward()
fwd.BaseCurrency.set("EUR")
fwd.QuoteCurrency.set("USD")
fwd.Spot.set(1.0850)
fwd.BaseRate.set(0.04)
fwd.QuoteRate.set(0.05)
fwd.TimeToExpiry.set(1.0)
fwd.Notional.set(1_000_000)
fwd.ContractRate.set(1.0750)

print(f"Forward Rate: {fwd.ForwardRate():.4f}")
print(f"Value: ${fwd.Value():,.2f}")
```

### Inputs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `BaseCurrency` | str | "EUR" | Base currency |
| `QuoteCurrency` | str | "USD" | Quote currency |
| `Spot` | float | 1.0 | Spot rate |
| `BaseRate` | float | 0.0 | Base currency rate |
| `QuoteRate` | float | 0.0 | Quote currency rate |
| `TimeToExpiry` | float | 1.0 | Time to expiry |
| `Notional` | float | 1000000 | Notional in base currency |
| `ContractRate` | float | 0.0 | Agreed forward rate |

### Outputs

| Field | Description |
|-------|-------------|
| `ForwardRate()` | Fair forward rate |
| `ForwardPoints()` | Forward - Spot |
| `Value()` | Current contract value |

## Common Interface

All instruments inherit from `Instrument` and implement a polymorphic interface:

| Method | Description |
|--------|-------------|
| `Summary()` | Human-readable summary of key parameters |
| `MarketValue()` | Current market value of the instrument |

This enables generic portfolio code without type-checking:

```python
from lattice import VanillaOption, Bond, Forward
from lattice.instruments.fx import FXForward

portfolio = {
    "AAPL_C_155": VanillaOption(),
    "UST_10Y": Bond(),
    "GOLD_FWD": Forward(),
    "EURUSD_FWD": FXForward(),
}

# Generic iteration - no isinstance() needed
for name, inst in portfolio.items():
    print(f"{name}: {inst.Summary()} = ${inst.MarketValue():,.2f}")
```

**Output examples:**
| Instrument | `Summary()` | `MarketValue()` |
|------------|-------------|-----------------|
| VanillaOption | `"K=155 S=150 C"` | Option price |
| Bond | `"5% 10Y"` | Bond price |
| Forward | `"S=1900 F=1952.98"` | Contract value |
| FXForward | `"EUR/USD @ 1.0950"` | MTM value |

## Common Patterns

### Reactivity

All instruments automatically update when inputs change:

```python
option = VanillaOption()
option.Strike.set(100.0)
option.Spot.set(100.0)

price1 = option.Price()  # First calculation

option.Spot.set(105.0)   # Change input
price2 = option.Price()  # Automatically recalculated
```

### Scenario Analysis

Use `lattice.scenario()` for temporary overrides:

```python
import lattice

option = VanillaOption()
option.Spot.set(100.0)

base_price = option.Price()

with lattice.scenario():
    option.Spot.override(110.0)
    bumped_price = option.Price()
    print(f"Impact: ${bumped_price - base_price:.4f}")

# Spot automatically restored to 100.0
```

### Web UI

Display any instrument with `show()`:

```python
from lattice.ui import show

option = VanillaOption()
show(option)  # Opens browser with interactive UI
```
