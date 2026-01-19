"""Market quote management using livetable."""

from typing import Optional
import livetable


class QuoteTable:
    """
    Market quote table backed by livetable.

    Example:
        quotes = QuoteTable()
        quotes.set("AAPL", spot=150.0, vol=0.25)
        quotes.set("GOOGL", spot=140.0, vol=0.30)

        print(quotes.get_spot("AAPL"))  # 150.0
        print(quotes.get_vol("AAPL"))   # 0.25
    """

    def __init__(self):
        """Create an empty quote table."""
        schema = livetable.Schema([
            ("symbol", livetable.ColumnType.STRING, False),
            ("spot", livetable.ColumnType.FLOAT64, True),
            ("bid", livetable.ColumnType.FLOAT64, True),
            ("ask", livetable.ColumnType.FLOAT64, True),
            ("vol", livetable.ColumnType.FLOAT64, True),
        ])
        self._table = livetable.Table("quotes", schema)
        self._symbol_to_row: dict[str, int] = {}

    def set(
        self,
        symbol: str,
        spot: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        vol: Optional[float] = None,
    ) -> None:
        """
        Set or update a quote.

        Args:
            symbol: Instrument identifier
            spot: Spot/mid price
            bid: Bid price
            ask: Ask price
            vol: Implied volatility
        """
        if symbol in self._symbol_to_row:
            row_idx = self._symbol_to_row[symbol]
            if spot is not None:
                self._table.set_value(row_idx, "spot", spot)
            if bid is not None:
                self._table.set_value(row_idx, "bid", bid)
            if ask is not None:
                self._table.set_value(row_idx, "ask", ask)
            if vol is not None:
                self._table.set_value(row_idx, "vol", vol)
        else:
            self._table.append_row({
                "symbol": symbol,
                "spot": spot,
                "bid": bid,
                "ask": ask,
                "vol": vol,
            })
            self._symbol_to_row[symbol] = len(self._table) - 1

    def get_spot(self, symbol: str) -> Optional[float]:
        """Get spot price for a symbol."""
        if symbol not in self._symbol_to_row:
            return None
        return self._table.get_value(self._symbol_to_row[symbol], "spot")

    def get_vol(self, symbol: str) -> Optional[float]:
        """Get implied volatility for a symbol."""
        if symbol not in self._symbol_to_row:
            return None
        return self._table.get_value(self._symbol_to_row[symbol], "vol")

    def get_bid(self, symbol: str) -> Optional[float]:
        """Get bid price for a symbol."""
        if symbol not in self._symbol_to_row:
            return None
        return self._table.get_value(self._symbol_to_row[symbol], "bid")

    def get_ask(self, symbol: str) -> Optional[float]:
        """Get ask price for a symbol."""
        if symbol not in self._symbol_to_row:
            return None
        return self._table.get_value(self._symbol_to_row[symbol], "ask")

    def __len__(self) -> int:
        """Return the number of symbols."""
        return len(self._table)

    @property
    def symbols(self) -> list[str]:
        """Get all symbols."""
        return list(self._symbol_to_row.keys())
