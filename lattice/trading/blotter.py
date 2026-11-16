"""Trade blotter using livetable."""

import re
from typing import Iterator, Callable, List, Optional
from datetime import datetime
import livetable

# Symbols that can be embedded in a livetable filter expression as-is.
_SIMPLE_SYMBOL = re.compile(r"^[A-Za-z0-9_.:/ -]+$")


class TradeBlotter:
    """
    Trade blotter backed by livetable for recording and querying trades.

    Example:
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150_Jun24", "BUY", 5, 5.25)
        blotter.record("AAPL_C_150_Jun24", "BUY", 5, 5.75)
        blotter.record("AAPL_P_145_Jun24", "SELL", 5, 3.20)

        for trade in blotter:
            print(f"{trade['side']} {trade['quantity']} {trade['symbol']}")
    """

    def __init__(self):
        """Create an empty trade blotter."""
        schema = livetable.Schema([
            ("trade_id", livetable.ColumnType.INT64, False),
            ("timestamp", livetable.ColumnType.STRING, False),  # ISO format
            ("symbol", livetable.ColumnType.STRING, False),
            ("side", livetable.ColumnType.STRING, False),  # "BUY" or "SELL"
            ("quantity", livetable.ColumnType.INT64, False),
            ("price", livetable.ColumnType.FLOAT64, False),
            ("notional", livetable.ColumnType.FLOAT64, False),
        ])
        self._table = livetable.Table("trades", schema)
        self._next_trade_id = 1

    def record(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """
        Record a trade.

        Args:
            symbol: Instrument identifier
            side: "BUY" or "SELL"
            quantity: Number of contracts
            price: Execution price
            timestamp: Trade time (defaults to now)

        Returns:
            Trade ID
        """
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be 'BUY' or 'SELL', got '{side}'")

        if timestamp is None:
            timestamp = datetime.now()

        trade_id = self._next_trade_id
        self._next_trade_id += 1

        self._table.append_row({
            "trade_id": trade_id,
            "timestamp": timestamp.isoformat(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "notional": quantity * price,
        })

        return trade_id

    def filter(self, predicate: Callable[[dict], bool]) -> "TradeBlotterView":
        """
        Filter trades by a predicate.

        Args:
            predicate: Function that takes a row dict and returns True to include.

        Returns:
            A view of filtered trades.
        """
        filtered = self._table.filter(predicate)
        return TradeBlotterView(filtered)

    def _where(self, expression: str) -> "TradeBlotterView":
        """Trades matching a livetable filter expression.

        The expression is evaluated in livetable itself, with no Python call
        per row, which is far faster than filter() with a lambda.
        """
        return TradeBlotterView(_Rows(self._table, self._table.filter_expr(expression)))

    def by_symbol(self, symbol: str) -> "TradeBlotterView":
        """Get all trades for a specific symbol."""
        if not _SIMPLE_SYMBOL.match(symbol):
            # Not safely quotable in a filter expression.
            return self.filter(lambda r: r["symbol"] == symbol)
        return self._where(f"symbol == '{symbol}'")

    def buys(self) -> "TradeBlotterView":
        """Get all buy trades."""
        return self._where("side == 'BUY'")

    def sells(self) -> "TradeBlotterView":
        """Get all sell trades."""
        return self._where("side == 'SELL'")

    def tail(self, n: int) -> List[dict]:
        """The most recent n trades, oldest first."""
        total = len(self._table)
        return [self._table[i] for i in range(max(0, total - n), total)]

    def __len__(self) -> int:
        """Return the number of trades."""
        return len(self._table)

    def __iter__(self) -> Iterator[dict]:
        """Iterate over all trades."""
        for i in range(len(self._table)):
            yield self._table[i]

    def __getitem__(self, index: int) -> dict:
        """Get a trade by index."""
        return self._table[index]

    @property
    def total_notional(self) -> float:
        """Total notional value of all trades."""
        return self._table.sum("notional")


    def show(
        self, port: int = 8080, open_browser: bool = True, max_rows: int = 1000
    ) -> None:
        """
        Display the trade blotter in a web browser.

        The page refreshes every second, so it shows only the most recent
        max_rows trades; the header still reports totals for all of them.

        Args:
            port: Server port (default 8080)
            open_browser: Whether to open browser automatically
            max_rows: Most recent trades to display

        Example:
            blotter = TradeBlotter()
            blotter.record("AAPL_C_150", "BUY", 10, 5.25)
            blotter.show()  # Opens browser with trade table
        """
        from .table_ui import run_table_ui

        columns = [
            {"key": "trade_id", "label": "ID"},
            {"key": "timestamp", "label": "Time"},
            {"key": "symbol", "label": "Symbol"},
            {"key": "side", "label": "Side", "format": "side"},
            {"key": "quantity", "label": "Qty", "format": "number"},
            {"key": "price", "label": "Price", "format": "currency"},
            {"key": "notional", "label": "Notional", "format": "currency"},
        ]

        def get_rows():
            return [
                {
                    "trade_id": t["trade_id"],
                    "timestamp": t["timestamp"],
                    "symbol": t["symbol"],
                    "side": t["side"],
                    "quantity": t["quantity"],
                    "price": t["price"],
                    "notional": t["notional"],
                }
                for t in self.tail(max_rows)
            ]

        def get_stats():
            return {
                "total_trades": len(self),
                "total_notional": f"${self.total_notional:,.2f}",
                "buys": len(self.buys()),
                "sells": len(self.sells()),
            }

        run_table_ui(
            title="Trade Blotter",
            columns=columns,
            get_rows=get_rows,
            get_stats=get_stats,
            port=port,
            open_browser=open_browser,
        )


class _Rows:
    """Selected rows of a table, by index: the minimal view interface."""

    def __init__(self, table, indices):
        self._table = table
        self._indices = indices

    def __len__(self) -> int:
        return len(self._indices)

    def __getitem__(self, index: int) -> dict:
        return self._table[self._indices[index]]


class TradeBlotterView:
    """Read-only view of filtered trades."""

    def __init__(self, view):
        self._view = view

    def __len__(self) -> int:
        return len(self._view)

    def __iter__(self) -> Iterator[dict]:
        for i in range(len(self._view)):
            yield self._view[i]

    def __getitem__(self, index: int) -> dict:
        return self._view[index]
