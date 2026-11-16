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
| `book(book_id, name=None, book_type="trading", parent_book_id="")` | Create or get a book |
| `trade(buyer, seller, symbol, quantity, price)` | Execute a trade between books (see validation below) |
| `set_market_price(symbol, price)` | Set market price for P&L calculation |
| `get_market_price(symbol)` | Get current market price |
| `register_instrument(symbol, inst)` | Back a symbol with a live instrument (reactive pricing) |
| `show()` | Open interactive dashboard |

`trade()` raises `ValueError`, before recording anything, for a quantity that
is not a positive integer, a price that is not a finite number, an empty
symbol, a book that was not created by this system, or the same book on both
sides. Negative prices are allowed (spreads and swaps trade at them).

### Properties

| Property | Description |
|----------|-------------|
| `books` | List of all books |
| `trades` | List of all trades |

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
| `BookId` | str | Unique identifier |
| `Name` | str | Human-readable name (defaults to the id) |
| `BookType` | str | "trading", "customer", etc. |
| `ParentBookId` | str | Parent book id (stored; no roll-up yet) |

### Outputs

| Field | Description |
|-------|-------------|
| `Positions()` | Open (non-flat) Position objects |
| `AllPositions()` | Every position the book has held, including flat ones |
| `TotalPnL()` | Realized plus unrealized P&L |
| `UnrealizedPnL()` | Mark-to-market P&L on open positions |
| `RealizedPnL()` | P&L locked in by reducing, closing or flipping positions |
| `NetExposure()` / `GrossExposure()` | Signed / absolute sum of position market values |
| `LongExposure()` / `ShortExposure()` | Market value of long / short positions |
| `Delta()` / `Vega()` / `Gamma()` | Portfolio Greeks (sum of the position Greeks below) |

## Trade

A transaction between two books.

```python
# Trades are created via system.trade()
system.trade(buyer=desk, seller=client, symbol="AAPL_C_150", quantity=10, price=5.25)

# Access trade details
for trade in system.trades:
    print(f"{trade.Symbol()}: {trade.Quantity()} @ ${trade.Price():.2f}")
```

### Fields

| Field | Description |
|-------|-------------|
| `Symbol()` | Instrument symbol |
| `Quantity()` | Trade quantity |
| `Price()` | Execution price |
| `BuyerBookId()` | Id of the buying book |
| `SellerBookId()` | Id of the selling book |
| `Timestamp()` | Execution timestamp |

## Position

Position in a single instrument with P&L calculation.

```python
for pos in desk.Positions():
    print(f"Symbol: {pos.Symbol()}")
    print(f"Quantity: {pos.Quantity()}")
    print(f"Avg Price: ${pos.AvgPrice():.2f}")
    print(f"Market Price: ${pos.MarketPrice():.2f}")
    print(f"Unrealized P&L: ${pos.UnrealizedPnL():.2f}")
    print(f"Realized P&L: ${pos.RealizedPnL():.2f}")
```

### Fields

| Field | Description |
|-------|-------------|
| `Symbol()` | Instrument symbol |
| `Quantity()` | Net position quantity |
| `AvgPrice()` | Average entry price |
| `MarketPrice()` | Current market price |
| `MarketValue()` | Quantity × per-unit price (the linked instrument's value if there is one, else `MarketPrice`) |
| `CostBasis()` | abs(Quantity) × AvgPrice |
| `UnrealizedPnL()` | MarketValue − Quantity × AvgPrice |
| `RealizedPnL()` | P&L realized by trades that reduced, closed or flipped the position |
| `TotalPnL()` | Realized plus unrealized |
| `Delta()` / `Gamma()` / `Vega()` | Quantity × the linked instrument's Greek (0 if there is no instrument, or it lacks the input) |
| `Greeks()` | The three above as a dict, computed together |

Position Greeks are cached: after a tick on one instrument, only positions in
that instrument are revalued, and a book's Greeks are a sum over cached values.

Adding to a position re-averages `AvgPrice`. Reducing it keeps `AvgPrice` and
realizes `closed quantity × (trade price − AvgPrice)` (sign reversed for a
short). Trading through zero realizes the whole old position and opens the
remainder at the trade price. Because every trade has two sides,
`system.total_pnl()` is zero for symbols marked at a single price.

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
aapl = positions.get("AAPL_C_150")
print(f"AAPL qty: {aapl['quantity']}")

# Indexing is positional (by row), not by symbol
first = positions[0]
```

### Methods

| Method | Description |
|--------|-------------|
| `add(symbol, quantity, avg_price)` | Add or update a position (in place) |
| `get(symbol)` | Get position by symbol (or `None`) |
| `remove(symbol)` | Remove a position by symbol |
| `filter(predicate)` | Create a filtered view |
| `show()` | Open interactive dashboard |

### Properties

| Property | Description |
|----------|-------------|
| `symbols` | List of all symbols |
| `total_market_value` | Sum of position market values |
| `total_unrealized_pnl` | Sum of unrealized P&L across positions |

### Instrument-linked positions

A position can derive its value from a live instrument instead of a static
price. Register the instrument on the system; positions in that symbol reprice
reactively as the instrument's inputs change:

```python
opt = VanillaOption(); opt.Spot.set(100.0); opt.Strike.set(100.0)
system.register_instrument("AAPL_C_150", opt)
system.trade(desk, client, "AAPL_C_150", 10, opt.MarketValue())

opt.Spot.set(110.0)        # the position and book reprice automatically
desk.Delta()               # portfolio delta from the linked instrument
```

For a linked symbol, drive the market through the instrument's inputs;
`set_market_price` raises for linked symbols.

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
print(f"Total notional: ${blotter.total_notional:,.2f}")  # property
print(f"Buy trades: {len(blotter.buys())}")
print(f"Sell trades: {len(blotter.sells())}")

# Filter by symbol
aapl_trades = blotter.by_symbol("AAPL_C_150")

# Show dashboard
blotter.show()
```

### Methods

| Method | Description |
|--------|-------------|
| `record(symbol, side, quantity, price)` | Record a trade |
| `by_symbol(symbol)` | Filter trades by symbol |
| `buys()` | Filter to buy trades |
| `sells()` | Filter to sell trades |
| `filter(predicate)` | Create a filtered view (calls the predicate per row; slower than the three above on large blotters) |
| `tail(n)` | The most recent n trades |
| `show(max_rows=1000)` | Open the blotter in a browser, showing the most recent `max_rows` trades |

### Properties

| Property | Description |
|----------|-------------|
| `total_notional` | Sum of quantity × price across all trades |

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
          f"(P&L: ${pos.TotalPnL():.2f})")

# Market moves - P&L updates automatically
system.set_market_price("AAPL_C_150", 6.00)
print(f"\nAfter AAPL rally: ${mm.TotalPnL():.2f}")

# Interactive dashboard
system.show()
```
