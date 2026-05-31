"""Tests for the lattice.risk module."""

import pytest
import math
import logging
import threading
import dag
from lattice import VanillaOption, Bond, Stock, Forward, risk
from lattice.trading import TradingSystem
from lattice.risk import RiskEngine


class _BrokenInstrument(dag.Model):
    """Instrument whose Price raises, to exercise error handling."""

    @dag.computed(dag.Input | dag.Overridable)
    def Spot(self) -> float:
        return 100.0

    @dag.computed
    def Price(self) -> float:
        raise ValueError("boom")


@pytest.fixture(autouse=True)
def reset_dag():
    """Reset dag state before each test to avoid stale references."""
    dag.reset()
    yield
    dag.reset()


class TestSensitivity:
    """Tests for core sensitivity function."""

    def test_sensitivity_basic(self):
        """Test basic sensitivity calculation."""
        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)
        option.Volatility.set(0.20)
        option.Rate.set(0.05)
        option.TimeToExpiry.set(1.0)

        sens = risk.sensitivity(option, "Spot", "Price", bump=0.01)
        assert sens > 0  # Call delta should be positive

    def test_sensitivity_absolute_vs_relative(self):
        """Test absolute vs relative bump types."""
        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)

        # Absolute bump
        sens_abs = risk.sensitivity(option, "Spot", bump=1.0, bump_type="absolute")

        # Relative bump (1% of 100 = 1.0)
        sens_rel = risk.sensitivity(option, "Spot", bump=0.01, bump_type="relative")

        # Should be very close (both are $1 bump)
        assert abs(sens_abs - sens_rel) < 0.01


class TestGreeks:
    """Tests for Greek calculations."""

    @pytest.fixture
    def atm_option(self):
        """Create an ATM option for testing."""
        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)
        option.Volatility.set(0.20)
        option.Rate.set(0.05)
        option.TimeToExpiry.set(1.0)
        option.IsCall.set(True)
        return option

    def test_delta_matches_closed_form(self, atm_option):
        """Numerical delta should match closed-form within tolerance."""
        numerical_delta = risk.delta(atm_option)
        closed_form_delta = atm_option.Delta()

        assert abs(numerical_delta - closed_form_delta) < 0.001

    def test_gamma_matches_closed_form(self, atm_option):
        """Numerical gamma should match closed-form within tolerance."""
        numerical_gamma = risk.gamma(atm_option)
        closed_form_gamma = atm_option.Gamma()

        # Gamma is smaller, so tolerance is tighter
        assert abs(numerical_gamma - closed_form_gamma) < 0.0001

    def test_vega_matches_closed_form(self, atm_option):
        """Numerical vega should match closed-form within tolerance."""
        numerical_vega = risk.vega(atm_option)
        closed_form_vega = atm_option.Vega()

        # Vega is larger, so tolerance is looser
        assert abs(numerical_vega - closed_form_vega) < 0.5

    def test_theta_matches_closed_form(self, atm_option):
        """Numerical theta should match closed-form within tolerance."""
        numerical_theta = risk.theta(atm_option)
        closed_form_theta = atm_option.Theta()

        # Theta has larger values, so relative tolerance
        assert abs(numerical_theta - closed_form_theta) < 0.1

    def test_rho_matches_closed_form(self, atm_option):
        """Numerical rho should match closed-form within tolerance."""
        numerical_rho = risk.rho(atm_option)
        closed_form_rho = atm_option.Rho()

        assert abs(numerical_rho - closed_form_rho) < 0.5

    def test_delta_positive_for_call(self, atm_option):
        """Call delta should be positive."""
        atm_option.IsCall.set(True)
        assert risk.delta(atm_option) > 0

    def test_delta_negative_for_put(self, atm_option):
        """Put delta should be negative."""
        atm_option.IsCall.set(False)
        assert risk.delta(atm_option) < 0

    def test_gamma_always_positive(self, atm_option):
        """Gamma should always be positive."""
        atm_option.IsCall.set(True)
        assert risk.gamma(atm_option) > 0

        atm_option.IsCall.set(False)
        assert risk.gamma(atm_option) > 0


