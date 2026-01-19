"""Position tracking using livetable."""

from typing import Iterator, Optional, Callable, Any
import livetable
import numpy as np


class PositionTable:
    """
    Position table backed by livetable for fast iteration and filtering.

    Example:
        positions = PositionTable()
        positions.add("AAPL_C_150_Jun24", quantity=10, avg_price=5.50)
        positions.add("AAPL_P_145_Jun24", quantity=-5, avg_price=3.20)

        for pos in positions:
            print(f"{pos['symbol']}: {pos['quantity']} @ {pos['avg_price']}")

        long_positions = positions.filter(lambda r: r["quantity"] > 0)
    """

    def __init__(self):
        """Create an empty position table."""
        schema = livetable.Schema([
            ("symbol", livetable.ColumnType.STRING, False),
            ("quantity", livetable.ColumnType.INT64, False),
            ("avg_price", livetable.ColumnType.FLOAT64, False),
            ("market_value", livetable.ColumnType.FLOAT64, True),
            ("unrealized_pnl", livetable.ColumnType.FLOAT64, True),
        ])
        self._table = livetable.Table("positions", schema)
        self._symbol_to_row: dict[str, int] = {}

    def add(
        self,
        symbol: str,
        quantity: int,
        avg_price: float,
        market_value: Optional[float] = None,
        unrealized_pnl: Optional[float] = None,
    ) -> None:
        """
        Add or update a position.

        Args:
            symbol: Position identifier (e.g., "AAPL_C_150_Jun24")
            quantity: Number of contracts (positive=long, negative=short)
            avg_price: Average entry price
            market_value: Current market value (optional)
            unrealized_pnl: Unrealized P&L (optional)
        """
        if symbol in self._symbol_to_row:
            # Update existing position by deleting and re-adding
            # (workaround for livetable int type inference issue)
            row_idx = self._symbol_to_row[symbol]
            self._table.delete_row(row_idx)
            self._table.append_row({
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": avg_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
            })
            self._rebuild_index()
        else:
            # Add new position
            self._table.append_row({
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": avg_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
            })
            self._symbol_to_row[symbol] = len(self._table) - 1

    def get(self, symbol: str) -> Optional[dict]:
        """Get a position by symbol."""
        if symbol not in self._symbol_to_row:
            return None
        row_idx = self._symbol_to_row[symbol]
        return self._table[row_idx]

    def remove(self, symbol: str) -> bool:
        """
        Remove a position by symbol.

        Returns:
            True if position was removed, False if not found.
        """
        if symbol not in self._symbol_to_row:
            return False
        row_idx = self._symbol_to_row[symbol]
        self._table.delete_row(row_idx)
        # Rebuild index (row indices shift after delete)
        self._rebuild_index()
        return True

    def _rebuild_index(self) -> None:
        """Rebuild the symbol-to-row index."""
        self._symbol_to_row.clear()
        for i in range(len(self._table)):
            symbol = self._table.get_value(i, "symbol")
            self._symbol_to_row[symbol] = i

    def filter(self, predicate: Callable[[dict], bool]) -> "PositionTableView":
        """
        Filter positions by a predicate.

        Args:
            predicate: Function that takes a row dict and returns True to include.

        Returns:
            A view of filtered positions.
        """
        filtered = self._table.filter(predicate)
        return PositionTableView(filtered)

    def __len__(self) -> int:
        """Return the number of positions."""
        return len(self._table)

    def __iter__(self) -> Iterator[dict]:
        """Iterate over all positions."""
        for i in range(len(self._table)):
            yield self._table[i]

    def __getitem__(self, index: int) -> dict:
        """Get a position by index."""
        return self._table[index]

    @property
    def symbols(self) -> list[str]:
        """Get all position symbols."""
        return list(self._symbol_to_row.keys())


    def show(self, port: int = 8080, open_browser: bool = True) -> None:
        """
        Display the position table in a web browser.

        Args:
            port: Server port (default 8080)
            open_browser: Whether to open browser automatically

        Example:
            positions = PositionTable()
            positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
            positions.show()  # Opens browser with position table
        """
        from .table_ui import run_table_ui

        columns = [
            {"key": "symbol", "label": "Symbol"},
            {"key": "quantity", "label": "Quantity", "format": "quantity"},
            {"key": "avg_price", "label": "Avg Price", "format": "currency"},
            {"key": "market_value", "label": "Market Value", "format": "currency"},
            {"key": "unrealized_pnl", "label": "Unrealized P&L", "format": "pnl"},
        ]

        def get_rows():
            return [
                {
                    "symbol": p["symbol"],
                    "quantity": p["quantity"],
                    "avg_price": p["avg_price"],
                    "market_value": p["market_value"],
                    "unrealized_pnl": p["unrealized_pnl"],
                }
                for p in self
            ]

        def get_stats():
            long_count = sum(1 for p in self if p["quantity"] > 0)
            short_count = sum(1 for p in self if p["quantity"] < 0)
            total_mv = sum(p["market_value"] or 0 for p in self)
            total_pnl = sum(p["unrealized_pnl"] or 0 for p in self)
            return {
                "positions": len(self),
                "long": long_count,
                "short": short_count,
                "market_value": f"${total_mv:,.2f}",
                "total_pnl": f"${total_pnl:+,.2f}",
            }

        run_table_ui(
            title="Position Table",
            columns=columns,
            get_rows=get_rows,
            get_stats=get_stats,
            port=port,
            open_browser=open_browser,
        )


class PositionTableView:
    """Read-only view of filtered positions."""

    def __init__(self, view):
        self._view = view

    def __len__(self) -> int:
        return len(self._view)

    def __iter__(self) -> Iterator[dict]:
        for i in range(len(self._view)):
            yield self._view[i]

    def __getitem__(self, index: int) -> dict:
        return self._view[index]
