"""Tests for trading books, trades, and positions."""

import pytest
import dag
from lattice import Book, Trade, Position, TradingSystem


@pytest.fixture(autouse=True)
def reset_dag():
    """Reset dag state before each test."""
    dag.reset()
    yield
    dag.reset()


class TestTrade:
    """Tests for Trade dag.Model."""

    def test_trade_inputs(self):
        trade = Trade()
        trade.TradeId.set(1)
        trade.Symbol.set("AAPL_C_150")
        trade.Quantity.set(10)
        trade.Price.set(5.25)
        trade.BuyerBookId.set("DESK_A")
        trade.SellerBookId.set("CUST_123")

        assert trade.TradeId() == 1
        assert trade.Symbol() == "AAPL_C_150"
        assert trade.Quantity() == 10
        assert trade.Price() == 5.25
        assert trade.BuyerBookId() == "DESK_A"
        assert trade.SellerBookId() == "CUST_123"

    def test_trade_notional(self):
        trade = Trade()
        trade.Quantity.set(10)
        trade.Price.set(5.25)

        assert trade.Notional() == 52.50

    def test_trade_market_value(self):
        trade = Trade()
        trade.Quantity.set(10)
        trade.Price.set(5.25)
        trade.MarketPrice.set(6.00)

        assert trade.MarketValue() == 60.00

    def test_trade_buyer_pnl(self):
        """Buyer profits when market price > trade price."""
        trade = Trade()
        trade.Quantity.set(10)
        trade.Price.set(5.25)
        trade.MarketPrice.set(6.00)

        assert trade.BuyerPnL() == 7.50  # (6.00 - 5.25) * 10

    def test_trade_seller_pnl(self):
        """Seller loses when market price > trade price."""
        trade = Trade()
        trade.Quantity.set(10)
        trade.Price.set(5.25)
        trade.MarketPrice.set(6.00)

        assert trade.SellerPnL() == -7.50  # (5.25 - 6.00) * 10

    def test_trade_pnl_zero_sum(self):
        """Buyer P&L + Seller P&L = 0."""
        trade = Trade()
        trade.Quantity.set(10)
        trade.Price.set(5.25)
        trade.MarketPrice.set(6.00)

        assert trade.BuyerPnL() + trade.SellerPnL() == 0

    def test_trade_market_price_default(self):
        """Market price defaults to trade price."""
        trade = Trade()
        trade.Price.set(5.25)

        assert trade.MarketPrice() == 5.25

    def test_trade_reactive(self):
        """P&L updates when market price changes."""
        trade = Trade()
        trade.Quantity.set(10)
        trade.Price.set(5.25)

        assert trade.BuyerPnL() == 0  # Market price = trade price

        trade.MarketPrice.set(5.75)
        assert trade.BuyerPnL() == 5.00  # (5.75 - 5.25) * 10


class TestPosition:
    """Tests for Position dag.Model."""

    def test_position_inputs(self):
        pos = Position()
        pos.Symbol.set("AAPL_C_150")
        pos.BookId.set("DESK_A")
        pos.Quantity.set(10)
        pos.AvgPrice.set(5.25)

        assert pos.Symbol() == "AAPL_C_150"
        assert pos.BookId() == "DESK_A"
        assert pos.Quantity() == 10
        assert pos.AvgPrice() == 5.25

    def test_position_cost_basis(self):
        pos = Position()
        pos.Quantity.set(10)
        pos.AvgPrice.set(5.25)

        assert pos.CostBasis() == 52.50

    def test_position_cost_basis_short(self):
        """Cost basis is absolute value."""
        pos = Position()
        pos.Quantity.set(-10)
        pos.AvgPrice.set(5.25)

        assert pos.CostBasis() == 52.50

    def test_position_market_value_long(self):
        pos = Position()
        pos.Quantity.set(10)
        pos.MarketPrice.set(6.00)

        assert pos.MarketValue() == 60.00

    def test_position_market_value_short(self):
        """Short position has negative market value."""
        pos = Position()
        pos.Quantity.set(-10)
        pos.MarketPrice.set(6.00)

        assert pos.MarketValue() == -60.00

    def test_position_unrealized_pnl_long(self):
        pos = Position()
        pos.Quantity.set(10)
        pos.AvgPrice.set(5.25)
        pos.MarketPrice.set(6.00)

        assert pos.UnrealizedPnL() == 7.50

    def test_position_unrealized_pnl_short(self):
        """Short position profits when price drops."""
        pos = Position()
        pos.Quantity.set(-10)
        pos.AvgPrice.set(6.00)
        pos.MarketPrice.set(5.50)

        assert pos.UnrealizedPnL() == 5.00  # -10 * 5.50 - (-10 * 6.00)

    def test_position_is_long(self):
        pos = Position()
        pos.Quantity.set(10)
        assert pos.IsLong() is True
        assert pos.IsShort() is False
        assert pos.IsFlat() is False
        assert pos.Side() == "LONG"

    def test_position_is_short(self):
        pos = Position()
        pos.Quantity.set(-10)
        assert pos.IsLong() is False
        assert pos.IsShort() is True
        assert pos.IsFlat() is False
        assert pos.Side() == "SHORT"

    def test_position_is_flat(self):
        pos = Position()
        pos.Quantity.set(0)
        assert pos.IsLong() is False
        assert pos.IsShort() is False
        assert pos.IsFlat() is True
        assert pos.Side() == "FLAT"

    def test_position_abs_quantity(self):
        pos = Position()
        pos.Quantity.set(-10)
        assert pos.AbsQuantity() == 10

    def test_position_reactive(self):
        """P&L updates when market price changes."""
        pos = Position()
        pos.Quantity.set(10)
        pos.AvgPrice.set(5.25)

        assert pos.UnrealizedPnL() == 0  # Market price = avg price

        pos.MarketPrice.set(5.75)
        assert pos.UnrealizedPnL() == 5.00