class TestDV01:
    """Tests for bond DV01 calculation."""

    @pytest.fixture
    def bond(self):
        """Create a bond for testing."""
        bond = Bond()
        bond.FaceValue.set(1000.0)
        bond.CouponRate.set(0.05)
        bond.YieldToMaturity.set(0.04)
        bond.Maturity.set(10.0)
        bond.Frequency.set(2)
        return bond

    def test_dv01_matches_closed_form(self, bond):
        """Numerical DV01 should match closed-form within tolerance."""
        numerical_dv01 = risk.dv01(bond)
        closed_form_dv01 = bond.DV01()

        # DV01 values are typically small (dollars per bp)
        assert abs(numerical_dv01 - closed_form_dv01) < 0.1

    def test_dv01_positive(self, bond):
        """DV01 should be positive (price decreases when yield increases)."""
        assert risk.dv01(bond) > 0

    def test_dv01_increases_with_maturity(self):
        """Longer maturity bonds have higher DV01."""
        bond_short = Bond()
        bond_short.FaceValue.set(1000.0)
        bond_short.CouponRate.set(0.05)
        bond_short.YieldToMaturity.set(0.04)
        bond_short.Maturity.set(5.0)

        bond_long = Bond()
        bond_long.FaceValue.set(1000.0)
        bond_long.CouponRate.set(0.05)
        bond_long.YieldToMaturity.set(0.04)
        bond_long.Maturity.set(10.0)

        # Compute DV01 for each while keeping references
        dv01_short = risk.dv01(bond_short)
        dv01_long = risk.dv01(bond_long)

        assert dv01_long > dv01_short


class TestPortfolioRisk:
    """Tests for portfolio-level risk calculations."""

    @pytest.fixture
    def trading_system(self):
        """Create a trading system with positions."""
        system = TradingSystem()
        desk = system.book("DESK")
        client = system.book("CLIENT")

        system.trade(desk, client, "AAPL_C_150", 100, 5.25)
        system.trade(desk, client, "GOOGL_C_140", 50, 8.00)

        # Set market prices
        system.set_market_price("AAPL_C_150", 5.50)
        system.set_market_price("GOOGL_C_140", 7.50)

        return system, desk

    def test_portfolio_delta(self, trading_system):
        """Portfolio delta should be sum of position quantities."""
        system, desk = trading_system

        # Total quantity is 150 (100 + 50)
        delta = risk.portfolio_delta(desk)

        # Delta should be close to total quantity for simple positions
        assert abs(delta - 150) < 1

    def test_stress_spot_shock(self, trading_system):
        """Stress test with spot shock should impact P&L."""
        system, desk = trading_system

        result = risk.stress(desk, spot_shock=-0.10)

        # -10% spot should cause negative P&L impact
        assert result["pnl_impact"] < 0
        assert result["stressed_pnl"] < result["base_pnl"]

    def test_stress_reverts_after_scenario(self, trading_system):
        """Original values should be restored after stress test."""
        system, desk = trading_system

        base_pnl_before = desk.TotalPnL()
        risk.stress(desk, spot_shock=-0.20)
        base_pnl_after = desk.TotalPnL()

        assert base_pnl_before == base_pnl_after

    def test_portfolio_exposure(self, trading_system):
        """Portfolio exposure should be calculated correctly."""
        system, desk = trading_system

        exposure = risk.portfolio_exposure(desk)

        assert exposure["num_positions"] == 2
        assert exposure["gross_exposure"] > 0
        assert exposure["num_long"] == 2
        assert exposure["num_short"] == 0

    def test_stress_accepts_vol_rate_skipped_on_unlinked_book(self, trading_system):
        """An unlinked book has no instrument to absorb vol/rate; report them skipped."""
        system, desk = trading_system
        result = risk.stress(desk, spot_shock=-0.10, vol_shock=0.5, rate_shock=0.01)
        assert "spot_shock" in result["applied_shocks"]
        assert result["skipped_shocks"] == {"vol_shock": 0.5, "rate_shock": 0.01}
        assert result["pnl_impact"] < 0          # spot leg still moves the book


