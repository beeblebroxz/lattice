"""TradingSystem - orchestrator for books, trades, and positions.

The TradingSystem provides a unified interface for:
- Creating and managing books (dag.Model)
- Recording trades between books
- Aggregating positions per book
- Reactive P&L updates

Uses hybrid storage:
- livetable for trade storage (fast bulk operations)
- dag.Model for Books/Positions (reactivity, scenarios, UI binding)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import livetable

from .book import Book
from .trade import Trade
from .position import Position


class TradingSystem:
    """Orchestrator for trading books and positions.

    TradingSystem manages the lifecycle of books and trades:
    - Books are created via system.book() and are dag.Model instances
    - Trades are recorded via system.trade() between two books
    - Positions are automatically aggregated per book

    Example:
        system = TradingSystem()

        # Create books
        mm = system.book("MARKET_MAKER")
        client = system.book("CLIENT_ABC", book_type="customer")

        # Execute trades
        system.trade(buyer=mm, seller=client, symbol="AAPL_C_150",
                    quantity=10, price=5.25)
        system.trade(buyer=mm, seller=client, symbol="GOOGL_C_140",
                    quantity=20, price=8.00)

        # Access P&L (reactive)
        print(f"MM P&L: ${mm.TotalPnL():.2f}")
        print(f"Client P&L: ${client.TotalPnL():.2f}")

        # Update market prices
        system.set_market_price("AAPL_C_150", 6.00)
        print(f"MM P&L after move: ${mm.TotalPnL():.2f}")

        # Show dashboard
        system.show()
    """

    def __init__(self) -> None:
        """Initialize the trading system."""
        # Book registry: book_id -> Book
        self._books: Dict[str, Book] = {}

        # Trade storage using livetable for performance
        schema = livetable.Schema([
            ("trade_id", livetable.ColumnType.INT64, False),
            ("symbol", livetable.ColumnType.STRING, False),
            ("quantity", livetable.ColumnType.INT64, False),
            ("price", livetable.ColumnType.FLOAT64, False),
            ("buyer_book_id", livetable.ColumnType.STRING, False),
            ("seller_book_id", livetable.ColumnType.STRING, False),
            ("timestamp", livetable.ColumnType.STRING, False),
        ])
        self._trades_table = livetable.Table("system_trades", schema)

        # Trade dag.Model instances for reactive P&L
        self._trades: List[Trade] = []

        # Position cache: (book_id, symbol) -> Position
        self._positions: Dict[Tuple[str, str], Position] = {}

        # Market prices: symbol -> price
        self._market_prices: Dict[str, float] = {}

        # Trade ID counter
        self._next_trade_id = 1

    def book(
        self,
        book_id: str,
        name: Optional[str] = None,
        book_type: str = "trading",
        parent_book_id: str = "",
    ) -> Book:
        """Get or create a book.

        Args:
            book_id: Unique book identifier
            name: Human-readable name (defaults to book_id)
            book_type: One of 'trading', 'customer', 'house', 'hedge'
            parent_book_id: Parent book for hierarchy roll-up

        Returns:
            Book instance (dag.Model)
        """
        if book_id in self._books:
            return self._books[book_id]

        book = Book()
        book.BookId.set(book_id)
        book.Name.set(name or book_id)
        book.BookType.set(book_type)
        book.ParentBookId.set(parent_book_id)
        book._set_system(self)
        book._set_positions([])

        self._books[book_id] = book
        return book

    def get_book(self, book_id: str) -> Optional[Book]:
        """Get a book by ID, or None if not found."""
        return self._books.get(book_id)

    @property
    def books(self) -> List[Book]:
        """All books in the system."""
        return list(self._books.values())

    @property
    def trades(self) -> List[Trade]:
        """All trades in the system."""
        return self._trades

    def trade(
        self,
        buyer: Book,
        seller: Book,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: Optional[datetime] = None,
    ) -> Trade:
        """Record a trade between two books.

        Creates a Trade dag.Model and updates positions for both books.

        Args:
            buyer: Book buying the instrument
            seller: Book selling the instrument
            symbol: Instrument symbol
            quantity: Number of units (positive)
            price: Execution price
            timestamp: Trade time (defaults to now)

        Returns:
            Trade instance (dag.Model)
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        ts = timestamp or datetime.now()
        trade_id = self._next_trade_id
        self._next_trade_id += 1

        # Store in livetable for fast queries
        self._trades_table.append_row({
            "trade_id": trade_id,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "buyer_book_id": buyer.BookId(),
            "seller_book_id": seller.BookId(),
            "timestamp": ts.isoformat(),
        })

        # Create dag.Model trade for reactive P&L
        trade = Trade()
        trade.TradeId.set(trade_id)
        trade.Symbol.set(symbol)
        trade.Quantity.set(quantity)
        trade.Price.set(price)
        trade.BuyerBookId.set(buyer.BookId())
        trade.SellerBookId.set(seller.BookId())
        trade.Timestamp.set(ts)

        # Set market price if known
        if symbol in self._market_prices:
            trade.MarketPrice.set(self._market_prices[symbol])

        self._trades.append(trade)

        # Update positions for both books
        self._update_position(buyer.BookId(), symbol, quantity, price)
        self._update_position(seller.BookId(), symbol, -quantity, price)

        return trade

    def _update_position(
        self, book_id: str, symbol: str, quantity_delta: int, price: float
    ) -> None:
        """Update a position for a book.

        Args:
            book_id: Book identifier
            symbol: Instrument symbol
            quantity_delta: Change in quantity (positive=buy, negative=sell)
            price: Execution price
        """
        key = (book_id, symbol)

        if key not in self._positions:
            # Create new position
            pos = Position()
            pos.Symbol.set(symbol)
            pos.BookId.set(book_id)
            pos.Quantity.set(quantity_delta)
            pos.AvgPrice.set(price)

            # Set market price if known
            if symbol in self._market_prices:
                pos.MarketPrice.set(self._market_prices[symbol])

            self._positions[key] = pos
        else:
            # Update existing position
            pos = self._positions[key]
            old_qty = pos.Quantity()
            new_qty = old_qty + quantity_delta

            if new_qty == 0:
                # Position closed
                pos.Quantity.set(0)
                pos.AvgPrice.set(0.0)
            elif (old_qty >= 0 and quantity_delta > 0) or (old_qty <= 0 and quantity_delta < 0):
                # Adding to position - calculate weighted average price
                old_cost = abs(old_qty) * pos.AvgPrice()
                new_cost = abs(quantity_delta) * price
                new_avg = (old_cost + new_cost) / abs(new_qty)
                pos.Quantity.set(new_qty)
                pos.AvgPrice.set(new_avg)
            else:
                # Reducing position - keep original avg price
                pos.Quantity.set(new_qty)
                # If position flips, use new price
                if (old_qty > 0 and new_qty < 0) or (old_qty < 0 and new_qty > 0):
                    pos.AvgPrice.set(price)

        # Update book's position list
        book = self._books.get(book_id)
        if book:
            book_positions = [
                p for (bid, _), p in self._positions.items()
                if bid == book_id and not p.IsFlat()
            ]
            book._set_positions(book_positions)

    def set_market_price(self, symbol: str, price: float) -> None:
        """Set the market price for a symbol.

        Updates all trades and positions referencing this symbol.

        Args:
            symbol: Instrument symbol
            price: New market price
        """
        self._market_prices[symbol] = price

        # Update all trades with this symbol
        for trade in self._trades:
            if trade.Symbol() == symbol:
                trade.MarketPrice.set(price)

        # Update all positions with this symbol
        for (book_id, sym), pos in self._positions.items():
            if sym == symbol:
                pos.MarketPrice.set(price)

    def get_market_price(self, symbol: str) -> Optional[float]:
        """Get the market price for a symbol."""
        return self._market_prices.get(symbol)

    def positions_for(self, book: Book) -> List[Position]:
        """Get all positions for a book.

        Args:
            book: Book instance

        Returns:
            List of Position instances
        """
        book_id = book.BookId()
        return [
            p for (bid, _), p in self._positions.items()
            if bid == book_id and not p.IsFlat()
        ]

    def trades_for(self, book: Book) -> List[Trade]:
        """Get all trades involving a book.

        Args:
            book: Book instance

        Returns:
            List of Trade instances where book is buyer or seller
        """
        book_id = book.BookId()
        return [
            t for t in self._trades
            if t.BuyerBookId() == book_id or t.SellerBookId() == book_id
        ]

    def total_pnl(self) -> float:
        """Total P&L across all books.

        Note: This should sum to zero as every trade has a buyer and seller.
        """
        return sum(book.TotalPnL() for book in self._books.values())

    def total_volume(self) -> float:
        """Total notional volume of all trades."""
        return sum(trade.Notional() for trade in self._trades)

    @property
    def num_trades(self) -> int:
        """Total number of trades."""
        return len(self._trades)

    @property
    def num_books(self) -> int:
        """Total number of books."""
        return len(self._books)

    def summary(self) -> Dict:
        """Get a summary of the trading system state."""
        return {
            "num_books": self.num_books,
            "num_trades": self.num_trades,
            "total_volume": self.total_volume(),
            "books": [
                {
                    "book_id": b.BookId(),
                    "name": b.DisplayName(),
                    "type": b.BookType(),
                    "num_positions": b.NumPositions(),
                    "total_pnl": b.TotalPnL(),
                    "gross_exposure": b.GrossExposure(),
                }
                for b in self._books.values()
            ],
        }

    def show(
        self,
        port: int = 8080,
        open_browser: bool = True,
        simulate: bool = False,
        simulate_interval: float = 1.0,
    ) -> None:
        """Display the trading system dashboard in a web browser.

        Args:
            port: Port for the HTTP server
            open_browser: Whether to open browser automatically
            simulate: If True, simulate random trades for demo
            simulate_interval: Seconds between simulated trades
        """
        from .table_ui import run_table_ui
        import random
        import asyncio

        # Define columns for the combined view
        columns = [
            {"key": "book_id", "label": "Book"},
            {"key": "type", "label": "Type"},
            {"key": "num_positions", "label": "Positions"},
            {"key": "total_pnl", "label": "Total P&L", "format": "currency"},
            {"key": "gross_exposure", "label": "Gross Exposure", "format": "currency"},
            {"key": "net_exposure", "label": "Net Exposure", "format": "currency"},
        ]

        def get_rows():
            return [
                {
                    "book_id": b.DisplayName(),
                    "type": b.BookType(),
                    "num_positions": b.NumPositions(),
                    "total_pnl": b.TotalPnL(),
                    "gross_exposure": b.GrossExposure(),
                    "net_exposure": b.NetExposure(),
                }
                for b in self._books.values()
            ]

        def get_stats():
            return {
                "Books": self.num_books,
                "Trades": self.num_trades,
                "Volume": f"${self.total_volume():,.2f}",
            }

        # Simulation callback for demo mode
        if simulate:
            symbols = ["AAPL_C_150", "GOOGL_C_140", "MSFT_P_380", "TSLA_C_250"]
            books = list(self._books.values())

            if len(books) < 2:
                # Create default books for simulation
                self.book("MARKET_MAKER", book_type="trading")
                self.book("CLIENT_A", book_type="customer")
                self.book("CLIENT_B", book_type="customer")
                books = list(self._books.values())

            async def simulate_trades(send_update):
                while True:
                    await asyncio.sleep(simulate_interval)

                    # Random trade
                    buyer = random.choice(books)
                    seller = random.choice([b for b in books if b != buyer])
                    symbol = random.choice(symbols)
                    quantity = random.randint(1, 20)
                    base_price = {"AAPL_C_150": 5.25, "GOOGL_C_140": 8.00,
                                 "MSFT_P_380": 6.50, "TSLA_C_250": 12.00}
                    price = base_price.get(symbol, 5.0) * (0.9 + random.random() * 0.2)

                    self.trade(buyer, seller, symbol, quantity, round(price, 2))

                    # Randomly update market prices
                    if random.random() < 0.3:
                        market_symbol = random.choice(symbols)
                        current = self._market_prices.get(market_symbol, base_price.get(market_symbol, 5.0))
                        new_price = current * (0.95 + random.random() * 0.1)
                        self.set_market_price(market_symbol, round(new_price, 2))

                    await send_update()

            run_table_ui(
                title="Trading System Dashboard",
                columns=columns,
                get_rows=get_rows,
                get_stats=get_stats,
                port=port,
                open_browser=open_browser,
                simulate_callback=simulate_trades,
            )
        else:
            run_table_ui(
                title="Trading System Dashboard",
                columns=columns,
                get_rows=get_rows,
                get_stats=get_stats,
                port=port,
                open_browser=open_browser,
            )
