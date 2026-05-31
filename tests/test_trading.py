"""Tests for trading module (positions and blotter)."""

import pytest
from lattice.trading import PositionTable, TradeBlotter, Position, TradingSystem
from lattice import VanillaOption


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

    def test_update_position_preserves_order(self):
        """Updating a position edits it in place, keeping iteration order stable."""
        positions = PositionTable()
        positions.add("AAPL_C_150", quantity=10, avg_price=5.50)
        positions.add("AAPL_P_145", quantity=-5, avg_price=3.20)
        positions.add("GOOGL_C_140", quantity=20, avg_price=8.00)

        # Update the first position; it should stay first, not jump to the end.
        positions.add("AAPL_C_150", quantity=99, avg_price=6.00)

        symbols = [pos["symbol"] for pos in positions]
        assert symbols == ["AAPL_C_150", "AAPL_P_145", "GOOGL_C_140"]
        assert positions.get("AAPL_C_150")["quantity"] == 99
        # Other positions remain intact after the in-place update.
        assert positions.get("GOOGL_C_140")["quantity"] == 20

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

    def test_total_market_value_and_pnl(self):
        positions = PositionTable()
        positions.add("A", quantity=10, avg_price=5.0, market_value=60.0, unrealized_pnl=10.0)
        positions.add("B", quantity=-5, avg_price=3.0, market_value=-20.0, unrealized_pnl=-5.0)
        assert positions.total_market_value == pytest.approx(40.0)
        assert positions.total_unrealized_pnl == pytest.approx(5.0)

    def test_totals_treat_unset_as_zero(self):
        positions = PositionTable()
        assert positions.total_market_value == 0.0
        assert positions.total_unrealized_pnl == 0.0
        # market_value / unrealized_pnl default to None when unset.
        positions.add("A", quantity=10, avg_price=5.0)
        assert positions.total_market_value == 0.0


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

    def test_total_notional_empty(self):
        assert TradeBlotter().total_notional == 0.0


class TestPositionInstrumentLink:
    """Position can optionally derive its value from a live instrument."""

    def _option(self):
        o = VanillaOption()
        o.Spot.set(100.0); o.Strike.set(100.0)
        o.Volatility.set(0.20); o.Rate.set(0.04)
        return o

    def test_unlinked_uses_market_price(self):
        pos = Position()
        pos.Quantity.set(10); pos.AvgPrice.set(5.0); pos.MarketPrice.set(6.0)
        assert pos.EffectivePrice() == 6.0
        assert pos.MarketValue() == 60.0
        assert pos.UnrealizedPnL() == 10.0   # 60 - 10*5

    def test_linked_uses_instrument_value(self):
        opt = self._option()
        pos = Position(); pos.Quantity.set(10); pos.AvgPrice.set(5.0)
        pos.LinkedInstrument.set(opt)
        assert pos.EffectivePrice() == opt.MarketValue()
        assert pos.MarketValue() == 10 * opt.MarketValue()

    def test_dynamic_link_recomputes_then_reverts(self):
        opt = self._option()
        pos = Position(); pos.Quantity.set(10); pos.MarketPrice.set(5.0)
        assert pos.MarketValue() == 50.0          # evaluated while unlinked
        pos.LinkedInstrument.set(opt)             # link AFTER first eval
        assert abs(pos.MarketValue() - 10 * opt.MarketValue()) < 1e-9
        pos.LinkedInstrument.set(None)            # unlink
        assert pos.MarketValue() == 50.0

    def test_linked_reprices_on_instrument_change(self):
        opt = self._option()
        pos = Position(); pos.Quantity.set(10); pos.LinkedInstrument.set(opt)
        before = pos.MarketValue()
        opt.Spot.set(120.0)                       # ITM call -> higher value
        assert pos.MarketValue() > before

    def test_linked_zero_value_does_not_fall_back(self):
        """A linked instrument worth 0 values the position at 0, not at MarketPrice.

        Locks the `is not None` invariant: a falsy-but-present instrument value
        must be used, never confused with 'no instrument linked'.
        """
        from lattice.instruments.base import Instrument
        pos = Position(); pos.Quantity.set(10); pos.MarketPrice.set(7.0)
        pos.LinkedInstrument.set(Instrument())    # base Instrument.MarketValue() == 0.0
        assert pos.EffectivePrice() == 0.0        # uses the instrument's 0, not MarketPrice 7
        assert pos.MarketValue() == 0.0


class TestInstrumentRegistry:
    """TradingSystem can back a symbol with a live instrument."""

    def _option(self):
        o = VanillaOption()
        o.Spot.set(100.0); o.Strike.set(100.0)
        o.Volatility.set(0.20); o.Rate.set(0.04)
        return o

    def test_register_links_existing_position(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        sys.trade(desk, client, "AAPL", 100, 5.0)        # position created first
        opt = self._option()
        sys.register_instrument("AAPL", opt)             # then registered
        pos = sys.positions_for(desk)[0]
        assert pos.LinkedInstrument() is opt
        assert abs(pos.MarketValue() - 100 * opt.MarketValue()) < 1e-9

    def test_register_links_future_position(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        opt = self._option()
        sys.register_instrument("AAPL", opt)             # registered first
        sys.trade(desk, client, "AAPL", 100, 5.0)        # position created after
        pos = sys.positions_for(desk)[0]
        assert pos.LinkedInstrument() is opt

    def test_set_market_price_raises_for_linked_symbol(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        opt = self._option()
        sys.register_instrument("AAPL", opt)
        with pytest.raises(ValueError):
            sys.set_market_price("AAPL", 5.5)

    def test_set_market_price_still_works_for_unlinked(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        sys.trade(desk, client, "AAPL", 100, 5.0)
        sys.set_market_price("AAPL", 6.0)                # unlinked symbol: fine
        assert sys.get_market_price("AAPL") == 6.0


class TestPortfolioGreeks:
    """Book.Delta/Vega/Gamma aggregate per-instrument sensitivities."""

    def test_book_delta_aggregates_linked_positions(self):
        import lattice.risk as risk
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0)
        opt.Volatility.set(0.20); opt.Rate.set(0.04)
        sys.register_instrument("OPT", opt)
        sys.trade(desk, client, "OPT", 10, opt.MarketValue())
        # All three Greeks are quantity-weighted sums of the instrument's Greek.
        assert abs(desk.Delta() - 10 * risk.delta(opt)) < 1e-6
        assert abs(desk.Vega() - 10 * risk.vega(opt)) < 1e-6
        assert abs(desk.Gamma() - 10 * risk.gamma(opt)) < 1e-6

    def test_unlinked_book_has_zero_greeks(self):
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        sys.trade(desk, client, "AAPL", 100, 5.0)
        sys.set_market_price("AAPL", 5.5)
        assert desk.Delta() == 0.0
        assert desk.Vega() == 0.0

    def test_bond_contributes_no_delta_or_vega(self):
        from lattice import Bond
        sys = TradingSystem(); desk = sys.book("D"); client = sys.book("C")
        bond = Bond()
        bond.FaceValue.set(1000.0); bond.CouponRate.set(0.05)
        bond.YieldToMaturity.set(0.04); bond.Maturity.set(10)
        sys.register_instrument("UST", bond)
        sys.trade(desk, client, "UST", 5, bond.MarketValue())
        assert desk.Delta() == 0.0          # bond has no Spot
        assert desk.Vega() == 0.0           # bond has no Volatility
