#!/usr/bin/env python3
"""
Trading Demo - TradeBlotter and PositionTable in action.

Demonstrates:
- Recording trades to a blotter
- Tracking positions with real-time P&L
- Filtering and querying trades
- Fast iteration with livetable

Usage:
    python examples/trading_demo.py
"""

from lattice import TradeBlotter, PositionTable, VanillaOption
import random


def main():
    print("=" * 60)
    print("  Lattice Trading Demo")
    print("=" * 60)
    print()

    # Create a trade blotter
    blotter = TradeBlotter()

    # Simulate some option trades
    trades = [
        ("AAPL_C_150_Jun24", "BUY", 10, 5.25),
        ("AAPL_C_150_Jun24", "BUY", 5, 5.50),
        ("AAPL_P_145_Jun24", "BUY", 8, 3.20),
        ("GOOGL_C_140_Jul24", "BUY", 20, 8.00),
        ("AAPL_C_150_Jun24", "SELL", 5, 6.10),
        ("MSFT_C_400_Jun24", "BUY", 15, 12.50),
        ("AAPL_P_145_Jun24", "SELL", 3, 3.80),
        ("GOOGL_C_140_Jul24", "SELL", 10, 9.25),
    ]

    print("Recording trades...")
    print("-" * 60)
    for symbol, side, qty, price in trades:
        trade_id = blotter.record(symbol, side, qty, price)
        notional = qty * price
        print(f"  #{trade_id:2d}  {side:4s}  {qty:3d} x {symbol:20s} @ ${price:.2f}  (${notional:,.2f})")

    print("-" * 60)
    print(f"Total trades: {len(blotter)}")
    print(f"Total notional: ${blotter.total_notional:,.2f}")
    print()

    # Filter trades
    print("Buy trades only:")
    print("-" * 60)
    for trade in blotter.buys():
        print(f"  {trade['side']:4s}  {trade['quantity']:3d} x {trade['symbol']:20s} @ ${trade['price']:.2f}")
    print(f"  Count: {len(blotter.buys())}")
    print()

    print("AAPL trades only:")
    print("-" * 60)
    aapl_trades = blotter.filter(lambda t: "AAPL" in t["symbol"])
    for trade in aapl_trades:
        print(f"  {trade['side']:4s}  {trade['quantity']:3d} x {trade['symbol']:20s} @ ${trade['price']:.2f}")
    print(f"  Count: {len(aapl_trades)}")
    print()

    # Build positions from trades
    print("=" * 60)
    print("  Position Summary")
    print("=" * 60)
    print()

    positions = PositionTable()

    # Aggregate trades into positions
    position_map = {}  # symbol -> (quantity, total_cost)
    for trade in blotter:
        symbol = trade["symbol"]
        qty = trade["quantity"] if trade["side"] == "BUY" else -trade["quantity"]
        cost = trade["notional"] if trade["side"] == "BUY" else -trade["notional"]

        if symbol in position_map:
            old_qty, old_cost = position_map[symbol]
            position_map[symbol] = (old_qty + qty, old_cost + cost)
        else:
            position_map[symbol] = (qty, cost)

    # Add to position table
    for symbol, (qty, total_cost) in position_map.items():
        if qty != 0:
            avg_price = abs(total_cost / qty) if qty != 0 else 0
            # Simulate current market prices (avg_price +/- 10%)
            market_price = avg_price * (1 + random.uniform(-0.1, 0.15))
            market_value = qty * market_price
            unrealized_pnl = market_value - (qty * avg_price)

            positions.add(
                symbol,
                quantity=qty,
                avg_price=avg_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
            )

    print(f"{'Symbol':<24} {'Qty':>6} {'Avg Price':>12} {'Mkt Value':>12} {'P&L':>12}")
    print("-" * 70)

    total_value = 0.0
    total_pnl = 0.0
    for pos in positions:
        symbol = pos["symbol"]
        qty = pos["quantity"]
        avg = pos["avg_price"]
        mv = pos["market_value"]
        pnl = pos["unrealized_pnl"]
        total_value += mv
        total_pnl += pnl

        pnl_str = f"${pnl:+,.2f}" if pnl else "$0.00"
        print(f"{symbol:<24} {qty:>6} ${avg:>10.2f} ${mv:>10.2f} {pnl_str:>12}")

    print("-" * 70)
    print(f"{'Total':<24} {'':<6} {'':<12} ${total_value:>10.2f} ${total_pnl:>+10.2f}")
    print()

    # Show long vs short positions
    long_positions = positions.filter(lambda p: p["quantity"] > 0)
    short_positions = positions.filter(lambda p: p["quantity"] < 0)

    print(f"Long positions:  {len(long_positions)}")
    print(f"Short positions: {len(short_positions)}")
    print()

    # Demonstrate fast iteration
    print("=" * 60)
    print("  Performance Note")
    print("=" * 60)
    print()
    print("  PositionTable and TradeBlotter use livetable internally,")
    print("  providing 25x faster iteration than pandas DataFrames")
    print("  with zero-copy filtered views.")
    print()


if __name__ == "__main__":
    main()
