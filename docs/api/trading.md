# Trading API Reference

Trading system with books, trades, positions, and real-time P&L.

## TradingSystem

Orchestrator for books, trades, and market prices.

```python
from lattice.trading import TradingSystem

system = TradingSystem()

# Create books
desk = system.book("MARKET_MAKER", book_type="trading")
client = system.book("CLIENT_ABC", book_type="customer")

# Execute trades
system.trade(buyer=desk, seller=client, symbol="AAPL_C_150", quantity=10, price=5.25)

# Set market prices for P&L
system.set_market_price("AAPL_C_150", 5.50)

# View P&L
print(f"Desk P&L: ${desk.TotalPnL():.2f}")
```

### Methods

| Method | Description |
|--------|-------------|
| `book(name, book_type="trading")` | Create or get a book |
| `trade(buyer, seller, symbol, quantity, price)` | Execute a trade between books |
| `set_market_price(symbol, price)` | Set market price for P&L calculation |
| `get_market_price(symbol)` | Get current market price |
| `show()` | Open interactive dashboard |

### Properties

| Property | Description |
|----------|-------------|
| `Books()` | Dict of all books |
| `Trades()` | List of all trades |

## Book

Trading book with reactive P&L aggregation.

```python
desk = system.book("MARKET_MAKER")

# Access positions
for pos in desk.Positions():
    print(f"{pos.Symbol()}: {pos.Quantity()} @ ${pos.AvgPrice():.2f}")

# P&L updates automatically when market prices change
print(f"Total P&L: ${desk.TotalPnL():.2f}")
```

### Inputs

| Field | Type | Description |
|-------|------|-------------|
| `Name` | str | Book name/identifier |
| `BookType` | str | "trading", "customer", etc. |

### Outputs

| Field | Description |
|-------|-------------|
| `Positions()` | List of Position objects |
| `TotalPnL()` | Sum of all position P&L |
| `TotalMarketValue()` | Sum of all position market values |

## Trade

A transaction between two books.

```python
# Trades are created via system.trade()
system.trade(buyer=desk, seller=client, symbol="AAPL_C_150", quantity=10, price=5.25)

# Access trade details
for trade in system.Trades():
    print(f"{trade.Symbol()}: {trade.Quantity()} @ ${trade.Price():.2f}")
```

### Fields

| Field | Description |
|-------|-------------|
| `Symbol()` | Instrument symbol |
| `Quantity()` | Trade quantity |
| `Price()` | Execution price |
| `Buyer()` | Buying book |
| `Seller()` | Selling book |
| `Timestamp()` | Execution timestamp |

## Position

Position in a single instrument with P&L calculation.

```python
for pos in desk.Positions():
    print(f"Symbol: {pos.Symbol()}")
    print(f"Quantity: {pos.Quantity()}")
    print(f"Avg Price: ${pos.AvgPrice():.2f}")
    print(f"Market Price: ${pos.MarketPrice():.2f}")
    print(f"P&L: ${pos.PnL():.2f}")
```

### Fields

| Field | Description |
|-------|-------------|
| `Symbol()` | Instrument symbol |
| `Quantity()` | Net position quantity |
| `AvgPrice()` | Average entry price |
| `MarketPrice()` | Current market price |
| `MarketValue()` | Quantity * MarketPrice |
| `Cost()` | Quantity * AvgPrice |
| `PnL()` | MarketValue - Cost |

## PositionTable (livetable-based)

Fast position tracking using livetable (25x faster than pandas).

```python
from lattice import PositionTable

positions = PositionTable()

# Add positions
positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
positions.add("AAPL_P_145", quantity=-5, avg_price=3.20)
positions.add("GOOGL_C_140", quantity=20, avg_price=8.00)

# Iterate
for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} @ ${pos['avg_price']:.2f}")

# Filter (zero-copy views)
long_positions = positions.filter(lambda r: r["quantity"] > 0)
short_positions = positions.filter(lambda r: r["quantity"] < 0)

# Access by symbol
aapl = positions["AAPL_C_150"]
print(f"AAPL qty: {aapl['quantity']}")
```

### Methods

| Method | Description |
|--------|-------------|
| `add(symbol, quantity, avg_price)` | Add or update a position |
| `get(symbol)` | Get position by symbol |
| `filter(predicate)` | Create filtered view |
| `show()` | Open interactive dashboard |

### Properties

| Property | Description |
|----------|-------------|
| `symbols` | List of all symbols |
| `long()` | Filter to long positions |
| `short()` | Filter to short positions |

## TradeBlotter

Trade recording and analysis using livetable.

```python
from lattice import TradeBlotter

blotter = TradeBlotter()

# Record trades
blotter.record("AAPL_C_150", "BUY", 5, 5.25)
blotter.record("AAPL_C_150", "BUY", 5, 5.75)
blotter.record("AAPL_P_145", "SELL", 5, 3.20)

# Analysis
print(f"Total notional: ${blotter.total_notional():,.2f}")
print(f"Buy trades: {len(blotter.buys())}")
print(f"Sell trades: {len(blotter.sells())}")

# Filter by symbol
aapl_trades = blotter.filter_by_symbol("AAPL_C_150")

# Show dashboard
blotter.show()
```

### Methods

| Method | Description |
|--------|-------------|
| `record(symbol, side, quantity, price)` | Record a trade |
| `filter_by_symbol(symbol)` | Filter trades by symbol |
| `buys()` | Filter to buy trades |
| `sells()` | Filter to sell trades |
| `total_notional()` | Sum of quantity * price |
| `show()` | Open interactive dashboard |

## Example: Full Trading Workflow

```python
from lattice.trading import TradingSystem

# Setup
system = TradingSystem()
mm = system.book("MARKET_MAKER", book_type="trading")
client = system.book("CLIENT_A", book_type="customer")

# Execute trades
system.trade(mm, client, "AAPL_C_150", 100, 5.25)
system.trade(mm, client, "GOOGL_C_140", 50, 8.00)
system.trade(client, mm, "AAPL_C_150", 30, 5.50)  # Partial close

# Set market prices
system.set_market_price("AAPL_C_150", 5.75)
system.set_market_price("GOOGL_C_140", 7.50)

# Check P&L
print(f"Market Maker P&L: ${mm.TotalPnL():.2f}")
print(f"Client P&L: ${client.TotalPnL():.2f}")

# Position details
print("\nMarket Maker Positions:")
for pos in mm.Positions():
    print(f"  {pos.Symbol()}: {pos.Quantity()} @ ${pos.AvgPrice():.2f} "
          f"(P&L: ${pos.PnL():.2f})")

# Market moves - P&L updates automatically
system.set_market_price("AAPL_C_150", 6.00)
print(f"\nAfter AAPL rally: ${mm.TotalPnL():.2f}")

# Interactive dashboard
system.show()
```