class TestBook:
    """Tests for Book dag.Model."""

    def test_book_inputs(self):
        book = Book()
        book.BookId.set("DESK_OPTIONS")
        book.Name.set("Options Trading Desk")
        book.BookType.set("trading")

        assert book.BookId() == "DESK_OPTIONS"
        assert book.Name() == "Options Trading Desk"
        assert book.BookType() == "trading"

    def test_book_display_name_with_name(self):
        book = Book()
        book.BookId.set("DESK_A")
        book.Name.set("Options Desk")

        assert book.DisplayName() == "Options Desk"

    def test_book_display_name_without_name(self):
        book = Book()
        book.BookId.set("DESK_A")
        book.Name.set("")

        assert book.DisplayName() == "DESK_A"

    def test_book_empty_positions(self):
        book = Book()
        assert book.Positions() == []
        assert book.TotalPnL() == 0
        assert book.GrossExposure() == 0
        assert book.NetExposure() == 0
        assert book.NumPositions() == 0


class TestTradingSystem:
    """Tests for TradingSystem orchestrator."""

    def test_create_book(self):
        system = TradingSystem()
        book = system.book("DESK_A", name="Options Desk", book_type="trading")

        assert book.BookId() == "DESK_A"
        assert book.Name() == "Options Desk"
        assert book.BookType() == "trading"

    def test_get_existing_book(self):
        system = TradingSystem()
        book1 = system.book("DESK_A")
        book2 = system.book("DESK_A")

        assert book1 is book2

    def test_get_book_by_id(self):
        system = TradingSystem()
        system.book("DESK_A")

        assert system.get_book("DESK_A") is not None
        assert system.get_book("NONEXISTENT") is None

    def test_list_books(self):
        system = TradingSystem()
        system.book("DESK_A")
        system.book("DESK_B")

        assert len(system.books) == 2

    def test_trade_creates_positions(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)

        assert buyer.NumPositions() == 1
        assert seller.NumPositions() == 1

    def test_trade_positions_mirror(self):
        """Buyer and seller positions are mirror images."""
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)

        buyer_pos = buyer.Positions()[0]
        seller_pos = seller.Positions()[0]

        assert buyer_pos.Quantity() == 10
        assert seller_pos.Quantity() == -10
        assert buyer_pos.AvgPrice() == seller_pos.AvgPrice()

    def test_trade_pnl_zero_sum(self):
        """Total P&L across all books is zero."""
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.set_market_price("AAPL", 110.0)

        assert abs(system.total_pnl()) < 0.0001

    def test_set_market_price(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.set_market_price("AAPL", 110.0)

        assert buyer.TotalPnL() == 100.0  # (110 - 100) * 10
        assert seller.TotalPnL() == -100.0

    def test_multiple_trades_aggregate(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=5, price=105.0)

        buyer_pos = buyer.Positions()[0]
        assert buyer_pos.Quantity() == 15
        # Weighted avg: (10*100 + 5*105) / 15 = 1525/15 = 101.67
        assert abs(buyer_pos.AvgPrice() - 101.6667) < 0.01

    def test_position_close(self):
        """Position goes flat when fully closed."""
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=seller, seller=buyer, symbol="AAPL", quantity=10, price=105.0)

        # Both books should have 0 non-flat positions
        assert buyer.NumPositions() == 0
        assert seller.NumPositions() == 0

    def test_position_partial_close(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=seller, seller=buyer, symbol="AAPL", quantity=3, price=105.0)

        buyer_pos = buyer.Positions()[0]
        assert buyer_pos.Quantity() == 7

    def test_trade_returns_trade_object(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        trade = system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)

        assert trade.Symbol() == "AAPL"
        assert trade.Quantity() == 10
        assert trade.Price() == 100.0

    def test_trades_list(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=buyer, seller=seller, symbol="GOOGL", quantity=5, price=200.0)

        assert len(system.trades) == 2
        assert system.num_trades == 2

    def test_total_volume(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=buyer, seller=seller, symbol="GOOGL", quantity=5, price=200.0)

        assert system.total_volume() == 2000.0  # 1000 + 1000

    def test_trades_for_book(self):
        system = TradingSystem()
        a = system.book("A")
        b = system.book("B")
        c = system.book("C")

        system.trade(buyer=a, seller=b, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=b, seller=c, symbol="GOOGL", quantity=5, price=200.0)

        a_trades = system.trades_for(a)
        b_trades = system.trades_for(b)
        c_trades = system.trades_for(c)

        assert len(a_trades) == 1
        assert len(b_trades) == 2
        assert len(c_trades) == 1

    def test_positions_for_book(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=buyer, seller=seller, symbol="GOOGL", quantity=5, price=200.0)

        positions = system.positions_for(buyer)
        assert len(positions) == 2

    def test_invalid_quantity_raises(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        with pytest.raises(ValueError, match="Quantity must be positive"):
            system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=-10, price=100.0)

    def test_summary(self):
        system = TradingSystem()
        buyer = system.book("BUYER", book_type="trading")
        seller = system.book("SELLER", book_type="customer")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)

        summary = system.summary()
        assert summary["num_books"] == 2
        assert summary["num_trades"] == 1
        assert summary["total_volume"] == 1000.0