class TestMultiFactorStress:
    """A book of instrument-linked positions absorbs vol and rate shocks."""

    def _linked_book(self):
        from lattice.trading import TradingSystem
        system = TradingSystem()
        desk = system.book("DESK"); client = system.book("CLIENT")
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0)
        opt.Volatility.set(0.20); opt.Rate.set(0.04)
        system.register_instrument("OPT", opt)
        system.trade(desk, client, "OPT", 100, opt.MarketValue())
        return system, desk, opt

    def test_vol_shock_moves_linked_book(self):
        system, desk, opt = self._linked_book()
        base = desk.TotalPnL()
        result = risk.stress(desk, vol_shock=0.5)        # +50% vol -> higher option value
        assert result["pnl_impact"] > 0
        assert result["applied_shocks"] == {"vol_shock": 0.5}
        assert desk.TotalPnL() == pytest.approx(base)    # reverted after scenario

    def test_rate_shock_is_additive_on_linked_book(self):
        system, desk, opt = self._linked_book()          # desk holds +100 of the option
        base_value = opt.MarketValue()
        with dag.scenario():
            opt.Rate.override(0.05)                       # +100bp absolute (0.04 -> 0.05)
            bumped_value = opt.MarketValue()
        expected_impact = 100 * (bumped_value - base_value)
        result = risk.stress(desk, rate_shock=0.01)
        assert result["applied_shocks"] == {"rate_shock": 0.01}
        assert result["pnl_impact"] == pytest.approx(expected_impact, abs=1e-6)

    def test_mixed_linked_and_unlinked_book(self):
        """A book with one linked and one price-only position: vol applies to the
        linked leg, spot moves both, and a bond-linked rate shock is non-zero."""
        from lattice.trading import TradingSystem
        from lattice import Bond
        system = TradingSystem()
        desk = system.book("DESK"); client = system.book("CLIENT")
        # linked option position
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0); opt.Volatility.set(0.20); opt.Rate.set(0.04)
        system.register_instrument("OPT", opt)
        system.trade(desk, client, "OPT", 10, opt.MarketValue())
        # price-only position (no instrument)
        system.trade(desk, client, "XYZ", 10, 5.0)
        system.set_market_price("XYZ", 5.0)

        # vol shock: applied (the linked option absorbs it); the price-only leg ignores it
        rv = risk.stress(desk, vol_shock=0.5)
        assert rv["applied_shocks"] == {"vol_shock": 0.5}
        assert rv["pnl_impact"] != 0.0

    def test_bond_linked_book_absorbs_rate_shock(self):
        """A bond-linked book moves on rate_shock (bonds use YieldToMaturity)."""
        from lattice.trading import TradingSystem
        from lattice import Bond
        system = TradingSystem()
        desk = system.book("DESK"); client = system.book("CLIENT")
        bond = Bond()
        bond.FaceValue.set(1000.0); bond.CouponRate.set(0.05)
        bond.YieldToMaturity.set(0.04); bond.Maturity.set(10)
        system.register_instrument("UST", bond)
        system.trade(desk, client, "UST", 5, bond.MarketValue())
        result = risk.stress(desk, rate_shock=0.01)     # +100bp
        assert result["applied_shocks"] == {"rate_shock": 0.01}
        assert result["pnl_impact"] != 0.0              # bond reprices on yield move
        # additive convention: compare to a direct +100bp yield bump
        base = bond.MarketValue()
        with dag.scenario():
            bond.YieldToMaturity.override(0.05)
            bumped = bond.MarketValue()
        assert result["pnl_impact"] == pytest.approx(5 * (bumped - base), abs=1e-6)

    def test_shared_instrument_not_compounded(self):
        """One instrument backing two symbols: a shock is applied once, not twice."""
        from lattice.trading import TradingSystem
        system = TradingSystem()
        desk = system.book("DESK"); client = system.book("C")
        opt = VanillaOption()
        opt.Spot.set(100.0); opt.Strike.set(100.0); opt.Volatility.set(0.20); opt.Rate.set(0.04)
        system.register_instrument("SYMA", opt)
        system.register_instrument("SYMB", opt)          # same instrument object, two symbols
        system.trade(desk, client, "SYMA", 10, opt.MarketValue())
        system.trade(desk, client, "SYMB", 10, opt.MarketValue())
        # desk now has two positions both linked to `opt`. Stress spot once.
        result = risk.stress(desk, spot_shock=0.10)
        with dag.scenario():
            opt.Spot.override(110.0)                      # a SINGLE override of the shared instrument
            single = desk.TotalPnL()
        # Without dedup, opt.Spot would be overridden twice (110 -> 121); dedup keeps it at 110.
        assert result["stressed_pnl"] == pytest.approx(single)


