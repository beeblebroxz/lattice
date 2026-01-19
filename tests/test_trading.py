"""Tests for trading module (positions and blotter)."""

import pytest
from lattice.trading import PositionTable, TradeBlotter


class TestPositionTable:
    """Test PositionTable."""

    def test_create_empty(self):
        positions = PositionTable()
        assert len(positions) == 0

    def test_add_position(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        assert len(positions) == 1

    def test_get_position(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        pos = positions.get("AAPL_C_150")
        assert pos is not None
        assert pos["symbol"] == "AAPL_C_150"
        assert pos["quantity"] == 10
        assert pos["avg_price"] == pytest.approx(5.50)

    def test_get_nonexistent(self):
        positions = PositionTable()
        assert positions.get("NONEXISTENT") is None

    def test_update_position(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("AAPL_C_150", quantity=15, avg_price=5.75)
        assert len(positions) == 1
        pos = positions.get("AAPL_C_150")
        assert pos["quantity"] == 15
        assert pos["avg_price"] == pytest.approx(5.75)

    def test_multiple_positions(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("AAPL_P_145", quantity=-5, avg_price=3.20)
        positions.add("GOOGL_C_140", quantity=20, avg_price=8.00)
        assert len(positions) == 3

    def test_iterate(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("AAPL_P_145", quantity=-5, avg_price=3.20)

        symbols = [pos["symbol"] for pos in positions]
        assert "AAPL_C_150" in symbols
        assert "AAPL_P_145" in symbols

    def test_filter_long(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("AAPL_P_145", quantity=-5, avg_price=3.20)
        positions.add("GOOGL_C_140", quantity=20, avg_price=8.00)

        long_positions = positions.filter(lambda r: r["quantity"] > 0)
        assert len(long_positions) == 2

    def test_filter_short(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("AAPL_P_145", quantity=-5, avg_price=3.20)

        short_positions = positions.filter(lambda r: r["quantity"] < 0)
        assert len(short_positions) == 1

    def test_symbols_property(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("GOOGL_C_140", quantity=20, avg_price=8.00)

        symbols = positions.symbols
        assert "AAPL_C_150" in symbols
        assert "GOOGL_C_140" in symbols

    def test_getitem(self):
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        pos = positions[0]
        assert pos["symbol"] == "AAPL_C_150"


class TestTradeBlotter:
    """Test TradeBlotter."""

    def test_create_empty(self):
        blotter = TradeBlotter()
        assert len(blotter) == 0

    def test_record_trade(self):
        blotter = TradeBlotter()
        trade_id = blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        assert trade_id == 1
        assert len(blotter) == 1

    def test_trade_id_increments(self):
        blotter = TradeBlotter()
        id1 = blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        id2 = blotter.record("AAPL_C_150", "BUY", 5, 5.50)
        assert id2 == id1 + 1

    def test_trade_content(self):
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        trade = blotter[0]
        assert trade["symbol"] == "AAPL_C_150"
        assert trade["side"] == "BUY"
        assert trade["quantity"] == 5
        assert trade["price"] == pytest.approx(5.25)
        assert trade["notional"] == pytest.approx(26.25)

    def test_invalid_side(self):
        blotter = TradeBlotter()
        with pytest.raises(ValueError):
            blotter.record("AAPL_C_150", "INVALID", 5, 5.25)

    def test_iterate(self):
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        blotter.record("AAPL_P_145", "SELL", 10, 3.20)

        trades = list(blotter)
        assert len(trades) == 2

    def test_filter_by_symbol(self):
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        blotter.record("GOOGL_C_140", "BUY", 10, 8.00)
        blotter.record("AAPL_C_150", "BUY", 5, 5.50)

        aapl_trades = blotter.by_symbol("AAPL_C_150")
        assert len(aapl_trades) == 2

    def test_buys(self):
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        blotter.record("AAPL_C_150", "SELL", 3, 5.50)
        blotter.record("AAPL_C_150", "BUY", 2, 5.30)

        buys = blotter.buys()
        assert len(buys) == 2

    def test_sells(self):
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150", "BUY", 5, 5.25)
        blotter.record("AAPL_C_150", "SELL", 3, 5.50)
        blotter.record("AAPL_C_150", "SELL", 2, 5.60)

        sells = blotter.sells()
        assert len(sells) == 2

    def test_total_notional(self):
        blotter = TradeBlotter()
        blotter.record("AAPL_C_150", "BUY", 10, 5.00)  # 50
        blotter.record("GOOGL_C_140", "BUY", 5, 10.00)  # 50

        assert blotter.total_notional == pytest.approx(100.0)
