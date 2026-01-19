"""Combined Trading Dashboard - Trade Blotter + Position Table with live updates."""

import asyncio
import random
import webbrowser
from typing import Callable, List, Dict, Any, Optional
from aiohttp import web

from .blotter import TradeBlotter
from .positions import PositionTable


class TradingDashboard:
    """
    Combined dashboard showing TradeBlotter and PositionTable side by side.

    Supports live trade simulation for demos.

    Example:
        from lattice.trading import TradingDashboard

        dashboard = TradingDashboard()
        dashboard.record("AAPL_C_150", "BUY", 10, 5.25)
        dashboard.show()  # Opens browser with both views

        # Or with live simulation:
        dashboard.show(simulate=True)  # Adds random trades every second
    """

    def __init__(self):
        self.blotter = TradeBlotter()
        self.positions = PositionTable()

    def record(self, symbol: str, side: str, quantity: int, price: float) -> int:
        """Record a trade and update positions."""
        trade_id = self.blotter.record(symbol, side, quantity, price)
        self._update_positions()
        return trade_id

    def _update_positions(self) -> None:
        """Recalculate positions from all trades."""
        # Aggregate trades into positions
        position_map: Dict[str, Dict[str, float]] = {}

        for trade in self.blotter:
            symbol = trade["symbol"]
            qty = trade["quantity"] if trade["side"] == "BUY" else -trade["quantity"]
            cost = trade["notional"] if trade["side"] == "BUY" else -trade["notional"]

            if symbol not in position_map:
                position_map[symbol] = {"quantity": 0, "total_cost": 0}

            position_map[symbol]["quantity"] += qty
            position_map[symbol]["total_cost"] += cost

        # Rebuild position table
        self.positions = PositionTable()
        for symbol, data in position_map.items():
            qty = data["quantity"]
            if qty != 0:
                avg_price = abs(data["total_cost"] / qty)
                # Simulate market price (±10% from avg)
                market_price = avg_price * (1 + random.uniform(-0.1, 0.15))
                market_value = qty * market_price
                unrealized_pnl = market_value - (qty * avg_price)

                self.positions.add(
                    symbol,
                    quantity=int(qty),
                    avg_price=avg_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                )

    def show(
        self,
        port: int = 8080,
        open_browser: bool = True,
        simulate: bool = False,
        simulate_interval: float = 1.0,
    ) -> None:
        """
        Display the combined dashboard in a web browser.

        Args:
            port: Server port (default 8080)
            open_browser: Whether to open browser automatically
            simulate: If True, periodically add random trades
            simulate_interval: Seconds between simulated trades
        """
        app = self._create_app(simulate, simulate_interval)

        if open_browser:
            async def open_browser_task():
                await asyncio.sleep(0.5)
                webbrowser.open(f"http://localhost:{port}")

            async def on_startup(app):
                asyncio.create_task(open_browser_task())

            app.on_startup.append(on_startup)

        print(f"Trading Dashboard running at http://localhost:{port}")
        if simulate:
            print(f"Live simulation: adding trades every {simulate_interval}s")
        print("Press Ctrl+C to stop")
        web.run_app(app, host="localhost", port=port, print=None)

    def _create_app(self, simulate: bool, simulate_interval: float) -> web.Application:
        """Create the aiohttp application."""

        async def handle_index(request):
            return web.Response(text=self._generate_html(), content_type="text/html")

        async def handle_trades(request):
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
                for t in self.blotter
            ]
            return web.json_response(trades)

        async def handle_positions(request):
            positions = [
                {
                    "symbol": p["symbol"],
                    "quantity": p["quantity"],
                    "avg_price": p["avg_price"],
                    "market_value": p["market_value"],
                    "unrealized_pnl": p["unrealized_pnl"],
                }
                for p in self.positions
            ]
            return web.json_response(positions)

        async def handle_stats(request):
            total_pnl = sum(p["unrealized_pnl"] or 0 for p in self.positions)
            return web.json_response({
                "total_trades": len(self.blotter),
                "total_notional": self.blotter.total_notional,
                "num_positions": len(self.positions),
                "buys": len(self.blotter.buys()),
                "sells": len(self.blotter.sells()),
                "total_pnl": total_pnl,
            })

        app = web.Application()
        app.router.add_get("/", handle_index)
        app.router.add_get("/api/trades", handle_trades)
        app.router.add_get("/api/positions", handle_positions)
        app.router.add_get("/api/stats", handle_stats)

        if simulate:
            async def simulate_trades():
                symbols = [
                    "AAPL_C_150_Jun24", "AAPL_P_145_Jun24",
                    "GOOGL_C_140_Jul24", "MSFT_C_400_Jun24",
                    "TSLA_C_250_Jun24", "NVDA_C_500_Jul24",
                ]
                while True:
                    await asyncio.sleep(simulate_interval)
                    symbol = random.choice(symbols)
                    side = random.choice(["BUY", "SELL"])
                    qty = random.randint(1, 20)
                    price = random.uniform(3.0, 15.0)
                    self.record(symbol, side, qty, round(price, 2))

            async def start_simulation(app):
                asyncio.create_task(simulate_trades())

            app.on_startup.append(start_simulation)

        return app

    def _generate_html(self) -> str:
        """Generate the combined dashboard HTML."""
        return """<!DOCTYPE html>
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
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        header h1 { font-weight: 500; color: #fff; }
        header h1 span { color: #4ecca3; }
        .live-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #4ecca3;
            font-size: 14px;
        }
        .live-dot {
            width: 8px;
            height: 8px;
            background: #4ecca3;
            border-radius: 50%;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .container { padding: 20px 30px; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: #16213e;
            padding: 18px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card .value { font-size: 24px; font-weight: 600; color: #4ecca3; }
        .stat-card .label { font-size: 11px; color: #888; margin-top: 5px; text-transform: uppercase; }
        .stat-card.pnl-positive .value { color: #4ecca3; }
        .stat-card.pnl-negative .value { color: #ff6b6b; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
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
        .card-header .count {
            background: rgba(78, 204, 163, 0.2);
            color: #4ecca3;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
        }
        .card-body { max-height: 400px; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; font-size: 13px; }
        th { background: rgba(0,0,0,0.2); font-size: 10px; text-transform: uppercase; color: #888; position: sticky; top: 0; }
        tr:not(:last-child) td { border-bottom: 1px solid #333; }
        .buy { color: #4ecca3; }
        .sell { color: #ff6b6b; }
        .positive { color: #4ecca3; }
        .negative { color: #ff6b6b; }
        .empty { padding: 30px; text-align: center; color: #666; }
        tr.new-row { animation: highlight 1s ease-out; }
        @keyframes highlight {
            from { background: rgba(78, 204, 163, 0.3); }
            to { background: transparent; }
        }
    </style>
</head>
<body>
    <header>
        <h1><span>Lattice</span> Trading Dashboard</h1>
        <div class="live-indicator">
            <div class="live-dot"></div>
            <span>LIVE</span>
        </div>
    </header>
    <div class="container">
        <div class="stats" id="stats">
            <div class="stat-card"><div class="value" id="stat-trades">0</div><div class="label">Trades</div></div>
            <div class="stat-card"><div class="value" id="stat-positions">0</div><div class="label">Positions</div></div>
            <div class="stat-card"><div class="value" id="stat-buys">0</div><div class="label">Buys</div></div>
            <div class="stat-card"><div class="value" id="stat-sells">0</div><div class="label">Sells</div></div>
            <div class="stat-card"><div class="value" id="stat-notional">$0</div><div class="label">Total Notional</div></div>
            <div class="stat-card" id="pnl-card"><div class="value" id="stat-pnl">$0</div><div class="label">Unrealized P&L</div></div>
        </div>
        <div class="grid">
            <div class="card">
                <div class="card-header">
                    Trade Blotter
                    <span class="count" id="trade-count">0</span>
                </div>
                <div class="card-body">
                    <table>
                        <thead><tr><th>ID</th><th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Notional</th></tr></thead>
                        <tbody id="trades-body"></tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    Positions
                    <span class="count" id="position-count">0</span>
                </div>
                <div class="card-body">
                    <table>
                        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg Price</th><th>Mkt Value</th><th>P&L</th></tr></thead>
                        <tbody id="positions-body"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    <script>
        let lastTradeCount = 0;

        async function refresh() {
            // Fetch stats
            const stats = await fetch('/api/stats').then(r => r.json());
            document.getElementById('stat-trades').textContent = stats.total_trades;
            document.getElementById('stat-positions').textContent = stats.num_positions;
            document.getElementById('stat-buys').textContent = stats.buys;
            document.getElementById('stat-sells').textContent = stats.sells;
            document.getElementById('stat-notional').textContent = '$' + stats.total_notional.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

            const pnl = stats.total_pnl;
            const pnlStr = (pnl >= 0 ? '+' : '') + '$' + pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            document.getElementById('stat-pnl').textContent = pnlStr;
            const pnlCard = document.getElementById('pnl-card');
            pnlCard.className = 'stat-card ' + (pnl >= 0 ? 'pnl-positive' : 'pnl-negative');

            document.getElementById('trade-count').textContent = stats.total_trades;
            document.getElementById('position-count').textContent = stats.num_positions;

            // Fetch trades
            const trades = await fetch('/api/trades').then(r => r.json());
            const tradesBody = document.getElementById('trades-body');
            const newTradeCount = trades.length;

            if (trades.length === 0) {
                tradesBody.innerHTML = '<tr><td colspan="7" class="empty">No trades yet</td></tr>';
            } else {
                // Show most recent trades first
                const reversedTrades = [...trades].reverse();
                tradesBody.innerHTML = reversedTrades.map((t, idx) => {
                    const isNew = idx < (newTradeCount - lastTradeCount) && lastTradeCount > 0;
                    return `
                    <tr class="${isNew ? 'new-row' : ''}">
                        <td>${t.trade_id}</td>
                        <td>${new Date(t.timestamp).toLocaleTimeString()}</td>
                        <td>${t.symbol}</td>
                        <td class="${t.side.toLowerCase()}">${t.side}</td>
                        <td>${t.quantity}</td>
                        <td>$${t.price.toFixed(2)}</td>
                        <td>$${t.notional.toFixed(2)}</td>
                    </tr>
                `}).join('');
            }
            lastTradeCount = newTradeCount;

            // Fetch positions
            const positions = await fetch('/api/positions').then(r => r.json());
            const posBody = document.getElementById('positions-body');
            if (positions.length === 0) {
                posBody.innerHTML = '<tr><td colspan="5" class="empty">No positions</td></tr>';
            } else {
                posBody.innerHTML = positions.map(p => {
                    const qtyClass = p.quantity >= 0 ? 'positive' : 'negative';
                    const pnl = p.unrealized_pnl || 0;
                    const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                    const pnlStr = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                    const mvStr = p.market_value ? '$' + p.market_value.toFixed(2) : '-';
                    return `
                    <tr>
                        <td>${p.symbol}</td>
                        <td class="${qtyClass}">${p.quantity}</td>
                        <td>$${p.avg_price.toFixed(2)}</td>
                        <td>${mvStr}</td>
                        <td class="${pnlClass}">${pnlStr}</td>
                    </tr>
                `}).join('');
            }
        }

        refresh();
        setInterval(refresh, 500);  // Fast refresh for live feel
    </script>
</body>
</html>
"""