class TestScenarios:
    """Tests for predefined stress scenarios."""

    @pytest.fixture
    def trading_system(self):
        """Create a trading system with positions."""
        system = TradingSystem()
        desk = system.book("DESK")
        client = system.book("CLIENT")

        system.trade(desk, client, "AAPL", 100, 150.0)
        system.set_market_price("AAPL", 155.0)

        return system, desk

    def test_run_scenario(self, trading_system):
        """Run a predefined scenario."""
        system, desk = trading_system

        result = risk.run_scenario(desk, "market_crash")

        assert "pnl_impact" in result
        assert result["scenario"] == "market_crash"

    def test_run_all_scenarios(self, trading_system):
        """Run all predefined scenarios."""
        system, desk = trading_system

        results = risk.run_all_scenarios(desk)

        assert len(results) > 5  # Should have multiple scenarios
        assert "market_crash" in results
        assert "rate_hike" in results

    def test_unknown_scenario_raises(self, trading_system):
        """Unknown scenario should raise KeyError."""
        system, desk = trading_system

        with pytest.raises(KeyError):
            risk.run_scenario(desk, "unknown_scenario")

    def test_list_scenarios(self):
        """List scenarios should return available scenarios."""
        scenarios = risk.list_scenarios()

        assert isinstance(scenarios, dict)
        assert "market_crash" in scenarios
        assert "spot_shock" in scenarios["market_crash"]

    def test_add_custom_scenario(self, trading_system):
        """Custom scenarios can be added."""
        system, desk = trading_system

        risk.add_scenario("my_scenario", spot_shock=-0.05)
        result = risk.run_scenario(desk, "my_scenario")

        assert result["spot_shock"] == -0.05

        # Cleanup
        risk.remove_scenario("my_scenario")

    def test_run_scenario_reports_applied_and_skipped(self, trading_system):
        """A multi-factor scenario applies the price leg and reports the rest as skipped."""
        system, desk = trading_system

        result = risk.run_scenario(desk, "market_crash")

        # market_crash = {spot_shock: -0.20, vol_shock: 0.50}
        assert result["applied_shocks"] == {"spot_shock": -0.20}
        assert result["skipped_shocks"] == {"vol_shock": 0.50}
        assert result["pnl_impact"] < 0  # the -20% spot leg moves the book

    def test_run_scenario_rate_only_is_zero_and_transparent(self, trading_system):
        """A rate-only scenario has no effect on a book, reported explicitly (not silently)."""
        system, desk = trading_system

        result = risk.run_scenario(desk, "rate_hike")

        # rate_hike = {rate_shock: 0.01}; a book has no rate sensitivity
        assert result["applied_shocks"] == {}
        assert result["skipped_shocks"] == {"rate_shock": 0.01}
        assert result["pnl_impact"] == 0.0


