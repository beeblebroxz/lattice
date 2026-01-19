"""Tests for option instruments."""

import pytest
import dag
from lattice.instruments import VanillaOption


class TestVanillaOptionDefaults:
    """Test default values of VanillaOption."""

    def setup_method(self):
        dag.reset()
        self.option = VanillaOption()

    def test_default_strike(self):
        assert self.option.Strike() == 100.0

    def test_default_spot(self):
        assert self.option.Spot() == 100.0

    def test_default_volatility(self):
        assert self.option.Volatility() == 0.20

    def test_default_rate(self):
        assert self.option.Rate() == 0.05

    def test_default_dividend(self):
        assert self.option.Dividend() == 0.0

    def test_default_time_to_expiry(self):
        assert self.option.TimeToExpiry() == 1.0

    def test_default_is_call(self):
        assert self.option.IsCall() is True


class TestVanillaOptionPricing:
    """Test VanillaOption pricing."""

    def setup_method(self):
        dag.reset()

    def test_price_positive(self):
        option = VanillaOption()
        assert option.Price() > 0

    def test_price_changes_with_spot(self):
        option = VanillaOption()
        option.IsCall.set(True)

        option.Spot.set(100.0)
        price_100 = option.Price()

        option.Spot.set(110.0)
        price_110 = option.Price()

        # Call price should increase when spot increases
        assert price_110 > price_100

    def test_put_price_changes_with_spot(self):
        option = VanillaOption()
        option.IsCall.set(False)

        option.Spot.set(100.0)
        price_100 = option.Price()

        option.Spot.set(110.0)
        price_110 = option.Price()

        # Put price should decrease when spot increases
        assert price_110 < price_100

    def test_intrinsic_value_itm_call(self):
        option = VanillaOption()
        option.Strike.set(100.0)
        option.Spot.set(110.0)
        option.IsCall.set(True)
        assert option.IntrinsicValue() == pytest.approx(10.0)

    def test_intrinsic_value_otm_call(self):
        option = VanillaOption()
        option.Strike.set(100.0)
        option.Spot.set(90.0)
        option.IsCall.set(True)
        assert option.IntrinsicValue() == pytest.approx(0.0)

    def test_time_value_positive(self):
        option = VanillaOption()
        option.TimeToExpiry.set(1.0)
        assert option.TimeValue() > 0


class TestVanillaOptionGreeks:
    """Test VanillaOption Greeks."""

    def setup_method(self):
        dag.reset()
        self.option = VanillaOption()

    def test_call_delta_range(self):
        self.option.IsCall.set(True)
        delta = self.option.Delta()
        assert 0 < delta < 1

    def test_put_delta_range(self):
        self.option.IsCall.set(False)
        delta = self.option.Delta()
        assert -1 < delta < 0

    def test_gamma_positive(self):
        assert self.option.Gamma() > 0

    def test_vega_positive(self):
        assert self.option.Vega() > 0

    def test_call_theta_negative(self):
        self.option.IsCall.set(True)
        assert self.option.Theta() < 0

    def test_call_rho_positive(self):
        self.option.IsCall.set(True)
        assert self.option.Rho() > 0

    def test_put_rho_negative(self):
        self.option.IsCall.set(False)
        assert self.option.Rho() < 0


class TestVanillaOptionMemoization:
    """Test that VanillaOption properly memoizes computations."""

    def setup_method(self):
        dag.reset()

    def test_price_memoized(self):
        option = VanillaOption()
        price1 = option.Price()
        price2 = option.Price()
        assert price1 == price2

    def test_price_invalidated_on_input_change(self):
        option = VanillaOption()
        option.Spot.set(100.0)
        price1 = option.Price()

        option.Spot.set(110.0)
        price2 = option.Price()

        assert price1 != price2


class TestVanillaOptionScenarios:
    """Test VanillaOption with dag scenarios."""

    def setup_method(self):
        dag.reset()

    def test_scenario_override(self):
        option = VanillaOption()
        option.Spot.set(100.0)
        option.Strike.set(100.0)
        option.IsCall.set(True)

        base_price = option.Price()

        with dag.scenario():
            option.Spot.override(110.0)
            bumped_price = option.Price()
            assert bumped_price > base_price

        # Should revert to base price
        assert option.Price() == pytest.approx(base_price)
