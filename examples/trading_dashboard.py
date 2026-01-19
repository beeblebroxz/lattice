#!/usr/bin/env python3
"""
Trading Dashboard - Web UI for TradeBlotter and PositionTable.

Displays trades and positions in a browser with real-time updates.

Usage:
    python examples/trading_dashboard.py
    Then open http://localhost:8080
"""

import asyncio
import json
from datetime import datetime
from aiohttp import web

from lattice import TradeBlotter, PositionTable


# Global state
blotter = TradeBlotter()
positions = PositionTable()


def update_positions():
    """Recalculate positions from trades."""
    global positions
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
            avg_price = abs(total_cost / qty)
            positions.add(symbol, quantity=qty, avg_price=avg_price)


async def handle_index(request):
    """Serve the main page."""
    return web.Response(text=HTML_PAGE, content_type="text/html")


async def handle_trades(request):
    """Get all trades as JSON."""
    trades = [
        {
            "trade_id": t["trade_id"],
            "timestamp": t["timestamp"],
            "symbol": t["symbol"],
            "side": t["side"],
            "quantity": t["quantity"],
            "price": t["price"],
            "notional": t["notional"],
        }
        for t in blotter
    ]
    return web.json_response(trades)


async def handle_positions(request):
    """Get all positions as JSON."""
    pos_list = [
        {
            "symbol": p["symbol"],
            "quantity": p["quantity"],
            "avg_price": p["avg_price"],
        }
        for p in positions
    ]
    return web.json_response(pos_list)


async def handle_add_trade(request):
    """Add a new trade."""
    data = await request.json()
    try:
        trade_id = blotter.record(
            symbol=data["symbol"],
            side=data["side"],
            quantity=int(data["quantity"]),
            price=float(data["price"]),
        )
        update_positions()
        return web.json_response({"success": True, "trade_id": trade_id})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=400)


async def handle_stats(request):
    """Get summary statistics."""
    total_notional = blotter.total_notional
    num_trades = len(blotter)
    num_positions = len(positions)
    num_buys = len(blotter.buys())
    num_sells = len(blotter.sells())

    return web.json_response({
        "total_notional": total_notional,
        "num_trades": num_trades,
        "num_positions": num_positions,
        "num_buys": num_buys,
        "num_sells": num_sells,
    })


HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>Lattice Trading Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }
        header {
            background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #333;
        }
        header h1 { font-weight: 500; color: #fff; }
        header h1 span { color: #4ecca3; }
        .container { padding: 20px 30px; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card .value { font-size: 28px; font-weight: 600; color: #4ecca3; }
        .stat-card .label { font-size: 12px; color: #888; margin-top: 5px; text-transform: uppercase; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
        .card {
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
        }
        .card-header {
            padding: 15px 20px;
            background: #0f3460;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-body { padding: 0; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; }
        th { background: rgba(0,0,0,0.2); font-size: 11px; text-transform: uppercase; color: #888; }
        tr:not(:last-child) td { border-bottom: 1px solid #333; }
        .buy { color: #4ecca3; }
        .sell { color: #ff6b6b; }
        .positive { color: #4ecca3; }
        .negative { color: #ff6b6b; }
        .form-row {
            display: flex;
            gap: 10px;
            padding: 15px 20px;
            background: rgba(0,0,0,0.2);
        }
        .form-row input, .form-row select {
            flex: 1;
            padding: 10px;
            border: 1px solid #333;
            border-radius: 4px;
            background: #1a1a2e;
            color: #eee;
            font-size: 14px;
        }
        .form-row input:focus, .form-row select:focus {
            outline: none;
            border-color: #4ecca3;
        }
        .form-row button {
            padding: 10px 20px;
            background: #4ecca3;
            color: #1a1a2e;
            border: none;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
        }
        .form-row button:hover { background: #3db892; }
        .empty { padding: 30px; text-align: center; color: #666; }
    </style>
</head>
<body>
    <header>
        <h1><span>Lattice</span> Trading Dashboard</h1>
    </header>
    <div class="container">
        <div class="stats" id="stats">
            <div class="stat-card"><div class="value" id="stat-trades">0</div><div class="label">Trades</div></div>
            <div class="stat-card"><div class="value" id="stat-positions">0</div><div class="label">Positions</div></div>
            <div class="stat-card"><div class="value" id="stat-buys">0</div><div class="label">Buys</div></div>
            <div class="stat-card"><div class="value" id="stat-sells">0</div><div class="label">Sells</div></div>
            <div class="stat-card"><div class="value" id="stat-notional">$0</div><div class="label">Total Notional</div></div>
        </div>
        <div class="grid">
            <div class="card">
                <div class="card-header">Trade Blotter</div>
                <div class="form-row">
                    <input type="text" id="symbol" placeholder="Symbol (e.g. AAPL_C_150)">
                    <select id="side">
                        <option value="BUY">BUY</option>
                        <option value="SELL">SELL</option>
                    </select>
                    <input type="number" id="quantity" placeholder="Qty" min="1">
                    <input type="number" id="price" placeholder="Price" step="0.01" min="0">
                    <button onclick="addTrade()">Add Trade</button>
                </div>
                <div class="card-body">
                    <table>
                        <thead><tr><th>ID</th><th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Notional</th></tr></thead>
                        <tbody id="trades-body"></tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <div class="card-header">Positions</div>
                <div class="card-body">
                    <table>
                        <thead><tr><th>Symbol</th><th>Quantity</th><th>Avg Price</th></tr></thead>
                        <tbody id="positions-body"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    <script>
        async function refresh() {
            // Fetch stats
            const stats = await fetch('/api/stats').then(r => r.json());
            document.getElementById('stat-trades').textContent = stats.num_trades;
            document.getElementById('stat-positions').textContent = stats.num_positions;
            document.getElementById('stat-buys').textContent = stats.num_buys;
            document.getElementById('stat-sells').textContent = stats.num_sells;
            document.getElementById('stat-notional').textContent = '$' + stats.total_notional.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

            // Fetch trades
            const trades = await fetch('/api/trades').then(r => r.json());
            const tradesBody = document.getElementById('trades-body');
            if (trades.length === 0) {
                tradesBody.innerHTML = '<tr><td colspan="7" class="empty">No trades yet. Add one above!</td></tr>';
            } else {
                tradesBody.innerHTML = trades.map(t => `
                    <tr>
                        <td>${t.trade_id}</td>
                        <td>${new Date(t.timestamp).toLocaleTimeString()}</td>
                        <td>${t.symbol}</td>
                        <td class="${t.side.toLowerCase()}">${t.side}</td>
                        <td>${t.quantity}</td>
                        <td>$${t.price.toFixed(2)}</td>
                        <td>$${t.notional.toFixed(2)}</td>
                    </tr>
                `).join('');
            }

            // Fetch positions
            const positions = await fetch('/api/positions').then(r => r.json());
            const posBody = document.getElementById('positions-body');
            if (positions.length === 0) {
                posBody.innerHTML = '<tr><td colspan="3" class="empty">No positions</td></tr>';
            } else {
                posBody.innerHTML = positions.map(p => `
                    <tr>
                        <td>${p.symbol}</td>
                        <td class="${p.quantity >= 0 ? 'positive' : 'negative'}">${p.quantity}</td>
                        <td>$${p.avg_price.toFixed(2)}</td>
                    </tr>
                `).join('');
            }
        }

        async function addTrade() {
            const symbol = document.getElementById('symbol').value.trim();
            const side = document.getElementById('side').value;
            const quantity = document.getElementById('quantity').value;
            const price = document.getElementById('price').value;

            if (!symbol || !quantity || !price) {
                alert('Please fill all fields');
                return;
            }

            const res = await fetch('/api/trades', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ symbol, side, quantity: parseInt(quantity), price: parseFloat(price) })
            });

            if (res.ok) {
                document.getElementById('symbol').value = '';
                document.getElementById('quantity').value = '';
                document.getElementById('price').value = '';
                refresh();
            } else {
                const err = await res.json();
                alert('Error: ' + err.error);
            }
        }

        // Initial load and auto-refresh
        refresh();
        setInterval(refresh, 2000);
    </script>
</body>
</html>
"""


def main():
    # Add some sample trades
    sample_trades = [
        ("AAPL_C_150_Jun24", "BUY", 10, 5.25),
        ("AAPL_C_150_Jun24", "BUY", 5, 5.50),
        ("GOOGL_C_140_Jul24", "BUY", 20, 8.00),
        ("MSFT_C_400_Jun24", "BUY", 15, 12.50),
    ]

    for symbol, side, qty, price in sample_trades:
        blotter.record(symbol, side, qty, price)

    update_positions()

    # Create web app
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/trades", handle_trades)
    app.router.add_get("/api/positions", handle_positions)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_post("/api/trades", handle_add_trade)

    print("Trading Dashboard running at http://localhost:8080")
    print("Press Ctrl+C to stop")
    web.run_app(app, host="localhost", port=8080, print=None)


if __name__ == "__main__":
    main()