class TestVaR:
    """Tests for Value at Risk calculations."""

    @pytest.fixture
    def trading_system(self):
        """Create a trading system with positions."""
        system = TradingSystem()
        desk = system.book("DESK")
        client = system.book("CLIENT")

        system.trade(desk, client, "AAPL", 1000, 150.0)
        system.set_market_price("AAPL", 150.0)

        return system, desk

    def test_parametric_var_basic(self, trading_system):
        """Basic VaR calculation."""
        system, desk = trading_system

        result = risk.parametric_var(desk, confidence=0.95, holding_period=1)

        assert result["var"] > 0
        assert result["expected_shortfall"] > result["var"]
        assert result["confidence"] == 0.95
        assert result["holding_period"] == 1

    def test_var_increases_with_confidence(self, trading_system):
        """Higher confidence should give higher VaR."""
        system, desk = trading_system

        var_90 = risk.parametric_var(desk, confidence=0.90)["var"]
        var_95 = risk.parametric_var(desk, confidence=0.95)["var"]
        var_99 = risk.parametric_var(desk, confidence=0.99)["var"]

        assert var_90 < var_95 < var_99

    def test_var_increases_with_holding_period(self, trading_system):
        """Longer holding period should give higher VaR."""
        system, desk = trading_system

        var_1d = risk.parametric_var(desk, holding_period=1)["var"]
        var_10d = risk.parametric_var(desk, holding_period=10)["var"]

        assert var_10d > var_1d

    def test_var_scales_with_sqrt_time(self, trading_system):
        """VaR should scale approximately with sqrt of time."""
        system, desk = trading_system

        var_1d = risk.parametric_var(desk, holding_period=1)["var"]
        var_4d = risk.parametric_var(desk, holding_period=4)["var"]

        # 4-day VaR should be ~2x 1-day VaR (sqrt(4) = 2)
        assert abs(var_4d / var_1d - 2.0) < 0.01

    def test_var_contribution(self, trading_system):
        """VaR contribution should sum to total VaR."""
        system, desk = trading_system

        contributions = risk.var_contribution(desk)

        assert len(contributions) == 1
        assert "AAPL" in contributions

    def test_var_report(self, trading_system):
        """VaR report should contain matrix."""
        system, desk = trading_system

        report = risk.var_report(desk)

        assert "var_matrix" in report
        assert 0.95 in report["var_matrix"]
        assert 1 in report["var_matrix"][0.95]


class TestRiskEngine:
    """Tests for RiskEngine class."""

    def test_engine_add_instruments(self):
        """Engine should track added instruments."""
        engine = RiskEngine()

        option = VanillaOption()
        bond = Bond()

        engine.add(option, "AAPL_C")
        engine.add(bond, "UST_10Y")

        assert len(engine.instruments) == 2
        assert "AAPL_C" in engine.instruments
        assert "UST_10Y" in engine.instruments

    def test_engine_compute_greeks(self):
        """Engine should compute greeks for all instruments."""
        engine = RiskEngine()

        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)

        engine.add(option, "AAPL_C")

        greeks = engine.compute_greeks()

        assert "AAPL_C" in greeks
        assert "delta" in greeks["AAPL_C"]
        assert "gamma" in greeks["AAPL_C"]
        assert "vega" in greeks["AAPL_C"]

    def test_engine_stress_test(self):
        """Engine should apply stress test to all instruments."""
        engine = RiskEngine()

        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)

        engine.add(option, "AAPL_C")

        results = engine.stress_test(Spot=-0.10)

        assert "AAPL_C" in results
        assert results["AAPL_C"]["price_impact"] < 0  # Price should decrease

    def test_engine_handles_missing_inputs(self):
        """Engine should handle instruments with missing inputs gracefully."""
        engine = RiskEngine()

        bond = Bond()  # No Spot or Volatility
        engine.add(bond, "UST_10Y")

        greeks = engine.compute_greeks()

        # Should have DV01 but not delta/vega
        assert "dv01" in greeks["UST_10Y"]
        assert "delta" not in greeks["UST_10Y"]

    def test_compute_greeks_logs_on_failure(self, caplog):
        """A genuine computation error is logged, not silently swallowed."""
        engine = RiskEngine()
        engine.add(_BrokenInstrument(), "BROKEN")

        with caplog.at_level(logging.WARNING):
            greeks = engine.compute_greeks()

        # No greek could be computed (Price raises)...
        assert greeks["BROKEN"] == {}
        # ...but the failure is visible in the logs, naming the instrument.
        assert "BROKEN" in caplog.text

    def test_engine_remove_instrument(self):
        """Engine should allow removing instruments."""
        engine = RiskEngine()

        option = VanillaOption()
        engine.add(option, "AAPL_C")
        engine.remove("AAPL_C")

        assert len(engine.instruments) == 0

    def test_engine_clear(self):
        """Engine should allow clearing all instruments."""
        engine = RiskEngine()

        engine.add(VanillaOption(), "opt1")
        engine.add(VanillaOption(), "opt2")
        engine.clear()

        assert len(engine.instruments) == 0