class TestBookMetrics:
    """Tests for book-level metrics."""

    def test_gross_exposure(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=buyer, seller=seller, symbol="GOOGL", quantity=5, price=200.0)

        # Gross = sum of abs market values
        assert buyer.GrossExposure() == 2000.0  # 1000 + 1000

    def test_net_exposure(self):
        system = TradingSystem()
        a = system.book("A")
        b = system.book("B")

        system.trade(buyer=a, seller=b, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=b, seller=a, symbol="GOOGL", quantity=5, price=200.0)

        # A: long AAPL (1000), short GOOGL (-1000) -> net = 0
        assert a.NetExposure() == 0

    def test_long_short_counts(self):
        system = TradingSystem()
        a = system.book("A")
        b = system.book("B")

        system.trade(buyer=a, seller=b, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=a, seller=b, symbol="GOOGL", quantity=5, price=200.0)
        system.trade(buyer=b, seller=a, symbol="MSFT", quantity=3, price=300.0)

        assert a.NumLongPositions() == 2
        assert a.NumShortPositions() == 1

    def test_long_short_exposure(self):
        system = TradingSystem()
        a = system.book("A")
        b = system.book("B")

        system.trade(buyer=a, seller=b, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=b, seller=a, symbol="GOOGL", quantity=5, price=200.0)

        assert a.LongExposure() == 1000.0
        assert a.ShortExposure() == 1000.0


class TestScenarioAnalysis:
    """Tests for scenario analysis with dag.scenario()."""

    def test_scenario_market_price_override(self):
        system = TradingSystem()
        buyer = system.book("BUYER")
        seller = system.book("SELLER")

        system.trade(buyer=buyer, seller=seller, symbol="AAPL", quantity=10, price=100.0)
        system.set_market_price("AAPL", 110.0)

        original_pnl = buyer.TotalPnL()
        assert original_pnl == 100.0

        # Scenario: what if market drops 20%?
        with dag.scenario():
            for pos in buyer.Positions():
                current = pos.MarketPrice()
                pos.MarketPrice.override(current * 0.8)

            scenario_pnl = buyer.TotalPnL()
            assert scenario_pnl == -120.0  # (88 - 100) * 10 = -120

        # Original value restored
        assert buyer.TotalPnL() == 100.0

    def test_scenario_stress_test(self):
        """Multi-position stress test."""
        system = TradingSystem()
        mm = system.book("MARKET_MAKER")
        client = system.book("CLIENT")

        system.trade(buyer=mm, seller=client, symbol="AAPL", quantity=10, price=100.0)
        system.trade(buyer=mm, seller=client, symbol="GOOGL", quantity=5, price=200.0)

        system.set_market_price("AAPL", 110.0)
        system.set_market_price("GOOGL", 210.0)

        base_pnl = mm.TotalPnL()
        assert base_pnl == 150.0  # 100 + 50

        # Stress test: all positions drop 10%
        with dag.scenario():
            for pos in mm.Positions():
                pos.MarketPrice.override(pos.MarketPrice() * 0.9)

            stress_pnl = mm.TotalPnL()
            # AAPL: (99 - 100) * 10 = -10
            # GOOGL: (189 - 200) * 5 = -55
            assert stress_pnl == -65.0

        # Back to normal
        assert mm.TotalPnL() == base_pnl