class TestScenarioReversion:
    """Tests to ensure scenarios properly revert."""

    def test_delta_reverts_after_calculation(self):
        """Spot should revert after delta calculation."""
        option = VanillaOption()
        option.Spot.set(100.0)

        original_spot = option.Spot()
        risk.delta(option)
        final_spot = option.Spot()

        assert original_spot == final_spot

    def test_gamma_reverts_after_calculation(self):
        """Spot should revert after gamma calculation."""
        option = VanillaOption()
        option.Spot.set(100.0)

        original_spot = option.Spot()
        risk.gamma(option)
        final_spot = option.Spot()

        assert original_spot == final_spot

    def test_stress_reverts_positions(self):
        """Positions should revert after stress test."""
        system = TradingSystem()
        desk = system.book("DESK")
        client = system.book("CLIENT")

        system.trade(desk, client, "AAPL", 100, 150.0)
        system.set_market_price("AAPL", 150.0)

        original_prices = [p.MarketPrice() for p in desk.Positions()]
        risk.stress(desk, spot_shock=-0.20)
        final_prices = [p.MarketPrice() for p in desk.Positions()]

        assert original_prices == final_prices


class TestScenarioThreadSafety:
    """dag scenarios are single-threaded; this guards lattice's reliance on it.

    Risk calculations are bump-and-reval inside dag.scenario(). dag forbids
    using the graph from another thread while a scenario is active, so batch
    risk must be parallelized across processes (the Temporal path), never
    in-process threads. This regression test fails loudly if that dag
    guarantee ever changes.
    """

    def test_cross_thread_scenario_raises(self):
        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)

        captured = {}

        def worker():
            try:
                with dag.scenario():
                    option.Spot.override(110.0)
                    option.Price()
            except Exception as e:  # noqa: BLE001 - we assert the type below
                captured["exc"] = e

        with dag.scenario():
            option.Spot.override(105.0)
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()

        assert isinstance(captured.get("exc"), dag.ConcurrentScenarioError)


class TestShockConvention:
    """Spot/vol shocks are relative; rate/yield shocks are absolute (bp)."""

    def test_relative_for_spot_and_vol(self):
        from lattice.risk.shocks import shocked_value
        assert shocked_value("Spot", 100.0, -0.20) == pytest.approx(80.0)
        assert shocked_value("Volatility", 0.20, 0.50) == pytest.approx(0.30)

    def test_absolute_for_rate_and_yield(self):
        from lattice.risk.shocks import shocked_value
        assert shocked_value("Rate", 0.04, 0.01) == pytest.approx(0.05)
        assert shocked_value("YieldToMaturity", 0.05, 0.01) == pytest.approx(0.06)

    def test_absolute_for_swap_rates(self):
        from lattice.risk.shocks import shocked_value
        assert shocked_value("DiscountRate", 0.03, 0.01) == pytest.approx(0.04)
        assert shocked_value("FloatingRate", 0.03, 0.01) == pytest.approx(0.04)
        assert shocked_value("FloatingSpread", 0.001, 0.0005) == pytest.approx(0.0015)

    def test_engine_stress_test_rate_is_additive(self):
        option = VanillaOption()
        option.Spot.set(100.0); option.Strike.set(100.0)
        option.Volatility.set(0.20); option.Rate.set(0.04)
        engine = RiskEngine(); engine.add(option, "OPT")
        # Expected stressed price = price with Rate moved +100bp (0.04 -> 0.05)
        with dag.scenario():
            option.Rate.override(0.05)
            expected = option.Price()
        res = engine.stress_test(Rate=0.01)
        assert res["OPT"]["stressed_price"] == pytest.approx(expected)
